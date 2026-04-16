# app/routes/admin/ad_zones.py
"""
Ad Zone management routes (Internal Admin only).

CRUD for geographic ad zones + flywheel state transitions.
Zones are the targeting unit for the geographic flywheel engine.
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_employee_user
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import (
    AdZoneCreateSchema,
    AdZoneResponseSchema,
    AdZoneUpdateSchema,
)
from app.services.ads.zone_service import (
    check_zone_overlap,
    create_zone,
    delete_zone,
    get_zone_by_id,
    list_zones,
    transition_zone_state,
    update_zone,
)

router = APIRouter(prefix="/admin/ad-zones", tags=["Admin Ad Zones"])


@router.post("", response_model=AdZoneResponseSchema, status_code=201)
async def create_ad_zone(
    body: AdZoneCreateSchema,
    db: psycopg2.extensions.connection = Depends(get_db),
    current_user: dict = Depends(get_employee_user),
):
    """
    Create a new ad zone for the geographic flywheel.

    **Authorization**: Internal employees only.

    Validates radius minimum. Checks for overlap with existing zones (warning in response, not blocking).
    Operator can set any initial flywheel_state (cold start support).
    """
    user_id = current_user.get("user_id")

    # Check overlaps (advisory, not blocking)
    overlaps = check_zone_overlap(body.latitude, body.longitude, body.radius_km, db)

    zone = create_zone(body.model_dump(), UUID(str(user_id)) if user_id else None, db)
    if not zone:
        raise HTTPException(status_code=500, detail="Failed to create zone")

    # Include overlap warnings in response headers
    if overlaps:
        overlap_names = ", ".join(o["zone_name"] for o in overlaps)
        zone["_overlap_warning"] = f"Overlaps with: {overlap_names}"

    return zone


@router.get("", response_model=list[AdZoneResponseSchema])
async def list_ad_zones(
    country_code: str | None = Query(None, min_length=2, max_length=2),
    flywheel_state: str | None = Query(None),
    db: psycopg2.extensions.connection = Depends(get_db),
    current_user: dict = Depends(get_employee_user),
):
    """
    List ad zones with optional filters.

    **Authorization**: Internal employees only.
    """
    return list_zones(db, country_code=country_code, flywheel_state=flywheel_state)


@router.get("/{zone_id}", response_model=AdZoneResponseSchema)
async def get_ad_zone(
    zone_id: UUID,
    db: psycopg2.extensions.connection = Depends(get_db),
    current_user: dict = Depends(get_employee_user),
):
    """
    Get a single ad zone by ID.

    **Authorization**: Internal employees only.
    """
    zone = get_zone_by_id(zone_id, db)
    if not zone:
        raise HTTPException(status_code=404, detail="Ad zone not found")
    return zone


@router.patch("/{zone_id}", response_model=AdZoneResponseSchema)
async def update_ad_zone(
    zone_id: UUID,
    body: AdZoneUpdateSchema,
    db: psycopg2.extensions.connection = Depends(get_db),
    current_user: dict = Depends(get_employee_user),
):
    """
    Update zone fields (name, neighborhood, budget, radius).

    **Authorization**: Internal employees only.

    To change flywheel state, use POST /{zone_id}/transition instead.
    """
    user_id = current_user.get("user_id")
    data = body.model_dump(exclude_unset=True)

    # If flywheel_state is in the update, route to transition instead
    if "flywheel_state" in data and data["flywheel_state"] is not None:
        new_state = data.pop("flywheel_state")
        transition_zone_state(zone_id, new_state, UUID(str(user_id)) if user_id else None, db)

    zone = update_zone(zone_id, data, UUID(str(user_id)) if user_id else None, db)
    if not zone:
        raise HTTPException(status_code=404, detail="Ad zone not found")
    return zone


@router.post("/{zone_id}/transition", response_model=AdZoneResponseSchema)
async def transition_ad_zone_state(
    zone_id: UUID,
    new_state: str = Query(..., description="Target flywheel state"),
    db: psycopg2.extensions.connection = Depends(get_db),
    current_user: dict = Depends(get_employee_user),
):
    """
    Transition a zone's flywheel state.

    **Authorization**: Internal employees only.

    Valid states: monitoring, supply_acquisition, demand_activation, growth, mature, paused.

    Operator can force any transition (cold start support). No automated
    threshold validation -- that is handled by the Gemini advisor (Phase 22).
    """
    user_id = current_user.get("user_id")
    zone = transition_zone_state(zone_id, new_state, UUID(str(user_id)) if user_id else None, db)
    if not zone:
        raise HTTPException(status_code=404, detail="Ad zone not found")
    return zone


@router.get("/{zone_id}/overlaps")
async def check_ad_zone_overlaps(
    zone_id: UUID,
    db: psycopg2.extensions.connection = Depends(get_db),
    current_user: dict = Depends(get_employee_user),
):
    """
    Check if a zone overlaps with other active zones.

    **Authorization**: Internal employees only.

    Returns list of overlapping zones with distance info.
    """
    zone = get_zone_by_id(zone_id, db)
    if not zone:
        raise HTTPException(status_code=404, detail="Ad zone not found")
    overlaps = check_zone_overlap(
        float(zone["latitude"]),
        float(zone["longitude"]),
        float(zone["radius_km"]),
        db,
        exclude_zone_id=zone_id,
    )
    return {"zone_id": str(zone_id), "overlaps": overlaps}


@router.delete("/{zone_id}", status_code=204)
async def delete_ad_zone(
    zone_id: UUID,
    db: psycopg2.extensions.connection = Depends(get_db),
    current_user: dict = Depends(get_employee_user),
):
    """
    Delete an ad zone.

    **Authorization**: Internal employees only.
    """
    deleted = delete_zone(zone_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ad zone not found")


# =============================================================================
# ZONE METRICS (cron + on-demand)
# =============================================================================


@router.post("/sync-metrics")
async def sync_all_zone_metrics(
    db: psycopg2.extensions.connection = Depends(get_db),
    current_user: dict = Depends(get_employee_user),
):
    """
    Refresh metrics for all active zones (notify-me leads, restaurants, subscribers).

    **Authorization**: Internal employees only.

    Designed to be called by Cloud Scheduler (daily) or on-demand from admin.
    Updates notify_me_lead_count, active_restaurant_count, active_subscriber_count
    for each non-paused zone.
    """
    from app.services.ads.zone_metrics_service import refresh_all_zone_metrics

    return refresh_all_zone_metrics(db)


@router.post("/{zone_id}/sync-metrics")
async def sync_zone_metrics(
    zone_id: UUID,
    db: psycopg2.extensions.connection = Depends(get_db),
    current_user: dict = Depends(get_employee_user),
):
    """
    Refresh metrics for a single zone.

    **Authorization**: Internal employees only.
    """
    from app.services.ads.zone_metrics_service import refresh_zone_metrics

    result = refresh_zone_metrics(zone_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="Ad zone not found")
    return result


@router.get("/{zone_id}/audience")
async def get_zone_audience(
    zone_id: UUID,
    db: psycopg2.extensions.connection = Depends(get_db),
    current_user: dict = Depends(get_employee_user),
):
    """
    Export hashed notify-me email list for Custom Audience upload.

    **Authorization**: Internal employees only.

    Returns list of SHA256-hashed emails from notify-me leads matching
    this zone's city + country. Ready for Meta Custom Audience or
    Google Customer Match upload.
    """
    zone = get_zone_by_id(zone_id, db)
    if not zone:
        raise HTTPException(status_code=404, detail="Ad zone not found")

    from app.services.ads.notify_me_sync import export_hashed_audience_for_zone

    audience = export_hashed_audience_for_zone(zone["country_code"], zone["city_name"], db)

    return {
        "zone_id": str(zone_id),
        "zone_name": zone["name"],
        "audience_size": len(audience),
        "hashed_emails": audience,
        "usage_guidance": {
            "meta_custom_audience": "Upload hashed_email values to Meta Custom Audience",
            "google_customer_match": "Upload hashed_email values to Google Customer Match",
            "lookalike_viable": len(audience) >= 300,
            "seed_viable": len(audience) >= 100,
        },
    }
