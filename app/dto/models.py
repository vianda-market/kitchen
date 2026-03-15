# app/dto/models.py
"""
Data Transfer Objects (DTOs) - Pure data structures with no functions.

This file contains all DTOs for the application, following the Clean Code principle
of separating data structures from behavior. DTOs are used for data transfer
between layers of the application.

Benefits:
- Pure data structures (no functions, no business logic)
- Clear separation of concerns
- Easier validation and serialization
- Better testability
- Reduced code duplication
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal
from app.config import Status, RoleType, RoleName, DiscretionaryReason

# =============================================================================
# CORE ENTITY DTOs
# =============================================================================

class UserDTO(BaseModel):
    """Pure DTO for user data - no functions, just data structure. market_id is required (v1: one market per user)."""
    user_id: UUID
    institution_id: UUID
    role_type: RoleType
    role_name: RoleName
    username: str
    hashed_password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    cellphone: Optional[str] = None
    employer_id: Optional[UUID] = None
    employer_address_id: Optional[UUID] = None
    market_id: UUID
    city_id: Optional[UUID] = None
    stripe_customer_id: Optional[str] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class InstitutionDTO(BaseModel):
    """Pure DTO for institution data"""
    institution_id: UUID
    name: str
    institution_type: RoleType  # Employee, Customer, Supplier, or Employer (Employer = benefits-program institution; users have role_type Customer)
    market_id: Optional[UUID] = None  # v1: NULL or Global = all markets; one UUID = local market
    no_show_discount: Optional[int] = None  # Percentage 0-100; required for Supplier, NULL for Employee/Customer
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

# RoleDTO removed - role_info table deprecated, roles stored directly on user_info as enums

class ProductDTO(BaseModel):
    """Pure DTO for product data"""
    product_id: UUID
    institution_id: UUID
    name: str
    ingredients: Optional[str] = None
    dietary: Optional[str] = None
    is_archived: bool = False
    status: Status
    image_url: str
    image_storage_path: str
    image_thumbnail_url: str
    image_thumbnail_storage_path: str
    image_checksum: str
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class PlateDTO(BaseModel):
    """Pure DTO for plate data. Savings are computed on the fly (e.g. explore by-city) from price, credit, and user plan credit_worth. no_show_discount comes from institution."""
    plate_id: UUID
    product_id: UUID
    restaurant_id: UUID
    price: Decimal
    credit: Decimal
    delivery_time_minutes: int
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class PlateReviewDTO(BaseModel):
    """Pure DTO for plate review data. One review per pickup; immutable after creation."""
    plate_review_id: UUID
    user_id: UUID
    plate_id: UUID
    plate_pickup_id: UUID
    stars_rating: int
    portion_size_rating: int
    is_archived: bool = False
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class UserFavoriteDTO(BaseModel):
    """Pure DTO for user favorite data. Polymorphic: entity_type is 'plate' or 'restaurant'; entity_id is plate_id or restaurant_id."""
    favorite_id: UUID
    user_id: UUID
    entity_type: str  # 'plate' | 'restaurant'
    entity_id: UUID
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


class RestaurantDTO(BaseModel):
    """Pure DTO for restaurant data. credit_currency comes from institution_entity."""
    restaurant_id: UUID
    institution_id: UUID
    institution_entity_id: UUID
    address_id: UUID
    name: str
    cuisine: Optional[str] = None
    pickup_instructions: Optional[str] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

# =============================================================================
# BILLING DTOs
# =============================================================================

class InstitutionBillDTO(BaseModel):
    """Pure DTO for institution bill data. One per entity per period (aggregates settlements). Restaurants per bill via institution_settlement."""
    institution_bill_id: UUID
    institution_id: UUID
    institution_entity_id: UUID
    credit_currency_id: UUID
    transaction_count: Optional[int] = None
    amount: Optional[Decimal] = None
    currency_code: Optional[str] = None
    period_start: datetime
    period_end: datetime
    is_archived: bool = False
    status: Status
    resolution: str
    tax_doc_external_id: Optional[str] = None
    stripe_payout_id: Optional[str] = None
    payout_completed_at: Optional[datetime] = None
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionSettlementDTO(BaseModel):
    """Pure DTO for institution settlement. One per restaurant per period (only when balance > 0)."""
    settlement_id: UUID
    institution_entity_id: UUID
    restaurant_id: UUID
    period_start: datetime
    period_end: datetime
    kitchen_day: str
    amount: Decimal
    currency_code: str
    credit_currency_id: UUID
    transaction_count: int
    balance_event_id: Optional[UUID] = None
    settlement_number: str
    settlement_run_id: Optional[UUID] = None
    institution_bill_id: Optional[UUID] = None
    country_code: str
    status: Status
    is_archived: bool = False
    created_at: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class ClientBillDTO(BaseModel):
    """Pure DTO for client bill data. Bills are created from subscription_payment (atomic flow)."""
    client_bill_id: UUID
    subscription_payment_id: UUID
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    credit_currency_id: UUID
    amount: Decimal
    currency_code: str
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class CreditCurrencyDTO(BaseModel):
    """Pure DTO for credit currency data"""
    credit_currency_id: UUID
    currency_name: str
    currency_code: str
    credit_value: Decimal
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

# =============================================================================
# ADDRESS & LOCATION DTOs
# =============================================================================

class AddressDTO(BaseModel):
    """Pure DTO for address data. user_id nullable (Supplier/Employee/Employer); floor, apartment_unit, is_default from address_subpremise."""
    address_id: UUID
    institution_id: UUID
    user_id: Optional[UUID] = None  # Required only for Customer Comensal home/other; nullable for Supplier, Employee, Employer
    employer_id: Optional[UUID] = None  # Links address to employer (nullable)
    address_type: List[str]
    is_default: bool = False
    floor: Optional[str] = None
    country_name: str
    country_code: str
    province: str
    city: str
    postal_code: str
    street_type: str
    street_name: str
    building_number: str
    apartment_unit: Optional[str] = None
    timezone: str
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class AddressSubpremiseDTO(BaseModel):
    """Pure DTO for address_subpremise (floor, unit, is_default per user at an address)."""
    subpremise_id: UUID
    address_id: UUID
    user_id: UUID
    floor: Optional[str] = None
    apartment_unit: Optional[str] = None
    is_default: bool = False
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class EmployerDTO(BaseModel):
    """Pure DTO for employer data"""
    employer_id: UUID
    name: str
    address_id: UUID
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class CityDTO(BaseModel):
    """Pure DTO for city data (supported cities for user onboarding and address scoping)."""
    city_id: UUID
    name: str
    country_code: str
    province_code: Optional[str] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class GeolocationDTO(BaseModel):
    """Pure DTO for geolocation data"""
    geolocation_id: UUID
    latitude: float
    longitude: float
    address_id: Optional[UUID] = None
    place_id: Optional[str] = None
    viewport: Optional[dict] = None
    formatted_address_google: Optional[str] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

# =============================================================================
# TRANSACTION DTOs
# =============================================================================

class RestaurantTransactionDTO(BaseModel):
    """Pure DTO for restaurant transaction data"""
    transaction_id: UUID
    restaurant_id: UUID
    plate_selection_id: Optional[UUID] = None
    discretionary_id: Optional[UUID] = None
    credit_currency_id: UUID
    was_collected: bool = False
    ordered_timestamp: datetime
    collected_timestamp: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    expected_completion_time: Optional[datetime] = None
    transaction_type: str
    credit: Decimal
    no_show_discount: Optional[Decimal] = None
    currency_code: Optional[str] = None
    final_amount: Decimal
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class ClientTransactionDTO(BaseModel):
    """Pure DTO for client transaction data"""
    transaction_id: UUID
    user_id: UUID
    source: str
    plate_selection_id: Optional[UUID] = None
    discretionary_id: Optional[UUID] = None
    credit: int
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

# =============================================================================
# PLATE SELECTION & PICKUP DTOs
# =============================================================================

class PlateSelectionDTO(BaseModel):
    """Pure DTO for plate selection data"""
    plate_selection_id: UUID
    user_id: UUID
    plate_id: UUID
    restaurant_id: UUID
    product_id: UUID
    qr_code_id: UUID
    credit: int
    kitchen_day: str
    pickup_date: date
    pickup_time_range: str
    pickup_intent: str = "self"
    flexible_on_time: Optional[bool] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class PickupPreferencesDTO(BaseModel):
    """Pure DTO for pickup preferences data"""
    preference_id: UUID
    plate_selection_id: UUID
    user_id: UUID
    pickup_type: str
    target_pickup_time: Optional[datetime] = None
    time_window_minutes: int = 30
    is_matched: bool = False
    matched_with_preference_id: Optional[UUID] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class MessagingPreferencesDTO(BaseModel):
    """Pure DTO for user messaging preferences"""
    user_id: UUID
    notify_coworker_pickup_alert: bool = True
    notify_plate_readiness_alert: bool = True
    notify_promotions_push: bool = True
    notify_promotions_email: bool = True
    coworkers_can_see_my_orders: bool = True
    can_participate_in_plate_pickups: bool = True
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# SUBSCRIPTION & PLAN DTOs
# =============================================================================

class SubscriptionDTO(BaseModel):
    """Pure DTO for subscription data"""
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    market_id: UUID  # Market (country) this subscription belongs to
    balance: Decimal
    renewal_date: datetime
    is_archived: bool = False
    status: Status  # General status (Active/Inactive)
    subscription_status: Optional[str] = None  # Specific subscription status (Active/On Hold/Pending/Cancelled)
    hold_start_date: Optional[datetime] = None  # When subscription was put on hold
    hold_end_date: Optional[datetime] = None  # When subscription is expected to resume
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class PlanDTO(BaseModel):
    """Pure DTO for plan data"""
    plan_id: UUID
    market_id: UUID  # Market (country) this plan belongs to
    name: str
    credit: int
    price: Decimal
    credit_worth: Decimal  # price / credit (local currency per credit), set by DB trigger
    rollover: bool
    rollover_cap: Optional[Decimal]
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

# =============================================================================
# INSTITUTION ENTITY DTOs
# =============================================================================

class InstitutionEntityDTO(BaseModel):
    """Pure DTO for institution entity data. credit_currency_id from market for entity address country."""
    institution_entity_id: UUID
    institution_id: UUID
    address_id: UUID
    credit_currency_id: UUID
    tax_id: str
    name: str
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

# =============================================================================
# ADDITIONAL DTOs FOR REMAINING MODELS
# =============================================================================

# StatusDTO removed - status_info table deprecated, status stored directly on entities as enum
# TransactionTypeDTO removed - transaction_type_info table deprecated, transaction_type stored directly on transaction tables as enum

class PaymentMethodDTO(BaseModel):
    """Pure DTO for payment method data. method_type is provider name (Stripe, Mercado Pago, PayU)."""
    payment_method_id: UUID
    user_id: UUID
    method_type: str = Field(..., max_length=50)
    method_type_id: Optional[UUID] = None
    address_id: Optional[UUID] = None
    is_archived: bool
    status: Status = Field(..., max_length=20)
    is_default: bool
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ExternalPaymentMethodDTO(BaseModel):
    """Pure DTO for external (aggregator) payment method link."""
    external_payment_method_id: UUID
    payment_method_id: UUID
    provider: str
    external_id: str
    last4: Optional[str] = None
    brand: Optional[str] = None
    provider_customer_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class QRCodeDTO(BaseModel):
    """Pure DTO for QR code data"""
    qr_code_id: UUID
    restaurant_id: UUID
    qr_code_payload: str = Field(..., max_length=255)
    qr_code_image_url: str = Field(..., max_length=500)
    image_storage_path: str = Field(..., max_length=500)
    qr_code_checksum: Optional[str] = None
    is_archived: bool
    status: Status = Field(..., max_length=20)
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class RestaurantBalanceDTO(BaseModel):
    """Pure DTO for restaurant balance data"""
    restaurant_id: UUID
    credit_currency_id: UUID
    transaction_count: int = Field(..., ge=0)
    balance: Decimal = Field(..., ge=0)
    currency_code: str = Field(..., max_length=10)
    is_archived: bool = False
    status: Status = Field(..., max_length=20)
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class RestaurantHolidaysDTO(BaseModel):
    """Pure DTO for restaurant holidays data"""
    holiday_id: UUID
    restaurant_id: UUID
    country: str = Field(..., max_length=100)
    holiday_date: date
    holiday_name: Optional[str] = Field(None, max_length=100)
    is_recurring: bool = False
    recurring_month_day: Optional[str] = Field(None, max_length=10)
    status: Status
    is_archived: bool
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class NationalHolidayDTO(BaseModel):
    """Pure DTO for national holiday data"""
    holiday_id: UUID
    country_code: str = Field(..., max_length=3)
    holiday_name: str = Field(..., max_length=100)
    holiday_date: date
    is_recurring: bool = False
    recurring_month: Optional[int] = Field(None, ge=1, le=12)
    recurring_day: Optional[int] = Field(None, ge=1, le=31)
    status: Status = Field(default="Active", description="Status of the holiday (defaults to 'Active' if not set)")
    is_archived: bool = False
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class PlateKitchenDaysDTO(BaseModel):
    """Pure DTO for plate kitchen days data"""
    plate_kitchen_day_id: UUID
    plate_id: UUID
    kitchen_day: str = Field(..., max_length=20)
    status: Status
    is_archived: bool
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class PlatePickupLiveDTO(BaseModel):
    """Pure DTO for plate pickup live data"""
    plate_pickup_id: UUID
    plate_selection_id: UUID
    user_id: UUID
    restaurant_id: UUID
    plate_id: UUID
    product_id: UUID
    qr_code_id: UUID
    qr_code_payload: str = Field(..., max_length=255)
    is_archived: bool
    status: Status = Field(..., max_length=20)
    was_collected: Optional[bool] = None
    arrival_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    expected_completion_time: Optional[datetime] = None
    confirmation_code: Optional[str] = None
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

# =============================================================================
# DISCRETIONARY CREDIT DTOs
# =============================================================================

class DiscretionaryDTO(BaseModel):
    """Pure DTO for discretionary credit request data"""
    discretionary_id: UUID
    user_id: Optional[UUID] = None  # NULL for Supplier requests, required for Client requests
    restaurant_id: Optional[UUID] = None  # NULL for Client requests, required for Supplier requests
    approval_id: Optional[UUID] = None
    category: DiscretionaryReason  # Classification enum (Marketing Campaign, Credit Refund, etc.)
    reason: Optional[str] = None  # Free-form explanation
    amount: Decimal = Field(..., gt=0)
    comment: Optional[str] = None
    is_archived: bool = False
    status: str = Field(..., max_length=20)  # DiscretionaryStatus: Pending, Cancelled, Approved, Rejected
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class DiscretionaryResolutionDTO(BaseModel):
    """Pure DTO for discretionary resolution data"""
    approval_id: UUID
    discretionary_id: UUID
    resolution: str = Field(..., max_length=20)  # 'Approved', 'Rejected'
    is_archived: bool = False
    status: Status = Field(..., max_length=20)
    resolved_by: UUID
    resolved_date: datetime
    created_date: datetime
    resolution_comment: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

