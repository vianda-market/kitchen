# app/services/ads/zone_service.py
"""
Ad zone CRUD and flywheel state management.

Zones are the geographic unit for the flywheel engine. Each zone has:
- A lat/lon center + radius defining the targeting area
- A flywheel state (monitoring -> supply_acquisition -> demand_activation -> growth -> mature)
- Metrics (notify-me leads, restaurants, subscribers, estimated MAU)
- Budget allocation across the 3 strategies

Zones are created by operators (cold start) or proposed by the Gemini advisor (data-driven).
Operators can override any automated threshold or state transition at any time.
"""

import json
import logging
from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
from uuid import UUID

import psycopg2.extensions

from app.config.settings import settings
from app.utils.db import db_read
from app.utils.log import log_info

logger = logging.getLogger(__name__)

VALID_FLYWHEEL_STATES = {
    "monitoring",
    "supply_acquisition",
    "demand_activation",
    "growth",
    "mature",
    "paused",
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two lat/lon points in kilometers."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def check_zone_overlap(
    latitude: float,
    longitude: float,
    radius_km: float,
    db: psycopg2.extensions.connection,
    exclude_zone_id: UUID | None = None,
) -> list[dict]:
    """
    Check if a proposed zone overlaps with existing zones.

    Returns list of overlapping zones with distance info.
    Overlap = distance between centers < sum of radii.
    """
    rows = db_read(
        "SELECT id, name, latitude, longitude, radius_km FROM core.ad_zone WHERE flywheel_state != 'paused'",
        connection=db,
    )
    overlaps = []
    for row in rows or []:
        if exclude_zone_id and str(row["id"]) == str(exclude_zone_id):
            continue
        distance = _haversine_km(latitude, longitude, float(row["latitude"]), float(row["longitude"]))
        combined_radii = radius_km + float(row["radius_km"])
        if distance < combined_radii:
            overlaps.append(
                {
                    "zone_id": row["id"],
                    "zone_name": row["name"],
                    "distance_km": round(distance, 2),
                    "combined_radii_km": round(combined_radii, 2),
                    "overlap_km": round(combined_radii - distance, 2),
                }
            )
    return overlaps


