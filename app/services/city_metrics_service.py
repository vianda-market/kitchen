"""
City metrics service for the lead flow (unauthenticated).

Returns metrics about a given city in a country to encourage signup:
restaurant count, has_coverage, matched_city, optional center.
Matching: case-insensitive match of requested city to address_info.city
for addresses that have at least one non-archived restaurant in the country.
We use city first (instead of zipcode) so coverage grows faster at city level;
zipcode refinement can be added later.
"""

from typing import Optional, List, Any
import psycopg2.extensions

from app.utils.db import db_read
from app.config.supported_cities import GLOBAL_CITY_ID


def get_cities_with_coverage(
    country_code: str,
    db: psycopg2.extensions.connection,
) -> List[str]:
    """
    Return sorted list of city names (from city_info) that have at least one restaurant.
    Intersection of: (a) supported cities in city_info, (b) cities with Active restaurant + plate_kitchen_days.
    Used by GET /leads/cities (public, no auth) and GET /restaurants/cities (auth).
    Single source for lead flow, signup picker, and explore dropdown.
    """
    country = (country_code or "").strip().upper()
    if not country:
        return []
    query = """
        SELECT c.name
        FROM city_info c
        WHERE c.country_code = %s
          AND c.city_id != %s
          AND c.is_archived = FALSE
          AND EXISTS (
            SELECT 1 FROM address_info a
            INNER JOIN restaurant_info r ON r.address_id = a.address_id
            WHERE UPPER(TRIM(a.city)) = UPPER(TRIM(c.name))
              AND a.country_code = c.country_code
              AND a.is_archived = FALSE
              AND r.is_archived = FALSE
              AND r.status = 'Active'
              AND EXISTS (
                SELECT 1 FROM plate_info p
                INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id
                  AND pkd.is_archived = FALSE AND pkd.status = 'Active'
                WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
              )
              AND EXISTS (
                SELECT 1 FROM qr_code qc
                WHERE qc.restaurant_id = r.restaurant_id
                  AND qc.is_archived = FALSE AND qc.status = 'Active'
              )
          )
        ORDER BY LOWER(c.name)
    """
    rows = db_read(query, (country, str(GLOBAL_CITY_ID)), connection=db)
    return [r["name"] for r in rows] if rows else []


def get_city_metrics(
    city: str,
    country_code: Optional[str],
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
          AND r.status = 'Active'
          AND EXISTS (
            SELECT 1 FROM plate_info p
            INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id AND pkd.is_archived = FALSE AND pkd.status = 'Active'
            WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
          )
          AND EXISTS (
            SELECT 1 FROM qr_code qc
            WHERE qc.restaurant_id = r.restaurant_id AND qc.is_archived = FALSE AND qc.status = 'Active'
          )
          AND TRIM(a.city) != ''
        ORDER BY city
    """
    rows = db_read(query_cities, (country,), connection=db)
    cities: List[str] = [r["city"] for r in rows] if rows else []

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
          AND r.status = 'Active'
          AND EXISTS (
            SELECT 1 FROM plate_info p
            INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id AND pkd.is_archived = FALSE AND pkd.status = 'Active'
            WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
          )
          AND EXISTS (
            SELECT 1 FROM qr_code qc
            WHERE qc.restaurant_id = r.restaurant_id AND qc.is_archived = FALSE AND qc.status = 'Active'
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

    # 4) Optional center: avg lat/lng from geolocation for addresses in matched_city (Active + plate_kitchen_days)
    center: Optional[dict] = None
    if matched_city and has_coverage:
        query_center = """
            SELECT AVG(g.latitude) AS lat, AVG(g.longitude) AS lng
            FROM geolocation_info g
            INNER JOIN address_info a ON g.address_id = a.address_id
            INNER JOIN restaurant_info r ON r.address_id = a.address_id
            WHERE a.country_code = %s
              AND TRIM(a.city) = %s
              AND a.is_archived = FALSE
              AND r.is_archived = FALSE
              AND r.status = 'Active'
              AND EXISTS (
                SELECT 1 FROM plate_info p
                INNER JOIN plate_kitchen_days pkd ON pkd.plate_id = p.plate_id AND pkd.is_archived = FALSE AND pkd.status = 'Active'
                WHERE p.restaurant_id = r.restaurant_id AND p.is_archived = FALSE
              )
              AND EXISTS (
                SELECT 1 FROM qr_code qc
                WHERE qc.restaurant_id = r.restaurant_id AND qc.is_archived = FALSE AND qc.status = 'Active'
              )
              AND g.is_archived = FALSE
        """
        center_row = db_read(
            query_center,
            (country, matched_city),
            connection=db,
            fetch_one=True,
        )
        if center_row and center_row.get("lat") is not None and center_row.get("lng") is not None:
            center = {"lat": float(center_row["lat"]), "lng": float(center_row["lng"])}

    return {
        "requested_city": requested or "",
        "matched_city": matched_city or requested or "",
        "restaurant_count": restaurant_count,
        "has_coverage": has_coverage,
        "center": center,
    }
