# app/schemas/consolidated_schemas.py
"""
Consolidated Pydantic Schemas

This module consolidates all Pydantic schemas by category/usecase to reduce
the number of small files and improve maintainability.

Categories:
1. Core Entities (User, Institution, Role)
2. Restaurant & Food (Restaurant, Product, Plate, QR Code)
3. Billing & Payments (Credit Currency, Bills, Payment Methods, Transactions)
4. Location & Address (Address, Geolocation, Employer)
5. Subscriptions & Plans (Plan, Subscription, Fintech Links)
6. Plate Selection & Pickup (Plate Selection, Pickup Preferences, Live Pickup)
7. Admin & Discretionary (Discretionary Requests, Resolutions)

Benefits:
- Reduced file count (25+ files → 7 files)
- Logical grouping by business domain
- Easier maintenance and navigation
- Better code organization
- Reduced import complexity
"""

from pydantic import BaseModel, Field, EmailStr, validator, root_validator
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal
from app.config import Status, RoleType, RoleName, TransactionType, KitchenDay, PickupType, AuditOperation, DiscretionaryReason

# =============================================================================
# 1. CORE ENTITIES SCHEMAS
# =============================================================================

class UserCreateSchema(BaseModel):
    """Schema for creating a new user"""
    institution_id: UUID
    role_type: RoleType
    role_name: RoleName
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    cellphone: str = Field(..., max_length=20)
    employer_id: Optional[UUID] = None
    
    @validator('role_name')
    def validate_role_combination(cls, v, values):
        """Validate that role_type and role_name combination is valid"""
        role_type = values.get('role_type')
        if not role_type:
            return v
        
        valid_combinations = {
            RoleType.EMPLOYEE: [RoleName.ADMIN, RoleName.SUPER_ADMIN, RoleName.MANAGEMENT, RoleName.OPERATOR],
            RoleType.SUPPLIER: [RoleName.ADMIN, RoleName.MANAGEMENT, RoleName.OPERATOR],
            RoleType.CUSTOMER: [RoleName.COMENSAL],
        }
        
        if v not in valid_combinations.get(role_type, []):
            raise ValueError(
                f"Invalid role combination: {role_type.value} + {v.value}. "
                f"Valid combinations: {[rn.value for rn in valid_combinations.get(role_type, [])]}"
            )
        return v

class UserUpdateSchema(BaseModel):
    """Schema for updating user information"""
    institution_id: Optional[UUID] = None
    role_type: Optional[RoleType] = None
    role_name: Optional[RoleName] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    cellphone: Optional[str] = Field(None, max_length=20)
    employer_id: Optional[UUID] = None
    
    @validator('role_name')
    def validate_role_combination(cls, v, values):
        """Validate that role_type and role_name combination is valid"""
        role_type = values.get('role_type')
        if not role_type or not v:
            return v
        
        valid_combinations = {
            RoleType.EMPLOYEE: [RoleName.ADMIN, RoleName.SUPER_ADMIN, RoleName.MANAGEMENT, RoleName.OPERATOR],
            RoleType.SUPPLIER: [RoleName.ADMIN, RoleName.MANAGEMENT, RoleName.OPERATOR],
            RoleType.CUSTOMER: [RoleName.COMENSAL],
        }
        
        if v not in valid_combinations.get(role_type, []):
            raise ValueError(
                f"Invalid role combination: {role_type.value} + {v.value}. "
                f"Valid combinations: {[rn.value for rn in valid_combinations.get(role_type, [])]}"
            )
        return v

class UserResponseSchema(BaseModel):
    """Schema for user response data"""
    user_id: UUID
    institution_id: UUID
    role_type: RoleType
    role_name: RoleName
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    cellphone: str
    employer_id: Optional[UUID]
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class UserEnrichedResponseSchema(BaseModel):
    """Schema for enriched user response data with role and institution names"""
    user_id: UUID
    institution_id: UUID
    institution_name: str
    role_type: RoleType
    role_name: RoleName
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    cellphone: str
    employer_id: Optional[UUID]
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class CustomerSignupSchema(BaseModel):
    """Schema for customer signup without institution_id nor role_id"""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=255)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    email: EmailStr
    cellphone: str = Field(..., max_length=20)
    is_archived: Optional[bool] = False
    status: Optional[Status] = Field(default=Status.ACTIVE)

class InstitutionCreateSchema(BaseModel):
    """Schema for creating a new institution"""
    name: str = Field(..., max_length=100)

class InstitutionUpdateSchema(BaseModel):
    """Schema for updating institution information"""
    name: Optional[str] = Field(None, max_length=100)

class InstitutionResponseSchema(BaseModel):
    """Schema for institution response data"""
    institution_id: UUID
    name: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

