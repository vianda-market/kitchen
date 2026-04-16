"""
City metrics service for the lead flow (unauthenticated).

Returns metrics about a given city in a country to encourage signup:
restaurant count, has_coverage, matched_city, optional center.
Matching: case-insensitive match of requested city to address_info.city
for addresses that have at least one non-archived restaurant in the country.
We use city first (instead of zipcode) so coverage grows faster at city level;
zipcode refinement can be added later.
"""

from typing import Any

import psycopg2.extensions

from app.config.supported_cities import GLOBAL_CITY_ID
from app.utils.db import db_read


def get_cities_with_coverage(
    country_code: str,
    db: psycopg2.extensions.connection,
) -> list[str]:
    """
    Return sorted list of city names (from core.city_metadata ∪ external.geonames_city)
    that have at least one active restaurant with plate_kitchen_days and QR code.
    Intersection of: (a) promoted cities in core.city_metadata (signup picker flag),
    (b) cities with Active restaurant + plate_kitchen_days.

    Used by GET /leads/cities (public, no auth) and GET /restaurants/cities (auth).
    Single source for lead flow, signup picker, and explore dropdown.

    NOTE: address_info.city is a PR2-deprecated free-text compat column; when it's
    dropped (follow-up PR2a.5) this query will match via a JOIN through
    address_info.city_metadata_id → geonames_city.ascii_name instead.
    """
    country = (country_code or "").strip().upper()
    if not country:
        return []
    query = """
        SELECT COALESCE(cm.display_name_override, gc.name) AS name
        FROM core.city_metadata cm
        JOIN external.geonames_city gc ON gc.geonames_id = cm.geonames_id
        WHERE cm.country_iso = %s
          AND cm.city_metadata_id != %s
          AND cm.is_archived = FALSE
          AND cm.show_in_signup_picker = TRUE
          AND EXISTS (
            SELECT 1 FROM core.address_info a
            INNER JOIN ops.restaurant_info r ON r.address_id = a.address_id
            WHERE UPPER(TRIM(a.city)) = UPPER(TRIM(COALESCE(cm.display_name_override, gc.name)))
              AND a.country_code = cm.country_iso
              AND a.is_archived = FALSE
              AND r.is_archived = FALSE
              AND r.status = 'active'
              AND EXISTS (
                SELECT 1 FROM ops.plate_info p
                INNER JOIN ops.plate_kitchen_days pkd ON pkd.plate_id = p.plate_id
                  AND pkd.is_archived = FALSE AND pkd.status = 'active'
                WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
              )
              AND EXISTS (
                SELECT 1 FROM ops.qr_code qc
                WHERE qc.restaurant_id = r.restaurant_id
                  AND qc.is_archived = FALSE AND qc.status = 'active'
              )
          )
        ORDER BY LOWER(COALESCE(cm.display_name_override, gc.name))
    """
    rows = db_read(query, (country, str(GLOBAL_CITY_ID)), connection=db)
    return [r["name"] for r in rows] if rows else []


def get_supplier_cities_for_country(
    country_code: str,
    db: psycopg2.extensions.connection,
) -> list[str]:
    """
    Return sorted list of city names appropriate for a supplier lead-capture dropdown.

    Source is a union — so that a newly-added market without city_metadata coverage
    still benefits from crowd-sourced data:
      1. external.geonames_city (GeoNames, bulk-seeded) — cities in the country with pop >= 5000
      2. core.city_metadata (curated served cities — ensures custom display names appear)
      3. core.restaurant_lead.city_name (crowd-sourced from prior supplier lead submissions)

    Deduped case-insensitively, sorted alphabetically by LOWER(name), capped at 1000.
    """
    country = (country_code or "").strip().upper()
    if not country:
        return []
    query = """
        WITH combined AS (
            SELECT gc.name
            FROM external.geonames_city gc
            WHERE gc.country_iso = %(country)s
            UNION
            SELECT COALESCE(cm.display_name_override, gc2.name)
            FROM core.city_metadata cm
            JOIN external.geonames_city gc2 ON gc2.geonames_id = cm.geonames_id
            WHERE cm.country_iso = %(country)s
              AND cm.is_archived = FALSE
              AND cm.city_metadata_id != %(global_city_id)s
            UNION
            SELECT DISTINCT rl.city_name
            FROM core.restaurant_lead rl
            WHERE rl.country_code = %(country)s
              AND rl.is_archived = FALSE
              AND rl.city_name IS NOT NULL AND rl.city_name <> ''
        )
        SELECT DISTINCT ON (LOWER(name)) name
        FROM combined
        ORDER BY LOWER(name)
        LIMIT 1000
    """
    rows = db_read(
        query,
        {"country": country, "global_city_id": str(GLOBAL_CITY_ID)},
        connection=db,
    )
    return [r["name"] for r in rows] if rows else []


