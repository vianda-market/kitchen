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
5. Subscriptions & Plans (Plan, Subscription)
6. Plate Selection & Pickup (Plate Selection, Pickup Preferences, Live Pickup)
7. Admin & Discretionary (Discretionary Requests, Resolutions)

Benefits:
- Reduced file count (25+ files → 7 files)
- Logical grouping by business domain
- Easier maintenance and navigation
- Better code organization
- Reduced import complexity
"""

from pydantic import BaseModel, ConfigDict, Field, EmailStr, RootModel, ValidationInfo, field_validator, model_validator
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal
from app.config import Status, RoleType, RoleName, TransactionType, KitchenDay, PickupType, AuditOperation, DiscretionaryReason
from app.config.supported_cuisines import is_supported_cuisine
from app.config.enums import FavoriteEntityType
from app.utils.country import normalize_country_code
from app.utils.phone import normalize_mobile_for_schema
from app.config.settings import settings

# =============================================================================
# 1. CORE ENTITIES SCHEMAS
# =============================================================================

class UserCreateSchema(BaseModel):
    """Schema for creating a new user. institution_id is optional for Customer+Comensal (backend assigns Vianda Customers). market_id optional: backend defaults to Global for Admin/Super Admin/Supplier Admin, required for Manager/Operator. market_ids (v2) optional: list of assigned markets (first is primary). Omit password to trigger B2B invite flow (email with link to set password)."""
    institution_id: Optional[UUID] = None
    role_type: RoleType
    role_name: RoleName
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: Optional[str] = Field(None, min_length=8, description="Optional. Omit to trigger B2B invite flow; user sets password via email link.")

    @field_validator("username", "email", mode="before")
    @classmethod
    def normalize_username_email_lowercase(cls, v):
        """Normalize username and email to lowercase for case-insensitive uniqueness."""
        if v is None or not isinstance(v, str):
            return v
        return v.strip().lower()
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    mobile_number: Optional[str] = Field(default=None)
    employer_id: Optional[UUID] = None
    market_id: Optional[UUID] = None
    city_id: Optional[UUID] = Field(None, description="Primary city for scoping (must match market's country)")
    market_ids: Optional[List[UUID]] = Field(None, description="v2: list of assigned market IDs (first is primary)")

    @field_validator("mobile_number", mode="before")
    @classmethod
    def normalize_mobile_number_create(cls, v):
        return normalize_mobile_for_schema(v, None)

    @field_validator("role_type", mode="before")
    @classmethod
    def normalize_role_type(cls, v):
        """Accept role_type string case-insensitively to avoid 422 from UI."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return v
        if isinstance(v, RoleType):
            return v
        s = (v if isinstance(v, str) else str(v)).strip()
        for rt in RoleType:
            if rt.value.lower() == s.lower():
                return rt
        return v

    @field_validator("role_name", mode="before")
    @classmethod
    def normalize_role_name(cls, v):
        """Accept role_name string case-insensitively to avoid 422 from UI."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return v
        if isinstance(v, RoleName):
            return v
        s = (v if isinstance(v, str) else str(v)).strip()
        for rn in RoleName:
            if rn.value.lower() == s.lower():
                return rn
        return v

    @field_validator('role_name')
    @classmethod
    def validate_role_combination(cls, v: RoleName, info: ValidationInfo) -> RoleName:
        """Validate that role_type and role_name combination is valid"""
        role_type = info.data.get('role_type')
        if not role_type:
            return v
        
        valid_combinations = {
            RoleType.INTERNAL: [RoleName.ADMIN, RoleName.SUPER_ADMIN, RoleName.MANAGER, RoleName.OPERATOR, RoleName.GLOBAL_MANAGER],
            RoleType.SUPPLIER: [RoleName.ADMIN, RoleName.MANAGER, RoleName.OPERATOR],
            RoleType.CUSTOMER: [RoleName.COMENSAL],
            RoleType.EMPLOYER: [RoleName.ADMIN, RoleName.MANAGER, RoleName.COMENSAL],
        }
        
        if v not in valid_combinations.get(role_type, []):
            raise ValueError(
                f"Invalid role combination: {role_type.value} + {v.value}. "
                f"Valid combinations: {[rn.value for rn in valid_combinations.get(role_type, [])]}"
            )
        return v

class UserUpdateSchema(BaseModel):
    """Schema for updating user information. role_type, institution_id, and username are immutable (set on create only). username is the login identifier; the API ignores or rejects username in update payloads. Only Super Admin / Admin can set market_id; Managers cannot assign Global. market_ids (v2) optional: replace assigned markets (first is primary)."""
    role_name: Optional[RoleName] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100, description="Ignored on update; username cannot be changed.")
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    mobile_number: Optional[str] = Field(default=None)
    employer_id: Optional[UUID] = None
    market_id: Optional[UUID] = None
    city_id: Optional[UUID] = Field(None, description="Primary city for scoping (must match market's country)")
    market_ids: Optional[List[UUID]] = Field(None, description="v2: replace assigned market IDs (first is primary)")
    status: Optional[Literal["Active", "Inactive"]] = Field(None, description="User status (Active/Inactive only)")
    locale: Optional[str] = Field(None, min_length=2, max_length=5, description="ISO 639-1 UI locale: en, es, pt")

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = tuple(settings.SUPPORTED_LOCALES)
        if v not in allowed:
            raise ValueError(f"Unsupported locale '{v}'. Must be one of: {', '.join(allowed)}")
        return v

    @field_validator("mobile_number", mode="before")
    @classmethod
    def normalize_mobile_number_update(cls, v):
        return normalize_mobile_for_schema(v, None)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_lowercase(cls, v):
        if v is None:
            return None
        if not isinstance(v, str):
            return v
        return v.strip().lower()

    @field_validator('role_name')
    @classmethod
    def validate_role_combination(cls, v, info: ValidationInfo):
        """Validate role_name when provided. role_type is immutable (not in update schema); validation against existing role_type is done in route."""
        if not v:
            return v
        # role_type is not in UserUpdateSchema (immutable) - combination validation done in route using existing_user.role_type
        return v


class EmailChangeVerifySchema(BaseModel):
    """Body for POST /users/me/verify-email-change — 6-digit code from email (or legacy longer token)."""
    code: str = Field(..., min_length=6, max_length=10, description="Verification code from email")


class AssignEmployerRequest(BaseModel):
    """Schema for PUT /users/me/employer - assign existing employer and address to current user."""
    employer_id: UUID = Field(..., description="Employer ID to assign")
    address_id: UUID = Field(..., description="Address (office) where user works; must belong to employer")
    floor: Optional[str] = Field(None, max_length=50, description="Floor at this office (stored per-user in address_subpremise)")
    apartment_unit: Optional[str] = Field(None, max_length=20, description="Unit at this office (stored per-user in address_subpremise)")


class ChangePasswordSchema(BaseModel):
    """Schema for self-service change password (PUT /users/me/password)."""
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")
    new_password_confirm: str = Field(..., min_length=1, description="Confirm new password")

    @field_validator("new_password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info: ValidationInfo) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("New password and confirmation do not match")
        return v

    @model_validator(mode="after")
    def new_password_different(self):
        if self.current_password and self.new_password and self.current_password == self.new_password:
            raise ValueError("New password must differ from current password")
        return self


class UserSearchResultSchema(BaseModel):
    """One user in GET /users/search/ response (minimal fields for discretionary recipient picker)."""
    user_id: UUID
    full_name: str
    username: str
    email: str


class UserSearchResponseSchema(BaseModel):
    """Response for GET /users/search/ (paginated list + total)."""
    results: List["UserSearchResultSchema"] = Field(..., description="Page of matching users")
    total: int = Field(..., description="Total number of matching users (for pagination)")


class AdminResetPasswordSchema(BaseModel):
    """Schema for admin reset another user's password (PUT /users/{user_id}/password)."""
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")
    new_password_confirm: str = Field(..., min_length=1, description="Confirm new password")

    @field_validator("new_password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info: ValidationInfo) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("New password and confirmation do not match")
        return v


class UserResponseSchema(BaseModel):
    """Schema for user response data. market_id is primary assigned market; market_ids (v2) lists all assigned markets."""
    user_id: UUID
    institution_id: UUID
    role_type: RoleType
    role_name: RoleName
    username: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    mobile_number: Optional[str] = None
    mobile_number_verified: bool = False
    mobile_number_verified_at: Optional[datetime] = None
    email_verified: bool = False
    email_verified_at: Optional[datetime] = None
    email_change_message: Optional[str] = Field(
        None,
        description="Set when an email change was requested: verification sent to new address; email field unchanged until verified.",
    )
    employer_id: Optional[UUID]
    employer_address_id: Optional[UUID] = None
    market_id: UUID
    city_id: Optional[UUID] = None
    market_ids: List[UUID] = Field(default_factory=list, description="v2: all assigned market IDs (primary first)")
    locale: str = Field("en", description="ISO 639-1 UI locale: en, es, pt")
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    @field_validator("employer_id")
    @classmethod
    def employer_null_for_supplier_employee(cls, v, info: ValidationInfo):
        """Supplier, Internal, and Employer users do not have an Employer; return None in response."""
        role_type = info.data.get("role_type")
        if role_type is None:
            return v
        rt = role_type.value if hasattr(role_type, "value") else str(role_type)
        if rt in ("Supplier", "Internal", "Employer"):
            return None
        return v

    model_config = ConfigDict(from_attributes=True)


class MessagingPreferencesResponseSchema(BaseModel):
    """Schema for messaging preferences response (GET /users/me/messaging-preferences)."""
    notify_coworker_pickup_alert: bool = Field(True, description="Receive push when a coworker offers to pick up your plate")
    notify_plate_readiness_alert: bool = Field(True, description="Receive push when restaurant signals plate is ready")
    notify_promotions_push: bool = Field(True, description="Receive in-app push for promotions and marketing")
    notify_promotions_email: bool = Field(True, description="Receive email campaigns for promotions and marketing")
    coworkers_can_see_my_orders: bool = Field(True, description="Allow coworkers to see my orders in explore and coworker-facing lists")
    can_participate_in_plate_pickups: bool = Field(True, description="I can appear on coworker list for pickup offers and volunteer")

    model_config = ConfigDict(from_attributes=True)


class MessagingPreferencesUpdateSchema(BaseModel):
    """Schema for updating messaging preferences (PUT /users/me/messaging-preferences). All fields optional."""
    notify_coworker_pickup_alert: Optional[bool] = None
    notify_plate_readiness_alert: Optional[bool] = None
    notify_promotions_push: Optional[bool] = None
    notify_promotions_email: Optional[bool] = None
    coworkers_can_see_my_orders: Optional[bool] = None
    can_participate_in_plate_pickups: Optional[bool] = None


class UserEnrichedResponseSchema(BaseModel):
    """Schema for enriched user response. market_id is primary; market_ids (v2) lists all assigned markets. market_name and employer_name for profile display."""
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
    mobile_number: Optional[str] = None
    mobile_number_display: Optional[str] = Field(None, description="Internationally formatted display string (e.g. '+54 9 11 2345-6789'). Read-only; computed from mobile_number.")
    mobile_number_verified: bool = False
    mobile_number_verified_at: Optional[datetime] = None
    email_verified: bool = False
    email_verified_at: Optional[datetime] = None
    employer_id: Optional[UUID]
    employer_address_id: Optional[UUID] = None
    employer_name: Optional[str] = None
    market_id: UUID
    market_name: str
    city_id: Optional[UUID] = None
    city_name: Optional[str] = None
    market_ids: List[UUID] = Field(default_factory=list, description="v2: all assigned market IDs (primary first)")
    locale: str = Field("en", description="ISO 639-1 UI locale: en, es, pt")
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    @field_validator("employer_id")
    @classmethod
    def employer_null_for_supplier_employee(cls, v, info: ValidationInfo):
        """Supplier, Internal, and Employer users do not have an Employer; return None in response."""
        role_type = info.data.get("role_type")
        if role_type is None:
            return v
        rt = role_type.value if hasattr(role_type, "value") else str(role_type)
        if rt in ("Supplier", "Internal", "Employer"):
            return None
        return v

    @field_validator("employer_name")
    @classmethod
    def employer_name_null_for_supplier_employee(cls, v, info: ValidationInfo):
        """Supplier, Internal, and Employer users do not have an Employer; return None in response."""
        role_type = info.data.get("role_type")
        if role_type is None:
            return v
        rt = role_type.value if hasattr(role_type, "value") else str(role_type)
        if rt in ("Supplier", "Internal", "Employer"):
            return None
        return v

    model_config = ConfigDict(from_attributes=True)

class CustomerSignupSchema(BaseModel):
    """Schema for customer signup. country_code required (from GET /api/v1/leads/markets). Provide city_id OR city_name (backend resolves city_name to city_id)."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=255)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    email: EmailStr
    mobile_number: Optional[str] = Field(default=None)

    @field_validator("username", "email", mode="before")
    @classmethod
    def normalize_username_email_lowercase(cls, v):
        """Normalize username and email to lowercase for case-insensitive uniqueness."""
        if v is None or not isinstance(v, str):
            return v
        return v.strip().lower()
    country_code: str = Field(..., min_length=2, max_length=3, description="ISO 3166-1 alpha-2 or alpha-3 (e.g. AR, US, ARG). From GET /api/v1/leads/markets. Backend resolves to market.")
    city_id: Optional[UUID] = Field(None, description="City UUID (optional if city_name provided). From GET /api/v1/cities/ or resolved from city_name.")
    city_name: Optional[str] = Field(None, max_length=100, description="City name (optional if city_id provided). From GET /api/v1/leads/cities?country_code=... Backend resolves to city_id.")
    is_archived: Optional[bool] = False
    status: Optional[Status] = Field(default=Status.ACTIVE)

    @field_validator("country_code")
    @classmethod
    def normalize_country_to_alpha2(cls, v: str) -> str:
        """Normalize to alpha-2 uppercase."""
        return normalize_country_code(v) if v else v

    @model_validator(mode="after")
    def require_city_and_normalize_mobile(self):
        if not self.city_id and not (self.city_name or "").strip():
            raise ValueError("Either city_id or city_name is required")
        normalized = normalize_mobile_for_schema(self.mobile_number, self.country_code)
        if normalized != self.mobile_number:
            return self.model_copy(update={"mobile_number": normalized})
        return self

class InstitutionCreateSchema(BaseModel):
    """Schema for creating a new institution. market_id is required. no_show_discount required for Supplier."""
    name: str = Field(..., max_length=100)
    institution_type: Optional[RoleType] = None  # Defaults to Supplier in DB if omitted
    market_id: UUID = Field(..., description="Required: market UUID (e.g. Global Marketplace or a country market from GET /api/v1/markets/enriched/)")
    no_show_discount: Optional[int] = Field(None, ge=0, le=100, description="Percentage 0-100; required when institution_type is Supplier")

    @model_validator(mode="after")
    def supplier_requires_no_show_discount(self):
        inst_type = self.institution_type
        no_show = self.no_show_discount
        is_supplier = inst_type is None or (hasattr(inst_type, "value") and inst_type.value == "Supplier") or inst_type == "Supplier"
        if is_supplier and no_show is None:
            raise ValueError("no_show_discount is required when institution_type is Supplier")
        return self

class InstitutionUpdateSchema(BaseModel):
    """Schema for updating institution information"""
    name: Optional[str] = Field(None, max_length=100)
    institution_type: Optional[RoleType] = None
    market_id: Optional[UUID] = None  # When provided, must be a valid market UUID (single, global, or multi)
    no_show_discount: Optional[int] = Field(None, ge=0, le=100, description="Percentage 0-100; cannot be None for Supplier institutions")

class InstitutionResponseSchema(BaseModel):
    """Schema for institution response data. market_id is always present (never null). no_show_discount is null for Internal/Customer."""
    institution_id: UUID
    name: str
    institution_type: RoleType
    market_id: UUID = Field(..., description="Required: market UUID (Global = all markets, one UUID = local market)")
    no_show_discount: Optional[int] = Field(None, description="Percentage 0-100; required for Supplier, null for Internal/Customer")
    is_archived: bool
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: Optional[UUID] = None
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

# RoleCreateSchema, RoleUpdateSchema, RoleResponseSchema removed
# role_info table removed - roles are now stored directly on user_info as enums

# =============================================================================
# 2. RESTAURANT & FOOD SCHEMAS
# =============================================================================

class RestaurantCreateSchema(BaseModel):
    """Schema for creating a new restaurant. credit_currency inherited from institution_entity."""
    institution_id: UUID
    institution_entity_id: UUID
    address_id: UUID
    name: str = Field(..., max_length=100)
    cuisine: Optional[str] = Field(None, max_length=50)
    pickup_instructions: Optional[str] = Field(None, max_length=500)

    @field_validator("cuisine")
    @classmethod
    def cuisine_must_be_supported(cls, v):
        """Validate cuisine is in supported list. Use GET /api/v1/cuisines/ for valid values."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return v
        if not is_supported_cuisine(v):
            raise ValueError(
                f"Cuisine '{v}' is not supported. Use GET /api/v1/cuisines/ for valid values."
            )
        return v

class RestaurantUpdateSchema(BaseModel):
    """Schema for updating restaurant information"""
    institution_id: Optional[UUID] = None
    institution_entity_id: Optional[UUID] = None
    address_id: Optional[UUID] = None
    name: Optional[str] = Field(None, max_length=100)
    cuisine: Optional[str] = Field(None, max_length=50)
    pickup_instructions: Optional[str] = Field(None, max_length=500)
    status: Optional[Status] = Field(None, description="Active only allowed when restaurant has active plate_kitchen_days; Inactive always allowed")

    @field_validator("cuisine")
    @classmethod
    def cuisine_must_be_supported(cls, v):
        """Validate cuisine is in supported list. Use GET /api/v1/cuisines/ for valid values."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return v
        if not is_supported_cuisine(v):
            raise ValueError(
                f"Cuisine '{v}' is not supported. Use GET /api/v1/cuisines/ for valid values."
            )
        return v

class RestaurantSearchResultSchema(BaseModel):
    """One restaurant in GET /restaurants/search/ response (minimal fields for discretionary recipient picker)."""
    restaurant_id: UUID
    name: str


class RestaurantSearchResponseSchema(BaseModel):
    """Response for GET /restaurants/search/ (paginated list + total)."""
    results: List["RestaurantSearchResultSchema"] = Field(..., description="Page of matching restaurants")
    total: int = Field(..., description="Total number of matching restaurants (for pagination)")


class RestaurantExplorerCitiesResponseSchema(BaseModel):
    """Response for GET /restaurants/cities (B2C explore dropdown)."""
    cities: List[str] = Field(..., description="City names that have at least one restaurant in the country")


class KitchenDayForExploreSchema(BaseModel):
    """One kitchen day option for GET /restaurants/explore/kitchen-days (closest-first order)."""
    kitchen_day: str = Field(..., description="Weekday name (Monday–Friday)")
    date: str = Field(..., description="ISO date (YYYY-MM-DD) for this occurrence")


class ExploreKitchenDaysResponseSchema(BaseModel):
    """Response for GET /restaurants/explore/kitchen-days. Ordered by date ascending (closest first)."""
    kitchen_days: List[KitchenDayForExploreSchema] = Field(
        ..., description="Allowed kitchen days in the explore window, closest date first"
    )


class PickupWindowsResponseSchema(BaseModel):
    """Response for GET /restaurants/explore/pickup-windows. 15-minute windows for the given kitchen day."""
    kitchen_day: str = Field(..., description="Weekday name (Monday–Friday)")
    date: str = Field(..., description="ISO date (YYYY-MM-DD) for this occurrence")
    pickup_windows: List[str] = Field(
        ..., description="15-minute windows in HH:MM-HH:MM format (e.g. 11:30-11:45)"
    )


class CoworkerPickupWindowItemSchema(BaseModel):
    """One coworker pickup window in GET /restaurants/{id}/coworker-pickup-windows."""
    pickup_time_range: str = Field(..., description="15-min window HH:MM-HH:MM (e.g. 11:30-11:45)")
    intent: str = Field(..., description="pickup_intent: 'offer' or 'request'")
    flexible_on_time: Optional[bool] = Field(None, description="True when original request has flexible_on_time")


class CoworkerPickupWindowsResponseSchema(BaseModel):
    """Response for GET /restaurants/{id}/coworker-pickup-windows."""
    pickup_windows: List[CoworkerPickupWindowItemSchema] = Field(
        ..., description="Pickup windows from coworkers (offer/request) for this restaurant+kitchen_day"
    )


class PlateExplorerItemSchema(BaseModel):
    """One plate in GET /restaurants/by-city restaurant.plates (lean payload for cards; modal fetches via enriched)."""
    plate_id: UUID
    product_name: str = Field(..., description="Product name from product_info")
    image_url: Optional[str] = Field(None, description="Product thumbnail URL (image_thumbnail_url)")
    credit: int = Field(..., description="Credit value")
    savings: int = Field(0, ge=0, le=100, description="Savings percentage for display (e.g. green box X% off)")
    is_recommended: bool = Field(False, description="True when recommendation score meets threshold; UI can show Recommended badge")
    is_favorite: bool = Field(False, description="True if the current user has favorited this plate")
    is_already_reserved: bool = Field(False, description="True when current user has reserved this plate for this kitchen_day; show alternative actions instead of Reserve")
    existing_plate_selection_id: Optional[str] = Field(None, description="When is_already_reserved, use for Change or cancel (PATCH/DELETE)")


class RestaurantExplorerItemSchema(BaseModel):
    """One restaurant in GET /restaurants/by-city response (list and map)."""
    restaurant_id: UUID
    name: str
    cuisine: Optional[str] = None
    lat: Optional[float] = Field(None, description="Latitude from geolocation; null if missing")
    lng: Optional[float] = Field(None, description="Longitude from geolocation; null if missing")
    postal_code: Optional[str] = Field(None, description="Zipcode/postal code from address")
    city: Optional[str] = Field(None, description="City from address")
    street_type: Optional[str] = Field(None, description="Street type from address (e.g. St, Ave) for address line")
    street_name: Optional[str] = Field(None, description="Street name from address for address line")
    building_number: Optional[str] = Field(None, description="Building number from address for address line")
    address_display: Optional[str] = Field(None, description="Pre-formatted street line per market (e.g. 123 Main St or Av Santa Fe 100)")
    pickup_instructions: Optional[str] = Field(None, description="Restaurant pickup instructions for customers")
    plates: Optional[List[PlateExplorerItemSchema]] = Field(None, description="Plates available for the response kitchen_day (when requested)")
    has_volunteer: bool = Field(False, description="True when kitchen_day set and at least one user has pickup_intent=offer for this restaurant")
    has_coworker_offer: bool = Field(False, description="True when user has employer and at least one coworker has pickup_intent=offer for this restaurant+kitchen_day")
    has_coworker_request: bool = Field(False, description="True when user has employer and at least one coworker has pickup_intent=request for this restaurant+kitchen_day")
    is_favorite: bool = Field(False, description="True if the current user has favorited this restaurant")
    is_recommended: bool = Field(False, description="True when recommendation score meets threshold; UI can show Recommended badge")


class RestaurantsByCityResponseSchema(BaseModel):
    """Response for GET /restaurants/by-city (B2C explore list/map, optional plates by kitchen day)."""
    requested_city: str = Field(..., description="City value the client sent")
    city: str = Field(..., description="Matched city (case-insensitive)")
    center: Optional["ZipcodeCenterSchema"] = Field(None, description="Optional lat/lng center for the city")
    kitchen_day: Optional[str] = Field(None, description="Kitchen day used for plates (when market/kitchen_day resolved)")
    restaurants: List[RestaurantExplorerItemSchema] = Field(..., description="Restaurants in the city with name, cuisine, geolocation; plates when kitchen_day present")


class RestaurantResponseSchema(BaseModel):
    """Schema for restaurant response data"""
    restaurant_id: UUID
    institution_id: UUID
    institution_entity_id: UUID
    address_id: UUID
    credit_currency_id: UUID
    name: str
    cuisine: Optional[str]
    pickup_instructions: Optional[str] = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

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
    """Schema for product response data. Includes both image sizes after upload."""
    product_id: UUID
    institution_id: UUID
    name: str
    ingredients: Optional[str]
    dietary: Optional[str]
    image_url: Optional[str]
    image_storage_path: str
    image_thumbnail_url: Optional[str] = None
    image_thumbnail_storage_path: Optional[str] = None
    image_checksum: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class ProductEnrichedResponseSchema(BaseModel):
    """Schema for enriched product response data with institution name. B2B suppliers get both image sizes."""
    product_id: UUID
    institution_id: UUID
    institution_name: str
    name: str
    ingredients: Optional[str]
    dietary: Optional[str]
    image_url: Optional[str]  # Full-size URL (e.g. max 1024px)
    image_storage_path: str
    image_thumbnail_url: Optional[str]  # Thumbnail URL (e.g. 300×300)
    image_thumbnail_storage_path: str
    image_checksum: str
    has_image: bool  # Flag indicating if product has a custom uploaded image (TRUE) or default placeholder (FALSE)
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class PlateCreateSchema(BaseModel):
    """Schema for creating a new plate. Savings are computed on the fly from plan credit_cost_local_currency. no_show_discount is at institution level."""
    product_id: UUID
    restaurant_id: UUID
    price: Decimal = Field(..., ge=0)
    credit: int = Field(..., gt=0)
    delivery_time_minutes: int = Field(default=15, gt=0)

class PlateUpdateSchema(BaseModel):
    """Schema for updating plate information"""
    product_id: Optional[UUID] = None
    restaurant_id: Optional[UUID] = None
    price: Optional[Decimal] = Field(None, ge=0)
    credit: Optional[int] = Field(None, gt=0)
    delivery_time_minutes: Optional[int] = Field(None, gt=0)

class PlateResponseSchema(BaseModel):
    """Schema for plate response data"""
    plate_id: UUID
    product_id: UUID
    restaurant_id: UUID
    price: Decimal
    credit: int
    expected_payout_local_currency: Decimal
    delivery_time_minutes: int
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class PlateEnrichedResponseSchema(BaseModel):
    """Schema for enriched plate response data with institution, restaurant, product, and address details"""
    plate_id: UUID
    product_id: UUID
    restaurant_id: UUID
    institution_name: str
    restaurant_name: str
    cuisine: Optional[str]
    pickup_instructions: Optional[str] = None
    country_name: str
    country_code: str
    province: str
    city: str
    street_type: Optional[str] = None
    street_name: Optional[str] = None
    building_number: Optional[str] = None
    address_display: Optional[str] = Field(None, description="Pre-formatted street line per market (e.g. 123 Main St or Av Santa Fe 100)")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    average_stars: Optional[float] = None
    average_portion_size: Optional[float] = None
    portion_size: Literal["light", "standard", "large", "insufficient_reviews"] = Field(
        "insufficient_reviews",
        description="Human-readable portion size; 'insufficient_reviews' when < 5 reviews (client shows 'not enough reviews' message)",
    )
    review_count: int = 0
    product_name: str
    dietary: Optional[str]
    ingredients: Optional[str] = None  # From product_info for plate modal
    product_image_url: Optional[str]  # Product image URL for display
    product_image_storage_path: str  # Product image storage path
    has_image: bool  # Flag indicating if product has a custom uploaded image (TRUE) or default placeholder (FALSE)
    price: Decimal
    credit: int
    expected_payout_local_currency: Decimal
    no_show_discount: Optional[int] = Field(None, description="From institution; null for non-Supplier")
    delivery_time_minutes: int
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime
    has_coworker_offer: Optional[bool] = Field(None, description="When kitchen_day provided and user has employer: True if coworker has pickup_intent=offer")
    has_coworker_request: Optional[bool] = Field(None, description="When kitchen_day provided and user has employer: True if coworker has pickup_intent=request")

    model_config = ConfigDict(from_attributes=True)

class PlateKitchenDayCreateSchema(BaseModel):
    """Schema for creating plate kitchen day assignments (supports single or multiple days)"""
    plate_id: UUID
    kitchen_days: List[KitchenDay] = Field(..., description="List of days of the week: Monday, Tuesday, Wednesday, Thursday, or Friday")
    status: Optional[Status] = Field(default=None, description="Optional; omit or null and backend assigns default (Active)")
    
    @field_validator('kitchen_days')
    @classmethod
    def validate_kitchen_days(cls, v):
        """Validate that all kitchen_days are valid weekdays"""
        if not v:
            raise ValueError("kitchen_days cannot be empty")
        # Check for duplicates
        if len(v) != len(set(v)):
            raise ValueError("kitchen_days cannot contain duplicate days")
        return v
    
    model_config = ConfigDict(from_attributes=True)

class PlateKitchenDayUpdateSchema(BaseModel):
    """Schema for updating plate kitchen day assignment.
    plate_id is immutable; if sent on update, the request will be rejected with 400.
    To change plate_id: create a new record and archive the old one."""
    plate_id: Optional[UUID] = Field(None, description="Immutable - cannot be changed; if provided, returns 400")
    kitchen_day: Optional[KitchenDay] = Field(None, description="Day of the week: Monday, Tuesday, Wednesday, Thursday, or Friday")
    status: Optional[Status] = Field(None, description="Status of the kitchen day assignment")
    is_archived: Optional[bool] = None
    
    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

class PlateReviewCreateSchema(BaseModel):
    """Schema for creating a plate review. One review per pickup; immutable after creation."""
    plate_pickup_id: UUID = Field(..., description="The pickup being reviewed; must be completed (was_collected=true) and belong to the user")
    stars_rating: int = Field(..., ge=1, le=5, description="Star rating 1-5")
    portion_size_rating: int = Field(..., ge=1, le=3, description="Portion size rating 1-3")

    model_config = ConfigDict(from_attributes=True)

class PlateReviewResponseSchema(BaseModel):
    """Schema for plate review response data"""
    plate_review_id: UUID
    user_id: UUID
    plate_id: UUID
    plate_pickup_id: UUID
    stars_rating: int
    portion_size_rating: int
    is_archived: bool
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class FavoriteCreateSchema(BaseModel):
    """Schema for adding a favorite. entity_type is 'plate' or 'restaurant'; entity_id is the plate_id or restaurant_id."""
    entity_type: FavoriteEntityType = Field(..., description="Type of entity to favorite: plate or restaurant")
    entity_id: UUID = Field(..., description="plate_id or restaurant_id")

    model_config = ConfigDict(from_attributes=True)


class FavoriteResponseSchema(BaseModel):
    """Schema for favorite response data"""
    favorite_id: UUID
    user_id: UUID
    entity_type: str
    entity_id: UUID
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


class FavoriteIdsResponseSchema(BaseModel):
    """Lightweight response with favorite IDs for client sorting/highlighting"""
    plate_ids: List[UUID] = Field(default_factory=list, description="Plate IDs the user has favorited")
    restaurant_ids: List[UUID] = Field(default_factory=list, description="Restaurant IDs the user has favorited")


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

    model_config = ConfigDict(from_attributes=True)

# =============================================================================
# 3. BILLING & PAYMENTS SCHEMAS
# =============================================================================

class CreditCurrencyCreateSchema(BaseModel):
    """Schema for creating a new credit currency. Backend assigns currency_code from supported list and fetches currency_conversion_usd from open.er-api.com."""
    currency_name: str = Field(..., max_length=50)
    credit_value_local_currency: Decimal = Field(..., gt=0)


class CreditCurrencyUpdateSchema(BaseModel):
    """Schema for updating credit currency information. currency_conversion_usd is cron-managed; do not send."""
    currency_name: Optional[str] = Field(None, max_length=50)
    currency_code: Optional[str] = Field(None, max_length=10)
    credit_value_local_currency: Optional[Decimal] = Field(None, gt=0)

class CreditCurrencyResponseSchema(BaseModel):
    """Schema for credit currency response data"""
    credit_currency_id: UUID
    currency_name: str
    currency_code: str
    credit_value_local_currency: Decimal
    currency_conversion_usd: Decimal
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class CreditCurrencyEnrichedResponseSchema(BaseModel):
    """Schema for enriched credit currency response data with market information"""
    credit_currency_id: UUID
    currency_name: str
    currency_code: str
    credit_value_local_currency: Decimal
    currency_conversion_usd: Decimal
    market_id: UUID  # Market that uses this currency
    market_name: str  # country_name from market_info
    country_code: str  # from market_info
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class PlanCreateSchema(BaseModel):
    """Schema for creating a new plan"""
    market_id: UUID = Field(..., description="Market (country) this plan belongs to")
    name: str = Field(..., max_length=100)
    credit: int = Field(..., gt=0)
    price: float = Field(..., ge=0)
    rollover: Optional[bool] = True
    rollover_cap: Optional[Decimal] = None

class PlanUpdateSchema(BaseModel):
    """Schema for updating plan information"""
    market_id: Optional[UUID] = Field(None, description="Market (country) this plan belongs to")
    name: Optional[str] = Field(None, max_length=100)
    credit: Optional[int] = Field(None, gt=0)
    price: Optional[float] = Field(None, ge=0)
    rollover: Optional[bool] = None
    rollover_cap: Optional[Decimal] = None
    status: Optional[Status] = None

class PlanResponseSchema(BaseModel):
    """Schema for plan response data"""
    plan_id: UUID
    market_id: UUID
    name: str
    credit: int
    price: float
    credit_cost_local_currency: float  # price / credit (local currency per credit)
    credit_cost_usd: float
    status: Status
    rollover: bool
    rollover_cap: Optional[Decimal]
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class PlanEnrichedResponseSchema(BaseModel):
    """Schema for enriched plan response data with currency name and code"""
    plan_id: UUID
    market_id: UUID
    market_name: str  # country_name from market_info
    country_code: str  # from market_info
    currency_name: str
    currency_code: str
    name: str
    credit: int
    price: float
    credit_cost_local_currency: float  # price / credit (local currency per credit)
    credit_cost_usd: float
    rollover: bool
    rollover_cap: Optional[Decimal]
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class SubscriptionEnrichedResponseSchema(BaseModel):
    """Schema for enriched subscription response data with user, plan, and market information"""
    subscription_id: UUID
    user_id: UUID
    user_full_name: str
    user_username: str
    user_email: str
    user_status: Status
    user_mobile_number: Optional[str] = None
    plan_id: UUID
    plan_name: str
    plan_credit: int
    plan_price: float
    plan_rollover: bool
    plan_rollover_cap: Optional[Decimal]
    plan_status: Status
    market_id: UUID  # Market (country) for this subscription
    market_name: str  # country_name from market_info
    country_code: str  # from market_info
    renewal_date: datetime
    balance: Decimal
    is_archived: bool
    status: Status
    subscription_status: Optional[str] = None
    hold_start_date: Optional[datetime] = None
    hold_end_date: Optional[datetime] = None
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class InstitutionBillEnrichedResponseSchema(BaseModel):
    """Schema for enriched institution bill response. Restaurants per bill via institution_settlement (not on bill)."""
    institution_bill_id: UUID
    institution_id: UUID
    institution_name: str
    institution_entity_id: UUID
    institution_entity_name: str
    credit_currency_id: UUID
    market_id: UUID  # Via credit_currency_id → market_info
    market_name: str  # country_name from market_info
    country_code: str  # from market_info
    transaction_count: Optional[int] = None
    amount: Optional[Decimal] = None
    currency_code: Optional[str] = None
    period_start: datetime
    period_end: datetime
    is_archived: bool
    status: Status
    resolution: str
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

# =============================================================================
# 4. LOCATION & ADDRESS SCHEMAS
# =============================================================================

class AddressCreateSchema(BaseModel):
    """Schema for creating a new address. address_type is ignored by the backend and derived from linkages.
    institution_id and user_id are optional for B2C (Customer); backend sets from JWT. For B2B they are required and must be sent by the client.
    When place_id is provided (from suggest selection), all address fields are ignored and backend fetches Place Details."""
    place_id: Optional[str] = Field(None, description="Google Place ID from suggest; when set, address fields are ignored and Place Details are fetched")
    institution_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    employer_id: Optional[UUID] = None  # Links address to employer (nullable)
    address_type: Optional[List[str]] = Field(
        None,
        description="Read-only: ignored on create. Backend derives address_type from connected objects (restaurant, bank account, employer, payment method).",
    )

    @field_validator("address_type")
    @classmethod
    def validate_address_types_if_provided(cls, v):
        """If client sends address_type, validate format only; backend will ignore and derive."""
        from app.config.enums.address_types import AddressType
        if v is None or not v:
            return v
        for addr_type in v:
            if not AddressType.is_valid(addr_type):
                valid_types = ", ".join(AddressType.values())
                raise ValueError(f"Invalid address_type '{addr_type}'. Must be one of: {valid_types}")
        if len(v) != len(set(v)):
            raise ValueError("address_type cannot contain duplicate values")
        return v

    is_default: bool = False
    floor: Optional[str] = Field(None, max_length=50)
    country_code: Optional[str] = Field(None, min_length=2, max_length=3, description="ISO 3166-1 alpha-2 or alpha-3 (e.g. AR or ARG). API normalizes to alpha-2 (uppercase).")
    country: Optional[str] = Field(None, max_length=100, description="Country name (e.g. Argentina); used to derive country_code when form has only 'country'")
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    street_type: Optional[str] = Field(None, max_length=50, description="Street type code from GET /api/v1/enums/ (e.g. St, Ave, Blvd)")
    street_name: Optional[str] = Field(None, max_length=100)
    building_number: Optional[str] = Field(None, max_length=20)
    apartment_unit: Optional[str] = Field(None, max_length=20)
    assign_employer: Optional[bool] = Field(
        True,
        description="If True (default), assign the employer to the current user when adding address. Only applies to Customers. Internal/Suppliers ignore this parameter. Can be set to False to opt-out of assignment."
    )
    # timezone is automatically assigned based on country_code/city - not required in API
    # country_name is resolved from market_info via country_code (not stored on address)

    @field_validator("country_code", "country")
    @classmethod
    def empty_str_to_none_country(cls, v):
        if v is not None and isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("country_code")
    @classmethod
    def normalize_country_code_create(cls, v):
        """Normalize country_code at API boundary (uppercase, max 2 chars)."""
        if v is None:
            return None
        n = normalize_country_code(v)
        return n if n else None

    @field_validator('street_type')
    @classmethod
    def validate_street_type(cls, v):
        """Validate that street_type is a valid enum value when provided"""
        from app.config.enums.street_types import StreetType
        if v is None or not str(v).strip():
            return v
        if not StreetType.is_valid(str(v).strip()):
            valid_types = ', '.join(StreetType.values())
            raise ValueError(f"Invalid street_type '{v}'. Must be one of: {valid_types}")
        return str(v).strip()

    @model_validator(mode="after")
    def require_country_or_place_id(self):
        place_id = (self.place_id or "").strip() if hasattr(self, "place_id") else ""
        if place_id:
            return self
        cc = (self.country_code or "").strip() if hasattr(self, "country_code") else ""
        cn = (self.country or "").strip() if hasattr(self, "country") else ""
        if not cc and not cn:
            raise ValueError("Either country_code or country (country name) must be provided, or use place_id from suggest")
        for field in ("province", "city", "postal_code", "street_type", "street_name", "building_number"):
            val = getattr(self, field, None) or ""
            if not str(val).strip():
                raise ValueError(f"{field} is required when place_id is not provided")
        return self


class AddressUpdateSchema(BaseModel):
    """Schema for updating address. Only floor, apartment_unit, is_default (subpremise) are editable. Address core is immutable."""
    floor: Optional[str] = Field(None, max_length=50)
    apartment_unit: Optional[str] = Field(None, max_length=20)
    is_default: Optional[bool] = None


class CityResponseSchema(BaseModel):
    """Schema for city response (from city_info). Used for employer address scoping and user profile."""
    city_id: UUID
    name: str
    country_code: str
    province_code: Optional[str] = None
    is_archived: bool
    status: Status

    model_config = ConfigDict(from_attributes=True)


class SupportedCitySchema(BaseModel):
    """One supported city for dropdowns (e.g. user onboarding, employer address filter)."""
    city_id: UUID
    city_name: str = Field(..., description="City name (e.g. Lima, Buenos Aires)")
    country_code: str = Field(..., description="ISO 3166-1 alpha-2 code (e.g. PE, AR)")


class AddressResponseSchema(BaseModel):
    """Schema for address response data"""
    address_id: UUID
    institution_id: UUID
    user_id: Optional[UUID] = None
    employer_id: Optional[UUID] = None  # Links address to employer (nullable)
    address_type: List[str]
    is_default: bool
    floor: Optional[str]
    country_name: str
    country_code: str
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

    model_config = ConfigDict(from_attributes=True)

class AddressEnrichedResponseSchema(BaseModel):
    """Schema for enriched address response data with institution name and user details.
    formatted_address is a single display line (street_name · city · postal_code) for pickers/dropdowns."""
    address_id: UUID
    institution_id: UUID
    institution_name: str
    user_id: Optional[UUID] = None
    user_username: Optional[str] = None
    user_first_name: Optional[str] = None
    user_last_name: Optional[str] = None
    user_full_name: str = ""  # Empty when no user
    employer_id: Optional[UUID] = None  # Links address to employer (nullable)
    address_type: List[str]
    is_default: bool
    floor: Optional[str]
    country_name: str
    country_code: str
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
    formatted_address: str = Field(
        ...,
        description="Single-line display label: street_name · city · postal_code (for dropdowns/pickers)"
    )

    model_config = ConfigDict(from_attributes=True)


# --- Address autocomplete (suggest / validate) ---

class AddressSuggestionSchema(BaseModel):
    """One address suggestion from GET /addresses/suggest. Autocomplete only – client selects and sends place_id on create."""
    place_id: str = Field(..., description="Google Place ID for Place Details on create")
    display_text: str = Field(..., description="Human-readable text for dropdown (e.g. '123 Main St, City, Country')")
    country_code: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 when country filter was applied (e.g. AR)")


class AddressSuggestResponseSchema(BaseModel):
    """Response for GET /api/v1/addresses/suggest."""
    suggestions: List[AddressSuggestionSchema] = Field(default_factory=list)


class RestaurantEnrichedResponseSchema(BaseModel):
    """Schema for enriched restaurant response data with institution, entity, and address details"""
    restaurant_id: UUID
    institution_id: UUID
    institution_name: str
    institution_entity_id: UUID
    institution_entity_name: str
    address_id: UUID
    country_name: str
    country_code: str
    province: str
    city: str
    postal_code: str
    credit_currency_id: UUID
    market_credit_value_local_currency: Decimal = Field(
        ...,
        description="Credit value in local currency for this market; use for live calculation of expected_payout_local_currency when creating plates (credit × market_credit_value_local_currency)",
    )
    name: str
    cuisine: Optional[str]
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

class RestaurantBalanceEnrichedResponseSchema(BaseModel):
    """Schema for enriched restaurant balance response data with institution, entity, restaurant, and address details (read-only)"""
    restaurant_id: UUID
    institution_id: UUID
    institution_name: str
    institution_entity_id: UUID
    institution_entity_name: str
    restaurant_name: str
    country_name: str
    country_code: str
    credit_currency_id: UUID
    transaction_count: int
    balance: Decimal
    currency_code: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

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
    country_name: str
    country_code: str
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

    model_config = ConfigDict(from_attributes=True)

class QRCodeEnrichedResponseSchema(BaseModel):
    """Schema for enriched QR code response data with institution, restaurant, and address details"""
    qr_code_id: UUID
    restaurant_id: UUID
    restaurant_name: str
    institution_id: UUID
    institution_name: str
    country_name: str
    country_code: str
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

    model_config = ConfigDict(from_attributes=True)


class QRCodePrintContextSchema(BaseModel):
    """QR + restaurant + raw address fields for supplier print HTML (image loaded separately)."""

    qr_code_id: UUID
    restaurant_id: UUID
    restaurant_name: str
    country_code: str
    street_type: Optional[str] = None
    street_name: Optional[str] = None
    building_number: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    country_name: Optional[str] = None
    image_storage_path: str

    model_config = ConfigDict(from_attributes=True)


class EmployerCreateSchema(BaseModel):
    """Schema for creating a new employer with embedded address"""
    name: str = Field(..., max_length=100, description="Employer company name")
    address: 'AddressCreateSchema' = Field(..., description="Complete address information for the employer location")
    assign_employer: bool = Field(
        True,
        description="If True (default), assign this employer to the current user after creation. Only applies to Customers. Internal/Suppliers ignore this parameter."
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

    model_config = ConfigDict(from_attributes=True)

class EmployerEnrichedResponseSchema(BaseModel):
    """Schema for enriched employer response data with address details"""
    employer_id: UUID
    name: str
    address_id: UUID
    address_country: Optional[str] = None
    address_country_code: Optional[str] = None
    address_province: Optional[str] = None
    address_city: Optional[str] = None
    address_postal_code: Optional[str] = None
    address_street_type: Optional[str] = None
    address_street_name: Optional[str] = None
    address_building_number: Optional[str] = None
    address_display: Optional[str] = None
    address_floor: Optional[str] = None
    address_apartment_unit: Optional[str] = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

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
    address_display: Optional[str] = None
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

    model_config = ConfigDict(from_attributes=True)
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
    pickup_intent: Optional[Literal["offer", "request", "self"]] = Field("self", description="offer=volunteer to pick up; request=need someone; self=pick up own")
    flexible_on_time: Optional[bool] = Field(None, description="Only when pickup_intent=request; ±30 min flexibility")

class PlateSelectionUpdateSchema(BaseModel):
    """Schema for updating plate selection information"""
    plate_id: Optional[UUID] = None
    restaurant_id: Optional[UUID] = None
    product_id: Optional[UUID] = None
    qr_code_id: Optional[UUID] = None
    credit: Optional[int] = Field(None, gt=0, description="Credit amount required")
    kitchen_day: Optional[KitchenDay] = None
    pickup_time_range: Optional[str] = Field(None, max_length=50)
    pickup_intent: Optional[Literal["offer", "request", "self"]] = None
    flexible_on_time: Optional[bool] = None
    cancel: Optional[bool] = Field(None, description="If true, cancel selection and refund credits")

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
    pickup_date: date = Field(..., description="Calendar date of pickup (YYYY-MM-DD)")
    pickup_time_range: str
    pickup_intent: Optional[str] = "self"
    flexible_on_time: Optional[bool] = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime
    plate_pickup_id: Optional[UUID] = Field(None, description="Present on create; use for Complete order and plate review")
    editable_until: Optional[datetime] = Field(None, description="Cutoff for edits; 1 hour before kitchen day opens")

    model_config = ConfigDict(from_attributes=True)


class DuplicateKitchenDayDetail(BaseModel):
    """Structured 409 response when user tries to reserve a second plate for same kitchen day"""
    code: Literal["DUPLICATE_KITCHEN_DAY"]
    kitchen_day: str
    existing_plate_selection_id: str  # UUID string
    message: str


class NotifyCoworkersRequest(BaseModel):
    """Request body for POST /plate-selections/{id}/notify-coworkers"""
    user_ids: List[UUID] = Field(..., description="List of coworker user_ids to notify")


class CoworkerEligibilityItem(BaseModel):
    """Single coworker with eligibility for pickup notification"""
    user_id: UUID
    first_name: str
    last_initial: str
    eligible: bool
    ineligibility_reason: Optional[str] = None  # When eligible=false: "already_ordered_different_restaurant" | "already_ordered_different_pickup_time"


class CoworkerEligibilityResponse(RootModel[List[CoworkerEligibilityItem]]):
    """Response for GET /plate-selections/{id}/coworkers - list of coworkers with eligibility"""


class NotifyCoworkersResponse(BaseModel):
    """Response for POST /plate-selections/{id}/notify-coworkers"""
    notified_count: int

# =============================================================================
# 6. ADMIN & DISCRETIONARY SCHEMAS
# =============================================================================

class DiscretionaryCreateSchema(BaseModel):
    """Schema for creating a new discretionary request"""
    user_id: Optional[UUID] = None
    restaurant_id: Optional[UUID] = None
    category: DiscretionaryReason  # Classification: Marketing Campaign, Credit Refund, etc.
    reason: Optional[str] = Field(None, max_length=500)  # Free-form explanation
    amount: Decimal = Field(..., gt=0)
    comment: Optional[str] = Field(None, max_length=500)
    institution_id: Optional[UUID] = Field(None, description="Optional: validate selected user/restaurant belongs to this institution")
    market_id: Optional[UUID] = Field(None, description="Optional: validate selected user/restaurant belongs to this market")
    
    @model_validator(mode="after")
    def validate_user_or_restaurant(self):
        """Ensure either user_id or restaurant_id is provided (mutually exclusive)"""
        user_id = self.user_id
        restaurant_id = self.restaurant_id

        if not user_id and not restaurant_id:
            raise ValueError("Either user_id or restaurant_id must be provided")

        if user_id and restaurant_id:
            raise ValueError("Cannot specify both user_id and restaurant_id")

        return self

    @model_validator(mode="after")
    def validate_restaurant_requirement(self):
        """Validate that restaurant_id is provided for restaurant-specific categories"""
        restaurant_id = self.restaurant_id
        category = self.category

        if category:
            restaurant_required = [
                DiscretionaryReason.ORDER_INCORRECTLY_MARKED,
                DiscretionaryReason.FULL_ORDER_REFUND
            ]

            if category in restaurant_required and not restaurant_id:
                raise ValueError(
                    f"Category '{category.value}' requires restaurant_id to be specified"
                )

        return self

class DiscretionaryUpdateSchema(BaseModel):
    """Schema for updating discretionary request information"""
    user_id: Optional[UUID] = None
    restaurant_id: Optional[UUID] = None
    category: Optional[DiscretionaryReason] = None  # Classification enum
    reason: Optional[str] = Field(None, max_length=500)  # Free-form explanation
    amount: Optional[Decimal] = Field(None, gt=0)
    comment: Optional[str] = Field(None, max_length=500)

class DiscretionaryResponseSchema(BaseModel):
    """Schema for discretionary request response data"""
    discretionary_id: UUID
    user_id: Optional[UUID] = None  # NULL for Supplier requests, required for Client requests
    restaurant_id: Optional[UUID] = None  # NULL for Client requests, required for Supplier requests
    approval_id: Optional[UUID]
    category: DiscretionaryReason  # Classification enum
    reason: Optional[str]  # Free-form explanation
    amount: Decimal
    comment: Optional[str]
    is_archived: bool
    status: str = Field(..., description="DiscretionaryStatus: Pending, Cancelled, Approved, Rejected")
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class DiscretionaryEnrichedResponseSchema(BaseModel):
    """Schema for enriched discretionary request response data with user, restaurant, institution, and market information"""
    discretionary_id: UUID
    user_id: Optional[UUID] = None  # NULL for Supplier requests
    user_full_name: Optional[str] = None  # For Customer requests (recipient)
    user_username: Optional[str] = None  # For Customer requests (recipient)
    restaurant_id: Optional[UUID] = None  # NULL for Client requests
    restaurant_name: Optional[str] = None  # For Supplier requests
    institution_id: UUID
    institution_name: str
    credit_currency_id: Optional[UUID] = None  # NULL for Client requests (no restaurant)
    currency_name: Optional[str] = None
    currency_code: Optional[str] = None
    market_id: Optional[UUID] = None  # Via credit_currency_id → market_info; NULL for Client
    market_name: Optional[str] = None  # country_name from market_info
    country_code: Optional[str] = None  # from market_info
    approval_id: Optional[UUID]
    category: DiscretionaryReason  # Classification enum
    reason: Optional[str]  # Free-form explanation
    amount: Decimal
    comment: Optional[str]
    is_archived: bool
    status: str = Field(..., description="DiscretionaryStatus: Pending, Cancelled, Approved, Rejected")
    created_date: datetime
    modified_date: datetime
    created_by: Optional[UUID] = None  # user_id of creator (derived from discretionary_history CREATE row)
    created_by_name: Optional[str] = None  # display name of creator for table

    model_config = ConfigDict(from_attributes=True)

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
    """Schema for discretionary request summary (dashboard view). Enriched fields from super-admin endpoints."""
    discretionary_id: UUID
    user_id: Optional[UUID] = None  # NULL for Supplier requests, required for Client requests
    restaurant_id: Optional[UUID] = None  # NULL for Supplier requests, required for Client requests
    category: DiscretionaryReason  # Classification enum
    reason: Optional[str]  # Free-form explanation
    amount: Decimal
    status: str = Field(..., description="DiscretionaryStatus: Pending, Cancelled, Approved, Rejected")
    created_date: datetime
    resolved_date: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
    resolution_comment: Optional[str] = None
    # Enriched (super-admin pending-requests / requests): creator and recipient
    created_by: Optional[UUID] = None  # user_id of creator (from discretionary_history CREATE)
    created_by_name: Optional[str] = None  # display name of creator
    user_full_name: Optional[str] = None  # recipient (Customer requests)
    user_username: Optional[str] = None   # recipient (Customer requests)
    restaurant_name: Optional[str] = None # recipient (Supplier requests)

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
    credit_currency_id: UUID
    tax_id: str
    name: str
    stripe_connect_account_id: Optional[str] = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class InstitutionEntityEnrichedResponseSchema(BaseModel):
    """Schema for enriched institution entity response data with institution, address, and market details"""
    institution_entity_id: UUID
    institution_id: UUID
    institution_name: str
    credit_currency_id: UUID
    market_id: UUID  # Via address country → market
    market_name: str  # country_name from market_info
    country_code: str  # from market_info
    address_id: UUID
    address_country_name: str
    address_country_code: str
    address_province: str
    address_city: str
    tax_id: str
    name: str
    stripe_connect_account_id: Optional[str] = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionBillPayoutResponseSchema(BaseModel):
    """Schema for a single payout attempt on an institution bill. Provider transfer details included once created."""
    bill_payout_id: UUID
    institution_bill_id: UUID
    provider: str
    provider_transfer_id: Optional[str] = None
    amount: Decimal
    currency_code: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# 8. NATIONAL HOLIDAYS SCHEMAS
# =============================================================================

class NationalHolidayCreateSchema(BaseModel):
    """Schema for creating a national holiday"""
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code (e.g., 'US', 'AR')")
    holiday_name: str = Field(..., max_length=100, description="Name of the holiday")
    holiday_date: date = Field(..., description="Date of the holiday")
    is_recurring: bool = Field(False, description="Whether this holiday recurs annually")
    recurring_month: Optional[int] = Field(None, ge=1, le=12, description="Month for recurring holidays (1-12)")
    recurring_day: Optional[int] = Field(None, ge=1, le=31, description="Day for recurring holidays (1-31)")
    status: Optional[Status] = Field(default=None, description="Optional; omit or null and backend assigns default (Active)")
    
    @model_validator(mode="after")
    def validate_recurring_complete(self):
        """Ensure both recurring_month and recurring_day are provided when is_recurring is True"""
        if self.is_recurring and (self.recurring_month is None or self.recurring_day is None):
            raise ValueError("Both recurring_month and recurring_day are required when is_recurring is True")
        return self

class NationalHolidayUpdateSchema(BaseModel):
    """Schema for updating a national holiday"""
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    holiday_name: Optional[str] = Field(None, max_length=100)
    holiday_date: Optional[date] = None
    is_recurring: Optional[bool] = None
    recurring_month: Optional[int] = Field(None, ge=1, le=12)
    recurring_day: Optional[int] = Field(None, ge=1, le=31)
    status: Optional[Status] = Field(None, description="Status of the holiday")
    
    @model_validator(mode="after")
    def validate_recurring_complete(self):
        """Ensure both recurring_month and recurring_day are provided when is_recurring is set to True"""
        if self.is_recurring is True and (self.recurring_month is None or self.recurring_day is None):
            raise ValueError("Both recurring_month and recurring_day are required when is_recurring is True")
        return self

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
    source: str = Field(..., description="'manual' | 'nager_date' — client creates are always manual")
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)

class NationalHolidayBulkCreateSchema(BaseModel):
    """Schema for bulk creating national holidays"""
    holidays: List[NationalHolidayCreateSchema] = Field(..., min_length=1, description="List of holidays to create")
    
    @field_validator('holidays')
    @classmethod
    def validate_holidays_not_empty(cls, v):
        """Ensure at least one holiday is provided"""
        if not v:
            raise ValueError("At least one holiday must be provided")
        return v


class NationalHolidaySyncFromProviderSchema(BaseModel):
    """Optional body for POST /national-holidays/sync-from-provider (Nager.Date import)."""
    years: Optional[List[int]] = Field(
        None,
        description="UTC-bounded calendar years to import; omit for default (current + next year, clamped)",
    )


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
    
    model_config = ConfigDict(from_attributes=True)


class OrderSummarySchema(BaseModel):
    """Schema for order summary statistics"""
    total_orders: int = Field(..., description="Total number of orders")
    pending: int = Field(..., description="Number of pending orders (not yet arrived)")
    arrived: int = Field(..., description="Number of arrived orders (waiting for pickup)")
    completed: int = Field(..., description="Number of completed orders")
    
    model_config = ConfigDict(from_attributes=True)


class RestaurantDailyOrdersSchema(BaseModel):
    """Schema for a restaurant's daily orders"""
    restaurant_id: UUID = Field(..., description="Restaurant UUID")
    restaurant_name: str = Field(..., description="Restaurant name")
    orders: List[DailyOrderItemSchema] = Field(..., description="List of orders for this restaurant")
    summary: OrderSummarySchema = Field(..., description="Summary statistics for this restaurant")
    
    model_config = ConfigDict(from_attributes=True)


class DailyOrdersResponseSchema(BaseModel):
    """Schema for daily orders response"""
    order_date: date = Field(..., description="Date of the orders")
    restaurants: List[RestaurantDailyOrdersSchema] = Field(..., description="List of restaurants with their orders")
    
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Market Schemas
# =============================================================================

class MarketResponseSchema(BaseModel):
    """Schema for market response (country-based subscription markets)"""
    market_id: UUID = Field(..., description="Unique identifier for the market")
    country_name: str = Field(..., description="Full country name (e.g., 'Argentina')")
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code (e.g., 'AR')")
    credit_currency_id: UUID = Field(..., description="FK to credit_currency_info")
    currency_code: Optional[str] = Field(None, description="Currency code (enriched from JOIN)")
    currency_name: Optional[str] = Field(None, description="Currency name (enriched from JOIN)")
    credit_value_local_currency: Optional[Decimal] = Field(
        None,
        description="Local currency amount per credit (from credit_currency_info). Use for plan form preview: credit_cost_local_currency = price / credit.",
    )
    currency_conversion_usd: Optional[Decimal] = Field(
        None,
        description="Local units per 1 USD (from credit_currency_info). Use for plan form preview: credit_cost_usd = credit_cost_local_currency / currency_conversion_usd.",
    )
    timezone: str = Field(..., description="Timezone for this market (e.g., 'America/Argentina/Buenos_Aires')")
    kitchen_close_time: str = Field(..., description="Order cutoff time (HH:MM local, e.g. 13:30)")
    language: str = Field("en", description="Default UI locale for this market: en, es, pt")
    phone_dial_code: Optional[str] = Field(None, description="E.164 dial code prefix for this market (e.g. '+54'). Use as default country in phone input fields.")
    phone_local_digits: Optional[int] = Field(None, description="Max digits in the national number after the dial code. Use as maxLength hint for phone input (e.g. 10).")
    is_archived: bool = Field(..., description="Whether this market is archived")
    status: Status = Field(..., description="Market status (Active/Inactive)")
    created_date: datetime = Field(..., description="When this market was created")
    modified_date: datetime = Field(..., description="When this market was last modified")

    @field_validator("kitchen_close_time", mode="before")
    @classmethod
    def parse_kitchen_close_time(cls, v):
        """Convert time object to HH:MM string for API responses."""
        if v is None:
            return "13:30"
        if hasattr(v, "strftime"):
            return v.strftime("%H:%M")
        return str(v)

    model_config = ConfigDict(from_attributes=True)


class MarketPublicMinimalSchema(BaseModel):
    """Minimal schema for public GET /leads/markets (no auth). country_code, country_name, language, and phone prefix for B2C pre-auth locale and signup form."""
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 (e.g. AR)")
    country_name: str = Field(..., description="Full country name (e.g. Argentina)")
    language: str = Field(..., min_length=2, max_length=5, description="Default UI locale for this market: en, es, pt")
    phone_dial_code: Optional[str] = Field(None, description="E.164 dial code prefix (e.g. '+54'). Use as default country in phone input fields.")
    phone_local_digits: Optional[int] = Field(None, description="Max digits in the national number after the dial code. Use as maxLength hint for phone input (e.g. 10).")


class MarketPublicResponseSchema(BaseModel):
    """Full market schema for authenticated endpoints. For unauthenticated /leads/markets use MarketPublicMinimalSchema."""
    market_id: UUID = Field(..., description="Unique identifier for the market")
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 (e.g. AR)")
    country_name: str = Field(..., description="Full country name (e.g. Argentina)")
    timezone: str = Field(..., description="Timezone for this market")
    kitchen_close_time: str = Field(..., description="Order cutoff time (HH:MM local, e.g. 13:30)")
    language: str = Field("en", description="Default UI locale for this market: en, es, pt")
    phone_dial_code: Optional[str] = Field(None, description="E.164 dial code prefix (e.g. '+54'). Use as default country in phone input fields.")
    phone_local_digits: Optional[int] = Field(None, description="Max digits in the national number after the dial code. Use as maxLength hint for phone input (e.g. 10).")
    currency_code: Optional[str] = Field(None, description="Currency code")
    currency_name: Optional[str] = Field(None, description="Currency name")

    @field_validator("kitchen_close_time", mode="before")
    @classmethod
    def parse_kitchen_close_time(cls, v):
        """Convert time object to HH:MM string for API responses."""
        if v is None:
            return "13:30"
        if hasattr(v, "strftime"):
            return v.strftime("%H:%M")
        return str(v)

    model_config = ConfigDict(from_attributes=True)


class MarketCreateSchema(BaseModel):
    """Schema for creating a new market. country_name is derived from country_code by the backend."""
    country_code: str = Field(..., description="ISO 3166-1 alpha-2 or alpha-3 (e.g. AR, ARG, DE, DEU). API normalizes to alpha-2.", min_length=2, max_length=3)
    credit_currency_id: UUID = Field(..., description="FK to credit_currency_info")
    timezone: str = Field(..., description="Timezone (e.g., 'America/Argentina/Buenos_Aires')", max_length=50)
    kitchen_close_time: Optional[str] = Field(None, description="Order cutoff time (HH:MM local, e.g. 13:30). Default 13:30 if omitted.")
    status: Optional[Status] = Field(default=None, description="Optional; omit or null and backend assigns default (Active)")
    language: Optional[str] = Field(None, min_length=2, max_length=5, description="Default UI locale: en, es, pt; derived from country if omitted")
    phone_dial_code: Optional[str] = Field(None, max_length=6, description="E.164 dial code prefix (e.g. '+54'). Derived from country_code if omitted.")
    phone_local_digits: Optional[int] = Field(None, description="Max digits in the national number after the dial code (e.g. 10).")

    @field_validator("country_code")
    @classmethod
    def normalize_country_code_create(cls, v):
        """Normalize country_code at API boundary (uppercase, max 2 chars)."""
        return normalize_country_code(v) if v else v

    @field_validator("language")
    @classmethod
    def validate_market_language_create(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = tuple(settings.SUPPORTED_LOCALES)
        if v not in allowed:
            raise ValueError(f"Unsupported language '{v}'. Must be one of: {', '.join(allowed)}")
        return v

    @field_validator("kitchen_close_time")
    @classmethod
    def validate_kitchen_close_time_format(cls, v):
        """Validate HH:MM format (00:00-23:59)."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return v
        import re
        if not re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", v.strip()):
            raise ValueError("kitchen_close_time must be HH:MM format (e.g. 13:30)")
        return v.strip()


class MarketUpdateSchema(BaseModel):
    """Schema for updating a market. When country_code is provided, country_name is derived by the backend."""
    country_code: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 or alpha-3. API normalizes to alpha-2.", min_length=2, max_length=3)
    credit_currency_id: Optional[UUID] = Field(None, description="FK to credit_currency_info")
    timezone: Optional[str] = Field(None, description="Timezone", max_length=50)
    kitchen_close_time: Optional[str] = Field(None, description="Order cutoff time (HH:MM local, e.g. 13:30)")
    status: Optional[Status] = Field(None, description="Market status")
    is_archived: Optional[bool] = Field(None, description="Archive status")
    language: Optional[str] = Field(None, min_length=2, max_length=5, description="Default UI locale: en, es, pt")
    phone_dial_code: Optional[str] = Field(None, max_length=6, description="E.164 dial code prefix (e.g. '+54').")
    phone_local_digits: Optional[int] = Field(None, description="Max digits in the national number after the dial code (e.g. 10).")

    @field_validator("country_code")
    @classmethod
    def normalize_country_code_update(cls, v):
        """Normalize country_code at API boundary (uppercase, max 2 chars)."""
        if v is None:
            return None
        n = normalize_country_code(v)
        return n if n else None

    @field_validator("language")
    @classmethod
    def validate_market_language_update(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = tuple(settings.SUPPORTED_LOCALES)
        if v not in allowed:
            raise ValueError(f"Unsupported language '{v}'. Must be one of: {', '.join(allowed)}")
        return v

    @field_validator("kitchen_close_time")
    @classmethod
    def validate_kitchen_close_time_format(cls, v):
        """Validate HH:MM format (00:00-23:59)."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return v
        import re
        if not re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", v.strip()):
            raise ValueError("kitchen_close_time must be HH:MM format (e.g. 13:30)")
        return v.strip()


# =============================================================================
# PHONE VALIDATION (no auth — real-time form feedback)
# =============================================================================

class PhoneValidateRequestSchema(BaseModel):
    """Request schema for POST /api/v1/phone/validate."""
    mobile_number: str = Field(..., description="Raw phone number string (E.164 or local format)")
    country_code: Optional[str] = Field(None, min_length=2, max_length=3, description="ISO 3166-1 alpha-2 hint (e.g. 'AR'). Helps parse local-format numbers without the dial code.")


class PhoneValidateResponseSchema(BaseModel):
    """Response schema for POST /api/v1/phone/validate. Always returns 200; valid indicates whether the number is valid."""
    valid: bool = Field(..., description="True if the number is valid and parseable")
    e164: Optional[str] = Field(None, description="Normalized E.164 form (e.g. '+5491112345678'). Present only when valid=true.")
    display: Optional[str] = Field(None, description="International display form (e.g. '+54 9 11 2345-6789'). Present only when valid=true.")
    error: Optional[str] = Field(None, description="Human-readable error message. Present only when valid=false.")


# =============================================================================
# LEAD ZIPCODE METRICS (no auth)
# =============================================================================

class ZipcodeCenterSchema(BaseModel):
    """Lat/lng center for a matched zipcode area."""
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")


# Resolve forward ref so RestaurantsByCityResponseSchema.center validates at runtime (ZipcodeCenterSchema defined above)
RestaurantsByCityResponseSchema.model_rebuild()


class ZipcodeMetricsResponseSchema(BaseModel):
    """Response for GET /api/v1/leads/zipcode-metrics (unauthenticated lead flow). Geolocation (center) removed for unauthenticated endpoints."""
    requested_zipcode: str = Field(..., description="Zipcode the lead entered")
    matched_zipcode: str = Field(..., description="Zipcode used for the count (exact or closest match)")
    restaurant_count: int = Field(..., description="Number of restaurants in the matched zipcode")
    has_coverage: bool = Field(..., description="True if restaurant_count > 0")


class LeadsCitiesResponseSchema(BaseModel):
    """Response for GET /api/v1/leads/cities (unauthenticated lead flow — cities we serve)."""
    cities: List[str] = Field(..., description="City names that have at least one restaurant in the country")


class EmailRegisteredResponseSchema(BaseModel):
    """Response for GET /api/v1/leads/email-registered (lead flow — check if email is already registered)."""
    registered: bool = Field(..., description="True if a user with this email exists; false otherwise.")


class CityMetricsResponseSchema(BaseModel):
    """Response for GET /api/v1/leads/city-metrics (unauthenticated lead flow, city-first). Geolocation (center) removed for unauthenticated endpoints."""
    requested_city: str = Field(..., description="City name the lead entered")
    matched_city: str = Field(..., description="City used for the count (case-insensitive match or same as requested)")
    restaurant_count: int = Field(..., description="Number of restaurants in the matched city")
    has_coverage: bool = Field(..., description="True if restaurant_count > 0")


# =============================================================================
# ENUM SERVICE SCHEMAS
# =============================================================================

class EnumLabeledValuesSchema(BaseModel):
    """Canonical enum codes plus display labels for a given `language` query param."""
    values: List[str] = Field(..., description="Canonical codes stored in DB / API")
    labels: Dict[str, str] = Field(..., description="Map of code -> display label for requested language (fallback: en, then code)")


class EnumsResponseSchema(RootModel[Dict[str, EnumLabeledValuesSchema]]):
    """
    All system enums as a map of enum name -> { values, labels }.
    Keys vary by role (e.g. Customers omit role_type / role_name).
    """
    root: Dict[str, EnumLabeledValuesSchema]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "street_type": {
                    "values": ["St", "Ave", "Blvd"],
                    "labels": {"St": "Street", "Ave": "Avenue", "Blvd": "Boulevard"},
                }
            }
        }
    )

