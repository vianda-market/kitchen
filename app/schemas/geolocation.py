# app/schemas/address_geolocation.py
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional
from uuid import UUID
from decimal import Decimal
from app.config import Status

class GeolocationCreateSchema(BaseModel):
    latitude: Decimal = Field(..., ge=-90, le=90)
    longitude: Decimal = Field(..., ge=-180, le=180)
    address_id: UUID
    is_archived: Optional[bool] = False
    # Status field removed - will be automatically set to 'Pending' by base model

class GeolocationUpdateSchema(BaseModel):
    address_id: Optional[UUID] = None
    latitude: Optional[float] = Field(
        None,
        ge=-90.0,
        le=90.0,
        description="Latitude in decimal degrees, between -90 and 90"
    )
    longitude: Optional[float] = Field(
        None,
        ge=-180.0,
        le=180.0,
        description="Longitude in decimal degrees, between -180 and 180"
    )
    is_archived: Optional[bool] = None
    status: Optional[Status] = None

class GeolocationResponseSchema(BaseModel):
    geolocation_id: UUID
    address_id: UUID
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    place_id: Optional[str] = Field(None, description="Google Place ID for deduplication")
    viewport: Optional[dict] = Field(None, description="Bounding box {low:{lat,lng},high:{lat,lng}} for map zoom")
    formatted_address_google: Optional[str] = Field(None, description="Google's formatted address")
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)
