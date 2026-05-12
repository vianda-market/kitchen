"""
Admin Routes for City Centroid Management

Provides a manual trigger endpoint for the weekly city centroid
recomputation cron job — same logic as the scheduled run.
"""

from typing import Any

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.services.cron.city_centroid_job import weekly_entry
from app.services.error_handling import handle_business_operation
from app.utils.log import log_info

router = APIRouter(prefix="/admin/city-centroid", tags=["Admin - City Centroid"])


@router.post("/recompute", response_model=dict[str, Any])
async def recompute_city_centroids(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """
    Manually trigger city centroid recomputation for all active cities.

    Runs the same process as the weekly scheduled cron job: computes the
    geographic centroid of active, geocoded restaurants per city and writes
    centroid_lat, centroid_lng, centroid_computed_at to core.city_metadata.

    Returns:
        cities_updated: number of cities whose centroid was written
        cities_skipped_no_restaurants: cities with no active geocoded restaurants
        timestamp: ISO 8601 UTC timestamp of when the run started
        success: true on success, false if a fatal error occurred

    Requires authentication (any authenticated user).
    """

    def _recompute() -> dict[str, Any]:
        log_info(f"[city-centroid] Manual recompute triggered by user {current_user['user_id']}")
        result = weekly_entry()
        if not result.get("success"):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=500,
                detail=f"City centroid recomputation failed: {result.get('error', 'unknown error')}",
            )
        return result

    return handle_business_operation(_recompute, "city centroid recomputation")
