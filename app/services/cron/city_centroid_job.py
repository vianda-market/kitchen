"""
Weekly cron job: recompute per-city centroids from active geocoded restaurants.

Idempotent by construction — running with the same restaurant set produces
the same UPDATE values. Cities with zero active geocoded restaurants are
left untouched (stale centroid > NULL for downstream consumers).
"""

import json
import sys
from datetime import UTC, datetime
from typing import Any

import psycopg2.extensions

from app.utils.db import db_read
from app.utils.db_pool import get_db_connection_context
from app.utils.log import log_error, log_info

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_QUERY_CITY_CENTROIDS = """
SELECT
    a.city_metadata_id,
    AVG(g.latitude)  AS centroid_lat,
    AVG(g.longitude) AS centroid_lng,
    COUNT(*)         AS restaurant_count
FROM restaurant_info r
INNER JOIN address_info a       ON r.address_id = a.address_id
INNER JOIN geolocation_info g   ON g.address_id = a.address_id AND g.is_archived = FALSE
WHERE a.is_archived = FALSE
  AND r.is_archived = FALSE
  AND r.status = 'active'
  AND g.latitude IS NOT NULL
  AND g.longitude IS NOT NULL
GROUP BY a.city_metadata_id
"""

_UPDATE_CITY_CENTROID = """
UPDATE core.city_metadata
   SET centroid_lat         = %s,
       centroid_lng         = %s,
       centroid_computed_at = now()
 WHERE city_metadata_id = %s
"""

_QUERY_ALL_CITY_IDS = """
SELECT city_metadata_id FROM core.city_metadata WHERE is_archived = FALSE
"""


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _compute_centroids(db: psycopg2.extensions.connection) -> list[dict[str, Any]]:
    """Return one row per city that has at least one active geocoded restaurant."""
    rows = db_read(_QUERY_CITY_CENTROIDS, connection=db)
    if not isinstance(rows, list):
        return []
    return rows


def _count_all_cities(db: psycopg2.extensions.connection) -> int:
    """Return total number of non-archived cities (to derive skipped count)."""
    rows = db_read(_QUERY_ALL_CITY_IDS, connection=db)
    if not isinstance(rows, list):
        return 0
    return len(rows)


def _update_centroid(
    db: psycopg2.extensions.connection,
    city_metadata_id: str,
    centroid_lat: float,
    centroid_lng: float,
) -> None:
    """Write rounded centroid values for a single city."""
    lat = round(float(centroid_lat), 6)
    lng = round(float(centroid_lng), 6)
    with db.cursor() as cur:
        cur.execute(_UPDATE_CITY_CENTROID, (lat, lng, city_metadata_id))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def weekly_entry() -> dict[str, Any]:
    """
    Weekly cron entry point — recomputes centroid_lat/lng/computed_at for
    every city with at least one active geocoded restaurant.

    Returns a result dict with cities_updated, cities_skipped_no_restaurants,
    timestamp, and success flag.
    """
    log_info("[city-centroid] Starting weekly centroid computation")
    timestamp = datetime.now(UTC).isoformat()

    try:
        with get_db_connection_context() as db:
            centroid_rows = _compute_centroids(db)
            total_cities = _count_all_cities(db)

            cities_updated = 0
            for row in centroid_rows:
                city_id = str(row["city_metadata_id"])
                lat = row["centroid_lat"]
                lng = row["centroid_lng"]
                count = row["restaurant_count"]

                _update_centroid(db, city_id, lat, lng)
                log_info(
                    f"[city-centroid] city_metadata_id={city_id} "
                    f"centroid=({round(float(lat), 6)}, {round(float(lng), 6)}) "
                    f"restaurant_count={count}"
                )
                cities_updated += 1

            db.commit()

        cities_skipped = max(0, total_cities - cities_updated)
        result: dict[str, Any] = {
            "cities_updated": cities_updated,
            "cities_skipped_no_restaurants": cities_skipped,
            "timestamp": timestamp,
            "success": True,
        }
        log_info(f"[city-centroid] Complete — updated={cities_updated} skipped={cities_skipped}")
        return result

    except Exception as exc:
        log_error(f"[city-centroid] Fatal error: {exc}")
        return {
            "cities_updated": 0,
            "cities_skipped_no_restaurants": 0,
            "timestamp": timestamp,
            "success": False,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# CLI — for ops manual trigger: python -m app.services.cron.city_centroid_job
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = weekly_entry()
    log_info(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result.get("success") else 1)
