"""
Restaurant explorer service for B2C explore-by-city flow.

- Cities for dropdown: use get_cities_with_coverage from city_metrics_service (city_metadata + has restaurant).
- get_restaurants_by_city(city, country_code, db, ...): list of restaurants in that city
  with name, cuisine, lat/lng for list and map; optional market filter and viandas for a kitchen day.
- resolve_kitchen_day_for_explore(country_code, timezone_str, db): next available kitchen day (or today if still open).
"""

from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID

import psycopg2.extensions
import pytz

from app.services.kitchen_day_service import (
    VALID_KITCHEN_DAYS,
    WEEKDAY_NUM_TO_NAME,
    get_effective_current_day,
    is_today_kitchen_closed,
)
from app.services.vianda_review_service import get_vianda_review_aggregates
from app.services.vianda_selection_validation import _find_next_available_kitchen_day_in_week
from app.utils.address_formatting import format_street_display
from app.utils.cursor_pagination import slice_restaurants_by_cursor
from app.utils.db import db_read
from app.utils.portion_size import bucket_portion_size

WEEKDAY_NAME_TO_NUM = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4}


def _parse_window_to_minutes(window: str) -> int | None:
    """Parse 'HH:MM-HH:MM' to start minutes since midnight. Returns None if invalid."""
    try:
        parts = window.strip().split("-")
        if len(parts) != 2:
            return None
        start_part = parts[0].strip()
        h, m = map(int, start_part.split(":"))
        return h * 60 + m
    except (ValueError, AttributeError):
        return None


def _expand_flexible_windows(original_window: str, all_windows: list[str]) -> list[str]:
    """Given original window and all valid windows, return original + adjacent within ±30 min."""
    start_min = _parse_window_to_minutes(original_window)
    if start_min is None:
        return [original_window]
    out: list[str] = []
    for w in all_windows:
        w_min = _parse_window_to_minutes(w)
        if w_min is not None and abs(w_min - start_min) <= 30:
            out.append(w)
    return sorted(set(out), key=_parse_window_to_minutes) if out else [original_window]