# RoleCreateSchema, RoleUpdateSchema, RoleResponseSchema removed
# role_info table removed - roles are now stored directly on user_info as enums

# =============================================================================
# 2. RESTAURANT & FOOD SCHEMAS
# =============================================================================

class RestaurantCreateSchema(BaseModel):
    """Schema for creating a new restaurant"""
    institution_id: UUID
    institution_entity_id: UUID
    address_id: UUID
    credit_currency_id: UUID
    name: str = Field(..., max_length=100)
    cuisine: Optional[str] = Field(None, max_length=50)

class RestaurantUpdateSchema(BaseModel):
    """Schema for updating restaurant information"""
    institution_id: Optional[UUID] = None
    institution_entity_id: Optional[UUID] = None
    address_id: Optional[UUID] = None
    credit_currency_id: Optional[UUID] = None
    name: Optional[str] = Field(None, max_length=100)
    cuisine: Optional[str] = Field(None, max_length=50)

class RestaurantResponseSchema(BaseModel):
    """Schema for restaurant response data"""
    restaurant_id: UUID
    institution_id: UUID
    institution_entity_id: UUID
    address_id: UUID
    credit_currency_id: UUID
    name: str
    cuisine: Optional[str]
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

PLACEHOLDER_IMAGE_URL = "http://localhost:8000/static/placeholders/product_default.png"
PLACEHOLDER_IMAGE_PATH = "static/placeholders/product_default.png"
PLACEHOLDER_IMAGE_CHECKSUM = "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c"


class ProductCreateSchema(BaseModel):
    """Schema for creating a new product"""
    institution_id: UUID
    name: str = Field(..., max_length=100)
    ingredients: Optional[str] = Field(None, max_length=255)
    dietary: Optional[str] = Field(None, max_length=255)
    image_url: str = Field(default=PLACEHOLDER_IMAGE_URL, max_length=500)
    image_storage_path: str = Field(default=PLACEHOLDER_IMAGE_PATH, max_length=500)
    image_checksum: str = Field(default=PLACEHOLDER_IMAGE_CHECKSUM, max_length=128)

class ProductUpdateSchema(BaseModel):
    """Schema for updating product information"""
    institution_id: Optional[UUID] = None
    name: Optional[str] = Field(None, max_length=100)
    ingredients: Optional[str] = Field(None, max_length=255)
    dietary: Optional[str] = Field(None, max_length=255)
    image_url: Optional[str] = Field(None, max_length=500)
    image_storage_path: Optional[str] = Field(None, max_length=500)
    image_checksum: Optional[str] = Field(None, max_length=128)

class ProductResponseSchema(BaseModel):
    """Schema for product response data"""
    product_id: UUID
    institution_id: UUID
    name: str
    ingredients: Optional[str]
    dietary: Optional[str]
    image_url: Optional[str]
    image_storage_path: str
    image_checksum: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class ProductEnrichedResponseSchema(BaseModel):
    """Schema for enriched product response data with institution name"""
    product_id: UUID
    institution_id: UUID
    institution_name: str
    name: str
    ingredients: Optional[str]
    dietary: Optional[str]
    image_url: Optional[str]
    image_storage_path: str
    image_checksum: str
    has_image: bool  # Flag indicating if product has a custom uploaded image (TRUE) or default placeholder (FALSE)
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class PlateCreateSchema(BaseModel):
    """Schema for creating a new plate"""
    product_id: UUID
    restaurant_id: UUID
    price: Decimal = Field(..., ge=0)
    credit: int = Field(..., gt=0)
    savings: int = Field(..., ge=0)
    no_show_discount: int = Field(..., ge=0)
    delivery_time_minutes: int = Field(default=15, gt=0)

class PlateUpdateSchema(BaseModel):
    """Schema for updating plate information"""
    product_id: Optional[UUID] = None
    restaurant_id: Optional[UUID] = None
    price: Optional[Decimal] = Field(None, ge=0)
    credit: Optional[int] = Field(None, gt=0)
    savings: Optional[int] = Field(None, ge=0)
    no_show_discount: Optional[int] = Field(None, ge=0)
    delivery_time_minutes: Optional[int] = Field(None, gt=0)

