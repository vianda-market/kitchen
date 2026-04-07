from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from datetime import datetime, date
from uuid import UUID
from typing import Optional, List
from app.config import Status

# --- For creating a new restaurant holiday ---
class RestaurantHolidayCreateSchema(BaseModel):
    restaurant_id: UUID
    holiday_date: date
    holiday_name: str = Field(..., max_length=100, description="Display name (e.g. Closed)")
    is_recurring: bool = False
    recurring_month: Optional[int] = Field(None, ge=1, le=12)
    recurring_day: Optional[int] = Field(None, ge=1, le=31)
    status: Optional[Status] = Field(default=None, description="Optional; omit or null and backend assigns default (Active)")

    @model_validator(mode="after")
    def validate_recurring_complete(self):
        if self.is_recurring and (
            self.recurring_month is None or self.recurring_day is None
        ):
            raise ValueError(
                "Both recurring_month and recurring_day are required when is_recurring is True"
            )
        return self


# --- For updating an existing restaurant holiday ---
class RestaurantHolidayUpdateSchema(BaseModel):
    restaurant_id: Optional[UUID] = None
    holiday_date: Optional[date] = None
    holiday_name: Optional[str] = Field(None, max_length=100)
    is_recurring: Optional[bool] = None
    recurring_month: Optional[int] = Field(None, ge=1, le=12)
    recurring_day: Optional[int] = Field(None, ge=1, le=31)
    status: Optional[Status] = Field(None, description="Status of the holiday")

    @model_validator(mode="after")
    def validate_recurring_complete(self):
        if self.is_recurring is True and (
            self.recurring_month is None or self.recurring_day is None
        ):
            raise ValueError(
                "Both recurring_month and recurring_day are required when is_recurring is True"
            )
        return self


# --- For returning restaurant holiday details in API responses ---
class RestaurantHolidayResponseSchema(BaseModel):
    holiday_id: UUID
    restaurant_id: UUID
    country_code: str
    holiday_date: date
    holiday_name: str
    is_recurring: bool
    recurring_month: Optional[int]
    recurring_day: Optional[int]
    status: Status
    is_archived: bool
    source: str = Field(..., description="'manual' | 'national_sync'")
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


# --- For bulk creating restaurant holidays ---
class RestaurantHolidayBulkCreateSchema(BaseModel):
    """Schema for bulk creating restaurant holidays"""
    holidays: List[RestaurantHolidayCreateSchema] = Field(
        ..., min_length=1, description="List of holidays to create"
    )

    @field_validator("holidays")
    @classmethod
    def validate_holidays_not_empty(cls, v):
        if not v:
            raise ValueError("At least one holiday must be provided")
        return v


# --- For enriched restaurant holidays (includes national holidays) ---
class RestaurantHolidayEnrichedResponseSchema(BaseModel):
    """
    Enriched response: restaurant-specific rows and applicable national holidays.

    Restaurant rows: country_code, recurring_month/day, source from restaurant_holidays.
    National rows: country_code, source, recurring fields from national_holidays when present.
    """

    holiday_type: str = Field(..., description="Type of holiday: 'restaurant' or 'national'")

    holiday_id: Optional[UUID] = None
    restaurant_id: Optional[UUID] = None
    restaurant_name: Optional[str] = None
    institution_name: Optional[str] = None
    country_code: Optional[str] = None
    recurring_month: Optional[int] = None
    recurring_day: Optional[int] = None
    source: Optional[str] = None
    is_archived: Optional[bool] = None
    created_date: Optional[datetime] = None
    modified_by: Optional[UUID] = None
    modified_date: Optional[datetime] = None

    holiday_name: Optional[str] = None
    holiday_date: date
    is_recurring: bool = False

    status: Status = Field(..., description="Status from database")
    is_editable: bool = Field(
        ...,
        description="True for restaurant holidays; False for national (read-only for suppliers)",
    )

    model_config = ConfigDict(from_attributes=True)
