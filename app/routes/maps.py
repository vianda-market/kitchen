"""
Map endpoints — static map image generation and interactive pin data for B2C Explore tab.

GET /maps/city-snapshot — (dormant) returns a cached static map image URL with restaurant pin positions.
GET /maps/city-pins    — (active)  returns restaurant markers + recommended viewport for interactive map.
"""

from typing import Any

import psycopg2.extensions
from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    CityPinsResponseSchema,
    CitySnapshotResponseSchema,
)
from app.services.city_map_service import MAX_MARKERS_PER_REQUEST, city_map_service

router = APIRouter(prefix="/maps")


@router.get("/city-snapshot", response_model=CitySnapshotResponseSchema)
def get_city_map_snapshot(
    city: str = Query(..., description="City name (same value used in GET /restaurants/by-city)"),
    country_code: str = Query("US", description="ISO 3166-1 alpha-2 (e.g. US, AR)"),
    center_lat: float = Query(..., description="Latitude of user's selected address (home, work, or other)"),
    center_lng: float = Query(..., description="Longitude of user's selected address"),
    width: int = Query(600, ge=100, le=1280, description="Image width in CSS pixels"),
    height: int = Query(400, ge=100, le=1280, description="Image height in CSS pixels"),
    retina: bool = Query(True, description="Return @2x image (double resolution)"),
    style: str = Query("light", description="Map style: 'light' or 'dark'"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Return a cached static map image URL centered on the user's address with restaurant pins.
    The client renders the image via <Image> and overlays tap targets at each marker's pixel_x/pixel_y.
    Grid-cell caching: nearby users (~500m) share the same cached image.
    """
    return city_map_service.get_snapshot(
        center_lat=center_lat,
        center_lng=center_lng,
        city=city,
        country_code=country_code.upper(),
        width=width,
        height=height,
        retina=retina,
        style=style if style in ("light", "dark") else "light",
        db=db,
    )


@router.get("/city-pins", response_model=CityPinsResponseSchema)
def get_city_pins(
    city: str = Query(..., description="City name (same value used in GET /restaurants/by-city)"),
    country_code: str = Query(..., description="ISO 3166-1 alpha-2 country code (e.g. PE, AR)"),
    center_lat: float | None = Query(
        None,
        description=(
            "Latitude of the user's selected address. "
            "Required together with center_lng. "
            "When provided, markers are ordered by distance from this point "
            "and the centroid anchor is set to the nearest restaurant."
        ),
    ),
    center_lng: float | None = Query(
        None,
        description=("Longitude of the user's selected address. Required together with center_lat."),
    ),
    limit: int = Query(
        MAX_MARKERS_PER_REQUEST,
        ge=1,
        le=50,
        description=f"Maximum number of markers to return (1–50, default {MAX_MARKERS_PER_REQUEST}).",
    ),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> dict[str, Any]:
    """
    Return active restaurant pins for a city plus a recommended NE/SW viewport and centroid.

    The viewport is computed server-side so the client can call fitBounds on first
    paint without its own projection math.  When no restaurants have coordinates,
    markers is [] and recommended_viewport is null.

    No image is generated.  This endpoint does not call Mapbox — it is pure DB + math.

    When center_lat/center_lng are provided, markers are ordered by distance from that
    anchor and the centroid is set to the nearest restaurant (source='user_nearest').
    If the anchor is more than OUTLIER_DISTANCE_KM from every restaurant, the city
    centroid is used instead (source='city_fallback').

    When neither center param is provided, markers are ordered by distance from the
    precomputed city centroid (source='city').

    center_lat and center_lng are required together — supplying only one returns 400.
    """
    if len(country_code) != 2:
        raise envelope_exception(
            ErrorCode.VALIDATION_INVALID_FORMAT,
            status=400,
            locale="en",
            field="country_code",
        )

    # center_lat and center_lng are required together
    if (center_lat is None) != (center_lng is None):
        raise envelope_exception(
            ErrorCode.VALIDATION_CUSTOM,
            status=400,
            locale="en",
            msg="center_lat and center_lng must be provided together",
        )

    return city_map_service.get_pins(
        city=city,
        country_code=country_code.upper(),
        db=db,
        center_lat=center_lat,
        center_lng=center_lng,
        limit=limit,
    )