class PlateResponseSchema(BaseModel):
    """Schema for plate response data"""
    plate_id: UUID
    product_id: UUID
    restaurant_id: UUID
    price: Decimal
    credit: int
    savings: int
    no_show_discount: int
    delivery_time_minutes: int
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class PlateEnrichedResponseSchema(BaseModel):
    """Schema for enriched plate response data with institution, restaurant, product, and address details"""
    plate_id: UUID
    product_id: UUID
    restaurant_id: UUID
    institution_name: str
    restaurant_name: str
    cuisine: Optional[str]
    country: str
    province: str
    city: str
    product_name: str
    dietary: Optional[str]
    product_image_url: Optional[str]  # Product image URL for display
    product_image_storage_path: str  # Product image storage path
    has_image: bool  # Flag indicating if product has a custom uploaded image (TRUE) or default placeholder (FALSE)
    price: Decimal
    credit: int
    savings: int
    no_show_discount: int
    delivery_time_minutes: int
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class PlateKitchenDayCreateSchema(BaseModel):
    """Schema for creating plate kitchen day assignments (supports single or multiple days)"""
    plate_id: UUID
    kitchen_days: List[KitchenDay] = Field(..., description="List of days of the week: Monday, Tuesday, Wednesday, Thursday, or Friday")
    status: Optional[Status] = Field(default=Status.ACTIVE, description="Status of the kitchen day assignment (default: 'Active')")
    
    @validator('kitchen_days')
    def validate_kitchen_days(cls, v):
        """Validate that all kitchen_days are valid weekdays"""
        if not v:
            raise ValueError("kitchen_days cannot be empty")
        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("kitchen_days cannot contain duplicate days")
        return v
    
    class Config:
        orm_mode = True

class PlateKitchenDayUpdateSchema(BaseModel):
    """Schema for updating plate kitchen day assignment"""
    plate_id: Optional[UUID] = None
    kitchen_day: Optional[KitchenDay] = Field(None, description="Day of the week: Monday, Tuesday, Wednesday, Thursday, or Friday")
    status: Optional[Status] = Field(None, description="Status of the kitchen day assignment")
    is_archived: Optional[bool] = None
    
    class Config:
        orm_mode = True

class PlateKitchenDayResponseSchema(BaseModel):
    """Schema for plate kitchen day response data"""
    plate_kitchen_day_id: UUID
    plate_id: UUID
    kitchen_day: KitchenDay
    status: Status
    is_archived: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class PlateKitchenDayEnrichedResponseSchema(BaseModel):
    """Schema for enriched plate kitchen day response data with institution, restaurant, plate, and product details"""
    plate_kitchen_day_id: UUID
    plate_id: UUID
    kitchen_day: KitchenDay
    status: Status
    institution_name: str
    restaurant_name: str
    plate_name: str  # Actually from product_info.name
    dietary: Optional[str]  # From product_info.dietary
    is_archived: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class QRCodeCreateSchema(BaseModel):
    """Schema for creating a new QR code - only restaurant_id needed"""
    restaurant_id: UUID
    # qr_code_payload, qr_code_image_url and image_storage_path will be auto-generated

class QRCodeUpdateSchema(BaseModel):
    """Schema for updating QR code information"""
    restaurant_id: Optional[UUID] = None
    status: Optional[Status] = None

class QRCodeResponseSchema(BaseModel):
    """Schema for QR code response data"""
    qr_code_id: UUID
    restaurant_id: UUID
    qr_code_payload: str
    qr_code_image_url: str
    image_storage_path: str
    qr_code_checksum: Optional[str] = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

# =============================================================================
# 3. BILLING & PAYMENTS SCHEMAS
# =============================================================================

class CreditCurrencyCreateSchema(BaseModel):
    """Schema for creating a new credit currency"""
    currency_name: str = Field(..., max_length=20)
    currency_code: str = Field(..., max_length=10)
    credit_value: Decimal = Field(..., gt=0)

class CreditCurrencyUpdateSchema(BaseModel):
    """Schema for updating credit currency information"""
    currency_name: Optional[str] = Field(None, max_length=20)
    currency_code: Optional[str] = Field(None, max_length=10)
    credit_value: Optional[Decimal] = Field(None, gt=0)

class CreditCurrencyResponseSchema(BaseModel):
    """Schema for credit currency response data"""
    credit_currency_id: UUID
    currency_name: str
    currency_code: str
    credit_value: Decimal
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class PlanCreateSchema(BaseModel):
    """Schema for creating a new plan"""
    credit_currency_id: UUID
    name: str = Field(..., max_length=100)
    credit: int = Field(..., gt=0)
    price: float = Field(..., ge=0)
    rollover: Optional[bool] = True
    rollover_cap: Optional[Decimal] = None

class PlanUpdateSchema(BaseModel):
    """Schema for updating plan information"""
    credit_currency_id: Optional[UUID] = None
    name: Optional[str] = Field(None, max_length=100)
    credit: Optional[int] = Field(None, gt=0)
    price: Optional[float] = Field(None, ge=0)
    rollover: Optional[bool] = None
    rollover_cap: Optional[Decimal] = None
    status: Optional[Status] = None

