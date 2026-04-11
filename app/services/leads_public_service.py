"""
Public leads service — query functions for unauthenticated marketing endpoints
and lead interest capture.

All functions return data from existing tables (restaurant_info, plan_info, lead_interest).
No external API calls. These are read-only projections for the marketing site.
"""

from typing import Any, Dict, List, Optional, Tuple

import psycopg2.extensions
import psycopg2.extras
from psycopg2.extras import RealDictCursor

from app.config.enums import InterestType
from app.utils.db import db_read


def get_public_restaurants(
    locale: str,
    db: psycopg2.extensions.connection,
    *,
    featured_only: bool = False,
    limit: int = 12,
) -> List[dict]:
    """
    Return active restaurants for public display.
    Limited projection: id, name, cuisine, tagline, rating, cover image.
    I18n resolved via COALESCE on JSONB fields.
    """
    featured_clause = "AND r.is_featured = TRUE" if featured_only else ""
    query = f"""
        SELECT r.restaurant_id, r.name,
               COALESCE(cu.cuisine_name_i18n->>%s, cu.cuisine_name) AS cuisine_name,
               COALESCE(r.tagline_i18n->>%s, r.tagline) AS tagline,
               r.average_rating, r.review_count, r.cover_image_url
        FROM restaurant_info r
        LEFT JOIN cuisine cu ON r.cuisine_id = cu.cuisine_id
        WHERE r.is_archived = FALSE AND r.status = 'active'
          {featured_clause}
        ORDER BY r.is_featured DESC, r.average_rating DESC NULLS LAST
        LIMIT %s
    """
    rows = db_read(query, (locale, locale, limit), connection=db)
    return [dict(r) for r in rows] if rows else []


def get_public_plans(
    locale: str,
    db: psycopg2.extensions.connection,
) -> List[dict]:
    """
    Return active plans for public pricing display.
    Limited projection with currency from market's credit_currency.
    Excludes Global Marketplace plans. I18n resolved for name,
    marketing_description, cta_label. Features i18n resolved in Python.
    """
    rows = db_read(
        """
        SELECT p.plan_id,
               COALESCE(p.name_i18n->>%s, p.name) AS name,
               COALESCE(p.marketing_description_i18n->>%s, p.marketing_description) AS marketing_description,
               p.features, p.features_i18n,
               COALESCE(p.cta_label_i18n->>%s, p.cta_label) AS cta_label,
               p.credit, p.price, p.highlighted,
               cc.currency_code AS currency
        FROM plan_info p
        JOIN market_info m ON p.market_id = m.market_id
        JOIN currency_metadata cc ON m.currency_metadata_id = cc.currency_metadata_id
        WHERE p.is_archived = FALSE AND p.status = 'active'
          AND p.market_id != '00000000-0000-0000-0000-000000000001'::uuid
        ORDER BY p.price ASC
        """,
        (locale, locale, locale),
        connection=db,
    )
    if not rows:
        return []

    results = []
    for row in rows:
        plan = dict(row)
        # Resolve features i18n (same pattern as member_perks_i18n in featured-restaurant)
        i18n = plan.pop("features_i18n", None) or {}
        if locale != "en" and locale in i18n:
            plan["features"] = i18n[locale]
        plan["features"] = plan.get("features") or []
        results.append(plan)
    return results


# ---------------------------------------------------------------------------
# Lead interest capture
# ---------------------------------------------------------------------------

VALID_INTEREST_TYPES = {t.value for t in InterestType}

EMPLOYEE_COUNT_RANGES = [
    {"range_id": "1-20", "label": "1–20 employees"},
    {"range_id": "21-50", "label": "21–50 employees"},
    {"range_id": "51-100", "label": "51–100 employees"},
    {"range_id": "101-500", "label": "101–500 employees"},
    {"range_id": "500+", "label": "500+ employees"},
]
VALID_EMPLOYEE_RANGES = {r["range_id"] for r in EMPLOYEE_COUNT_RANGES}