def create_zone(
    data: dict,
    created_by_user_id: UUID | None,
    db: psycopg2.extensions.connection,
) -> dict:
    """
    Create a new ad zone. Validates radius and checks for overlaps (warning only).

    Args:
        data: Zone fields from AdZoneCreateSchema.
        created_by_user_id: The operator creating the zone (for state_changed_by).
        db: DB connection.

    Returns:
        The created zone record.
    """
    radius_km = data.get("radius_km", settings.ZONE_DEFAULT_RADIUS_KM)
    if radius_km < settings.ZONE_MIN_RADIUS_KM:
        radius_km = settings.ZONE_MIN_RADIUS_KM

    flywheel_state = data.get("flywheel_state", "monitoring")
    if flywheel_state not in VALID_FLYWHEEL_STATES:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=f"Invalid flywheel_state: {flywheel_state}")

    budget_allocation = data.get("budget_allocation") or {"b2c_subscriber": 0, "b2b_employer": 0, "b2b_restaurant": 100}

    now = datetime.now(UTC)
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO core.ad_zone (
                name, country_code, city_name, neighborhood,
                latitude, longitude, radius_km,
                flywheel_state, state_changed_at, state_changed_by,
                budget_allocation, daily_budget_cents,
                created_by, approved_by,
                created_date, modified_date
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s::jsonb, %s,
                %s, %s,
                %s, %s
            ) RETURNING id
            """,
            (
                data["name"],
                data["country_code"],
                data["city_name"],
                data.get("neighborhood"),
                data["latitude"],
                data["longitude"],
                radius_km,
                flywheel_state,
                now,
                str(created_by_user_id) if created_by_user_id else None,
                json.dumps(budget_allocation),
                data.get("daily_budget_cents"),
                "operator",
                str(created_by_user_id) if created_by_user_id else None,
                now,
                now,
            ),
        )
        row = cursor.fetchone()
        db.commit()
        zone_id = row[0] if row else None
        log_info(f"Ad zone created: {data['name']} id={zone_id} state={flywheel_state}")
        return get_zone_by_id(zone_id, db)
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()


def get_zone_by_id(
    zone_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict | None:
    """Get a zone by ID."""
    return db_read(
        "SELECT * FROM core.ad_zone WHERE id = %s::uuid",
        (str(zone_id),),
        connection=db,
        fetch_one=True,
    )


def list_zones(
    db: psycopg2.extensions.connection,
    country_code: str | None = None,
    flywheel_state: str | None = None,
) -> list[dict]:
    """List zones with optional filters."""
    query = "SELECT * FROM core.ad_zone WHERE 1=1"
    params = []

    if country_code:
        query += " AND country_code = %s"
        params.append(country_code)
    if flywheel_state:
        query += " AND flywheel_state = %s"
        params.append(flywheel_state)

    query += " ORDER BY created_date DESC"
    return db_read(query, tuple(params), connection=db) or []


def update_zone(
    zone_id: UUID,
    data: dict,
    updated_by_user_id: UUID | None,
    db: psycopg2.extensions.connection,
) -> dict | None:
    """
    Update zone fields (name, neighborhood, budget, radius).
    For state transitions, use transition_zone_state instead.
    """
    sets = []
    params = []

    for field in ("name", "neighborhood", "daily_budget_cents", "radius_km"):
        if field in data and data[field] is not None:
            sets.append(f"{field} = %s")
            params.append(data[field])

    if "budget_allocation" in data and data["budget_allocation"] is not None:
        import json

        sets.append("budget_allocation = %s::jsonb")
        params.append(json.dumps(data["budget_allocation"]))

    if not sets:
        return get_zone_by_id(zone_id, db)

    sets.append("modified_date = %s")
    params.append(datetime.now(UTC))
    params.append(str(zone_id))

    cursor = db.cursor()
    try:
        cursor.execute(
            f"UPDATE core.ad_zone SET {', '.join(sets)} WHERE id = %s::uuid",
            tuple(params),
        )
        db.commit()
        return get_zone_by_id(zone_id, db)
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()


def transition_zone_state(
    zone_id: UUID,
    new_state: str,
    changed_by_user_id: UUID | None,
    db: psycopg2.extensions.connection,
) -> dict | None:
    """
    Transition a zone's flywheel state. Operator can force any transition.

    Args:
        zone_id: Zone UUID.
        new_state: Target flywheel state.
        changed_by_user_id: Operator performing the transition.
        db: DB connection.

    Returns:
        Updated zone record, or None if not found.
    """
    if new_state not in VALID_FLYWHEEL_STATES:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=f"Invalid flywheel_state: {new_state}")

    zone = get_zone_by_id(zone_id, db)
    if not zone:
        return None

    now = datetime.now(UTC)
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            UPDATE core.ad_zone
            SET flywheel_state = %s,
                state_changed_at = %s,
                state_changed_by = %s,
                modified_date = %s
            WHERE id = %s::uuid
            """,
            (
                new_state,
                now,
                str(changed_by_user_id) if changed_by_user_id else None,
                now,
                str(zone_id),
            ),
        )
        db.commit()
        log_info(
            f"Ad zone state transition: {zone['name']} "
            f"{zone['flywheel_state']} -> {new_state} "
            f"by user {changed_by_user_id}"
        )
        return get_zone_by_id(zone_id, db)
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()


def delete_zone(
    zone_id: UUID,
    db: psycopg2.extensions.connection,
) -> bool:
    """Delete a zone. Returns True if deleted, False if not found."""
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM core.ad_zone WHERE id = %s::uuid", (str(zone_id),))
        deleted = cursor.rowcount > 0
        db.commit()
        return deleted
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