class PlanResponseSchema(BaseModel):
    """Schema for plan response data"""
    plan_id: UUID
    credit_currency_id: UUID
    name: str
    credit: int
    price: float
    status: Status
    rollover: bool
    rollover_cap: Optional[Decimal]
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class PlanEnrichedResponseSchema(BaseModel):
    """Schema for enriched plan response data with currency name and code"""
    plan_id: UUID
    credit_currency_id: UUID
    currency_name: str
    currency_code: str
    name: str
    credit: int
    price: float
    rollover: bool
    rollover_cap: Optional[Decimal]
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class SubscriptionEnrichedResponseSchema(BaseModel):
    """Schema for enriched subscription response data with user and plan information"""
    subscription_id: UUID
    user_id: UUID
    user_full_name: str
    user_username: str
    user_email: str
    user_status: Status
    user_cellphone: str
    plan_id: UUID
    plan_name: str
    plan_credit: int
    plan_price: float
    plan_rollover: bool
    plan_rollover_cap: Optional[Decimal]
    plan_status: Status
    renewal_date: datetime
    balance: Decimal
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class InstitutionBillEnrichedResponseSchema(BaseModel):
    """Schema for enriched institution bill response data with institution, entity, and restaurant details"""
    institution_bill_id: UUID
    institution_id: UUID
    institution_name: str
    institution_entity_id: UUID
    institution_entity_name: str
    restaurant_id: UUID
    restaurant_name: str
    credit_currency_id: UUID
    payment_id: Optional[UUID] = None
    transaction_count: Optional[int] = None
    amount: Optional[Decimal] = None
    currency_code: Optional[str] = None
    balance_event_id: Optional[UUID] = None
    period_start: datetime
    period_end: datetime
    is_archived: bool
    status: Status
    resolution: str
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class InstitutionBankAccountEnrichedResponseSchema(BaseModel):
    """Schema for enriched institution bank account response data with institution, entity, and address details"""
    bank_account_id: UUID
    institution_entity_id: UUID
    institution_id: UUID
    institution_name: str
    institution_entity_name: str
    address_id: UUID
    country: str
    account_holder_name: str
    bank_name: str
    account_type: str
    routing_number: str
    account_number: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID

    class Config:
        orm_mode = True

class InstitutionPaymentAttemptEnrichedResponseSchema(BaseModel):
    """Schema for enriched institution payment attempt response data with institution, entity, bank account, and bill details"""
    payment_id: UUID
    institution_entity_id: UUID
    institution_name: str
    institution_entity_name: str
    bank_account_id: UUID
    bank_name: str
    country: str
    institution_bill_id: Optional[UUID]
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    credit_currency_id: UUID
    amount: Decimal
    currency_code: str
    transaction_result: Optional[str]
    external_transaction_id: Optional[str]
    is_archived: bool
    status: Status
    created_date: datetime
    resolution_date: datetime

    class Config:
        orm_mode = True

# =============================================================================
# 4. LOCATION & ADDRESS SCHEMAS
# =============================================================================

class AddressCreateSchema(BaseModel):
    """Schema for creating a new address"""
    institution_id: UUID
    user_id: UUID
    employer_id: Optional[UUID] = None  # Links address to employer (nullable)
    address_type: List[str] = Field(..., min_items=1, description="At least one address type is required")
    
    @validator('address_type')
    def validate_address_types(cls, v):
        """Validate that all address types are valid enum values"""
        from app.config.enums.address_types import AddressType
        if not v:
            raise ValueError("address_type cannot be empty")
        for addr_type in v:
            if not AddressType.is_valid(addr_type):
                valid_types = ', '.join(AddressType.values())
                raise ValueError(f"Invalid address_type '{addr_type}'. Must be one of: {valid_types}")
        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("address_type cannot contain duplicate values")
        return v
    is_default: bool = False
    floor: Optional[str] = Field(None, max_length=50)
    country: str = Field(..., max_length=50)
    province: str = Field(..., max_length=50)
    city: str = Field(..., max_length=50)
    postal_code: str = Field(..., max_length=20)
    street_type: str = Field(..., max_length=50)
    street_name: str = Field(..., max_length=100)
    building_number: str = Field(..., max_length=20)
    apartment_unit: Optional[str] = Field(None, max_length=20)
    assign_employer: Optional[bool] = Field(
        True,
        description="If True (default), assign the employer to the current user when adding address. Only applies to Customers. Employees/Suppliers ignore this parameter. Can be set to False to opt-out of assignment."
    )
    # timezone is automatically assigned based on country/city - not required in API

