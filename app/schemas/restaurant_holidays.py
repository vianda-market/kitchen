from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import Status
from app.i18n.envelope import I18nValueError


# --- For creating a new restaurant holiday ---
class RestaurantHolidayCreateSchema(BaseModel):
    restaurant_id: UUID
    holiday_date: date
    holiday_name: str = Field(..., max_length=100, description="Display name (e.g. Closed)")
    is_recurring: bool = False
    recurring_month: int | None = Field(None, ge=1, le=12)
    recurring_day: int | None = Field(None, ge=1, le=31)
    status: Status | None = Field(
        default=None, description="Optional; omit or null and backend assigns default (Active)"
    )

    @model_validator(mode="after")
    def validate_recurring_complete(self):
        if self.is_recurring and (self.recurring_month is None or self.recurring_day is None):
            raise I18nValueError("validation.holiday.recurring_fields_required")
        return self


# --- For updating an existing restaurant holiday ---
class RestaurantHolidayUpdateSchema(BaseModel):
    restaurant_id: UUID | None = None
    holiday_date: date | None = None
    holiday_name: str | None = Field(None, max_length=100)
    is_recurring: bool | None = None
    recurring_month: int | None = Field(None, ge=1, le=12)
    recurring_day: int | None = Field(None, ge=1, le=31)
    status: Status | None = Field(None, description="Status of the holiday")

    @model_validator(mode="after")
    def validate_recurring_complete(self):
        if self.is_recurring is True and (self.recurring_month is None or self.recurring_day is None):
            raise I18nValueError("validation.holiday.recurring_fields_required")
        return self


# --- For returning restaurant holiday details in API responses ---
class RestaurantHolidayResponseSchema(BaseModel):
    holiday_id: UUID
    restaurant_id: UUID
    country_code: str
    holiday_date: date
    holiday_name: str
    is_recurring: bool
    recurring_month: int | None
    recurring_day: int | None
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

    holidays: list[RestaurantHolidayCreateSchema] = Field(..., min_length=1, description="List of holidays to create")

    @field_validator("holidays")
    @classmethod
    def validate_holidays_not_empty(cls, v):
        if not v:
            raise I18nValueError("validation.holiday.list_empty")
        return v


# --- For enriched restaurant holidays (includes national holidays) ---
class RestaurantHolidayEnrichedResponseSchema(BaseModel):
    """
    Enriched response: restaurant-specific rows and applicable national holidays.

    Restaurant rows: country_code, recurring_month/day, source from restaurant_holidays.
    National rows: country_code, source, recurring fields from national_holidays when present.
    """

    holiday_type: str = Field(..., description="Type of holiday: 'restaurant' or 'national'")

    holiday_id: UUID | None = None
    restaurant_id: UUID | None = None
    restaurant_name: str | None = None
    institution_name: str | None = None
    country_code: str | None = None
    recurring_month: int | None = None
    recurring_day: int | None = None
    source: str | None = None
    is_archived: bool | None = None
    created_date: datetime | None = None
    modified_by: UUID | None = None
    modified_date: datetime | None = None

    holiday_name: str | None = None
    holiday_date: date
    is_recurring: bool = False

    status: Status = Field(..., description="Status from database")
    is_editable: bool = Field(
        ...,
        description="True for restaurant holidays; False for national (read-only for suppliers)",
    )

    model_config = ConfigDict(from_attributes=True)
