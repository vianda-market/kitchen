"""
Zipcode metrics service for the lead flow (unauthenticated).

Returns metrics about a given zipcode in a country to encourage signup:
restaurant count, has_coverage, matched_zipcode, optional center.
Matching: exact match of requested zip to a postal_code with restaurants;
if none, fallback to first available postal_code in the country (or zero count).
"""

from typing import Any

import psycopg2.extensions

from app.utils.db import db_read


def get_zipcode_metrics(
    zip_code: str,
    country_code: str | None,
    db: psycopg2.extensions.connection,
) -> dict[str, Any]:
    """
    Return metrics for the lead zipcode flow: requested_zipcode, matched_zipcode,
    restaurant_count, has_coverage, optional center (lat/lng).

    Expects country_code already normalized (e.g. from route); default US is applied at the route.
    Matching rule: exact match of zip_code to address_info.postal_code (for
    addresses that have at least one non-archived restaurant in the country).
    If no exact match, use the first available postal_code in the country for
    display and return count 0 for the requested zip (so has_coverage False).
    """
    country = country_code or ""
    requested = (zip_code or "").strip()

    # 1) Get distinct postal_codes that have at least one Active restaurant with plate_kitchen_days
    query_postal_codes = """
        SELECT DISTINCT a.postal_code
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
        ORDER BY a.postal_code
    """
    rows = db_read(query_postal_codes, (country,), connection=db)
    postal_codes: list[str] = [r["postal_code"] for r in rows] if rows else []

    # 2) Match: exact first, else fallback to first in list (or requested with count 0)
    matched_zipcode: str = requested
    if postal_codes:
        for pc in postal_codes:
            if (pc or "").strip() == requested:
                matched_zipcode = pc
                break
        else:
            matched_zipcode = postal_codes[0]

    # 3) Count restaurants in matched_zipcode (Active, with plate_kitchen_days)
    query_count = """
        SELECT COUNT(DISTINCT r.restaurant_id) AS cnt
        FROM restaurant_info r
        INNER JOIN address_info a ON r.address_id = a.address_id
        WHERE a.country_code = %s
          AND a.postal_code = %s
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
    count_row = db_read(query_count, (country, matched_zipcode), connection=db, fetch_one=True)
    restaurant_count = int(count_row["cnt"]) if count_row else 0
    has_coverage = restaurant_count > 0

    return {
        "requested_zipcode": requested or "",
        "matched_zipcode": matched_zipcode or requested or "",
        "restaurant_count": restaurant_count,
        "has_coverage": has_coverage,
    }