class AddressUpdateSchema(BaseModel):
    """Schema for updating address information"""
    institution_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    employer_id: Optional[UUID] = None  # Links address to employer (nullable)
    address_type: Optional[List[str]] = None
    
    @validator('address_type')
    def validate_address_types(cls, v):
        """Validate that all address types are valid enum values"""
        from app.config.enums.address_types import AddressType
        if v is None:
            return v
        if not v:
            raise ValueError("address_type cannot be empty - at least one address type is required")
        for addr_type in v:
            if not AddressType.is_valid(addr_type):
                valid_types = ', '.join(AddressType.values())
                raise ValueError(f"Invalid address_type '{addr_type}'. Must be one of: {valid_types}")
        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("address_type cannot contain duplicate values")
        return v
    is_default: Optional[bool] = None
    floor: Optional[str] = Field(None, max_length=50)
    country: Optional[str] = Field(None, max_length=50)
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    street_type: Optional[str] = Field(None, max_length=50)
    street_name: Optional[str] = Field(None, max_length=100)
    building_number: Optional[str] = Field(None, max_length=20)
    apartment_unit: Optional[str] = Field(None, max_length=20)
    # timezone is automatically assigned based on country/city - not required in API

class AddressResponseSchema(BaseModel):
    """Schema for address response data"""
    address_id: UUID
    institution_id: UUID
    user_id: UUID
    employer_id: Optional[UUID] = None  # Links address to employer (nullable)
    address_type: List[str]
    is_default: bool
    floor: Optional[str]
    country: str
    province: str
    city: str
    postal_code: str
    street_type: str
    street_name: str
    building_number: str
    apartment_unit: Optional[str]
    timezone: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class AddressEnrichedResponseSchema(BaseModel):
    """Schema for enriched address response data with institution name and user details"""
    address_id: UUID
    institution_id: UUID
    institution_name: str
    user_id: UUID
    user_username: str
    user_first_name: Optional[str]
    user_last_name: Optional[str]
    user_full_name: str
    employer_id: Optional[UUID] = None  # Links address to employer (nullable)
    address_type: List[str]
    is_default: bool
    floor: Optional[str]
    country: str
    province: str
    city: str
    postal_code: str
    street_type: str
    street_name: str
    building_number: str
    apartment_unit: Optional[str]
    timezone: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class RestaurantEnrichedResponseSchema(BaseModel):
    """Schema for enriched restaurant response data with institution, entity, and address details"""
    restaurant_id: UUID
    institution_id: UUID
    institution_name: str
    institution_entity_id: UUID
    institution_entity_name: str
    address_id: UUID
    country: str
    province: str
    city: str
    postal_code: str
    credit_currency_id: UUID
    name: str
    cuisine: Optional[str]
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class RestaurantBalanceResponseSchema(BaseModel):
    """Schema for restaurant balance response data (read-only)"""
    restaurant_id: UUID
    credit_currency_id: UUID
    transaction_count: int
    balance: Decimal
    currency_code: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class RestaurantBalanceEnrichedResponseSchema(BaseModel):
    """Schema for enriched restaurant balance response data with institution, entity, restaurant, and address details (read-only)"""
    restaurant_id: UUID
    institution_id: UUID
    institution_name: str
    institution_entity_id: UUID
    institution_entity_name: str
    restaurant_name: str
    country: str
    credit_currency_id: UUID
    transaction_count: int
    balance: Decimal
    currency_code: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class RestaurantTransactionResponseSchema(BaseModel):
    """Schema for restaurant transaction response data (read-only)"""
    transaction_id: UUID
    restaurant_id: UUID
    plate_selection_id: Optional[UUID]
    discretionary_id: Optional[UUID]
    credit_currency_id: UUID
    was_collected: bool
    ordered_timestamp: datetime
    collected_timestamp: Optional[datetime]
    arrival_time: Optional[datetime]
    completion_time: Optional[datetime]
    expected_completion_time: Optional[datetime]
    transaction_type: TransactionType
    credit: Decimal
    no_show_discount: Optional[Decimal]
    currency_code: Optional[str]
    final_amount: Decimal
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class RestaurantTransactionEnrichedResponseSchema(BaseModel):
    """Schema for enriched restaurant transaction response data with institution, entity, restaurant, plate, and address details (read-only)"""
    transaction_id: UUID
    restaurant_id: UUID
    institution_id: UUID
    institution_name: str
    institution_entity_id: UUID
    institution_entity_name: str
    restaurant_name: str
    plate_selection_id: Optional[UUID]
    plate_name: Optional[str]  # Optional because plate_selection_id can be NULL for discretionary transactions
    discretionary_id: Optional[UUID]
    credit_currency_id: UUID
    currency_code: Optional[str]
    country: str
    was_collected: bool
    ordered_timestamp: datetime
    collected_timestamp: Optional[datetime]
    arrival_time: Optional[datetime]
    completion_time: Optional[datetime]
    expected_completion_time: Optional[datetime]
    transaction_type: TransactionType
    credit: Decimal
    no_show_discount: Optional[Decimal]
    final_amount: Decimal
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class QRCodeEnrichedResponseSchema(BaseModel):
    """Schema for enriched QR code response data with institution, restaurant, and address details"""
    qr_code_id: UUID
    restaurant_id: UUID
    restaurant_name: str
    institution_id: UUID
    institution_name: str
    country: str
    province: str
    city: str
    postal_code: str
    street_address: str  # Concatenated: street_type + street_name + building_number
    qr_code_payload: str
    qr_code_image_url: str
    image_storage_path: str
    qr_code_checksum: Optional[str]
    has_image: bool  # Flag indicating if QR code has an image (qr_code_image_url exists and is not empty)
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class EmployerCreateSchema(BaseModel):
    """Schema for creating a new employer with embedded address"""
    name: str = Field(..., max_length=100, description="Employer company name")
    address: 'AddressCreateSchema' = Field(..., description="Complete address information for the employer location")
    assign_employer: bool = Field(
        True,
        description="If True (default), assign this employer to the current user after creation. Only applies to Customers. Employees/Suppliers ignore this parameter."
    )