def get_coworker_pickup_windows(
    restaurant_id: UUID,
    kitchen_day: str,
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> list[dict]:
    """
    Return pickup windows from coworkers (same employer) with offer/request for this restaurant+kitchen_day.
    Excludes users who opted out (coworkers_can_see_my_orders=false or can_participate_in_vianda_pickups=false).
    When pickup_intent=request and flexible_on_time=true: expands ±30 min; marks original with flexible_on_time.
    Returns empty list when user has no employer.
    """
    if kitchen_day not in VALID_KITCHEN_DAYS:
        return []

    user_row = db_read(
        "SELECT employer_entity_id, employer_address_id, workplace_group_id FROM user_info WHERE user_id = %s",
        (str(user_id),),
        connection=db,
        fetch_one=True,
    )
    if not user_row:
        return []

    workplace_group_id = user_row.get("workplace_group_id")
    employer_entity_id = user_row.get("employer_entity_id")
    employer_address_id = user_row.get("employer_address_id")

    if not workplace_group_id and not employer_entity_id:
        return []

    # Get country_code from restaurant for market windows
    addr_row = db_read(
        """
        SELECT a.country_code FROM restaurant_info r
        INNER JOIN address_info a ON r.address_id = a.address_id
        WHERE r.restaurant_id = %s
        """,
        (str(restaurant_id),),
        connection=db,
        fetch_one=True,
    )
    country_code = ((addr_row or {}).get("country_code") or "US").strip().upper()
    target_date = resolve_weekday_to_next_occurrence(kitchen_day, "UTC")
    all_windows = get_pickup_windows_for_kitchen_day(country_code, kitchen_day, target_date)
    if not all_windows:
        return []

    if workplace_group_id:
        # workplace_group_id takes precedence — match all users in the same group
        sel_query = """
            SELECT ps.pickup_time_range, ps.pickup_intent, ps.flexible_on_time
            FROM vianda_selection_info ps
            INNER JOIN user_info u_ps ON ps.user_id = u_ps.user_id
            INNER JOIN user_messaging_preferences ump ON ps.user_id = ump.user_id
            WHERE ps.restaurant_id = %s AND ps.kitchen_day = %s
              AND ps.pickup_intent IN ('offer', 'request') AND ps.is_archived = FALSE
              AND ump.coworkers_can_see_my_orders = TRUE
              AND ump.can_participate_in_vianda_pickups = TRUE
              AND u_ps.workplace_group_id = %s
        """
        params = (str(restaurant_id), kitchen_day, str(workplace_group_id))
    elif employer_address_id is not None:
        sel_query = """
            SELECT ps.pickup_time_range, ps.pickup_intent, ps.flexible_on_time
            FROM vianda_selection_info ps
            INNER JOIN user_info u_ps ON ps.user_id = u_ps.user_id
            INNER JOIN user_messaging_preferences ump ON ps.user_id = ump.user_id
            WHERE ps.restaurant_id = %s AND ps.kitchen_day = %s
              AND ps.pickup_intent IN ('offer', 'request') AND ps.is_archived = FALSE
              AND ump.coworkers_can_see_my_orders = TRUE
              AND ump.can_participate_in_vianda_pickups = TRUE
              AND u_ps.employer_entity_id = %s AND u_ps.employer_address_id = %s
        """
        params = (str(restaurant_id), kitchen_day, str(employer_entity_id), str(employer_address_id))
    else:
        sel_query = """
            SELECT ps.pickup_time_range, ps.pickup_intent, ps.flexible_on_time
            FROM vianda_selection_info ps
            INNER JOIN user_info u_ps ON ps.user_id = u_ps.user_id
            INNER JOIN user_messaging_preferences ump ON ps.user_id = ump.user_id
            WHERE ps.restaurant_id = %s AND ps.kitchen_day = %s
              AND ps.pickup_intent IN ('offer', 'request') AND ps.is_archived = FALSE
              AND ump.coworkers_can_see_my_orders = TRUE
              AND ump.can_participate_in_vianda_pickups = TRUE
              AND u_ps.employer_entity_id = %s AND u_ps.employer_address_id IS NULL
        """
        params = (str(restaurant_id), kitchen_day, str(employer_entity_id))

    rows = db_read(sel_query, params, connection=db) or []
    seen: set = set()
    result: list[dict] = []
    for r in rows:
        ptr = (r.get("pickup_time_range") or "").strip()
        intent = (r.get("pickup_intent") or "self").strip()
        flexible = r.get("flexible_on_time") is True and intent == "request"
        if not ptr or intent not in ("offer", "request"):
            continue
        if flexible:
            expanded = _expand_flexible_windows(ptr, all_windows)
            for w in expanded:
                key = (w, intent)
                if key not in seen:
                    seen.add(key)
                    result.append(
                        {
                            "pickup_time_range": w,
                            "intent": intent,
                            "flexible_on_time": True if w == ptr else None,
                        }
                    )
        else:
            key = (ptr, intent)
            if key not in seen:
                seen.add(key)
                result.append(
                    {
                        "pickup_time_range": ptr,
                        "intent": intent,
                        "flexible_on_time": None,
                    }
                )
    return result


def _compute_savings_pct(vianda_price: float, vianda_credit: int, credit_cost_local_currency: float) -> int:
    """
    Compute savings percentage: (vianda_price - vianda_credit * credit_cost_local_currency) / vianda_price * 100.
    Clamped to [0, 100]. Returns 0 if vianda_price <= 0.
    """
    if vianda_price <= 0:
        return 0
    raw = (vianda_price - vianda_credit * credit_cost_local_currency) / vianda_price * 100
    return int(round(max(0.0, min(100.0, raw))))


def get_allowed_kitchen_date_range(timezone_str: str) -> tuple[date, date]:
    """
    Allowed kitchen_day window: today (in market TZ) through next week's Friday inclusive.
    Returns (start_date, end_date) for validation.
    """
    try:
        tz = pytz.timezone(timezone_str or "UTC")
    except Exception:
        tz = pytz.UTC
    today = datetime.now(tz).date()
    # Monday of current week (weekday 0 = Monday in Python)
    current_week_monday = today - timedelta(days=today.weekday())
    next_week_friday = current_week_monday + timedelta(days=7 + 4)  # next week's Friday
    return today, next_week_friday


def resolve_weekday_to_next_occurrence(weekday_name: str, timezone_str: str) -> date:
    """Return the next occurrence of the given weekday (Monday–Friday) from today in the given TZ.

    In DEV_MODE, when today is a weekend and the target day was mapped to friday,
    return TODAY instead of next Friday — so vianda pickups, QR scans, and billing
    all operate on the same date and the E2E flow works any day of the week.
    """
    from app.config.settings import settings as _settings

    try:
        tz = pytz.timezone(timezone_str or "UTC")
    except Exception:
        tz = pytz.UTC
    today = datetime.now(tz).date()
    target = WEEKDAY_NAME_TO_NUM.get(weekday_name)
    if target is None:
        raise ValueError(f"Invalid kitchen_day: {weekday_name!r}")
    days_ahead = (target - today.weekday() + 7) % 7
    # DEV_MODE: if today is a weekend, return today so the full E2E pipeline
    # (vianda selection → QR scan → complete → billing) all operates on the same date.
    # The DB CHECK constraint on pickup_date DOW was removed — business logic owns the guard.
    if _settings.DEV_MODE and today.weekday() >= 5 and days_ahead > 0:
        return today
    return today + timedelta(days=days_ahead)


def get_allowed_kitchen_days_sorted_by_date(
    timezone_str: str,
    country_code: str | None = None,
) -> list[dict]:
    """
    Return the list of allowed kitchen days for the explore window (today through next week's Friday),
    ordered by date ascending (closest first). Each item has kitchen_day (weekday name) and date (ISO).
    Use for B2C explore kitchen-day dropdown; client can default to the first item.

    When country_code is provided and the market has kitchen_day_config, today is excluded from the
    list if the kitchen has already closed (e.g. after 1:30 PM local). For unknown markets or when
    country_code is omitted, today is always included (backward compatible).
    """
    start_date, end_date = get_allowed_kitchen_date_range(timezone_str or "UTC")
    out: list[dict] = []
    d = start_date
    while d <= end_date:
        if d.weekday() < 5:  # Monday=0 .. Friday=4
            # Skip today if kitchen has closed (after cutoff in market timezone)
            if d == start_date and country_code and is_today_kitchen_closed(country_code, timezone_str):
                d += timedelta(days=1)
                continue
            out.append(
                {
                    "kitchen_day": WEEKDAY_NUM_TO_NAME[d.weekday()],
                    "date": d.isoformat(),
                }
            )
        d += timedelta(days=1)
    return out


def get_pickup_windows_for_kitchen_day(
    country_code: str,
    kitchen_day: str,
    target_date: date,
) -> list[str]:
    """
    Return 15-minute pickup windows for a given kitchen day and market, in market local time.

    Uses MarketConfiguration.business_hours for open/close. Windows are non-overlapping,
    from open to close, formatted as "HH:MM-HH:MM" (e.g. "11:30-11:45").

    Args:
        country_code: ISO country code (e.g. AR, US, PE)
        kitchen_day: Weekday name (Monday–Friday)
        target_date: The date for the kitchen day (used for validation; times are day-agnostic)

    Returns:
        List of window strings, or empty list if config missing or day not in business_hours.
    """
    from app.config.market_config import MarketConfiguration

    config = MarketConfiguration.get_market_config((country_code or "").strip().upper())
    if not config or not config.business_hours:
        return []
    day_hours = config.business_hours.get(kitchen_day)
    if not day_hours:
        return []
    open_t = day_hours.get("open")
    close_t = day_hours.get("close")
    if not isinstance(open_t, time) or not isinstance(close_t, time):
        return []
    if open_t >= close_t:
        return []

    windows: list[str] = []
    current_minutes = open_t.hour * 60 + open_t.minute
    close_minutes = close_t.hour * 60 + close_t.minute
    while current_minutes + 15 <= close_minutes:
        start_h = current_minutes // 60
        start_m = current_minutes % 60
        end_minutes = current_minutes + 15
        end_h = end_minutes // 60
        end_m = end_minutes % 60
        windows.append(f"{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}")
        current_minutes += 15
    return windows


def validate_kitchen_day_in_window(kitchen_day: str, timezone_str: str) -> None:
    """
    Validate that the given weekday (Monday–Friday) falls within the allowed window:
    this week and next week at most, with next week ending on Friday.
    Raises ValueError if kitchen_day is invalid or its next occurrence is after next week's Friday.
    """
    if kitchen_day not in VALID_KITCHEN_DAYS:
        raise ValueError(f"kitchen_day must be one of: {', '.join(VALID_KITCHEN_DAYS)}")
    start_date, end_date = get_allowed_kitchen_date_range(timezone_str)
    occurrence = resolve_weekday_to_next_occurrence(kitchen_day, timezone_str)
    if occurrence > end_date:
        raise ValueError(
            f"kitchen_day {kitchen_day!r} (date {occurrence}) is after the allowed window. "
            f"Allowed: from today ({start_date}) through next week's Friday ({end_date})."
        )


def resolve_kitchen_day_for_explore(
    country_code: str,
    timezone_str: str,
    db: psycopg2.extensions.connection,
) -> str:
    """
    Resolve the kitchen day to use for explore when the client does not send one.
    Returns today if it's a weekday and the kitchen is still open in the market's timezone;
    otherwise the next available weekday (e.g. Saturday -> Monday).
    """
    from app.config.market_config import MarketConfiguration

    current_day = get_effective_current_day(timezone_str or "UTC")
    config = MarketConfiguration.get_market_config((country_code or "").upper()) if country_code else None

    if current_day not in VALID_KITCHEN_DAYS:
        next_day = _find_next_available_kitchen_day_in_week(current_day, list(VALID_KITCHEN_DAYS), country_code, db)
        return next_day or "monday"

    if config and config.kitchen_day_config:
        day_config = config.kitchen_day_config.get(current_day)
        if day_config and day_config.get("enabled", True):
            try:
                tz = pytz.timezone(timezone_str)
            except Exception:
                tz = pytz.UTC
            now_local = datetime.now(tz)
            close_time = day_config.get("kitchen_close")
            if close_time and now_local.time() < close_time:
                return current_day

    next_day = _find_next_available_kitchen_day_in_week(current_day, list(VALID_KITCHEN_DAYS), country_code, db)
    return next_day or "monday"


def _build_lean_vianda_dict(vianda: dict) -> dict:
    """Build lean vianda payload for by-city cards (modal fetches via enriched)."""
    return {
        "vianda_id": vianda["vianda_id"],
        "product_name": vianda.get("product_name") or "",
        "image_url": vianda.get("image_url"),
        "credit": vianda["credit"],
        "savings": vianda.get("savings", 0),
        "is_recommended": vianda.get("is_recommended", False),
        "is_favorite": vianda.get("is_favorite", False),
        "is_already_reserved": vianda.get("is_already_reserved", False),
        "existing_vianda_selection_id": vianda.get("existing_vianda_selection_id"),
    }


def get_viandas_for_restaurants(
    restaurant_ids: list[Any],
    kitchen_day: str,
    db: psycopg2.extensions.connection,
    *,
    favorite_vianda_ids: list[UUID] | None = None,
    max_credits: int | None = None,
    dietary_filter: list[str] | None = None,
) -> dict:
    """
    Return map restaurant_id -> list of viandas (vianda_id, product_name, price, credit, kitchen_day,
    image_url — always None post image-pipeline-atomic; pipeline populates via image_asset).
    Savings are NOT read from DB; caller should compute from
    price, credit, and user's credit_cost_local_currency (see get_restaurants_by_city).
    Only non-archived viandas with a matching vianda_kitchen_day.

    max_credits: when set, only viandas with credit <= max_credits are returned.
    dietary_filter: when set, only viandas whose dietary TEXT[] column overlaps the requested flags
    are returned (PostgreSQL && array overlap operator — a vianda matches if it has AT LEAST ONE of
    the requested flags). Direct SQL, NOT routed through filter_builder (avoids the kitchen#87
    IN/ANY mismatch bug for TEXT[] columns).
    """
    if not restaurant_ids or kitchen_day not in VALID_KITCHEN_DAYS:
        return {}
    ids_placeholder = ",".join("%s" for _ in restaurant_ids)
    extra_where = ""
    params: list = [kitchen_day] + [str(rid) for rid in restaurant_ids]

    if max_credits is not None:
        extra_where += "\n          AND p.credit <= %s"
        params.append(max_credits)

    if dietary_filter:
        # Use PostgreSQL array overlap (&&) to match viandas containing ANY of the requested flags.
        # Do NOT use IN / = ANY(...) — those apply scalar equality against an array column and
        # produce wrong results (kitchen#87). The && operator correctly checks array intersection.
        extra_where += "\n          AND pr.dietary && %s::text[]"
        params.append(dietary_filter)

    query = (
        """
        SELECT
            p.restaurant_id,
            p.vianda_id,
            COALESCE(pr.name, '') AS product_name,
            p.price,
            p.credit,
            pkd.kitchen_day,
            NULL::text AS image_url,
            pr.ingredients,
            pr.dietary
        FROM vianda_info p
        INNER JOIN vianda_kitchen_days pkd ON pkd.vianda_id = p.vianda_id AND pkd.kitchen_day = %s
          AND pkd.is_archived = FALSE AND pkd.status = 'active'
        INNER JOIN product_info pr ON pr.product_id = p.product_id AND pr.is_archived = FALSE
        WHERE p.restaurant_id IN ("""
        + ids_placeholder
        + """)
          AND p.is_archived = FALSE"""
        + extra_where
        + """
        ORDER BY p.restaurant_id, pr.name
    """
    )
    rows = db_read(query, tuple(params), connection=db) or []
    by_restaurant: dict = {}
    vianda_ids: list[Any] = []
    for row in rows:
        rid = row["restaurant_id"]
        vianda_ids.append(row["vianda_id"])
        if rid not in by_restaurant:
            by_restaurant[rid] = []
        fav_ids = {str(x) for x in (favorite_vianda_ids or [])}
        by_restaurant[rid].append(
            {
                "vianda_id": row["vianda_id"],
                "product_name": (row.get("product_name") or "").strip(),
                "price": float(row["price"]),
                "credit": int(row["credit"]),
                "kitchen_day": row["kitchen_day"],
                "image_url": (row.get("image_url") or "").strip() or None,
                "ingredients": (row.get("ingredients") or "").strip() or None,
                "savings": 0,  # Set by get_restaurants_by_city from credit_cost_local_currency
                "average_stars": None,
                "average_portion_size": None,
                "portion_size": "insufficient_reviews",
                "review_count": 0,
                "is_favorite": str(row["vianda_id"]) in fav_ids,
            }
        )
    # Merge review aggregates; apply minimum-threshold (5 reviews) and portion_size bucketing
    aggregates = get_vianda_review_aggregates(vianda_ids, db)
    for _rid, viandas in by_restaurant.items():
        for p in viandas:
            pid_str = str(p["vianda_id"])
            if pid_str in aggregates:
                agg = aggregates[pid_str]
                rc = agg["review_count"]
                p["review_count"] = rc
                if rc >= 5:
                    p["average_stars"] = agg["average_stars"]
                    p["average_portion_size"] = agg["average_portion_size"]
                    p["portion_size"] = bucket_portion_size(agg["average_portion_size"], rc)
                else:
                    p["average_stars"] = None
                    p["average_portion_size"] = None
                    p["portion_size"] = "insufficient_reviews"
            # else: no aggregates, keep defaults (averages=None, portion_size=insufficient_reviews)
    return by_restaurant


def _match_city_in_country(
    requested: str,
    country: str,
    db: psycopg2.extensions.connection,
) -> str:
    """Case-insensitive match of requested city against active restaurant cities in the country."""
    query_cities = """
        SELECT DISTINCT TRIM(a.city) AS city
        FROM address_info a
        INNER JOIN restaurant_info r ON r.address_id = a.address_id
        WHERE a.country_code = %s
          AND a.is_archived = FALSE
          AND r.is_archived = FALSE
          AND r.status = 'active'
          AND EXISTS (
            SELECT 1 FROM vianda_info p
            INNER JOIN vianda_kitchen_days pkd ON pkd.vianda_id = p.vianda_id AND pkd.is_archived = FALSE AND pkd.status = 'active'
            WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
          )
          AND EXISTS (
            SELECT 1 FROM qr_code qc
            WHERE qc.restaurant_id = r.restaurant_id AND qc.is_archived = FALSE AND qc.status = 'active'
          )
          AND TRIM(a.city) != ''
    """
    rows = db_read(query_cities, (country,), connection=db)
    if not requested or not rows:
        return requested
    requested_lower = requested.lower()
    for c in rows:
        city_val = (c["city"] or "").strip()
        if city_val.lower() == requested_lower:
            return city_val
    return requested


def _query_city_restaurants(
    country: str,
    matched_city: str,
    locale: str,
    db: psycopg2.extensions.connection,
    *,
    cuisine_filter: list[str] | None = None,
    geo_filter: tuple[float, float, float] | None = None,
) -> list[dict]:
    """Query active restaurants with geolocation in the given city/country.

    Optional filters (all apply in the WHERE clause, before cursor slicing):
    - cuisine_filter: list of cuisine_name values; restricts to restaurants whose
      cuisine matches any of the given names (restaurant-level, NOT vianda-level).
      City vs radius AND-composition: a restaurant must satisfy BOTH city and radius.
    - geo_filter: (lat, lng, radius_km) tuple; restricts to restaurants within
      radius_km kilometres via PostGIS ST_DWithin on r.location::geography.
    """
    extra_clauses = ""
    params: list = [locale, locale, country, matched_city]

    if cuisine_filter:
        extra_clauses += "\n          AND cu.cuisine_name = ANY(%s)"
        params.append(cuisine_filter)

    if geo_filter:
        lat, lng, radius_km = geo_filter
        extra_clauses += (
            "\n          AND ST_DWithin("
            "\n              r.location::geography,"
            "\n              ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,"
            "\n              %s"
            "\n          )"
        )
        params.extend([lng, lat, radius_km * 1000])

    query_restaurants = (
        """
        SELECT
            r.restaurant_id,
            r.name,
            COALESCE(cu.cuisine_name_i18n->>%s, cu.cuisine_name) AS cuisine_name,
            COALESCE(r.tagline_i18n->>%s, r.tagline) AS tagline,
            r.pickup_instructions,
            a.postal_code,
            TRIM(a.city) AS city,
            a.street_type::text AS street_type,
            a.street_name,
            a.building_number,
            g.latitude AS lat,
            g.longitude AS lng
        FROM restaurant_info r
        INNER JOIN address_info a ON r.address_id = a.address_id
        LEFT JOIN cuisine cu ON r.cuisine_id = cu.cuisine_id
        LEFT JOIN geolocation_info g ON g.address_id = a.address_id AND g.is_archived = FALSE
        WHERE a.country_code = %s
          AND TRIM(a.city) = %s
          AND a.is_archived = FALSE
          AND r.is_archived = FALSE
          AND r.status = 'active'
          AND EXISTS (
            SELECT 1 FROM vianda_info p
            INNER JOIN vianda_kitchen_days pkd ON pkd.vianda_id = p.vianda_id AND pkd.is_archived = FALSE AND pkd.status = 'active'
            WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
          )
          AND EXISTS (
            SELECT 1 FROM qr_code qc
            WHERE qc.restaurant_id = r.restaurant_id AND qc.is_archived = FALSE AND qc.status = 'active'
          )"""
        + extra_clauses
        + """
        ORDER BY r.name
    """
    )
    rest_rows = db_read(query_restaurants, tuple(params), connection=db) or []
    return [_build_restaurant_dict(row, country) for row in rest_rows]


def _strip_or_none(value: Any) -> str | None:
    """Strip whitespace from a string value, returning None if empty or None."""
    return (value or "").strip() or None


def _build_restaurant_dict(row: dict, country: str) -> dict:
    """Build a restaurant dict from a DB row."""
    street_type = _strip_or_none(row.get("street_type"))
    street_name = _strip_or_none(row.get("street_name"))
    building_number = _strip_or_none(row.get("building_number"))
    return {
        "restaurant_id": row["restaurant_id"],
        "name": row["name"] or "",
        "cuisine_name": row.get("cuisine_name"),
        "tagline": row.get("tagline"),
        "pickup_instructions": _strip_or_none(row.get("pickup_instructions")),
        "lat": float(row["lat"]) if row.get("lat") is not None else None,
        "lng": float(row["lng"]) if row.get("lng") is not None else None,
        "postal_code": _strip_or_none(row.get("postal_code")),
        "city": _strip_or_none(row.get("city")),
        "street_type": street_type,
        "street_name": street_name,
        "building_number": building_number,
        "address_display": format_street_display(country, street_type, street_name, building_number),
        "viandas": None,
        "has_volunteer": False,
        "has_coworker_offer": False,
        "has_coworker_request": False,
    }


def _attach_viandas_and_savings(
    restaurants: list[dict],
    kitchen_day: str,
    credit_cost_local_currency: float | None,
    db: psycopg2.extensions.connection,
    *,
    max_credits: int | None = None,
    dietary_filter: list[str] | None = None,
) -> list[dict]:
    """Attach viandas for the kitchen day and compute savings per vianda.

    When max_credits or dietary_filter are set, restaurants whose vianda list becomes empty
    after filtering are removed from the response (drop-on-empty-viandas rule).
    Returns the (possibly shorter) restaurants list.
    """
    rest_ids = [r["restaurant_id"] for r in restaurants]
    viandas_by_restaurant = get_viandas_for_restaurants(
        rest_ids,
        kitchen_day,
        db,
        max_credits=max_credits,
        dietary_filter=dietary_filter,
    )
    surviving: list[dict] = []
    for r in restaurants:
        viandas = viandas_by_restaurant.get(r["restaurant_id"]) or []
        # Drop restaurants with empty vianda list when a vianda-level filter is active
        if (max_credits is not None or dietary_filter) and not viandas:
            continue
        for vianda in viandas:
            vianda["savings"] = (
                _compute_savings_pct(vianda["price"], vianda["credit"], credit_cost_local_currency)
                if credit_cost_local_currency is not None
                else 0
            )
        r["viandas"] = viandas
        surviving.append(r)
    return surviving


def _mark_volunteer_restaurants(
    restaurants: list[dict],
    rest_ids_str: list[str],
    kitchen_day: str,
    db: psycopg2.extensions.connection,
) -> None:
    """Set has_volunteer flag on restaurants that have a pickup_intent=offer."""
    vol_query = """
        SELECT DISTINCT ps.restaurant_id
        FROM vianda_selection_info ps
        INNER JOIN user_messaging_preferences ump ON ps.user_id = ump.user_id
        WHERE ps.restaurant_id = ANY(%s::uuid[]) AND ps.kitchen_day = %s
          AND ps.pickup_intent = 'offer' AND ps.is_archived = FALSE
          AND ump.coworkers_can_see_my_orders = TRUE
          AND ump.can_participate_in_vianda_pickups = TRUE
    """
    vol_rows = db_read(vol_query, (rest_ids_str, kitchen_day), connection=db) or []
    volunteer_rest_ids = {r["restaurant_id"] for r in vol_rows}
    for r in restaurants:
        r["has_volunteer"] = r["restaurant_id"] in volunteer_rest_ids


def _build_coworker_match_clause(
    workplace_group_id: UUID | None,
    employer_entity_id: UUID | None,
    employer_address_id: UUID | None,
) -> tuple[str, tuple]:
    """Return (SQL clause, params) for coworker matching based on workplace/employer scope."""
    if workplace_group_id:
        return "AND u_ps.workplace_group_id = %s", (str(workplace_group_id),)
    if employer_address_id is not None:
        return (
            "AND u_ps.employer_entity_id = %s AND u_ps.employer_address_id = %s",
            (str(employer_entity_id), str(employer_address_id)),
        )
    return (
        "AND u_ps.employer_entity_id = %s AND u_ps.employer_address_id IS NULL",
        (str(employer_entity_id),),
    )


def _query_coworker_intent_restaurants(
    rest_ids_str: list[str],
    kitchen_day: str,
    intent: str,
    coworker_match_clause: str,
    match_params: tuple,
    user_id: UUID | None,
    db: psycopg2.extensions.connection,
) -> set:
    """Query restaurant IDs that have coworker pickup intents (offer or request)."""
    exclude_self_clause = " AND ps.user_id != %s" if user_id else ""
    query = (
        f"""
        SELECT DISTINCT ps.restaurant_id
        FROM vianda_selection_info ps
        INNER JOIN user_info u_ps ON ps.user_id = u_ps.user_id
        INNER JOIN user_messaging_preferences ump ON ps.user_id = ump.user_id
        WHERE ps.restaurant_id = ANY(%s::uuid[]) AND ps.kitchen_day = %s
          AND ps.pickup_intent = %s AND ps.is_archived = FALSE
          AND ump.coworkers_can_see_my_orders = TRUE
          AND ump.can_participate_in_vianda_pickups = TRUE
          {coworker_match_clause}
    """
        + exclude_self_clause
    )
    params = (rest_ids_str, kitchen_day, intent) + match_params
    if user_id:
        params += (str(user_id),)
    rows = db_read(query, params, connection=db) or []
    return {r["restaurant_id"] for r in rows}


def _mark_coworker_restaurants(
    restaurants: list[dict],
    rest_ids_str: list[str],
    kitchen_day: str,
    user_id: UUID | None,
    workplace_group_id: UUID | None,
    employer_entity_id: UUID | None,
    employer_address_id: UUID | None,
    db: psycopg2.extensions.connection,
) -> None:
    """Set has_coworker_offer and has_coworker_request flags on restaurants."""
    if not (workplace_group_id or employer_entity_id):
        return
    coworker_match_clause, match_params = _build_coworker_match_clause(
        workplace_group_id,
        employer_entity_id,
        employer_address_id,
    )
    offer_ids = _query_coworker_intent_restaurants(
        rest_ids_str,
        kitchen_day,
        "offer",
        coworker_match_clause,
        match_params,
        user_id,
        db,
    )
    request_ids = _query_coworker_intent_restaurants(
        rest_ids_str,
        kitchen_day,
        "request",
        coworker_match_clause,
        match_params,
        user_id,
        db,
    )
    for r in restaurants:
        r["has_coworker_offer"] = r["restaurant_id"] in offer_ids
        r["has_coworker_request"] = r["restaurant_id"] in request_ids


def _mark_reserved_viandas(
    restaurants: list[dict],
    user_id: UUID | None,
    kitchen_day: str | None,
    db: psycopg2.extensions.connection,
) -> None:
    """Mark viandas the user has already reserved for the kitchen day."""
    reserved_vianda_to_selection: dict = {}
    if user_id and kitchen_day:
        reserved_query = """
            SELECT vianda_id, vianda_selection_id FROM vianda_selection_info
            WHERE user_id = %s AND kitchen_day = %s AND is_archived = FALSE
        """
        reserved_rows = db_read(reserved_query, (str(user_id), kitchen_day), connection=db) or []
        reserved_vianda_to_selection = {str(r["vianda_id"]): str(r["vianda_selection_id"]) for r in reserved_rows}
    for r in restaurants:
        for p in r.get("viandas") or []:
            pid_str = str(p.get("vianda_id", ""))
            if pid_str in reserved_vianda_to_selection:
                p["is_already_reserved"] = True
                p["existing_vianda_selection_id"] = reserved_vianda_to_selection[pid_str]
            else:
                p["is_already_reserved"] = False
                p["existing_vianda_selection_id"] = None


def _apply_favorites_and_recommendations(
    restaurants: list[dict],
    user_id: UUID | None,
    db: psycopg2.extensions.connection,
) -> None:
    """Apply favorites, recommendations, sorting, and narrow viandas to lean payload."""
    if user_id:
        from app.services.favorite_service import get_favorite_ids
        from app.services.recommendation_service import apply_recommendation

        fav = get_favorite_ids(user_id, db)
        fav_rest_str = {str(rid) for rid in fav["restaurant_ids"]}
        fav_vianda_str = {str(pid) for pid in fav["vianda_ids"]}
        for r in restaurants:
            r["is_favorite"] = str(r["restaurant_id"]) in fav_rest_str
            for p in r.get("viandas") or []:
                p["is_favorite"] = str(p["vianda_id"]) in fav_vianda_str
        apply_recommendation(restaurants, user_id, db, favorite_ids=fav)
        _sort_by_recommendation(restaurants)
    else:
        for r in restaurants:
            r["is_favorite"] = False
            r["is_recommended"] = False
            for p in r.get("viandas") or []:
                p["is_favorite"] = False
                p["is_recommended"] = False
    # Narrow viandas to lean payload (modal fetches via enriched)
    for r in restaurants:
        r["viandas"] = [_build_lean_vianda_dict(p) for p in (r.get("viandas") or [])]


def _recommendation_sort_key(x: dict) -> tuple:
    """Sort key: recommended first, then by score descending, then name."""
    return (
        not x.get("is_recommended", False),
        -(x.get("_recommendation_score", 0)),
        (x.get("name", x.get("product_name", "")) or "").lower(),
    )


def _sort_by_recommendation(restaurants: list[dict]) -> None:
    """Sort restaurants and their viandas by recommendation score."""
    for r in restaurants:
        viandas = r.get("viandas") or []
        viandas.sort(
            key=lambda x: (
                not x.get("is_recommended", False),
                -(x.get("_recommendation_score", 0)),
                (x.get("product_name") or "").lower(),
            )
        )
        r["viandas"] = viandas
    restaurants.sort(key=_recommendation_sort_key)


def _compute_city_center(
    country: str,
    matched_city: str,
    db: psycopg2.extensions.connection,
) -> dict | None:
    """Compute center lat/lng from active restaurants, falling back to city default."""
    query_center = """
        SELECT AVG(g.latitude) AS lat, AVG(g.longitude) AS lng
        FROM geolocation_info g
        INNER JOIN address_info a ON g.address_id = a.address_id
        INNER JOIN restaurant_info r ON r.address_id = a.address_id
        WHERE a.country_code = %s
          AND TRIM(a.city) = %s
          AND a.is_archived = FALSE
          AND r.is_archived = FALSE
          AND r.status = 'active'
          AND EXISTS (
            SELECT 1 FROM vianda_info p
            INNER JOIN vianda_kitchen_days pkd ON pkd.vianda_id = p.vianda_id AND pkd.is_archived = FALSE AND pkd.status = 'active'
            WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
          )
          AND EXISTS (
            SELECT 1 FROM qr_code qc
            WHERE qc.restaurant_id = r.restaurant_id AND qc.is_archived = FALSE AND qc.status = 'active'
          )
          AND g.is_archived = FALSE
    """
    center_row = db_read(query_center, (country, matched_city), connection=db, fetch_one=True)
    if center_row and center_row.get("lat") is not None and center_row.get("lng") is not None:
        return {"lat": float(center_row["lat"]), "lng": float(center_row["lng"])}
    from app.config.supported_cities_default_location import get_city_default_location_by_name

    return get_city_default_location_by_name(country, matched_city)


def get_restaurants_by_city(
    city: str,
    country_code: str,
    db: psycopg2.extensions.connection,
    *,
    timezone_str: str | None = None,
    kitchen_day: str | None = None,
    credit_cost_local_currency: float | None = None,
    user_id: UUID | None = None,
    employer_entity_id: UUID | None = None,
    employer_address_id: UUID | None = None,
    workplace_group_id: UUID | None = None,
    locale: str = "en",
    cursor: str | None = None,
    limit: int | None = None,
    cuisine_filter: list[str] | None = None,
    max_credits: int | None = None,
    dietary_filter: list[str] | None = None,
    geo_filter: tuple[float, float, float] | None = None,
) -> dict[str, Any]:
    """
    Return restaurants in the given city (case-insensitive match) in the given country.
    Only restaurants with status = 'Active' and is_archived = FALSE are returned
    (Pending/Inactive or archived restaurants are excluded).
    Response: requested_city, city (matched), center (optional lat/lng), optional kitchen_day,
    and restaurants list with restaurant_id, name, cuisine, lat, lng, etc.
    When timezone_str is set and kitchen_day is omitted, resolve next available kitchen day.
    When kitchen_day is set (or resolved), attach viandas for that day to each restaurant.
    credit_cost_local_currency: optional plan credit cost (local currency per credit); when set, savings
    are computed per vianda; otherwise savings=0.
    user_id: optional; when set, favorites are surfaced at top and is_favorite set on items.
    workplace_group_id: optional; takes precedence over employer_entity_id for coworker matching.
    employer_entity_id, employer_address_id: optional; when set (user has employer), has_coworker_offer
    and has_coworker_request are computed per restaurant for coworker-scoped pickup intents.
    cuisine_filter: optional list of cuisine_name strings (restaurant-level, multi-select OR logic).
    max_credits: optional integer; viandas with credit > max_credits are excluded. Restaurants with no
    surviving viandas after this filter are dropped from the response (drop-on-empty-viandas).
    dietary_filter: optional list of DietaryFlag values; viandas whose dietary TEXT[] column does not
    overlap with the requested flags are excluded (array overlap, NOT IN/ANY). Restaurants with no
    surviving viandas after this filter are dropped (drop-on-empty-viandas).
    geo_filter: optional (lat, lng, radius_km) tuple; restricts to restaurants within radius_km km via
    PostGIS ST_DWithin. Applied inside the WHERE clause (before cursor slicing) so pagination is correct.
    City and radius are AND-composed: a restaurant must satisfy both constraints.
    No institution scope; B2C explore by market (country + city).
    """
    country = (country_code or "").strip().upper()
    requested = (city or "").strip()

    # Resolve kitchen_day
    resolved_kitchen_day: str | None = None
    if kitchen_day and kitchen_day in VALID_KITCHEN_DAYS:
        resolved_kitchen_day = kitchen_day
    elif timezone_str and country:
        resolved_kitchen_day = resolve_kitchen_day_for_explore(country, timezone_str, db)

    matched_city = _match_city_in_country(requested, country, db)
    restaurants = _query_city_restaurants(
        country,
        matched_city,
        locale,
        db,
        cuisine_filter=cuisine_filter,
        geo_filter=geo_filter,
    )

    # Attach viandas, volunteers, coworker flags, and reservations
    if resolved_kitchen_day and restaurants:
        restaurants = _attach_viandas_and_savings(
            restaurants,
            resolved_kitchen_day,
            credit_cost_local_currency,
            db,
            max_credits=max_credits,
            dietary_filter=dietary_filter,
        )
        rest_ids_str = [str(r["restaurant_id"]) for r in restaurants]
        _mark_volunteer_restaurants(restaurants, rest_ids_str, resolved_kitchen_day, db)
        _mark_coworker_restaurants(
            restaurants,
            rest_ids_str,
            resolved_kitchen_day,
            user_id,
            workplace_group_id,
            employer_entity_id,
            employer_address_id,
            db,
        )
        _mark_reserved_viandas(restaurants, user_id, resolved_kitchen_day, db)

    _apply_favorites_and_recommendations(restaurants, user_id, db)

    # Cursor pagination
    page_restaurants, next_cursor, has_more = slice_restaurants_by_cursor(restaurants, cursor, limit)
    restaurants = page_restaurants

    # Center: avg lat/lng (first page only — frontend caches it)
    center = None
    if cursor is None and matched_city and country:
        center = _compute_city_center(country, matched_city, db)

    out: dict[str, Any] = {
        "requested_city": requested or "",
        "city": matched_city or requested or "",
        "center": center,
        "restaurants": restaurants,
    }
    if resolved_kitchen_day:
        out["kitchen_day"] = resolved_kitchen_day
    out["next_cursor"] = next_cursor
    out["has_more"] = has_more
    return out