def get_city_metrics(
    city: str,
    country_code: str | None,
    db: psycopg2.extensions.connection,
) -> dict[str, Any]:
    """
    Return metrics for the lead city flow: requested_city, matched_city,
    restaurant_count, has_coverage, optional center (lat/lng).

    Expects country_code already normalized (e.g. from route); default US at route.
    Matching: case-insensitive exact match of city to address_info.city (trimmed)
    for addresses that have at least one non-archived restaurant in the country.
    If no match, matched_city = requested_city and restaurant_count = 0.
    """
    country = country_code or ""
    requested = (city or "").strip()

    # 1) Get distinct cities that have at least one Active restaurant with plate_kitchen_days
    query_cities = """
        SELECT DISTINCT TRIM(a.city) AS city
        FROM address_info a
        INNER JOIN restaurant_info r ON r.address_id = a.address_id
        WHERE a.country_code = %s
          AND a.is_archived = FALSE
          AND r.is_archived = FALSE
          AND r.status = 'active'
          AND EXISTS (
            SELECT 1 FROM plate_info p
            INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id AND pkd.is_archived = FALSE AND pkd.status = 'active'
            WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
          )
          AND EXISTS (
            SELECT 1 FROM qr_code qc
            WHERE qc.restaurant_id = r.restaurant_id AND qc.is_archived = FALSE AND qc.status = 'active'
          )
          AND TRIM(a.city) != ''
        ORDER BY city
    """
    rows = db_read(query_cities, (country,), connection=db)
    cities: list[str] = [r["city"] for r in rows] if rows else []

    # 2) Match: case-insensitive exact match; if none, keep requested and count 0
    matched_city: str = requested
    if requested and cities:
        requested_lower = requested.lower()
        for c in cities:
            if (c or "").strip().lower() == requested_lower:
                matched_city = (c or "").strip()
                break
        # else: no match, matched_city stays requested, we'll return count 0

    # 3) Count restaurants in matched_city (Active, with plate_kitchen_days)
    query_count = """
        SELECT COUNT(DISTINCT r.restaurant_id) AS cnt
        FROM restaurant_info r
        INNER JOIN address_info a ON r.address_id = a.address_id
        WHERE a.country_code = %s
          AND TRIM(a.city) = %s
          AND a.is_archived = FALSE
          AND r.is_archived = FALSE
          AND r.status = 'active'
          AND EXISTS (
            SELECT 1 FROM plate_info p
            INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id AND pkd.is_archived = FALSE AND pkd.status = 'active'
            WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
          )
          AND EXISTS (
            SELECT 1 FROM qr_code qc
            WHERE qc.restaurant_id = r.restaurant_id AND qc.is_archived = FALSE AND qc.status = 'active'
          )
    """
    count_row = db_read(
        query_count,
        (country, matched_city),
        connection=db,
        fetch_one=True,
    )
    restaurant_count = int(count_row["cnt"]) if count_row else 0
    has_coverage = restaurant_count > 0

    return {
        "requested_city": requested or "",
        "matched_city": matched_city or requested or "",
        "restaurant_count": restaurant_count,
        "has_coverage": has_coverage,
    }
