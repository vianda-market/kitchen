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

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal
from app.config import Status, RoleType, RoleName, DiscretionaryReason

# =============================================================================
# CORE ENTITY DTOs
# =============================================================================

class UserDTO(BaseModel):
    """Pure DTO for user data - no functions, just data structure"""
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
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class InstitutionDTO(BaseModel):
    """Pure DTO for institution data"""
    institution_id: UUID
    name: str
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

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
    image_checksum: str
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class PlateDTO(BaseModel):
    """Pure DTO for plate data"""
    plate_id: UUID
    product_id: UUID
    restaurant_id: UUID
    price: Decimal
    credit: Decimal
    savings: int
    no_show_discount: int
    delivery_time_minutes: int
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class RestaurantDTO(BaseModel):
    """Pure DTO for restaurant data"""
    restaurant_id: UUID
    institution_id: UUID
    institution_entity_id: UUID
    address_id: UUID
    credit_currency_id: UUID
    name: str
    cuisine: Optional[str] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

# =============================================================================
# BILLING DTOs
# =============================================================================

class InstitutionBillDTO(BaseModel):
    """Pure DTO for institution bill data"""
    institution_bill_id: UUID
    institution_id: UUID
    institution_entity_id: UUID
    restaurant_id: UUID
    credit_currency_id: UUID
    payment_id: Optional[UUID] = None
    transaction_count: Optional[int] = None
    amount: Optional[Decimal] = None
    currency_code: Optional[str] = None
    balance_event_id: Optional[UUID] = None
    period_start: datetime
    period_end: datetime
    is_archived: bool = False
    status: Status
    resolution: str
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class ClientBillDTO(BaseModel):
    """Pure DTO for client bill data"""
    client_bill_id: UUID
    payment_id: UUID
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    credit_currency_id: UUID
    amount: Decimal
    currency_code: str
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

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

    class Config:
        orm_mode = True

# =============================================================================
# ADDRESS & LOCATION DTOs
# =============================================================================

class AddressDTO(BaseModel):
    """Pure DTO for address data"""
    address_id: UUID
    institution_id: UUID
    user_id: UUID
    employer_id: Optional[UUID] = None  # Links address to employer (nullable)
    address_type: List[str]
    is_default: bool = False
    floor: Optional[str] = None
    country: str
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
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class EmployerDTO(BaseModel):
    """Pure DTO for employer data"""
    employer_id: UUID
    name: str
    address_id: UUID
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class GeolocationDTO(BaseModel):
    """Pure DTO for geolocation data"""
    geolocation_id: UUID
    latitude: float
    longitude: float
    address_id: Optional[UUID] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

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
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

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
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

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
    pickup_time_range: str
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

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
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

# =============================================================================
# PAYMENT DTOs
# =============================================================================

class InstitutionPaymentAttemptDTO(BaseModel):
    """Pure DTO for institution payment attempt data"""
    payment_id: UUID
    institution_entity_id: UUID
    bank_account_id: UUID
    institution_bill_id: Optional[UUID] = None
    credit_currency_id: UUID
    amount: Decimal
    currency_code: str
    transaction_result: Optional[str] = None
    external_transaction_id: Optional[str] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    resolution_date: datetime

    class Config:
        orm_mode = True

class ClientPaymentAttemptDTO(BaseModel):
    """Pure DTO for client payment attempt data"""
    payment_id: UUID
    payment_method_id: UUID
    credit_currency_id: UUID
    currency_code: str
    amount: Decimal
    transaction_result: str
    external_transaction_id: Optional[str] = None
    created_date: datetime
    resolution_date: Optional[datetime] = None
    is_archived: bool = False
    status: Status

    class Config:
        orm_mode = True

# =============================================================================
# SUBSCRIPTION & PLAN DTOs
# =============================================================================

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
    image_checksum: str
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class SubscriptionDTO(BaseModel):
    """Pure DTO for subscription data"""
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    balance: Decimal
    renewal_date: datetime
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class PlanDTO(BaseModel):
    """Pure DTO for plan data"""
    plan_id: UUID
    credit_currency_id: UUID
    name: str
    credit: int
    price: Decimal
    rollover: bool
    rollover_cap: Optional[Decimal]
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

# =============================================================================
# INSTITUTION ENTITY DTOs
# =============================================================================

class InstitutionEntityDTO(BaseModel):
    """Pure DTO for institution entity data"""
    institution_entity_id: UUID
    institution_id: UUID
    address_id: UUID
    tax_id: str
    name: str
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class InstitutionBankAccountDTO(BaseModel):
    """Pure DTO for institution bank account data"""
    bank_account_id: UUID
    institution_entity_id: UUID
    address_id: UUID
    account_holder_name: str
    bank_name: str
    account_type: str
    routing_number: str
    account_number: str
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID

    class Config:
        orm_mode = True

# =============================================================================
# ADDITIONAL DTOs FOR REMAINING MODELS
# =============================================================================

# StatusDTO removed - status_info table deprecated, status stored directly on entities as enum
# TransactionTypeDTO removed - transaction_type_info table deprecated, transaction_type stored directly on transaction tables as enum

class PaymentMethodDTO(BaseModel):
    """Pure DTO for payment method data"""
    payment_method_id: UUID
    user_id: UUID
    method_type: str = Field(..., max_length=20)
    method_type_id: Optional[UUID] = None
    address_id: Optional[UUID] = None
    is_archived: bool
    status: Status = Field(..., max_length=20)
    is_default: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

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
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class FintechLinkDTO(BaseModel):
    """Pure DTO for fintech link data"""
    fintech_link_id: UUID
    plan_id: UUID
    provider: str
    fintech_link: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True
class FintechLinkAssignmentDTO(BaseModel):
    """Pure DTO for fintech link assignment data"""
    fintech_link_assignment_id: UUID
    payment_method_id: UUID
    fintech_link_id: UUID
    is_archived: bool
    status: Status
    created_date: datetime

    class Config:
        orm_mode = True

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
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

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
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

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
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class PlateKitchenDaysDTO(BaseModel):
    """Pure DTO for plate kitchen days data"""
    plate_kitchen_day_id: UUID
    plate_id: UUID
    kitchen_day: str = Field(..., max_length=20)
    status: Status
    is_archived: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

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
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

# =============================================================================
# DISCRETIONARY CREDIT DTOs
# =============================================================================

class DiscretionaryDTO(BaseModel):
    """Pure DTO for discretionary credit request data"""
    discretionary_id: UUID
    user_id: Optional[UUID] = None  # NULL for Supplier requests, required for Client requests
    restaurant_id: Optional[UUID] = None  # NULL for Client requests, required for Supplier requests
    approval_id: Optional[UUID] = None
    category: str = Field(..., max_length=50)
    reason: DiscretionaryReason
    amount: Decimal = Field(..., gt=0)
    comment: Optional[str] = None
    is_archived: bool = False
    status: Status = Field(..., max_length=20)  # 'Pending', 'Approved', 'Rejected'
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

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

    class Config:
        orm_mode = True

