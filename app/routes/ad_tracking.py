# app/routes/ad_tracking.py
"""
Ad click tracking routes (authenticated users).

Frontend submits click identifiers (gclid, fbclid, fbc, fbp) captured
on landing. These are stored and used for conversion attribution when
the user subscribes.
"""
from fastapi import APIRouter, Depends, HTTPException
import psycopg2.extensions

from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import (
    AdClickTrackingCreateSchema,
    AdClickTrackingResponseSchema,
)
from app.services.ads.click_tracking_service import create_click_tracking

router = APIRouter(prefix="/ad-tracking", tags=["Ad Tracking"])


@router.post("", response_model=AdClickTrackingResponseSchema, status_code=201)
async def capture_click_tracking(
    body: AdClickTrackingCreateSchema,
    db: psycopg2.extensions.connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Capture ad click identifiers from the frontend.

    **Authorization**: Any authenticated user.

    Called by the B2C app or marketing site when a user lands from an ad click.
    The frontend extracts gclid/fbclid from URL params and fbc/fbp from cookies,
    then submits them here. These are used later for conversion attribution.

    Idempotent: if click tracking already exists for this user + subscription_id,
    returns the existing record.
    """
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")

    record = create_click_tracking(user_id, body.model_dump(), db)
    if not record:
        raise HTTPException(status_code=500, detail="Failed to create click tracking record")
    return record