class EmployerUpdateSchema(BaseModel):
    """Schema for updating employer information"""
    name: Optional[str] = Field(None, max_length=100)
    address_id: Optional[UUID] = None

class EmployerResponseSchema(BaseModel):
    """Schema for employer response data"""
    employer_id: UUID
    name: str
    address_id: UUID
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class EmployerEnrichedResponseSchema(BaseModel):
    """Schema for enriched employer response data with address details"""
    employer_id: UUID
    name: str
    address_id: UUID
    address_country: Optional[str] = None
    address_province: Optional[str] = None
    address_city: Optional[str] = None
    address_postal_code: Optional[str] = None
    address_street_type: Optional[str] = None
    address_street_name: Optional[str] = None
    address_building_number: Optional[str] = None
    address_floor: Optional[str] = None
    address_apartment_unit: Optional[str] = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class EmployerSearchSchema(BaseModel):
    """Schema for employer search functionality"""
    search_term: Optional[str] = Field(None, description="Search term for employer name")
    limit: Optional[int] = Field(10, ge=1, le=50, description="Maximum number of results")

# =============================================================================
# 5. PLATE SELECTION & PICKUP SCHEMAS

class PlatePickupEnrichedResponseSchema(BaseModel):
    """Schema for enriched plate pickup response data with restaurant, address, product, and credit information"""
    plate_pickup_id: UUID
    plate_selection_id: UUID
    user_id: UUID
    restaurant_id: UUID
    restaurant_name: str
    country: str
    province: str
    city: str
    postal_code: str
    plate_id: UUID
    product_id: UUID
    product_name: str
    credit: int
    qr_code_id: UUID
    qr_code_payload: str
    is_archived: bool
    status: Status
    was_collected: Optional[bool] = False
    arrival_time: Optional[datetime]
    completion_time: Optional[datetime]
    expected_completion_time: Optional[datetime]
    confirmation_code: Optional[str]
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True
# =============================================================================

class PlateSelectionCreateSchema(BaseModel):
    """Schema for creating a new plate selection"""
    plate_id: UUID
    restaurant_id: UUID
    product_id: UUID
    qr_code_id: UUID
    credit: int = Field(..., gt=0, description="Credit amount required")
    kitchen_day: KitchenDay
    pickup_time_range: str = Field(..., max_length=50)

class PlateSelectionUpdateSchema(BaseModel):
    """Schema for updating plate selection information"""
    plate_id: Optional[UUID] = None
    restaurant_id: Optional[UUID] = None
    product_id: Optional[UUID] = None
    qr_code_id: Optional[UUID] = None
    credit: Optional[int] = Field(None, gt=0, description="Credit amount required")
    kitchen_day: Optional[KitchenDay] = None
    pickup_time_range: Optional[str] = Field(None, max_length=50)

class PlateSelectionResponseSchema(BaseModel):
    """Schema for plate selection response data"""
    plate_selection_id: UUID
    user_id: UUID
    plate_id: UUID
    restaurant_id: UUID
    product_id: UUID
    qr_code_id: UUID
    credit: int
    kitchen_day: KitchenDay
    pickup_time_range: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

# =============================================================================
# 6. ADMIN & DISCRETIONARY SCHEMAS
# =============================================================================