_EMPLOYEE_RANGE_LABELS_I18N = {
    "es": "empleados",
    "pt": "funcionários",
}


def get_employee_count_ranges(locale: str = "en") -> List[dict]:
    """Return employee count ranges with localized labels."""
    if locale == "en" or locale not in _EMPLOYEE_RANGE_LABELS_I18N:
        return list(EMPLOYEE_COUNT_RANGES)
    word = _EMPLOYEE_RANGE_LABELS_I18N[locale]
    return [
        {"range_id": r["range_id"], "label": r["label"].replace("employees", word)}
        for r in EMPLOYEE_COUNT_RANGES
    ]


def get_leads_cuisines(
    locale: str,
    db: psycopg2.extensions.connection,
) -> List[dict]:
    """Return active cuisines for public lead interest form dropdowns."""
    rows = db_read(
        """
        SELECT cuisine_id,
               COALESCE(cuisine_name_i18n->>%s, cuisine_name) AS cuisine_name
        FROM cuisine
        WHERE NOT is_archived AND status = 'active'
        ORDER BY display_order NULLS LAST, cuisine_name
        """,
        (locale,),
        connection=db,
    )
    return [dict(r) for r in rows] if rows else []


def create_lead_interest(
    data: dict,
    source: str,
    db: psycopg2.extensions.connection,
) -> Optional[dict]:
    """
    Insert a new lead interest record. Returns the created row or None.
    Validates interest_type, cuisine_id, and employee_count_range.
    """
    interest_type = (data.get("interest_type") or "customer").strip().lower()
    if interest_type not in VALID_INTEREST_TYPES:
        return None  # caller raises 422

    # Validate cuisine_id if provided
    cuisine_id = data.get("cuisine_id")
    if cuisine_id:
        exists = db_read(
            "SELECT 1 FROM cuisine WHERE cuisine_id = %s AND NOT is_archived AND status = 'active'",
            (str(cuisine_id),),
            connection=db,
            fetch_one=True,
        )
        if not exists:
            return None  # caller raises 422

    # Validate employee_count_range if provided
    emp_range = (data.get("employee_count_range") or "").strip() or None
    if emp_range and emp_range not in VALID_EMPLOYEE_RANGES:
        return None  # caller raises 422

    email = (data.get("email") or "").strip().lower()
    country_code = (data.get("country_code") or "").strip().upper()

    with db.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            INSERT INTO core.lead_interest (
                email, country_code, city_name, zipcode, zipcode_only,
                interest_type, business_name, message,
                cuisine_id, employee_count_range, source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                email,
                country_code,
                (data.get("city_name") or "").strip() or None,
                (data.get("zipcode") or "").strip() or None,
                bool(data.get("zipcode_only", False)),
                interest_type,
                (data.get("business_name") or "").strip() or None,
                (data.get("message") or "").strip() or None,
                str(cuisine_id) if cuisine_id else None,
                emp_range,
                source,
            ),
        )
        row = cursor.fetchone()
        db.commit()
    return dict(row) if row else None


