# app/services/ads/zone_metrics_service.py
"""
Zone metrics refresh service.

Refreshes per-zone counts for:
- notify_me_lead_count (from lead_interest, city-level match)
- active_restaurant_count (from restaurant_info + geolocation, radius match)
- active_subscriber_count (from subscription_info + user address + geolocation, radius match)

Called by a cron endpoint (Cloud Scheduler daily) or on-demand from admin.

Uses PostgreSQL's earth_distance functions for radius matching. Falls back
to application-level haversine if the extension is not available.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

import psycopg2.extensions

from app.services.ads.notify_me_sync import count_notify_me_leads_for_zone
from app.utils.db import db_read
from app.utils.log import log_info, log_error

logger = logging.getLogger(__name__)


def _count_restaurants_in_radius(
    latitude: float,
    longitude: float,
    radius_km: float,
    db: psycopg2.extensions.connection,
) -> int:
    """
    Count active restaurants with geolocations within radius_km of the zone center.

    Uses the haversine formula in SQL (no PostGIS extension needed).
    """
    row = db_read(
        """
        SELECT COUNT(DISTINCT r.restaurant_id) AS cnt
        FROM ops.restaurant_info r
        JOIN core.geolocation_info g ON r.address_id = g.address_id
        WHERE r.is_archived = FALSE
          AND r.status = 'active'
          AND g.is_archived = FALSE
          AND (
            2 * 6371 * ASIN(SQRT(
              POWER(SIN(RADIANS(g.latitude - %s) / 2), 2) +
              COS(RADIANS(%s)) * COS(RADIANS(g.latitude)) *
              POWER(SIN(RADIANS(g.longitude - %s) / 2), 2)
            ))
          ) <= %s
        """,
        (latitude, latitude, longitude, radius_km),
        connection=db,
        fetch_one=True,
    )
    return row["cnt"] if row else 0


def _count_subscribers_in_radius(
    latitude: float,
    longitude: float,
    radius_km: float,
    db: psycopg2.extensions.connection,
) -> int:
    """
    Count active subscribers with a home address within radius_km of the zone center.

    Join path: subscription_info.user_id -> address_info.user_id -> geolocation_info.address_id
    """
    row = db_read(
        """
        SELECT COUNT(DISTINCT s.subscription_id) AS cnt
        FROM customer.subscription_info s
        JOIN core.address_info a ON s.user_id = a.user_id
        JOIN core.geolocation_info g ON a.address_id = g.address_id
        WHERE s.is_archived = FALSE
          AND s.subscription_status = 'active'
          AND a.is_archived = FALSE
          AND g.is_archived = FALSE
          AND (
            2 * 6371 * ASIN(SQRT(
              POWER(SIN(RADIANS(g.latitude - %s) / 2), 2) +
              COS(RADIANS(%s)) * COS(RADIANS(g.latitude)) *
              POWER(SIN(RADIANS(g.longitude - %s) / 2), 2)
            ))
          ) <= %s
        """,
        (latitude, latitude, longitude, radius_km),
        connection=db,
        fetch_one=True,
    )
    return row["cnt"] if row else 0


def refresh_zone_metrics(
    zone_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict:
    """
    Refresh all metrics for a single zone.

    Updates notify_me_lead_count, active_restaurant_count, active_subscriber_count.
    Returns the updated counts.
    """
    zone = db_read(
        "SELECT * FROM core.ad_zone WHERE id = %s::uuid",
        (str(zone_id),),
        connection=db,
        fetch_one=True,
    )
    if not zone:
        return {}

    lat = float(zone["latitude"])
    lon = float(zone["longitude"])
    radius = float(zone["radius_km"])

    lead_count = count_notify_me_leads_for_zone(zone["country_code"], zone["city_name"], db)
    restaurant_count = _count_restaurants_in_radius(lat, lon, radius, db)
    subscriber_count = _count_subscribers_in_radius(lat, lon, radius, db)

    now = datetime.now(timezone.utc)
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            UPDATE core.ad_zone
            SET notify_me_lead_count = %s,
                active_restaurant_count = %s,
                active_subscriber_count = %s,
                modified_date = %s
            WHERE id = %s::uuid
            """,
            (lead_count, restaurant_count, subscriber_count, now, str(zone_id)),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()

    return {
        "zone_id": str(zone_id),
        "zone_name": zone["name"],
        "notify_me_lead_count": lead_count,
        "active_restaurant_count": restaurant_count,
        "active_subscriber_count": subscriber_count,
    }


def refresh_all_zone_metrics(
    db: psycopg2.extensions.connection,
) -> dict:
    """
    Refresh metrics for all active (non-paused) zones.

    Returns summary with per-zone counts and total zones refreshed.
    """
    zones = db_read(
        "SELECT id FROM core.ad_zone WHERE flywheel_state != 'paused' ORDER BY created_date",
        connection=db,
    )
    if not zones:
        return {"zones_refreshed": 0, "zones": []}

    results = []
    errors = []
    for zone_row in zones:
        try:
            result = refresh_zone_metrics(zone_row["id"], db)
            results.append(result)
        except Exception as e:
            log_error(f"Failed to refresh metrics for zone {zone_row['id']}: {e}")
            errors.append({"zone_id": str(zone_row["id"]), "error": str(e)})

    log_info(f"Zone metrics refresh: {len(results)} zones refreshed, {len(errors)} errors")
    return {
        "zones_refreshed": len(results),
        "zones": results,
        "errors": errors,
    }
