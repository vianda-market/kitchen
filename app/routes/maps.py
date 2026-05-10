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
from app.services.city_map_service import city_map_service

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
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> dict[str, Any]:
    """
    Return all active restaurant pins for a city plus a recommended NE/SW viewport.

    The viewport is computed server-side so the client can call fitBounds on first
    paint without its own projection math.  When no restaurants have coordinates,
    markers is [] and recommended_viewport is null.

    No image is generated.  This endpoint does not call Mapbox — it is pure DB + math.
    """
    if len(country_code) != 2:
        raise envelope_exception(
            ErrorCode.VALIDATION_INVALID_FORMAT,
            status=400,
            locale="en",
            field="country_code",
        )

    return city_map_service.get_pins(
        city=city,
        country_code=country_code.upper(),
        db=db,
    )