def get_lead_interests(
    db: psycopg2.extensions.connection,
    *,
    country_code: Optional[str] = None,
    city_name: Optional[str] = None,
    interest_type: Optional[str] = None,
    interest_status: Optional[str] = None,
    cuisine_id: Optional[str] = None,
    employee_count_range: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[dict], int]:
    """
    Paginated query of lead interest records with optional filters.
    Returns (rows, total_count). Internal use only.
    """
    conditions: List[str] = ["NOT is_archived"]
    params: List[Any] = []

    if country_code:
        conditions.append("country_code = %s")
        params.append(country_code.strip().upper())
    if city_name:
        conditions.append("UPPER(TRIM(city_name)) = UPPER(TRIM(%s))")
        params.append(city_name)
    if interest_type:
        conditions.append("interest_type = %s")
        params.append(interest_type.strip().lower())
    if interest_status:
        conditions.append("status = %s")
        params.append(interest_status.strip().lower())
    if cuisine_id:
        conditions.append("cuisine_id = %s")
        params.append(cuisine_id)
    if employee_count_range:
        conditions.append("employee_count_range = %s")
        params.append(employee_count_range)
    if created_after:
        conditions.append("created_date >= %s::timestamptz")
        params.append(created_after)
    if created_before:
        conditions.append("created_date <= %s::timestamptz")
        params.append(created_before)

    where = " AND ".join(conditions)

    # Total count
    count_row = db_read(
        f"SELECT COUNT(*) AS cnt FROM core.lead_interest WHERE {where}",
        tuple(params),
        connection=db,
        fetch_one=True,
    )
    total = int(count_row["cnt"]) if count_row else 0

    # Paginated results
    offset = (max(page, 1) - 1) * page_size
    rows = db_read(
        f"""
        SELECT lead_interest_id, email, country_code, city_name, zipcode,
               zipcode_only, interest_type, business_name, message,
               cuisine_id, employee_count_range,
               status, source, created_date
        FROM core.lead_interest
        WHERE {where}
        ORDER BY created_date DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (page_size, offset),
        connection=db,
    )
    return ([dict(r) for r in rows] if rows else [], total)


# ---------------------------------------------------------------------------
# Restaurant Lead (vetting pipeline)
# ---------------------------------------------------------------------------

VALID_REFERRAL_SOURCES = {"ad", "referral", "search", "other"}


def create_restaurant_lead(
    data: dict,
    db: psycopg2.extensions.connection,
) -> Optional[dict]:
    """
    Insert a new restaurant lead application and link cuisine selections.
    Returns the created row or None on validation failure.
    """
    referral_source = (data.get("referral_source") or "").strip().lower()
    if referral_source not in VALID_REFERRAL_SOURCES:
        return None

    cuisine_ids = data.get("cuisine_ids") or []
    if not cuisine_ids:
        return None

    email = (data.get("contact_email") or "").strip().lower()
    country_code = (data.get("country_code") or "").strip().upper()

    with db.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            INSERT INTO core.restaurant_lead (
                business_name, contact_name, contact_email, contact_phone,
                country_code, city_name,
                years_in_operation, employee_count_range, kitchen_capacity_daily,
                website_url, referral_source, message, vetting_answers,
                gclid, fbclid, fbc, fbp, event_id, source_platform
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::restaurant_lead_referral_source_enum, %s,
                    %s::jsonb,
                    %s, %s, %s, %s, %s, %s)
            RETURNING restaurant_lead_id, business_name, contact_email,
                      country_code, lead_status, created_date
            """,
            (
                (data.get("business_name") or "").strip(),
                (data.get("contact_name") or "").strip(),
                email,
                (data.get("contact_phone") or "").strip(),
                country_code,
                (data.get("city_name") or "").strip(),
                data.get("years_in_operation", 0),
                (data.get("employee_count_range") or "").strip(),
                data.get("kitchen_capacity_daily", 1),
                (data.get("website_url") or "").strip() or None,
                referral_source,
                (data.get("message") or "").strip() or None,
                psycopg2.extras.Json(data.get("vetting_answers") or {}),
                data.get("gclid"),
                data.get("fbclid"),
                data.get("fbc"),
                data.get("fbp"),
                data.get("event_id"),
                data.get("source_platform"),
            ),
        )
        row = cursor.fetchone()
        if not row:
            db.rollback()
            return None

        lead_id = str(row["restaurant_lead_id"])

        # Insert cuisine junction rows
        for cid in cuisine_ids:
            cursor.execute(
                "INSERT INTO core.restaurant_lead_cuisine (restaurant_lead_id, cuisine_id) VALUES (%s, %s)",
                (lead_id, str(cid)),
            )

        db.commit()
    return dict(row) if row else None