class DiscretionaryCreateSchema(BaseModel):
    """Schema for creating a new discretionary request"""
    user_id: Optional[UUID] = None
    restaurant_id: Optional[UUID] = None
    category: str = Field(..., max_length=50)
    reason: DiscretionaryReason
    amount: Decimal = Field(..., gt=0)
    comment: Optional[str] = Field(None, max_length=500)
    
    @root_validator
    def validate_user_or_restaurant(cls, values):
        """Ensure either user_id (Client) or restaurant_id (Supplier) is provided"""
        user_id = values.get("user_id")
        restaurant_id = values.get("restaurant_id")
        category = values.get("category")
        
        if not user_id and not restaurant_id:
            raise ValueError("Either user_id (for Client) or restaurant_id (for Supplier) must be provided")
        
        # Enforce category based on provided IDs
        if user_id and not restaurant_id:
            if category != "Client":
                raise ValueError("Category must be 'Client' when user_id is set and restaurant_id is null")
        elif restaurant_id:
            if category != "Supplier":
                raise ValueError("Category must be 'Supplier' when restaurant_id is set")
        
        return values
    
    @root_validator
    def validate_reason_for_category(cls, values):
        """Validate that reason is valid for the given category"""
        category = values.get("category")
        reason = values.get("reason")
        
        if category and reason:
            # Convert enum to string if needed
            reason_str = reason.value if isinstance(reason, DiscretionaryReason) else str(reason)
            
            if not DiscretionaryReason.is_valid_for_category(reason_str, category):
                valid_reasons = DiscretionaryReason.get_valid_for_category(category)
                raise ValueError(
                    f"Invalid reason for {category} category. Must be one of: {', '.join(valid_reasons)}"
                )
        
        return values

class DiscretionaryUpdateSchema(BaseModel):
    """Schema for updating discretionary request information"""
    user_id: Optional[UUID] = None
    restaurant_id: Optional[UUID] = None
    category: Optional[str] = Field(None, max_length=50)
    reason: Optional[DiscretionaryReason] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    comment: Optional[str] = Field(None, max_length=500)

class DiscretionaryResponseSchema(BaseModel):
    """Schema for discretionary request response data"""
    discretionary_id: UUID
    user_id: Optional[UUID] = None  # NULL for Supplier requests, required for Client requests
    restaurant_id: Optional[UUID] = None  # NULL for Client requests, required for Supplier requests
    approval_id: Optional[UUID]
    category: str
    reason: DiscretionaryReason
    amount: Decimal
    comment: Optional[str]
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    class Config:
        orm_mode = True

class DiscretionaryResolutionCreateSchema(BaseModel):
    """Schema for creating discretionary resolutions"""
    discretionary_id: UUID = Field(..., description="ID of the discretionary request")
    resolution: str = Field(..., description="Resolution: 'Approved' or 'Rejected'")
    resolution_comment: Optional[str] = Field(None, description="Comment on the resolution")

class DiscretionaryResolutionResponseSchema(BaseModel):
    """Schema for discretionary resolution responses"""
    approval_id: UUID
    discretionary_id: UUID
    resolution: str
    is_archived: bool
    status: Status
    resolved_by: UUID
    resolved_date: datetime
    created_date: datetime
    resolution_comment: Optional[str] = None

class DiscretionaryApprovalSchema(BaseModel):
    """Schema for approving discretionary requests"""
    resolution_comment: Optional[str] = Field(None, description="Comment on the approval")

class DiscretionaryRejectionSchema(BaseModel):
    """Schema for rejecting discretionary requests"""
    resolution_comment: str = Field(..., description="Reason for rejection")

class DiscretionarySummarySchema(BaseModel):
    """Schema for discretionary request summary (dashboard view)"""
    discretionary_id: UUID
    user_id: Optional[UUID] = None  # NULL for Supplier requests, required for Client requests
    restaurant_id: Optional[UUID] = None  # NULL for Client requests, required for Supplier requests
    category: str
    reason: DiscretionaryReason
    amount: Decimal
    status: Status
    created_date: datetime
    resolved_date: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
    resolution_comment: Optional[str] = None

# =============================================================================
# 6. INSTITUTION ENTITY SCHEMAS
# =============================================================================

class InstitutionEntityCreateSchema(BaseModel):
    """Schema for creating a new institution entity"""
    institution_id: UUID
    address_id: UUID
    tax_id: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    is_archived: bool = False

class InstitutionEntityUpdateSchema(BaseModel):
    """Schema for updating institution entity information"""
    institution_id: Optional[UUID] = None
    address_id: Optional[UUID] = None
    tax_id: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=100)
    is_archived: Optional[bool] = None
    status: Optional[Status] = None

class InstitutionEntityResponseSchema(BaseModel):
    """Schema for institution entity response data"""
    institution_entity_id: UUID
    institution_id: UUID
    address_id: UUID
    tax_id: str
    name: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class InstitutionEntityEnrichedResponseSchema(BaseModel):
    """Schema for enriched institution entity response data with institution name and address details"""
    institution_entity_id: UUID
    institution_id: UUID
    institution_name: str
    address_id: UUID
    address_country: str
    address_province: str
    address_city: str
    tax_id: str
    name: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True


# =============================================================================
# 8. NATIONAL HOLIDAYS SCHEMAS
# =============================================================================

