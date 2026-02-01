from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from uuid import UUID
from typing import Optional, List
from app.config import Status

# --- For creating a new restaurant holiday ---
class RestaurantHolidayCreateSchema(BaseModel):
    restaurant_id: UUID
    country: str = Field(..., max_length=100, description="Country where this holiday applies")
    holiday_date: date
    holiday_name: Optional[str] = Field(None, max_length=100)
    is_recurring: bool = False
    recurring_month_day: Optional[str] = Field(None, max_length=10, description="MM-DD format for recurring holidays")
    status: Optional[Status] = Field(default=Status.ACTIVE, description="Status of the holiday (default: 'Active')")

    @validator('recurring_month_day')
    def validate_recurring_month_day(cls, v, values):
        if v is not None:
            # Validate MM-DD format
            try:
                month, day = v.split('-')
                month_int = int(month)
                day_int = int(day)
                if not (1 <= month_int <= 12):
                    raise ValueError("Month must be between 01 and 12")
                if not (1 <= day_int <= 31):
                    raise ValueError("Day must be between 01 and 31")
            except ValueError:
                raise ValueError("recurring_month_day must be in MM-DD format (e.g., '12-25')")
            
            # If is_recurring is True, recurring_month_day should be set
            if values.get('is_recurring') and not v:
                raise ValueError("recurring_month_day is required when is_recurring is True")
        
        return v

# --- For updating an existing restaurant holiday ---
class RestaurantHolidayUpdateSchema(BaseModel):
    restaurant_id: Optional[UUID] = None
    country: Optional[str] = Field(None, max_length=100, description="Country where this holiday applies")
    holiday_date: Optional[date] = None
    holiday_name: Optional[str] = Field(None, max_length=100)
    is_recurring: Optional[bool] = None
    recurring_month_day: Optional[str] = Field(None, max_length=10, description="MM-DD format for recurring holidays")
    status: Optional[Status] = Field(None, description="Status of the holiday")

    @validator('recurring_month_day')
    def validate_recurring_month_day(cls, v):
        if v is not None:
            # Validate MM-DD format
            try:
                month, day = v.split('-')
                month_int = int(month)
                day_int = int(day)
                if not (1 <= month_int <= 12):
                    raise ValueError("Month must be between 01 and 12")
                if not (1 <= day_int <= 31):
                    raise ValueError("Day must be between 01 and 31")
            except ValueError:
                raise ValueError("recurring_month_day must be in MM-DD format (e.g., '12-25')")
        return v

# --- For returning restaurant holiday details in API responses ---
class RestaurantHolidayResponseSchema(BaseModel):
    holiday_id: UUID
    restaurant_id: UUID
    country: str
    holiday_date: date
    holiday_name: Optional[str]
    is_recurring: bool
    recurring_month_day: Optional[str]
    status: Status
    is_archived: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

# --- For bulk creating restaurant holidays ---
class RestaurantHolidayBulkCreateSchema(BaseModel):
    """Schema for bulk creating restaurant holidays"""
    holidays: List[RestaurantHolidayCreateSchema] = Field(..., min_items=1, description="List of holidays to create")
    
    @validator('holidays')
    def validate_holidays_not_empty(cls, v):
        """Ensure at least one holiday is provided"""
        if not v:
            raise ValueError("At least one holiday must be provided")
        return v

# --- For enriched restaurant holidays (includes national holidays) ---
class RestaurantHolidayEnrichedResponseSchema(BaseModel):
    """
    Enriched restaurant holiday response that includes both restaurant-specific holidays
    and applicable national holidays.
    
    For restaurant holidays (holiday_type='restaurant'):
    - All restaurant_holidays fields are populated
    - holiday_id, restaurant_id, restaurant_name, institution_name, country, holiday_date, holiday_name, is_recurring, recurring_month_day, etc.
    - status: From database ('Active', 'Inactive', or 'Cancelled')
    - is_editable=True (suppliers can edit/delete these holidays)
    
    For national holidays (holiday_type='national'):
    - Only national holiday fields are populated: country_code, holiday_name, holiday_date, is_recurring
    - restaurant_id, restaurant_name, institution_name, holiday_id, etc. are None or empty
    - status: From database ('Active', 'Inactive', or 'Cancelled') - typically 'Active' for non-archived holidays
    - is_editable=False (national holidays are read-only, cannot be edited by suppliers)
    """
    holiday_type: str = Field(..., description="Type of holiday: 'restaurant' or 'national'")
    
    # Restaurant holiday fields (populated when holiday_type='restaurant')
    holiday_id: Optional[UUID] = None
    restaurant_id: Optional[UUID] = None
    restaurant_name: Optional[str] = Field(None, description="Name of the restaurant (only for restaurant holidays)")
    institution_name: Optional[str] = Field(None, description="Name of the institution (only for restaurant holidays)")
    country: Optional[str] = None
    recurring_month_day: Optional[str] = None
    is_archived: Optional[bool] = None
    created_date: Optional[datetime] = None
    modified_by: Optional[UUID] = None
    modified_date: Optional[datetime] = None
    
    # National holiday fields (populated when holiday_type='national')
    country_code: Optional[str] = None
    
    # Common fields (populated for both types)
    holiday_name: Optional[str] = None
    holiday_date: date
    is_recurring: bool = False
    
    # Status field (from database, not computed)
    status: Status = Field(..., description="Status of the holiday: 'Active', 'Inactive', or 'Cancelled'")
    
    # Editability flag (for client UI)
    is_editable: bool = Field(..., description="True if this holiday can be edited by suppliers (restaurant holidays), False if it's a national holiday (read-only)")
    
    class Config:
        orm_mode = True