class NationalHolidayCreateSchema(BaseModel):
    """Schema for creating a national holiday"""
    country_code: str = Field(..., max_length=3, description="ISO country code (e.g., 'USA', 'ARG')")
    holiday_name: str = Field(..., max_length=100, description="Name of the holiday")
    holiday_date: date = Field(..., description="Date of the holiday")
    is_recurring: bool = Field(False, description="Whether this holiday recurs annually")
    recurring_month: Optional[int] = Field(None, ge=1, le=12, description="Month for recurring holidays (1-12)")
    recurring_day: Optional[int] = Field(None, ge=1, le=31, description="Day for recurring holidays (1-31)")
    status: Optional[Status] = Field(default=Status.ACTIVE, description="Status of the holiday (default: 'Active')")
    
    @root_validator
    def validate_recurring_complete(cls, values):
        """Ensure both recurring_month and recurring_day are provided when is_recurring is True"""
        is_recurring = values.get('is_recurring', False)
        if is_recurring:
            recurring_month = values.get('recurring_month')
            recurring_day = values.get('recurring_day')
            if recurring_month is None or recurring_day is None:
                raise ValueError("Both recurring_month and recurring_day are required when is_recurring is True")
        return values

class NationalHolidayUpdateSchema(BaseModel):
    """Schema for updating a national holiday"""
    country_code: Optional[str] = Field(None, max_length=3)
    holiday_name: Optional[str] = Field(None, max_length=100)
    holiday_date: Optional[date] = None
    is_recurring: Optional[bool] = None
    recurring_month: Optional[int] = Field(None, ge=1, le=12)
    recurring_day: Optional[int] = Field(None, ge=1, le=31)
    status: Optional[Status] = Field(None, description="Status of the holiday")
    
    @root_validator
    def validate_recurring_complete(cls, values):
        """Ensure both recurring_month and recurring_day are provided when is_recurring is set to True"""
        is_recurring = values.get('is_recurring')
        if is_recurring is True:
            recurring_month = values.get('recurring_month')
            recurring_day = values.get('recurring_day')
            if recurring_month is None or recurring_day is None:
                raise ValueError("Both recurring_month and recurring_day are required when is_recurring is True")
        return values

class NationalHolidayResponseSchema(BaseModel):
    """Schema for national holiday response data"""
    holiday_id: UUID
    country_code: str
    holiday_name: str
    holiday_date: date
    is_recurring: bool
    recurring_month: Optional[int]
    recurring_day: Optional[int]
    status: Status
    is_archived: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    class Config:
        orm_mode = True

class NationalHolidayBulkCreateSchema(BaseModel):
    """Schema for bulk creating national holidays"""
    holidays: List[NationalHolidayCreateSchema] = Field(..., min_items=1, description="List of holidays to create")
    
    @validator('holidays')
    def validate_holidays_not_empty(cls, v):
        """Ensure at least one holiday is provided"""
        if not v:
            raise ValueError("At least one holiday must be provided")
        return v


# ============================================================================
# Restaurant Staff Schemas
# ============================================================================

class DailyOrderItemSchema(BaseModel):
    """Schema for a single order item in daily orders view"""
    customer_name: str = Field(..., description="Privacy-safe customer name (First L.)")
    plate_name: str = Field(..., description="Name of the plate ordered")
    confirmation_code: str = Field(..., description="Pickup confirmation code")
    status: str = Field(..., description="Order status")
    arrival_time: Optional[datetime] = Field(None, description="When customer arrived")
    pickup_time_range: str = Field(..., description="Expected pickup time range")
    kitchen_day: str = Field(..., description="Kitchen day for the order")
    
    class Config:
        orm_mode = True


class OrderSummarySchema(BaseModel):
    """Schema for order summary statistics"""
    total_orders: int = Field(..., description="Total number of orders")
    pending: int = Field(..., description="Number of pending orders (not yet arrived)")
    arrived: int = Field(..., description="Number of arrived orders (waiting for pickup)")
    completed: int = Field(..., description="Number of completed orders")
    
    class Config:
        orm_mode = True


class RestaurantDailyOrdersSchema(BaseModel):
    """Schema for a restaurant's daily orders"""
    restaurant_id: UUID = Field(..., description="Restaurant UUID")
    restaurant_name: str = Field(..., description="Restaurant name")
    orders: List[DailyOrderItemSchema] = Field(..., description="List of orders for this restaurant")
    summary: OrderSummarySchema = Field(..., description="Summary statistics for this restaurant")
    
    class Config:
        orm_mode = True


class DailyOrdersResponseSchema(BaseModel):
    """Schema for daily orders response"""
    order_date: date = Field(..., description="Date of the orders")
    restaurants: List[RestaurantDailyOrdersSchema] = Field(..., description="List of restaurants with their orders")
    
    class Config:
        orm_mode = True

