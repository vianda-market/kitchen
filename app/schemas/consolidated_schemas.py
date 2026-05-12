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

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    RootModel,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)

from app.config import (
    DiscretionaryReason,
    KitchenDay,
    RoleName,
    RoleType,
    Status,
    TransactionType,
)
from app.config.enums import (
    DietaryFlag,
    FavoriteEntityType,
    NationalHolidaySource,
    PaymentAttemptStatus,
    PaymentFrequency,
    PaymentProvider,
)
from app.config.settings import settings
from app.i18n.envelope import I18nValueError
from app.schemas.types import MoneyDecimal, NullableMoneyDecimal
from app.utils.country import normalize_country_code
from app.utils.phone import normalize_mobile_for_schema

# =============================================================================
# 1. CORE ENTITIES SCHEMAS
# =============================================================================


class UserCreateSchema(BaseModel):
    """Schema for creating a new user. institution_id is optional for Customer+Comensal (backend assigns Vianda Customers). market_id optional: backend defaults to Global for Admin/Super Admin/Supplier Admin, required for Manager/Operator. market_ids (v2) optional: list of assigned markets (first is primary). Omit password to trigger B2B invite flow (email with link to set password)."""

    institution_id: UUID | None = None
    role_type: RoleType
    role_name: RoleName
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str | None = Field(
        None, min_length=8, description="Optional. Omit to trigger B2B invite flow; user sets password via email link."
    )

    @field_validator("username", "email", mode="before")
    @classmethod
    def normalize_username_email_lowercase(cls, v):
        """Normalize username and email to lowercase for case-insensitive uniqueness."""
        if v is None or not isinstance(v, str):
            return v
        return v.strip().lower()

    first_name: str | None = Field(None, max_length=50)
    last_name: str | None = Field(None, max_length=50)
    mobile_number: str | None = Field(default=None)
    employer_entity_id: UUID | None = None
    workplace_group_id: UUID | None = None
    market_id: UUID | None = None
    city_metadata_id: UUID | None = Field(
        None, description="Primary city for scoping (FK to core.city_metadata; must match market's country)"
    )
    market_ids: list[UUID] | None = Field(None, description="v2: list of assigned market IDs (first is primary)")

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

    @field_validator("role_name")
    @classmethod
    def validate_role_combination(cls, v: RoleName, info: ValidationInfo) -> RoleName:
        """Validate that role_type and role_name combination is valid"""
        role_type = info.data.get("role_type")
        if not role_type:
            return v

        valid_combinations = {
            RoleType.INTERNAL: [
                RoleName.ADMIN,
                RoleName.SUPER_ADMIN,
                RoleName.MANAGER,
                RoleName.OPERATOR,
                RoleName.GLOBAL_MANAGER,
            ],
            RoleType.SUPPLIER: [RoleName.ADMIN, RoleName.MANAGER, RoleName.OPERATOR],
            RoleType.CUSTOMER: [RoleName.COMENSAL],
            RoleType.EMPLOYER: [RoleName.ADMIN, RoleName.MANAGER, RoleName.COMENSAL],
        }

        if v not in valid_combinations.get(role_type, []):
            raise I18nValueError(
                "validation.user.invalid_role_combination",
                role_type=role_type.value,
                role_name=v.value,
            )
        return v


class UserUpdateSchema(BaseModel):
    """Schema for updating user information. role_type, institution_id, and username are immutable (set on create only). username is the login identifier; the API ignores or rejects username in update payloads. Only Super Admin / Admin can set market_id; Managers cannot assign Global. market_ids (v2) optional: replace assigned markets (first is primary)."""

    role_name: RoleName | None = None
    username: str | None = Field(
        None, min_length=3, max_length=100, description="Ignored on update; username cannot be changed."
    )
    email: EmailStr | None = None
    first_name: str | None = Field(None, max_length=50)
    last_name: str | None = Field(None, max_length=50)
    mobile_number: str | None = Field(default=None)
    employer_entity_id: UUID | None = None
    workplace_group_id: UUID | None = None
    market_id: UUID | None = None
    city_metadata_id: UUID | None = Field(
        None, description="Primary city for scoping (FK to core.city_metadata; must match market's country)"
    )
    market_ids: list[UUID] | None = Field(None, description="v2: replace assigned market IDs (first is primary)")
    status: Literal["active", "inactive"] | None = Field(None, description="User status (active/inactive only)")
    locale: str | None = Field(None, min_length=2, max_length=5, description="ISO 639-1 UI locale: en, es, pt")

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = tuple(settings.SUPPORTED_LOCALES)
        if v not in allowed:
            raise I18nValueError(
                "validation.user.unsupported_locale",
                requested=v,
                allowed=", ".join(allowed),
            )
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

    @field_validator("role_name")
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
    """Schema for PUT /users/me/employer-entity - assign employer entity and work address to current user."""

    employer_entity_id: UUID = Field(..., description="Employer entity ID to assign (institution_entity_info)")
    address_id: UUID = Field(..., description="Address (office) where user works")
    floor: str | None = Field(
        None, max_length=50, description="Floor at this office (stored per-user in address_subpremise)"
    )
    apartment_unit: str | None = Field(
        None, max_length=20, description="Unit at this office (stored per-user in address_subpremise)"
    )


class ChangePasswordSchema(BaseModel):
    """Schema for self-service change password (PUT /users/me/password)."""

    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")
    new_password_confirm: str = Field(..., min_length=1, description="Confirm new password")

    @field_validator("new_password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info: ValidationInfo) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise I18nValueError("validation.user.passwords_do_not_match")
        return v

    @model_validator(mode="after")
    def new_password_different(self):
        if self.current_password and self.new_password and self.current_password == self.new_password:
            raise I18nValueError("validation.user.new_password_same_as_current")
        return self


class UserSearchResultSchema(BaseModel):
    """One user in GET /users/search/ response (minimal fields for discretionary recipient picker)."""

    user_id: UUID
    full_name: str
    username: str
    email: str


class UserSearchResponseSchema(BaseModel):
    """Response for GET /users/search/ (paginated list + total)."""

    results: list["UserSearchResultSchema"] = Field(..., description="Page of matching users")
    total: int = Field(..., description="Total number of matching users (for pagination)")


class AdminResetPasswordSchema(BaseModel):
    """Schema for admin reset another user's password (PUT /users/{user_id}/password)."""

    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")
    new_password_confirm: str = Field(..., min_length=1, description="Confirm new password")

    @field_validator("new_password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info: ValidationInfo) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise I18nValueError("validation.user.passwords_do_not_match")
        return v


class UserResponseSchema(BaseModel):
    """Schema for user response data. market_id is primary assigned market; market_ids (v2) lists all assigned markets."""

    user_id: UUID
    institution_id: UUID
    role_type: RoleType
    role_name: RoleName
    username: str
    email: str
    first_name: str | None
    last_name: str | None
    mobile_number: str | None = None
    mobile_number_verified: bool = False
    mobile_number_verified_at: datetime | None = None
    email_verified: bool = False
    email_verified_at: datetime | None = None
    email_change_message: str | None = Field(
        None,
        description="Set when an email change was requested: verification sent to new address; email field unchanged until verified.",
    )
    employer_entity_id: UUID | None = None
    employer_address_id: UUID | None = None
    workplace_group_id: UUID | None = None
    market_id: UUID
    city_metadata_id: UUID | None = None
    market_ids: list[UUID] = Field(default_factory=list, description="v2: all assigned market IDs (primary first)")
    locale: str = Field("en", description="ISO 639-1 UI locale: en, es, pt")
    is_archived: bool
    status: Status
    canonical_key: str | None = Field(None, description="Stable seed/fixture identifier. Null for ad-hoc users.")
    created_date: datetime
    modified_date: datetime

    @field_validator("employer_entity_id")
    @classmethod
    def employer_null_for_supplier_employee(cls, v, info: ValidationInfo):
        """Supplier, Internal, and Employer users do not have an Employer; return None in response."""
        role_type = info.data.get("role_type")
        if role_type is None:
            return v
        rt = role_type.value if hasattr(role_type, "value") else str(role_type)
        if rt in ("supplier", "internal", "employer"):
            return None
        return v

    model_config = ConfigDict(from_attributes=True)


class UserUpsertByKeySchema(BaseModel):
    """Schema for idempotent user upsert by canonical_key.

    If a user with the given canonical_key already exists it is updated in-place;
    otherwise a new user is inserted with that canonical_key.

    Use this endpoint for Postman seed runs and fixture data — NEVER for
    self-registration, customer-facing signup, or B2B invite flows (use POST
    /users or the B2C signup endpoint instead).

    Auth: Internal only (get_employee_user dependency — same tier as POST /users
    for Internal users). Returns 403 for Customer/Supplier roles.

    Password semantics:
    - On INSERT: ``password`` is REQUIRED. The plain-text value is hashed
      server-side before storage; the raw value is never persisted.
    - On UPDATE: ``password`` is OPTIONAL. When provided it is re-hashed and
      stored, replacing the existing hash. When absent, the existing password
      hash is left untouched — callers can update any other field without
      resetting authentication credentials.
    """

    canonical_key: str = Field(
        ...,
        max_length=200,
        description="Stable human-readable identifier, e.g. 'E2E_USER_SUPPLIER_ADMIN'",
    )
    institution_id: UUID = Field(..., description="Institution this user belongs to (FK to core.institution_info)")
    role_type: RoleType = Field(..., description="Role type: Supplier, Internal, Employer, Customer")
    role_name: RoleName = Field(..., description="Role name within the role_type")
    username: str = Field(..., min_length=3, max_length=100, description="Login username (must be unique)")
    email: str = Field(..., description="User email address")
    password: str | None = Field(
        None,
        min_length=8,
        description=(
            "Plain-text password. Required on INSERT; optional on UPDATE. "
            "When absent on update the existing hash is preserved."
        ),
    )
    first_name: str | None = Field(None, max_length=50)
    last_name: str | None = Field(None, max_length=50)
    mobile_number: str | None = Field(None, description="E.164 format, e.g. +15005550006")
    market_id: UUID | None = Field(None, description="Primary market ID for this user")
    city_metadata_id: UUID | None = Field(
        None,
        description=(
            "City metadata FK (core.city_metadata). Required for Customer Comensal users "
            "to resolve timezone and city. Not required for Employer/Supplier/Internal users."
        ),
    )
    employer_entity_id: UUID | None = Field(
        None,
        description=(
            "Employer entity FK (ops.institution_entity_info). "
            "For Customer Comensal users enrolled under an employer entity. "
            "Not required for Employer Admin users (they are scoped by institution_id)."
        ),
    )
    status: Status = Status.ACTIVE

    @field_validator("username", "email", mode="before")
    @classmethod
    def normalize_lowercase(cls, v: object) -> object:
        """Normalize username and email to lowercase."""
        if v is None or not isinstance(v, str):
            return v
        return v.strip().lower()

    @field_validator("role_type", mode="before")
    @classmethod
    def normalize_role_type(cls, v: object) -> object:
        """Accept role_type string case-insensitively."""
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
    def normalize_role_name(cls, v: object) -> object:
        """Accept role_name string case-insensitively."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return v
        if isinstance(v, RoleName):
            return v
        s = (v if isinstance(v, str) else str(v)).strip()
        for rn in RoleName:
            if rn.value.lower() == s.lower():
                return rn
        return v


class MessagingPreferencesResponseSchema(BaseModel):
    """Schema for messaging preferences response (GET /users/me/messaging-preferences)."""

    notify_coworker_pickup_alert: bool = Field(
        True, description="Receive push when a coworker offers to pick up your plate"
    )
    notify_plate_readiness_alert: bool = Field(True, description="Receive push when restaurant signals plate is ready")
    notify_promotions_push: bool = Field(True, description="Receive in-app push for promotions and marketing")
    notify_promotions_email: bool = Field(True, description="Receive email campaigns for promotions and marketing")
    coworkers_can_see_my_orders: bool = Field(
        True, description="Allow coworkers to see my orders in explore and coworker-facing lists"
    )
    can_participate_in_plate_pickups: bool = Field(
        True, description="I can appear on coworker list for pickup offers and volunteer"
    )

    model_config = ConfigDict(from_attributes=True)


class MessagingPreferencesUpdateSchema(BaseModel):
    """Schema for updating messaging preferences (PUT /users/me/messaging-preferences). All fields optional."""

    notify_coworker_pickup_alert: bool | None = None
    notify_plate_readiness_alert: bool | None = None
    notify_promotions_push: bool | None = None
    notify_promotions_email: bool | None = None
    coworkers_can_see_my_orders: bool | None = None
    can_participate_in_plate_pickups: bool | None = None


class UserEnrichedResponseSchema(BaseModel):
    """Schema for enriched user response. market_id is primary; market_ids (v2) lists all assigned markets. market_name and employer_name for profile display."""

    user_id: UUID
    institution_id: UUID
    institution_name: str
    role_type: RoleType
    role_name: RoleName
    username: str
    email: str
    first_name: str | None
    last_name: str | None
    full_name: str
    mobile_number: str | None = None
    mobile_number_display: str | None = Field(
        None,
        description="Internationally formatted display string (e.g. '+54 9 11 2345-6789'). Read-only; computed from mobile_number.",
    )
    mobile_number_verified: bool = False
    mobile_number_verified_at: datetime | None = None
    email_verified: bool = False
    email_verified_at: datetime | None = None
    employer_entity_id: UUID | None = None
    employer_address_id: UUID | None = None
    employer_entity_name: str | None = None
    workplace_group_id: UUID | None = None
    workplace_group_name: str | None = None
    market_id: UUID
    market_name: str
    city_metadata_id: UUID | None = None
    city_name: str | None = None
    market_ids: list[UUID] = Field(default_factory=list, description="v2: all assigned market IDs (primary first)")
    locale: str = Field("en", description="ISO 639-1 UI locale: en, es, pt")
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    @field_validator("employer_entity_id")
    @classmethod
    def employer_null_for_supplier_employee(cls, v, info: ValidationInfo):
        """Supplier, Internal, and Employer users do not have an Employer; return None in response."""
        role_type = info.data.get("role_type")
        if role_type is None:
            return v
        rt = role_type.value if hasattr(role_type, "value") else str(role_type)
        if rt in ("supplier", "internal", "employer"):
            return None
        return v

    @field_validator("employer_entity_name")
    @classmethod
    def employer_name_null_for_supplier_employee(cls, v, info: ValidationInfo):
        """Supplier, Internal, and Employer users do not have an Employer; return None in response."""
        role_type = info.data.get("role_type")
        if role_type is None:
            return v
        rt = role_type.value if hasattr(role_type, "value") else str(role_type)
        if rt in ("supplier", "internal", "employer"):
            return None
        return v

    model_config = ConfigDict(from_attributes=True)


class CustomerSignupSchema(BaseModel):
    """Schema for customer signup. country_code required (from GET /api/v1/leads/markets). Provide city_metadata_id OR city_name (backend resolves city_name → city_metadata_id via the city_metadata + external.geonames_city join)."""

    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=255)
    first_name: str | None = Field(None, max_length=50)
    last_name: str | None = Field(None, max_length=50)
    email: EmailStr
    mobile_number: str | None = Field(default=None)

    @field_validator("username", "email", mode="before")
    @classmethod
    def normalize_username_email_lowercase(cls, v):
        """Normalize username and email to lowercase for case-insensitive uniqueness."""
        if v is None or not isinstance(v, str):
            return v
        return v.strip().lower()

    country_code: str = Field(
        ...,
        min_length=2,
        max_length=3,
        description="ISO 3166-1 alpha-2 or alpha-3 (e.g. AR, US, ARG). From GET /api/v1/leads/markets. Backend resolves to market.",
    )
    city_metadata_id: UUID | None = Field(
        None,
        description="City metadata UUID (optional if city_name provided). From GET /api/v1/cities/ or resolved from city_name.",
    )
    city_name: str | None = Field(
        None,
        max_length=100,
        description="City name (optional if city_metadata_id provided). From GET /api/v1/leads/cities?country_code=... Backend resolves to city_metadata_id.",
    )
    referral_code: str | None = Field(None, max_length=20, description="Referrer's referral code (e.g. MARIA-V7X2)")
    is_archived: bool | None = False
    status: Status | None = Field(default=Status.ACTIVE)

    @field_validator("country_code")
    @classmethod
    def normalize_country_to_alpha2(cls, v: str) -> str:
        """Normalize to alpha-2 uppercase."""
        return normalize_country_code(v) if v else v

    @model_validator(mode="after")
    def require_city_and_normalize_mobile(self):
        if not self.city_metadata_id and not (self.city_name or "").strip():
            raise I18nValueError("validation.address.city_required")
        normalized = normalize_mobile_for_schema(self.mobile_number, self.country_code)
        if normalized != self.mobile_number:
            return self.model_copy(update={"mobile_number": normalized})
        return self


class SupplierTermsEmbedSchema(BaseModel):
    """Optional embedded supplier terms for composite institution creation.
    All fields have defaults — an empty object is treated as absent."""

    no_show_discount: int = Field(0, ge=0, le=100, description="Percentage 0-100 deducted on no-show")
    payment_frequency: PaymentFrequency = Field(
        PaymentFrequency.DAILY, description="daily, weekly, biweekly, or monthly"
    )
    kitchen_open_time: str | None = Field(
        None, description="Pickup available time (HH:MM, e.g. 09:00). NULL = inherit from market default."
    )
    kitchen_close_time: str | None = Field(
        None, description="Order cutoff time (HH:MM, e.g. 13:30). NULL = inherit from market default."
    )
    require_invoice: bool | None = Field(None, description="NULL = inherit from market; TRUE/FALSE = override")
    invoice_hold_days: int | None = Field(None, gt=0, description="NULL = inherit from market default")


class InstitutionCreateSchema(BaseModel):
    """Schema for creating a new institution. market_ids assigns markets via institution_market junction.
    Optionally embed supplier_terms for atomic creation (valid only when institution_type is Supplier)."""

    name: str = Field(..., max_length=100)
    institution_type: RoleType | None = None  # Defaults to Supplier in DB if omitted
    market_ids: list[UUID] = Field(
        ..., min_length=1, description="Markets to assign (first is primary). At least one required."
    )
    supplier_terms: SupplierTermsEmbedSchema | None = Field(
        None, description="Embedded supplier terms — only valid when institution_type is Supplier"
    )


class InstitutionUpdateSchema(BaseModel):
    """Schema for updating institution information"""

    name: str | None = Field(None, max_length=100)
    institution_type: RoleType | None = None
    market_ids: list[UUID] | None = Field(
        None, description="Replace assigned markets (first is primary). Omit to leave unchanged."
    )
    support_email_suppressed_until: datetime | None = Field(
        None, description="Manual override: suppress onboarding emails until this date"
    )


class InstitutionResponseSchema(BaseModel):
    """Schema for institution response data. market_ids lists assigned markets (primary first)."""

    institution_id: UUID
    name: str
    institution_type: RoleType
    market_ids: list[UUID] = Field(default_factory=list, description="Assigned markets (primary first)")
    support_email_suppressed_until: datetime | None = None
    last_support_email_date: datetime | None = None
    is_archived: bool
    status: Status
    canonical_key: str | None = None
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID | None = None
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionUpsertByKeySchema(BaseModel):
    """Schema for idempotent institution upsert by canonical_key.

    If an institution with the given canonical_key already exists it is updated
    in-place; otherwise a new institution is inserted with that canonical_key.
    Use this endpoint for Postman seed runs and fixture data — never for
    ad-hoc institution creation (use POST /institutions instead).

    Auth: Internal only (get_employee_user dependency). Returns 403 for
    Customer/Supplier roles.

    Immutable fields on UPDATE: ``institution_type`` is locked after insert and
    ignored on the update path. The market assignment is always applied (both
    on INSERT and UPDATE) so the institution remains in the expected markets after
    each idempotent run.
    """

    canonical_key: str = Field(
        ...,
        max_length=200,
        description="Stable human-readable identifier, e.g. 'E2E_INSTITUTION_SUPPLIER'",
    )
    name: str = Field(..., max_length=100, description="Display name of the institution")
    institution_type: RoleType = Field(..., description="Discriminator: supplier, employer, customer, or internal")
    market_ids: list[UUID] = Field(
        ...,
        min_length=1,
        description="Markets to assign (first is primary). At least one required.",
    )
    status: Status = Status.ACTIVE


# RoleCreateSchema, RoleUpdateSchema, RoleResponseSchema removed
# role_info table removed - roles are now stored directly on user_info as enums

# =============================================================================
# 2. RESTAURANT & FOOD SCHEMAS
# =============================================================================

# =============================================================================
# CUISINE SCHEMAS
# =============================================================================


class CuisineResponseSchema(BaseModel):
    """Public cuisine response for dropdowns and autocomplete."""

    cuisine_id: UUID
    cuisine_name: str
    slug: str
    parent_cuisine_id: UUID | None = None
    description: str | None = None
    display_order: int | None = None


class CuisineDetailResponseSchema(BaseModel):
    """Admin cuisine response with full detail including i18n."""

    cuisine_id: UUID
    cuisine_name: str
    cuisine_name_i18n: dict | None = None
    slug: str
    parent_cuisine_id: UUID | None = None
    description: str | None = None
    origin_source: str
    display_order: int | None = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime


class CuisineCreateSchema(BaseModel):
    """Schema for creating a new cuisine (admin)."""

    cuisine_name: str = Field(..., max_length=80)
    cuisine_name_i18n: dict | None = None
    slug: str | None = Field(None, max_length=80, description="Auto-generated from cuisine_name if not provided")
    parent_cuisine_id: UUID | None = None
    description: str | None = Field(None, max_length=500)
    display_order: int | None = None


class CuisineUpdateSchema(BaseModel):
    """Schema for updating a cuisine (admin)."""

    cuisine_name: str | None = Field(None, max_length=80)
    cuisine_name_i18n: dict | None = None
    slug: str | None = Field(None, max_length=80)
    parent_cuisine_id: UUID | None = None
    description: str | None = Field(None, max_length=500)
    display_order: int | None = None


class CuisineSuggestionCreateSchema(BaseModel):
    """Schema for supplier to suggest a new cuisine."""

    suggested_name: str = Field(..., max_length=120)
    restaurant_id: UUID | None = None


class CuisineSuggestionResponseSchema(BaseModel):
    """Response for cuisine suggestion."""

    suggestion_id: UUID
    suggested_name: str
    suggested_by: UUID
    restaurant_id: UUID | None = None
    suggestion_status: str
    reviewed_by: UUID | None = None
    reviewed_date: datetime | None = None
    review_notes: str | None = None
    resolved_cuisine_id: UUID | None = None
    created_date: datetime


class CuisineSuggestionApproveSchema(BaseModel):
    """Schema for approving a cuisine suggestion."""

    resolved_cuisine_id: UUID | None = Field(
        None, description="Map to existing cuisine; if null, creates new from suggested_name"
    )
    review_notes: str | None = Field(None, max_length=500)


class CuisineSuggestionRejectSchema(BaseModel):
    """Schema for rejecting a cuisine suggestion."""

    review_notes: str | None = Field(None, max_length=500)


# =============================================================================
# RESTAURANT SCHEMAS
# =============================================================================


class RestaurantCreateSchema(BaseModel):
    """Schema for creating a new restaurant. credit_currency inherited from institution_entity."""

    institution_id: UUID
    institution_entity_id: UUID
    address_id: UUID
    name: str = Field(..., max_length=100)
    cuisine_id: UUID | None = None
    pickup_instructions: str | None = Field(None, max_length=500)
    tagline: str | None = Field(None, max_length=500)
    tagline_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    is_featured: bool | None = None
    cover_image_url: str | None = None
    average_rating: Decimal | None = None
    review_count: int | None = None
    verified_badge: bool | None = None
    spotlight_label: str | None = Field(None, max_length=200)
    spotlight_label_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    member_perks: list[str] | None = None
    member_perks_i18n: dict | None = Field(None, description="Locale map: {en: [...], es: [...]}")


class RestaurantUpdateSchema(BaseModel):
    """Schema for updating restaurant information"""

    institution_id: UUID | None = None
    institution_entity_id: UUID | None = None
    address_id: UUID | None = None
    name: str | None = Field(None, max_length=100)
    cuisine_id: UUID | None = None
    pickup_instructions: str | None = Field(None, max_length=500)
    tagline: str | None = Field(None, max_length=500)
    tagline_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    is_featured: bool | None = None
    cover_image_url: str | None = None
    average_rating: Decimal | None = None
    review_count: int | None = None
    verified_badge: bool | None = None
    spotlight_label: str | None = Field(None, max_length=200)
    spotlight_label_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    member_perks: list[str] | None = None
    member_perks_i18n: dict | None = Field(None, description="Locale map: {en: [...], es: [...]}")
    require_kiosk_code_verification: bool | None = Field(
        None, description="Enable kiosk code verification for this restaurant (Supplier Admin only)"
    )
    status: Status | None = Field(
        None, description="Active only allowed when restaurant has active plate_kitchen_days; Inactive always allowed"
    )


class RestaurantUpsertByKeySchema(BaseModel):
    """Schema for idempotent restaurant upsert by canonical_key.

    If a restaurant with the given canonical_key already exists it is updated
    in-place; otherwise a new restaurant is inserted with that canonical_key.
    Use this endpoint for Postman seed runs and fixture data — never for
    ad-hoc restaurant creation (use POST /restaurants instead).

    Auth: Internal only (get_employee_user dependency). Returns 403 for
    Customer/Supplier roles.

    Immutable fields on UPDATE: ``institution_id`` and ``institution_entity_id``
    are locked after insert and ignored on the update path. The balance record
    is only created on INSERT; updates leave the balance untouched.
    """

    canonical_key: str = Field(
        ...,
        max_length=200,
        description="Stable human-readable identifier, e.g. 'E2E_RESTAURANT_CAMBALACHE'",
    )
    institution_id: UUID = Field(..., description="FK to core.institution_info — the supplier institution")
    institution_entity_id: UUID = Field(
        ..., description="FK to ops.institution_entity_info — the legal entity that owns this restaurant"
    )
    address_id: UUID = Field(..., description="FK to core.address_info — physical pickup location")
    name: str = Field(..., max_length=100, description="Display name of the restaurant")
    cuisine_id: UUID | None = Field(None, description="FK to ops.cuisine — primary cuisine category")
    pickup_instructions: str | None = Field(None, max_length=500)
    tagline: str | None = Field(None, max_length=500)
    tagline_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    is_featured: bool = False
    cover_image_url: str | None = None
    spotlight_label: str | None = Field(None, max_length=200)
    spotlight_label_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    member_perks: list[str] | None = None
    member_perks_i18n: dict | None = Field(None, description="Locale map: {en: [...], es: [...]}")
    status: Status = Status.PENDING


class RestaurantSearchResultSchema(BaseModel):
    """One restaurant in GET /restaurants/search/ response (minimal fields for discretionary recipient picker)."""

    restaurant_id: UUID
    name: str


class RestaurantSearchResponseSchema(BaseModel):
    """Response for GET /restaurants/search/ (paginated list + total)."""

    results: list["RestaurantSearchResultSchema"] = Field(..., description="Page of matching restaurants")
    total: int = Field(..., description="Total number of matching restaurants (for pagination)")


class RestaurantExplorerCitiesResponseSchema(BaseModel):
    """Response for GET /restaurants/cities (B2C explore dropdown)."""

    cities: list[str] = Field(..., description="City names that have at least one restaurant in the country")


class KitchenDayForExploreSchema(BaseModel):
    """One kitchen day option for GET /restaurants/explore/kitchen-days (closest-first order)."""

    kitchen_day: str = Field(..., description="Weekday name (Monday–Friday)")
    date: str = Field(..., description="ISO date (YYYY-MM-DD) for this occurrence")


class ExploreKitchenDaysResponseSchema(BaseModel):
    """Response for GET /restaurants/explore/kitchen-days. Ordered by date ascending (closest first)."""

    kitchen_days: list[KitchenDayForExploreSchema] = Field(
        ..., description="Allowed kitchen days in the explore window, closest date first"
    )


class PickupWindowsResponseSchema(BaseModel):
    """Response for GET /restaurants/explore/pickup-windows. 15-minute windows for the given kitchen day."""

    kitchen_day: str = Field(..., description="Weekday name (Monday–Friday)")
    date: str = Field(..., description="ISO date (YYYY-MM-DD) for this occurrence")
    pickup_windows: list[str] = Field(..., description="15-minute windows in HH:MM-HH:MM format (e.g. 11:30-11:45)")


class CoworkerPickupWindowItemSchema(BaseModel):
    """One coworker pickup window in GET /restaurants/{id}/coworker-pickup-windows."""

    pickup_time_range: str = Field(..., description="15-min window HH:MM-HH:MM (e.g. 11:30-11:45)")
    intent: str = Field(..., description="pickup_intent: 'offer' or 'request'")
    flexible_on_time: bool | None = Field(None, description="True when original request has flexible_on_time")


class CoworkerPickupWindowsResponseSchema(BaseModel):
    """Response for GET /restaurants/{id}/coworker-pickup-windows."""

    pickup_windows: list[CoworkerPickupWindowItemSchema] = Field(
        ..., description="Pickup windows from coworkers (offer/request) for this restaurant+kitchen_day"
    )


class PlateExplorerItemSchema(BaseModel):
    """One plate in GET /restaurants/by-city restaurant.plates (lean payload for cards; modal fetches via enriched)."""

    plate_id: UUID
    product_name: str = Field(..., description="Product name from product_info")
    image_url: str | None = Field(None, description="Product thumbnail URL (image_thumbnail_url)")
    credit: int = Field(..., description="Credit value")
    savings: int = Field(0, ge=0, le=100, description="Savings percentage for display (e.g. green box X% off)")
    is_recommended: bool = Field(
        False, description="True when recommendation score meets threshold; UI can show Recommended badge"
    )
    is_favorite: bool = Field(False, description="True if the current user has favorited this plate")
    is_already_reserved: bool = Field(
        False,
        description="True when current user has reserved this plate for this kitchen_day; show alternative actions instead of Reserve",
    )
    existing_plate_selection_id: str | None = Field(
        None, description="When is_already_reserved, use for Change or cancel (PATCH/DELETE)"
    )


class RestaurantExplorerItemSchema(BaseModel):
    """One restaurant in GET /restaurants/by-city response (list and map)."""

    restaurant_id: UUID
    name: str
    cuisine_name: str | None = None
    tagline: str | None = None
    lat: float | None = Field(None, description="Latitude from geolocation; null if missing")
    lng: float | None = Field(None, description="Longitude from geolocation; null if missing")
    postal_code: str | None = Field(None, description="Zipcode/postal code from address")
    city: str | None = Field(None, description="City from address")
    street_type: str | None = Field(None, description="Street type from address (e.g. St, Ave) for address line")
    street_name: str | None = Field(None, description="Street name from address for address line")
    building_number: str | None = Field(None, description="Building number from address for address line")
    address_display: str | None = Field(
        None, description="Pre-formatted street line per market (e.g. 123 Main St or Av Santa Fe 100)"
    )
    pickup_instructions: str | None = Field(None, description="Restaurant pickup instructions for customers")
    plates: list[PlateExplorerItemSchema] | None = Field(
        None, description="Plates available for the response kitchen_day (when requested)"
    )
    has_volunteer: bool = Field(
        False, description="True when kitchen_day set and at least one user has pickup_intent=offer for this restaurant"
    )
    has_coworker_offer: bool = Field(
        False,
        description="True when user has employer and at least one coworker has pickup_intent=offer for this restaurant+kitchen_day",
    )
    has_coworker_request: bool = Field(
        False,
        description="True when user has employer and at least one coworker has pickup_intent=request for this restaurant+kitchen_day",
    )
    is_favorite: bool = Field(False, description="True if the current user has favorited this restaurant")
    is_recommended: bool = Field(
        False, description="True when recommendation score meets threshold; UI can show Recommended badge"
    )


class RestaurantsByCityResponseSchema(BaseModel):
    """Response for GET /restaurants/by-city (B2C explore list/map, optional plates by kitchen day)."""

    requested_city: str = Field(..., description="City value the client sent")
    city: str = Field(..., description="Matched city (case-insensitive)")
    center: Optional["ZipcodeCenterSchema"] = Field(None, description="Optional lat/lng center for the city")
    kitchen_day: str | None = Field(None, description="Kitchen day used for plates (when market/kitchen_day resolved)")
    restaurants: list[RestaurantExplorerItemSchema] = Field(
        ..., description="Restaurants in the city with name, cuisine_name, geolocation; plates when kitchen_day present"
    )
    next_cursor: str | None = Field(None, description="Opaque cursor for the next page; null when no more results")
    has_more: bool = Field(..., description="Whether more results exist after this page")


class RestaurantResponseSchema(BaseModel):
    """Schema for restaurant response data. Includes full _i18n locale maps for B2B edit forms."""

    restaurant_id: UUID
    institution_id: UUID
    institution_entity_id: UUID
    address_id: UUID
    currency_metadata_id: UUID
    name: str
    cuisine_id: UUID | None = None
    cuisine_name: str | None = None
    pickup_instructions: str | None = None
    tagline: str | None = None
    tagline_i18n: dict | None = None
    is_featured: bool = False
    cover_image_url: str | None = None
    average_rating: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    review_count: int = 0
    verified_badge: bool = False
    spotlight_label: str | None = None
    spotlight_label_i18n: dict | None = None
    member_perks: list[str] | None = None
    member_perks_i18n: dict | None = None
    require_kiosk_code_verification: bool = False
    is_archived: bool
    status: Status
    canonical_key: str | None = None
    created_date: datetime
    modified_date: datetime
    is_ready_for_signup: bool | None = Field(
        None,
        description=(
            "Computed at read time. True when the restaurant meets all activation prerequisites: "
            "status='active', not archived, ≥1 active plate_kitchen_days, active QR code. "
            "Null when the endpoint does not compute this field (e.g. plain CRUD list). "
            "No DB column — rules may evolve without a migration."
        ),
    )
    missing: list[str] | None = Field(
        None,
        description=(
            "Subset of ['status_active', 'not_archived', 'plate_kitchen_days', 'qr'] listing "
            "unmet prerequisites. Empty list when is_ready_for_signup is True. "
            "Null when the endpoint does not compute this field."
        ),
    )

    model_config = ConfigDict(from_attributes=True)


class ProductCreateSchema(BaseModel):
    """Schema for creating a new product.
    Optionally embed ingredient_ids for atomic product + ingredients creation.
    Image upload is handled separately via POST /api/v1/uploads."""

    institution_id: UUID
    name: str = Field(..., max_length=100)
    name_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    ingredients: str | None = Field(None, max_length=255)
    ingredients_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    description: str | None = Field(None, max_length=1000)
    description_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    dietary: list[DietaryFlag] | None = None
    ingredient_ids: list[UUID] | None = Field(
        None, max_length=30, description="Ingredient UUIDs — atomic assignment at creation"
    )


class ProductUpdateSchema(BaseModel):
    """Schema for updating product information.
    If ingredient_ids is provided, the ingredient set is full-replaced atomically.
    Image upload is handled separately via POST /api/v1/uploads."""

    institution_id: UUID | None = None
    name: str | None = Field(None, max_length=100)
    name_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    ingredients: str | None = Field(None, max_length=255)
    ingredients_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    description: str | None = Field(None, max_length=1000)
    description_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    dietary: list[DietaryFlag] | None = None
    ingredient_ids: list[UUID] | None = Field(
        None, max_length=30, description="Full-replace ingredient set; absent = no change, [] = remove all"
    )


class ProductResponseSchema(BaseModel):
    """Schema for product response data. Includes full _i18n locale maps for B2B edit forms.
    Image state is no longer inline — query GET /api/v1/uploads/{image_asset_id} for image URLs."""

    product_id: UUID
    institution_id: UUID
    name: str
    name_i18n: dict | None = None
    ingredients: str | None
    ingredients_i18n: dict | None = None
    description: str | None = None
    description_i18n: dict | None = None
    dietary: list[DietaryFlag] | None
    is_archived: bool
    status: Status
    canonical_key: str | None = None
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductUpsertByKeySchema(BaseModel):
    """Schema for idempotent product upsert by canonical_key.

    If a product with the given canonical_key already exists it is updated
    in-place; otherwise a new product is inserted with that canonical_key.
    Use this endpoint for Postman seed runs and fixture data — never for
    ad-hoc product creation (use POST /products instead).

    Auth: Internal only (get_employee_user dependency). Returns 403 for
    Customer/Supplier roles.

    Immutable fields on UPDATE: ``institution_id`` is locked after insert and
    ignored on the update path (the owning institution cannot change after
    creation).

    Inline image columns have been removed. Image state is managed via
    POST /api/v1/uploads (two-step signed-URL upload flow).
    """

    canonical_key: str = Field(
        ...,
        max_length=200,
        description="Stable human-readable identifier, e.g. 'E2E_PRODUCT_BIG_BURGUER'",
    )
    institution_id: UUID = Field(..., description="FK to core.institution_info — the owning supplier institution")
    name: str = Field(..., max_length=100, description="Display name of the product")
    name_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    ingredients: str | None = Field(None, max_length=255, description="Free-text ingredient list (primary locale)")
    ingredients_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    description: str | None = Field(None, max_length=1000, description="Short product description")
    description_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    dietary: list[DietaryFlag] | None = Field(None, description="Dietary attribute slugs for consumer filtering")
    status: Status = Status.ACTIVE


class ProductEnrichedResponseSchema(BaseModel):
    """Schema for enriched product response data with institution name.
    Inline image fields removed — image state lives in image_asset (see GET /api/v1/uploads/{id}).
    Image summary is surfaced here for list/detail views without requiring a separate uploads call."""

    product_id: UUID
    institution_id: UUID
    institution_name: str
    name: str
    name_i18n: dict | None = Field(None, exclude=True)
    ingredients: str | None
    ingredients_i18n: dict | None = Field(None, exclude=True)
    description: str | None = None
    description_i18n: dict | None = Field(None, exclude=True)
    dietary: list[DietaryFlag] | None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime
    # Image asset fields — populated via LEFT JOIN on ops.image_asset.
    # NULL when no upload exists for the product.
    image_asset_id: UUID | None = Field(
        None,
        description="image_asset PK. Use with DELETE /api/v1/uploads/{id} to remove the image.",
    )
    image_pipeline_status: str | None = Field(
        None,
        description="Pipeline lifecycle: pending | processing | ready | rejected | failed. NULL = no upload.",
    )
    image_moderation_status: str | None = Field(
        None,
        description="SafeSearch result: pending | passed | rejected. NULL = no upload.",
    )
    image_signed_urls: dict[str, str] | None = Field(
        None,
        description="Signed read URLs for hero, card, thumbnail. Non-null only when image_pipeline_status='ready'.",
    )

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# IMAGE ASSET / UPLOAD SCHEMAS (image-pipeline Phase 2)
# =============================================================================


class ImageAssetRead(BaseModel):
    """Response schema for a single image_asset row (from GET /api/v1/uploads/{id})."""

    image_asset_id: UUID
    product_id: UUID
    pipeline_status: str
    moderation_status: str
    signed_urls: dict[str, str] | None = Field(
        None,
        description="Signed read URLs for hero, card, thumbnail. Populated only when pipeline_status='ready'.",
    )

    model_config = ConfigDict(from_attributes=True)


class UploadCreateRequest(BaseModel):
    """Request body for POST /api/v1/uploads — initiates a two-step product image upload."""

    product_id: UUID = Field(..., description="Product the image belongs to.")


class UploadCreateResponse(BaseModel):
    """Response body for POST /api/v1/uploads — includes the signed PUT URL for direct GCS upload."""

    image_asset_id: UUID
    signed_write_url: str = Field(..., description="Signed PUT URL for direct GCS upload of the original image.")
    expires_at: datetime = Field(..., description="UTC expiry of the signed write URL.")


class UploadStatusResponse(BaseModel):
    """Response body for GET /api/v1/uploads/{image_asset_id}."""

    image_asset_id: UUID
    product_id: UUID = Field(..., description="Product this image asset belongs to.")
    pipeline_status: str
    moderation_status: str
    signed_urls: dict[str, str] | None = Field(
        None,
        description="Signed read URLs for hero, card, thumbnail. Null until pipeline_status='ready'.",
    )


class PlateCreateSchema(BaseModel):
    """Schema for creating a new plate. Savings are computed on the fly from plan credit_cost_local_currency."""

    product_id: UUID
    restaurant_id: UUID
    price: Decimal = Field(..., ge=0)
    credit: int = Field(..., gt=0)
    delivery_time_minutes: int = Field(default=15, gt=0)


class PlateUpdateSchema(BaseModel):
    """Schema for updating plate information"""

    product_id: UUID | None = None
    restaurant_id: UUID | None = None
    price: Decimal | None = Field(None, ge=0)
    credit: int | None = Field(None, gt=0)
    delivery_time_minutes: int | None = Field(None, gt=0)


class PlateResponseSchema(BaseModel):
    """Schema for plate response data"""

    plate_id: UUID
    product_id: UUID
    restaurant_id: UUID
    price: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    # filter-registry:exempt reason="range-bound; use credit_from / credit_to filter params"
    credit: int
    # filter-registry:exempt reason="computed display value; not filterable"
    expected_payout_local_currency: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    delivery_time_minutes: int
    is_archived: bool
    status: Status
    canonical_key: str | None = None
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class PlateUpsertByKeySchema(BaseModel):
    """Schema for idempotent plate upsert by canonical_key.

    If a plate with the given canonical_key already exists it is updated in-place;
    otherwise a new plate is inserted with that canonical_key.
    Use this endpoint for Postman seed runs and fixture data — never for
    ad-hoc plate creation (use POST /plates instead).
    """

    canonical_key: str = Field(
        ...,
        max_length=200,
        description="Stable human-readable identifier, e.g. 'RESTAURANT_LA_COCINA_PORTENA_PLATE_BONDIOLA'",
    )
    product_id: UUID = Field(..., description="FK to ops.product_info — the recipe this plate is based on")
    restaurant_id: UUID = Field(..., description="FK to ops.restaurant_info — the restaurant offering this plate")
    price: Decimal = Field(..., ge=0, description="Local-currency price charged to subscribers")
    credit: int = Field(..., gt=0, description="Credit cost deducted from the subscriber's balance")
    delivery_time_minutes: int = Field(default=15, gt=0, description="Estimated minutes from order to plate readiness")
    status: Status = Status.ACTIVE


class PlateEnrichedResponseSchema(BaseModel):
    """Schema for enriched plate response data with institution, restaurant, product, and address details"""

    # filter-registry:exempt reason="enriched join field; not a direct column on plate_info"
    plate_id: UUID
    # filter-registry:exempt reason="enriched join field; product_id is a join key, not a filterable dimension"
    product_id: UUID
    restaurant_id: UUID
    # filter-registry:exempt reason="enriched join field; filter by restaurant_id instead"
    institution_name: str
    # filter-registry:exempt reason="enriched join field; filter by restaurant_id instead"
    restaurant_name: str
    # filter-registry:exempt reason="enriched join field; filter by cuisine_id instead"
    cuisine_name: str | None = None
    # filter-registry:exempt reason="i18n translation payload; not filterable"
    cuisine_name_i18n: dict | None = Field(None, exclude=True)
    # filter-registry:exempt reason="enriched join field; filter by restaurant_id instead"
    pickup_instructions: str | None = None
    # filter-registry:exempt reason="enriched join field; country_code is registered instead"
    country_name: str
    # filter-registry:exempt reason="enriched join field; address join country; not registered for plate-level filtering"
    country_code: str
    # filter-registry:exempt reason="enriched join field; address subfield, not independently filterable"
    province: str
    # filter-registry:exempt reason="enriched join field; address subfield, not independently filterable"
    city: str
    # filter-registry:exempt reason="enriched join field; address subfield, not independently filterable"
    street_type: str | None = None
    # filter-registry:exempt reason="enriched join field; address subfield, not independently filterable"
    street_name: str | None = None
    # filter-registry:exempt reason="enriched join field; address subfield, not independently filterable"
    building_number: str | None = None
    # filter-registry:exempt reason="enriched join field; computed display field, not independently filterable"
    address_display: str | None = Field(
        None, description="Pre-formatted street line per market (e.g. 123 Main St or Av Santa Fe 100)"
    )
    # filter-registry:exempt reason="enriched join field; geo filtering handled by geo op if needed"
    latitude: float | None = None
    # filter-registry:exempt reason="enriched join field; geo filtering handled by geo op if needed"
    longitude: float | None = None
    # filter-registry:exempt reason="computed aggregate; not independently filterable"
    average_stars: float | None = None
    # filter-registry:exempt reason="computed aggregate; use portion_size for filtering"
    average_portion_size: float | None = None
    # filter-registry:exempt reason="Python-computed from average_portion_size; deferred to kitchen#87"
    portion_size: Literal["light", "standard", "large", "insufficient_reviews"] = Field(
        "insufficient_reviews",
        description="Human-readable portion size; 'insufficient_reviews' when < 5 reviews (client shows 'not enough reviews' message)",
    )
    # filter-registry:exempt reason="computed aggregate; not independently filterable"
    review_count: int = 0
    # filter-registry:exempt reason="enriched join field; filter by plate_id instead"
    product_name: str
    # filter-registry:exempt reason="i18n translation payload; not filterable"
    product_name_i18n: dict | None = Field(None, exclude=True)
    dietary: list[DietaryFlag] | None
    # filter-registry:exempt reason="enriched join field; free-text, not independently filterable"
    ingredients: str | None = None
    # filter-registry:exempt reason="i18n translation payload; not filterable"
    ingredients_i18n: dict | None = Field(None, exclude=True)
    # filter-registry:exempt reason="enriched join field; free-text, not independently filterable"
    description: str | None = None
    # filter-registry:exempt reason="i18n translation payload; not filterable"
    description_i18n: dict | None = Field(None, exclude=True)
    # filter-registry:exempt reason="range-bound; use price_from / price_to filter params"
    price: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    # filter-registry:exempt reason="range-bound; use credit_from / credit_to filter params"
    credit: int
    # filter-registry:exempt reason="computed display value; not filterable"
    expected_payout_local_currency: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    # filter-registry:exempt reason="enriched join field; supplier_terms field, not independently filterable"
    no_show_discount: int | None = Field(None, description="From supplier_terms; null when no terms configured")
    # filter-registry:exempt reason="enriched join field; not independently filterable"
    delivery_time_minutes: int
    # filter-registry:exempt reason="status field used in restaurant scoping; not a plate filter dimension"
    is_archived: bool
    status: Status
    # filter-registry:exempt reason="Python-computed contextual flag; not a DB column"
    has_coworker_offer: bool | None = Field(
        None, description="When kitchen_day provided and user has employer: True if coworker has pickup_intent=offer"
    )
    # filter-registry:exempt reason="Python-computed contextual flag; not a DB column"
    has_coworker_request: bool | None = Field(
        None, description="When kitchen_day provided and user has employer: True if coworker has pickup_intent=request"
    )

    model_config = ConfigDict(from_attributes=True)


class RestaurantActivatedSchema(BaseModel):
    """Embedded in mutation responses when lazy activation fires for a restaurant.

    Included as ``restaurant_activated`` on POST /plate-kitchen-days and POST /qr-codes.
    Value is ``null`` (field present, value None) when activation did not fire.
    """

    restaurant_id: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class PlateKitchenDayCreateSchema(BaseModel):
    """Schema for creating plate kitchen day assignments (supports single or multiple days)"""

    plate_id: UUID
    kitchen_days: list[KitchenDay] = Field(
        ..., description="List of days of the week: Monday, Tuesday, Wednesday, Thursday, or Friday"
    )
    status: Status | None = Field(
        default=None, description="Optional; omit or null and backend assigns default (Active)"
    )

    @field_validator("kitchen_days")
    @classmethod
    def validate_kitchen_days(cls, v):
        """Validate that all kitchen_days are valid weekdays"""
        if not v:
            raise I18nValueError("validation.plate.kitchen_days_empty")
        # Check for duplicates
        if len(v) != len(set(v)):
            raise I18nValueError("validation.plate.kitchen_days_duplicate")
        return v

    model_config = ConfigDict(from_attributes=True)


class PlateKitchenDayUpdateSchema(BaseModel):
    """Schema for updating plate kitchen day assignment.
    plate_id is immutable; if sent on update, the request will be rejected with 400.
    To change plate_id: create a new record and archive the old one."""

    plate_id: UUID | None = Field(None, description="Immutable - cannot be changed; if provided, returns 400")
    kitchen_day: KitchenDay | None = Field(
        None, description="Day of the week: Monday, Tuesday, Wednesday, Thursday, or Friday"
    )
    status: Status | None = Field(None, description="Status of the kitchen day assignment")
    is_archived: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class PlateKitchenDayResponseSchema(BaseModel):
    """Schema for plate kitchen day response data"""

    plate_kitchen_day_id: UUID
    plate_id: UUID
    kitchen_day: KitchenDay
    status: Status
    is_archived: bool
    canonical_key: str | None = None
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class PlateKitchenDayUpsertByKeySchema(BaseModel):
    """Schema for idempotent plate kitchen day upsert by canonical_key.

    If a plate kitchen day with the given canonical_key already exists it is
    updated in-place; otherwise a new row is inserted.  Use this endpoint for
    Postman seed runs and fixture data — never for ad-hoc kitchen day creation
    (use POST /plate-kitchen-days instead).

    Auth: Internal only (get_employee_user dependency). Returns 403 for
    Customer/Supplier roles.

    Immutable fields on UPDATE:
        - ``plate_id`` — FK to the plate; cannot change after creation.
          To reassign a kitchen day to a different plate, archive the old row
          and create a new one.
        - ``kitchen_day`` — the weekday this row represents; cannot change after
          creation.  To reassign the same plate to a different day, archive the
          old row and create a new canonical row for the new day.
    """

    canonical_key: str = Field(
        ...,
        max_length=200,
        description="Stable identifier, e.g. 'E2E_PKD_CAMBALACHE_BONDIOLA_MONDAY'",
    )
    plate_id: UUID = Field(..., description="FK to ops.plate_info. Immutable after INSERT.")
    kitchen_day: KitchenDay = Field(..., description="Weekday (Monday–Friday). Immutable after INSERT.")
    status: Status = Status.ACTIVE

    model_config = ConfigDict(from_attributes=True)


class PlateKitchenDayCreateResponseSchema(BaseModel):
    """Response schema for POST /plate-kitchen-days.

    Wraps the list of created records plus an optional ``restaurant_activated``
    envelope that is populated when lazy activation fires for the restaurant.
    ``restaurant_activated`` is always present in the response (null when
    activation did not fire) so clients can reliably check the field.
    """

    items: list[PlateKitchenDayResponseSchema]
    restaurant_activated: RestaurantActivatedSchema | None = None

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
    dietary: list[DietaryFlag] | None  # From product_info.dietary
    is_archived: bool
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class PlateReviewCreateSchema(BaseModel):
    """Schema for creating a plate review. One review per pickup; immutable after creation."""

    plate_pickup_id: UUID = Field(
        ..., description="The pickup being reviewed; must be completed (was_collected=true) and belong to the user"
    )
    stars_rating: int = Field(..., ge=1, le=5, description="Star rating 1-5")
    portion_size_rating: int = Field(..., ge=1, le=3, description="Portion size rating 1-3")
    would_order_again: bool | None = Field(None, description="Would order this plate again")
    comment: str | None = Field(
        None, max_length=500, description="Optional text feedback for the restaurant (max 500 chars)"
    )

    model_config = ConfigDict(from_attributes=True)


class PlateReviewResponseSchema(BaseModel):
    """Schema for plate review response data"""

    plate_review_id: UUID
    user_id: UUID
    plate_id: UUID
    plate_pickup_id: UUID
    stars_rating: int
    portion_size_rating: int
    would_order_again: bool | None = None
    comment: str | None = None
    is_archived: bool
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationActionSchema(BaseModel):
    """Nested schema for notification banner action display"""

    action_type: str
    action_label: str


class NotificationBannerResponseSchema(BaseModel):
    """Schema for a single notification banner in the active list"""

    notification_id: UUID
    notification_type: str
    priority: str
    created_at: datetime
    expires_at: datetime
    payload: dict
    action: NotificationActionSchema

    model_config = ConfigDict(from_attributes=True)


class ActiveNotificationsResponseSchema(BaseModel):
    """Wrapper response for GET /notifications/active"""

    notifications: list[NotificationBannerResponseSchema]


class NotificationAcknowledgeSchema(BaseModel):
    """Request body for POST /notifications/{id}/acknowledge"""

    action_taken: str = Field(..., pattern=r"^(dismissed|opened|completed)$")


class PlateReviewEnrichedResponseSchema(BaseModel):
    """Supplier-facing enriched plate review — no customer PII."""

    plate_review_id: UUID
    plate_id: UUID
    plate_name: str
    restaurant_name: str
    stars_rating: int
    portion_size_rating: int
    would_order_again: bool | None = None
    comment: str | None = None
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


class PortionComplaintCreateSchema(BaseModel):
    """Schema for filing a portion complaint after rating portion size as 1."""

    plate_pickup_id: UUID = Field(..., description="The pickup being complained about")
    complaint_text: str | None = Field(None, max_length=1000, description="Details about the portion issue")

    model_config = ConfigDict(from_attributes=True)


class PortionComplaintResponseSchema(BaseModel):
    """Schema for portion complaint response."""

    complaint_id: UUID
    plate_pickup_id: UUID
    plate_review_id: UUID | None = None
    restaurant_id: UUID
    photo_storage_path: str | None = None
    complaint_text: str | None = None
    resolution_status: str
    created_date: datetime

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

    plate_ids: list[UUID] = Field(default_factory=list, description="Plate IDs the user has favorited")
    restaurant_ids: list[UUID] = Field(default_factory=list, description="Restaurant IDs the user has favorited")


class QRCodeCreateSchema(BaseModel):
    """Schema for creating a new QR code - only restaurant_id needed"""

    restaurant_id: UUID
    # qr_code_payload, qr_code_image_url and image_storage_path will be auto-generated


class QRCodeUpdateSchema(BaseModel):
    """Schema for updating QR code information"""

    restaurant_id: UUID | None = None
    status: Status | None = None


class QRCodeResponseSchema(BaseModel):
    """Schema for QR code response data"""

    qr_code_id: UUID
    restaurant_id: UUID
    qr_code_payload: str
    qr_code_image_url: str
    image_storage_path: str
    qr_code_checksum: str | None = None
    is_archived: bool
    status: Status
    canonical_key: str | None = None
    created_date: datetime
    modified_date: datetime
    restaurant_activated: RestaurantActivatedSchema | None = Field(
        None,
        description=(
            "Populated when the POST /qr-codes call triggers lazy restaurant activation. "
            "Always present (null when activation did not fire). "
            "Absent on GET, PUT, DELETE responses."
        ),
    )

    model_config = ConfigDict(from_attributes=True)


class QrCodeUpsertByKeySchema(BaseModel):
    """Schema for idempotent QR code upsert by canonical_key.

    If a QR code with the given canonical_key already exists it is updated
    in-place; otherwise a new QR code is created atomically (including QR
    image generation) with that canonical_key.

    Use this endpoint for Postman seed runs and fixture data — never for
    ad-hoc QR code creation (use POST /qr-codes instead).

    Auth: Internal only (get_employee_user dependency). Returns 403 for
    Customer/Supplier roles.

    Immutable fields on UPDATE: ``restaurant_id`` is locked after insert and
    ignored on the update path (a QR code always belongs to the restaurant it
    was originally created for).
    """

    canonical_key: str = Field(
        ...,
        max_length=200,
        description="Stable human-readable identifier, e.g. 'E2E_QR_CAMBALACHE'",
    )
    restaurant_id: UUID = Field(
        ...,
        description=(
            "FK to ops.restaurant_info. **Immutable after INSERT** — "
            "ignored on the update path to prevent reassignment."
        ),
    )


# =============================================================================
# 3. BILLING & PAYMENTS SCHEMAS
# =============================================================================


class CreditCurrencyCreateSchema(BaseModel):
    """Schema for creating a new credit currency. Backend assigns currency_code from supported list and fetches currency_conversion_usd from open.er-api.com."""

    currency_name: str = Field(..., max_length=50)
    credit_value_supplier_local: Decimal = Field(
        ..., gt=0, description="Stable per-credit fiat payout value to suppliers"
    )
    acknowledge_spread_compression: bool = Field(
        False,
        description="Set to true to acknowledge that this write compresses spread below the market floor, if applicable.",
    )
    spread_acknowledgement_justification: str | None = Field(
        None, description="Optional free-text justification for spread compression acknowledgement."
    )


class CreditCurrencyUpdateSchema(BaseModel):
    """Schema for updating credit currency information. currency_conversion_usd is cron-managed; do not send."""

    currency_name: str | None = Field(None, max_length=50)
    currency_code: str | None = Field(None, max_length=10)
    credit_value_supplier_local: Decimal | None = Field(
        None, gt=0, description="Stable per-credit fiat payout value to suppliers"
    )
    acknowledge_spread_compression: bool = Field(
        False,
        description="Set to true to acknowledge that this write compresses spread below the market floor, if applicable.",
    )
    spread_acknowledgement_justification: str | None = Field(
        None, description="Optional free-text justification for spread compression acknowledgement."
    )


class CreditCurrencyResponseSchema(BaseModel):
    """Schema for credit currency response data.

    currency_name is Optional because the underlying column was dropped in PR2a.
    Basic CRUD responses omit it (=None); use CreditCurrencyEnrichedResponseSchema
    to get the display name resolved via JOIN external.iso4217_currency.
    """

    currency_metadata_id: UUID
    currency_name: str | None = None
    currency_code: str
    credit_value_supplier_local: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    currency_conversion_usd: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime
    canonical_key: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CreditCurrencyUpsertByKeySchema(BaseModel):
    """Request schema for PUT /api/v1/credit-currencies/by-key (idempotent seed upsert).

    INTERNAL SEED/FIXTURE ENDPOINT ONLY. Never use for ad-hoc currency creation
    (use POST /credit-currencies instead).

    Immutable fields on UPDATE:
      - ``currency_code`` is the ISO 4217 natural unique key for a currency row.
        It is locked after insert and silently ignored on the update path.
        (Changing a currency's code after creation would break all FK references
        and market associations.)
    """

    canonical_key: str = Field(..., max_length=200, description="Stable seed-fixture identifier, e.g. E2E_CURRENCY_ARS")
    currency_name: str = Field(
        ...,
        max_length=50,
        description="ISO 4217 currency name used to resolve currency_code server-side (e.g. 'Argentine Peso')",
    )
    credit_value_supplier_local: Decimal = Field(
        ..., gt=0, description="Stable per-credit fiat payout value to suppliers"
    )


class CreditCurrencyMarketSchema(BaseModel):
    """Nested market reference within a credit currency response."""

    market_id: str
    market_name: str | None = None
    country_code: str


class CreditCurrencyEnrichedResponseSchema(BaseModel):
    """Schema for enriched credit currency response data with aggregated market information.
    One row per currency; markets that use this currency are nested in the markets array.
    currency_name is populated via JOIN external.iso4217_currency."""

    currency_metadata_id: UUID
    currency_name: str
    currency_code: str
    credit_value_supplier_local: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    currency_conversion_usd: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    markets: list[CreditCurrencyMarketSchema] = Field(
        default_factory=list, description="Markets that use this currency"
    )
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanCreateSchema(BaseModel):
    """Schema for creating a new plan"""

    market_id: UUID = Field(..., description="Market (country) this plan belongs to")
    name: str = Field(..., max_length=100)
    name_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    marketing_description: str | None = Field(None, max_length=1000)
    marketing_description_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    features: list[str] | None = None
    features_i18n: dict | None = Field(None, description="Locale map: {en: [...], es: [...]}")
    cta_label: str | None = Field(None, max_length=200)
    cta_label_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    credit: int = Field(..., gt=0)
    price: float = Field(..., ge=0)
    rollover: bool | None = True
    rollover_cap: Decimal | None = None
    canonical_key: str | None = Field(
        None, max_length=200, description="Optional stable identifier for seed/fixture plans"
    )
    acknowledge_spread_compression: bool = Field(
        False,
        description="Set to true to acknowledge that this plan compresses spread below the market floor.",
    )
    spread_acknowledgement_justification: str | None = Field(
        None, description="Optional free-text justification for spread compression acknowledgement."
    )


class PlanUpdateSchema(BaseModel):
    """Schema for updating plan information"""

    market_id: UUID | None = Field(None, description="Market (country) this plan belongs to")
    name: str | None = Field(None, max_length=100)
    name_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    marketing_description: str | None = Field(None, max_length=1000)
    marketing_description_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    features: list[str] | None = None
    features_i18n: dict | None = Field(None, description="Locale map: {en: [...], es: [...]}")
    cta_label: str | None = Field(None, max_length=200)
    cta_label_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    credit: int | None = Field(None, gt=0)
    price: float | None = Field(None, ge=0)
    rollover: bool | None = None
    rollover_cap: Decimal | None = None
    status: Status | None = None
    canonical_key: str | None = Field(
        None, max_length=200, description="Optional stable identifier for seed/fixture plans"
    )
    acknowledge_spread_compression: bool = Field(
        False,
        description="Set to true to acknowledge that this plan update compresses spread below the market floor.",
    )
    spread_acknowledgement_justification: str | None = Field(
        None, description="Optional free-text justification for spread compression acknowledgement."
    )


class PlanUpsertByKeySchema(BaseModel):
    """Schema for idempotent plan upsert by canonical_key.

    If a plan with the given canonical_key already exists it is updated in-place;
    otherwise a new plan is inserted with that canonical_key.
    Use this endpoint for Postman seed runs and fixture data — never for
    ad-hoc plan creation (use POST /plans instead).
    """

    canonical_key: str = Field(
        ..., max_length=200, description="Stable human-readable identifier, e.g. 'MARKET_AR_PLAN_STANDARD_50000_ARS'"
    )
    market_id: UUID = Field(..., description="Market (country) this plan belongs to")
    name: str = Field(..., max_length=100)
    name_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    marketing_description: str | None = Field(None, max_length=1000)
    marketing_description_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    features: list[str] | None = None
    features_i18n: dict | None = Field(None, description="Locale map: {en: [...], es: [...]}")
    cta_label: str | None = Field(None, max_length=200)
    cta_label_i18n: dict | None = Field(None, description="Locale map: {en: '...', es: '...'}")
    credit: int = Field(..., gt=0)
    price: float = Field(..., ge=0)
    highlighted: bool = False
    status: Status = Status.ACTIVE
    acknowledge_spread_compression: bool = Field(
        False,
        description="Set to true to acknowledge that this upsert compresses spread below the market floor.",
    )
    spread_acknowledgement_justification: str | None = Field(
        None, description="Optional free-text justification for spread compression acknowledgement."
    )


class PlanResponseSchema(BaseModel):
    """Schema for plan response data. Includes full _i18n locale maps for B2B edit forms."""

    plan_id: UUID
    market_id: UUID
    name: str
    name_i18n: dict | None = None
    marketing_description: str | None = None
    marketing_description_i18n: dict | None = None
    features: list[str] | None = None
    features_i18n: dict | None = None
    cta_label: str | None = None
    cta_label_i18n: dict | None = None
    credit: int
    price: float
    credit_cost_local_currency: float
    credit_cost_usd: float
    status: Status
    rollover: bool
    rollover_cap: NullableMoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    canonical_key: str | None = None
    is_archived: bool
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanEnrichedResponseSchema(BaseModel):
    """Schema for enriched plan response data with currency name and code"""

    # filter-registry:exempt reason="primary key"
    plan_id: UUID
    market_id: UUID
    # filter-registry:exempt reason="display label for market_id"
    market_name: str
    country_code: str
    # filter-registry:exempt reason="display label for currency_code"
    currency_name: str
    currency_code: str
    # filter-registry:exempt reason="free-text label"
    name: str
    # filter-registry:exempt reason="translation payload; not filterable"
    name_i18n: dict | None = Field(None, exclude=True)
    # filter-registry:exempt reason="free-text marketing copy"
    marketing_description: str | None = None
    # filter-registry:exempt reason="translation payload; not filterable"
    marketing_description_i18n: dict | None = Field(None, exclude=True)
    # filter-registry:exempt reason="free-text marketing copy"
    features: list[str] | None = None
    # filter-registry:exempt reason="translation payload; not filterable"
    features_i18n: dict | None = Field(None, exclude=True)
    # filter-registry:exempt reason="free-text marketing copy"
    cta_label: str | None = None
    # filter-registry:exempt reason="translation payload; not filterable"
    cta_label_i18n: dict | None = Field(None, exclude=True)
    # filter-registry:exempt reason="range-bound; use credit_from / credit_to filter params"
    credit: int
    # filter-registry:exempt reason="range-bound; use price_from / price_to filter params"
    price: float
    # filter-registry:exempt reason="computed display value"
    credit_cost_local_currency: float
    # filter-registry:exempt reason="computed display value"
    credit_cost_usd: float
    rollover: bool
    # filter-registry:exempt reason="only meaningful when rollover=true"
    rollover_cap: NullableMoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    # filter-registry:exempt reason="soft-delete flag; server filters by default"
    is_archived: bool
    status: Status

    model_config = ConfigDict(from_attributes=True)


class SubscriptionEnrichedResponseSchema(BaseModel):
    """Schema for enriched subscription response data with user, plan, and market information"""

    subscription_id: UUID
    user_id: UUID
    user_full_name: str
    user_username: str
    user_email: str
    user_status: Status
    user_mobile_number: str | None = None
    plan_id: UUID
    plan_name: str
    plan_credit: int
    plan_price: float
    plan_rollover: bool
    plan_rollover_cap: NullableMoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    plan_status: Status
    market_id: UUID  # Market (country) for this subscription
    market_name: str  # country_name from market_info
    country_code: str  # from market_info
    renewal_date: datetime
    balance: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    is_archived: bool
    status: Status
    subscription_status: str | None = None
    hold_start_date: datetime | None = None
    hold_end_date: datetime | None = None
    early_renewal_threshold: int | None = 10
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
    currency_metadata_id: UUID
    market_id: UUID  # Via currency_metadata_id → market_info
    market_name: str  # country_name from market_info
    country_code: str  # from market_info
    transaction_count: int | None = None
    amount: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    currency_code: str | None = None
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

    place_id: str | None = Field(
        None,
        description="Place identifier from address search (Mapbox mapbox_id or Google place_id); when set, address fields are ignored and details are fetched",
    )
    session_token: str | None = Field(None, description="Session token from suggest flow for billing optimization")
    institution_id: UUID | None = None
    user_id: UUID | None = None
    workplace_group_id: UUID | None = None
    address_type: list[str] | None = Field(
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
                raise I18nValueError(
                    "validation.address.invalid_address_type",
                    address_type=addr_type,
                )
        if len(v) != len(set(v)):
            raise I18nValueError("validation.address.duplicate_address_type")
        return v

    is_default: bool = False
    floor: str | None = Field(None, max_length=50)
    city_metadata_id: UUID | None = Field(
        None,
        description=(
            "FK to core.city_metadata. Required in the manual/structured path (schema validator "
            "enforces when place_id is absent); resolve via GET /api/v1/cities?country_code=... "
            "In the place_id path, omit — the backend resolves it server-side from Mapbox place "
            "details. Either way, core.address_info.city_metadata_id is always NOT NULL."
        ),
    )
    country_code: str | None = Field(
        None,
        min_length=2,
        max_length=3,
        description="ISO 3166-1 alpha-2 or alpha-3 (e.g. AR or ARG). API normalizes to alpha-2 (uppercase).",
    )
    country: str | None = Field(
        None,
        max_length=100,
        description="Country name (e.g. Argentina); used to derive country_code when form has only 'country'",
    )
    province: str | None = Field(None, max_length=50)
    city: str | None = Field(None, max_length=50)
    postal_code: str | None = Field(None, max_length=20)
    street_type: str | None = Field(
        None, max_length=50, description="Street type code from GET /api/v1/enums/ (e.g. St, Ave, Blvd)"
    )
    street_name: str | None = Field(None, max_length=100)
    building_number: str | None = Field(None, max_length=20)
    apartment_unit: str | None = Field(None, max_length=20)
    assign_employer: bool | None = Field(
        True,
        description="If True (default), assign the employer to the current user when adding address. Only applies to Customers. Internal/Suppliers ignore this parameter. Can be set to False to opt-out of assignment.",
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

    @field_validator("street_type")
    @classmethod
    def validate_street_type(cls, v):
        """Validate that street_type is a valid enum value when provided"""
        from app.config.enums.street_types import StreetType

        if v is None or not str(v).strip():
            return v
        if not StreetType.is_valid(str(v).strip()):
            raise I18nValueError("validation.address.invalid_street_type", street_type=str(v).strip())
        return str(v).strip()

    @model_validator(mode="after")
    def require_country_or_place_id(self):
        place_id = (self.place_id or "").strip() if hasattr(self, "place_id") else ""
        if place_id:
            return self
        cc = (self.country_code or "").strip() if hasattr(self, "country_code") else ""
        cn = (self.country or "").strip() if hasattr(self, "country") else ""
        if not cc and not cn:
            raise I18nValueError("validation.address.country_required")
        for field in ("province", "city", "postal_code", "street_type", "street_name", "building_number"):
            val = getattr(self, field, None) or ""
            if not str(val).strip():
                raise I18nValueError("validation.address.field_required", address_field=field)
        # PR4c: city_metadata_id is required in the manual/structured path.
        # In the place_id path the writer resolves it from the Mapbox place details.
        if not getattr(self, "city_metadata_id", None):
            raise I18nValueError("validation.address.city_metadata_id_required")
        return self


class AddressUpdateSchema(BaseModel):
    """Schema for updating address. Only floor, apartment_unit, is_default, map_center_label (subpremise) are editable. Address core is immutable."""

    floor: str | None = Field(None, max_length=50)
    apartment_unit: str | None = Field(None, max_length=20)
    is_default: bool | None = None
    map_center_label: str | None = Field(
        None, max_length=20, description="Map center-of-gravity label: 'home' or 'other'. NULL defaults to 'home'."
    )


class CityResponseSchema(BaseModel):
    """Schema for city response (from core.city_metadata + external.geonames_city JOIN).

    `name` is populated by the query via `external.geonames_city.name` or
    `COALESCE(cm.display_name_override, gc.name)`; `country_code` is the ISO
    alpha-2 from city_metadata.country_iso.
    """

    city_metadata_id: UUID
    name: str
    country_code: str
    is_archived: bool
    status: Status

    model_config = ConfigDict(from_attributes=True)


class SupportedCitySchema(BaseModel):
    """One supported city for dropdowns (e.g. user onboarding, employer address filter).
    Backed by core.city_metadata + external.geonames_city."""

    city_metadata_id: UUID
    city_name: str = Field(..., description="City name (e.g. Lima, Buenos Aires)")
    country_code: str = Field(..., description="ISO 3166-1 alpha-2 code (e.g. PE, AR)")


class AddressResponseSchema(BaseModel):
    """Schema for address response data"""

    address_id: UUID
    institution_id: UUID
    user_id: UUID | None = None
    workplace_group_id: UUID | None = None
    address_type: list[str]
    is_default: bool
    floor: str | None
    country_name: str
    country_code: str
    province: str
    city: str
    postal_code: str
    street_type: str
    street_name: str
    building_number: str
    apartment_unit: str | None
    latitude: float | None = Field(None, description="Latitude from geolocation (null if not geocoded)")
    longitude: float | None = Field(None, description="Longitude from geolocation (null if not geocoded)")
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
    user_id: UUID | None = None
    user_username: str | None = None
    user_first_name: str | None = None
    user_last_name: str | None = None
    user_full_name: str = ""  # Empty when no user
    address_type: list[str]
    is_default: bool
    floor: str | None
    country_name: str
    country_code: str
    province: str
    city: str
    postal_code: str
    street_type: str
    street_name: str
    building_number: str
    apartment_unit: str | None
    latitude: float | None = Field(None, description="Latitude from geolocation (null if not geocoded)")
    longitude: float | None = Field(None, description="Longitude from geolocation (null if not geocoded)")
    timezone: str
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime
    formatted_address: str = Field(
        ..., description="Single-line display label: street_name · city · postal_code (for dropdowns/pickers)"
    )

    model_config = ConfigDict(from_attributes=True)


# --- Address autocomplete (suggest / validate) ---


class AddressSuggestionSchema(BaseModel):
    """One address suggestion from GET /addresses/suggest. Autocomplete only – client selects and sends place_id on create."""

    place_id: str = Field(..., description="Place identifier from address search (Mapbox mapbox_id or Google place_id)")
    display_text: str = Field(..., description="Human-readable text for dropdown (e.g. '123 Main St, City, Country')")
    country_code: str | None = Field(None, description="ISO 3166-1 alpha-2 when country filter was applied (e.g. AR)")


class AddressSuggestResponseSchema(BaseModel):
    """Response for GET /api/v1/addresses/suggest."""

    suggestions: list[AddressSuggestionSchema] = Field(default_factory=list)


class CitySnapshotMarkerSchema(BaseModel):
    """One restaurant marker on a static map snapshot."""

    restaurant_id: UUID
    name: str
    lat: float
    lng: float
    pixel_x: int = Field(..., description="X position in CSS pixels from top-left of image")
    pixel_y: int = Field(..., description="Y position in CSS pixels from top-left of image")


class CitySnapshotResponseSchema(BaseModel):
    """Response for GET /api/v1/maps/city-snapshot. Static map image with restaurant pin positions."""

    image_url: str | None = Field(
        None, description="Signed URL for the cached map image. None when no restaurants have coordinates."
    )
    center: dict | None = Field(None, description="Center point used for the image: { lat, lng }")
    zoom: int = 14
    width: int
    height: int
    retina: bool
    markers: list[CitySnapshotMarkerSchema] = Field(
        default_factory=list,
        description="Restaurant pins visible in the image with pixel positions for tap target overlay",
    )


# ---------------------------------------------------------------------------
# Interactive map — city pins (GET /api/v1/maps/city-pins)
# ---------------------------------------------------------------------------


class MapPinSchema(BaseModel):
    """One restaurant pin for the interactive Mapbox map."""

    restaurant_id: UUID
    name: str
    lat: float
    lng: float


class ViewportCornerSchema(BaseModel):
    """A single lat/lng corner of a bounding-box viewport."""

    lat: float
    lng: float


class ViewportSchema(BaseModel):
    """NE + SW corners of a recommended camera viewport."""

    ne: ViewportCornerSchema
    sw: ViewportCornerSchema


class CentroidSchema(BaseModel):
    """Geographic anchor point returned alongside city-pins markers."""

    lat: float = Field(description="Latitude of the camera anchor point.")
    lng: float = Field(description="Longitude of the camera anchor point.")
    source: Literal["user_nearest", "city", "city_fallback"] = Field(
        description=(
            "How the anchor was derived. "
            "'user_nearest' — nearest restaurant to the user-supplied address. "
            "'city' — precomputed city centroid (no user anchor supplied). "
            "'city_fallback' — user anchor was >OUTLIER_DISTANCE_KM from every restaurant; "
            "city centroid used instead."
        )
    )


class CityPinsResponseSchema(BaseModel):
    """Response for GET /api/v1/maps/city-pins. Lean marker list + recommended viewport."""

    markers: list[MapPinSchema] = Field(
        default_factory=list,
        description="Active restaurants with coordinates in the requested city, ordered by distance from anchor.",
    )
    recommended_viewport: ViewportSchema | None = Field(
        None,
        description=(
            "NE/SW bounding box enclosing all markers. None when markers is empty. "
            "Pass to fitBounds on the client; add UI-aware padding there."
        ),
    )
    centroid: CentroidSchema | None = Field(
        None,
        description="Camera anchor point. None only when the city has zero geocoded restaurants.",
    )
    more_available: bool = Field(
        False,
        description="True when the city has more restaurants than the returned limit.",
    )
    omitted_count: int = Field(
        0,
        description="Count of restaurants in the city that were not included in this response.",
    )


class RestaurantEnrichedResponseSchema(BaseModel):
    """Schema for enriched restaurant response data with institution, entity, and address details"""

    # filter-registry:exempt reason="primary key; route param not filter param"
    restaurant_id: UUID
    # filter-registry:exempt reason="enriched join field; filter by institution_id instead"
    institution_id: UUID
    # filter-registry:exempt reason="enriched join field; filter by institution_id instead"
    institution_name: str
    # filter-registry:exempt reason="enriched join field; filter by institution_entity_id instead"
    institution_entity_id: UUID
    # filter-registry:exempt reason="enriched join field; filter by institution_entity_id instead"
    institution_entity_name: str
    # filter-registry:exempt reason="enriched join field; address join key, not independently filterable"
    address_id: UUID
    # filter-registry:exempt reason="enriched join field; country_code is registered instead"
    country_name: str
    # filter-registry:exempt reason="enriched join field; address join country; not registered for plate-level filtering"
    country_code: str
    # filter-registry:exempt reason="enriched join field; address subfield, not independently filterable"
    province: str
    # filter-registry:exempt reason="enriched join field; address subfield, not independently filterable"
    city: str
    # filter-registry:exempt reason="enriched join field; address subfield, not independently filterable"
    postal_code: str
    # filter-registry:exempt reason="enriched join field; market dimension, not a restaurant filter"
    currency_metadata_id: UUID
    # filter-registry:exempt reason="enriched join field; market dimension, not a restaurant filter"
    market_credit_value_supplier_local: MoneyDecimal = Field(  # serialises as JSON number; see app/schemas/types.py
        ...,
        description="Supplier credit value in local currency for this market (credit_value_supplier_local); use for live calculation of expected_payout_local_currency when creating plates (credit × market_credit_value_supplier_local)",
    )
    # filter-registry:exempt reason="free-text label; use search filter instead"
    name: str
    # filter-registry:exempt reason="enriched join field; cuisine filter uses cuisine op on name, not cuisine_id directly"
    cuisine_id: UUID | None = None
    # filter-registry:exempt reason="enriched join field; filter by cuisine_id instead"
    cuisine_name: str | None = None
    # filter-registry:exempt reason="i18n translation payload; not filterable"
    cuisine_name_i18n: dict | None = Field(None, exclude=True)
    # filter-registry:exempt reason="free-text display field; not independently filterable"
    tagline: str | None = None
    # filter-registry:exempt reason="i18n translation payload; not filterable"
    tagline_i18n: dict | None = Field(None, exclude=True)
    # filter-registry:exempt reason="boolean display flag; not a filter dimension"
    is_featured: bool = False
    # filter-registry:exempt reason="computed URL; not independently filterable"
    cover_image_url: str | None = None
    # filter-registry:exempt reason="computed aggregate; not independently filterable"
    average_rating: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    # filter-registry:exempt reason="computed aggregate; not independently filterable"
    review_count: int = 0
    # filter-registry:exempt reason="boolean display flag; not a filter dimension"
    verified_badge: bool = False
    # filter-registry:exempt reason="display label; not independently filterable"
    spotlight_label: str | None = None
    # filter-registry:exempt reason="i18n translation payload; not filterable"
    spotlight_label_i18n: dict | None = Field(None, exclude=True)
    # filter-registry:exempt reason="display list; not independently filterable"
    member_perks: list[str] | None = None
    # filter-registry:exempt reason="i18n translation payload; not filterable"
    member_perks_i18n: dict | None = Field(None, exclude=True)
    # filter-registry:exempt reason="internal archival flag; use status filter instead"
    is_archived: bool
    status: Status
    # PostGIS location as GeoJSON dict: {"type": "Point", "coordinates": [lng, lat]}.
    # IMPORTANT: GeoJSON uses [longitude, latitude] ordering — the reverse of conversational
    # "lat/lng". Consumers must read coordinates[0] as longitude and coordinates[1] as latitude.
    # None when the restaurant has not been geocoded yet.
    # filter-registry:exempt reason="PostGIS geometry; geo filter op handles spatial queries separately"
    location: dict | None = None
    # filter-registry:exempt reason="computed readiness flag; not a filter dimension"
    is_ready_for_signup: bool | None = Field(
        None,
        description=(
            "Computed at read time. True when the restaurant meets all activation prerequisites: "
            "status='active', not archived, ≥1 active plate_kitchen_days, active QR code. "
            "Admin-facing endpoints compute this field; public/B2C endpoints do not."
        ),
    )
    # filter-registry:exempt reason="computed readiness detail list; not a filter dimension"
    missing: list[str] | None = Field(
        None,
        description=(
            "Subset of ['status_active', 'not_archived', 'plate_kitchen_days', 'qr'] listing "
            "unmet prerequisites. Empty list when is_ready_for_signup is True."
        ),
    )

    model_config = ConfigDict(from_attributes=True)


class RestaurantBalanceResponseSchema(BaseModel):
    """Schema for restaurant balance response data (read-only)"""

    restaurant_id: UUID
    currency_metadata_id: UUID
    transaction_count: int
    balance: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
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
    currency_metadata_id: UUID
    transaction_count: int
    balance: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
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
    plate_selection_id: UUID | None
    discretionary_id: UUID | None
    currency_metadata_id: UUID
    was_collected: bool
    ordered_timestamp: datetime
    collected_timestamp: datetime | None
    arrival_time: datetime | None
    completion_time: datetime | None
    expected_completion_time: datetime | None
    transaction_type: TransactionType
    credit: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    no_show_discount: NullableMoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    currency_code: str | None
    final_amount: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
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
    plate_selection_id: UUID | None
    plate_name: str | None  # Optional because plate_selection_id can be NULL for discretionary transactions
    discretionary_id: UUID | None
    currency_metadata_id: UUID
    currency_code: str | None
    country_name: str
    country_code: str
    was_collected: bool
    ordered_timestamp: datetime
    collected_timestamp: datetime | None
    arrival_time: datetime | None
    completion_time: datetime | None
    expected_completion_time: datetime | None
    transaction_type: TransactionType
    credit: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    no_show_discount: NullableMoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    final_amount: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
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
    qr_code_checksum: str | None
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
    street_type: str | None = None
    street_name: str | None = None
    building_number: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    country_name: str | None = None
    image_storage_path: str

    model_config = ConfigDict(from_attributes=True)


## Employer schemas REMOVED — employer identity is institution_info (type=employer) + institution_entity_info.
## See docs/plans/MULTINATIONAL_INSTITUTIONS.md

# =============================================================================
# WORKPLACE GROUPS (B2C coworker pickup coordination)
# =============================================================================


# =============================================================================
# 5. PLATE SELECTION & PICKUP SCHEMAS


class PlatePickupEnrichedResponseSchema(BaseModel):
    """Schema for enriched plate pickup response data with restaurant, address, product, and credit information"""

    # filter-registry:exempt reason="primary key"
    plate_pickup_id: UUID
    # filter-registry:exempt reason="FK; not a filter dimension"
    plate_selection_id: UUID
    # filter-registry:exempt reason="auth-scoped via JWT; not a user-input filter"
    user_id: UUID
    restaurant_id: UUID
    # filter-registry:exempt reason="free-text label"
    restaurant_name: str
    # filter-registry:exempt reason="address; restaurant scope handles location filtering"
    country: str
    # filter-registry:exempt reason="address; restaurant scope handles location filtering"
    province: str
    # filter-registry:exempt reason="address; restaurant scope handles location filtering"
    city: str
    # filter-registry:exempt reason="address; restaurant scope handles location filtering"
    postal_code: str
    # filter-registry:exempt reason="computed display string"
    address_display: str | None = None
    plate_id: UUID
    # filter-registry:exempt reason="free-text label"
    product_name: str
    # filter-registry:exempt reason="range-bound; use credit_from / credit_to filter params"
    credit: int
    # filter-registry:exempt reason="kiosk QR data; not a filter dimension"
    qr_code_id: UUID
    # filter-registry:exempt reason="kiosk QR data; not a filter dimension"
    qr_code_payload: str
    # filter-registry:exempt reason="soft-delete flag; server filters by default"
    is_archived: bool
    status: Status
    was_collected: bool | None = False
    # filter-registry:exempt reason="range-bound; use arrival_time_from / arrival_time_to filter params"
    arrival_time: datetime | None
    # filter-registry:exempt reason="range-bound; use completion_time_from / completion_time_to filter params"
    completion_time: datetime | None
    # filter-registry:exempt reason="computed projection; clients display only"
    expected_completion_time: datetime | None
    # filter-registry:exempt reason="opaque token; never filtered"
    confirmation_code: str | None
    # filter-registry:exempt reason="range-bound; use window_from / window_to filter params (deferred to follow-up)"
    window_start: datetime | None = None
    # filter-registry:exempt reason="range-bound; use window_from / window_to filter params (deferred to follow-up)"
    window_end: datetime | None = None

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
    pickup_intent: Literal["offer", "request", "self"] | None = Field(
        "self", description="offer=volunteer to pick up; request=need someone; self=pick up own"
    )
    flexible_on_time: bool | None = Field(None, description="Only when pickup_intent=request; ±30 min flexibility")


class PlateSelectionUpdateSchema(BaseModel):
    """Schema for updating plate selection information"""

    plate_id: UUID | None = None
    restaurant_id: UUID | None = None
    product_id: UUID | None = None
    qr_code_id: UUID | None = None
    credit: int | None = Field(None, gt=0, description="Credit amount required")
    kitchen_day: KitchenDay | None = None
    pickup_time_range: str | None = Field(None, max_length=50)
    pickup_intent: Literal["offer", "request", "self"] | None = None
    flexible_on_time: bool | None = None
    cancel: bool | None = Field(None, description="If true, cancel selection and refund credits")


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
    pickup_intent: str | None = "self"
    flexible_on_time: bool | None = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime
    plate_pickup_id: UUID | None = Field(None, description="Present on create; use for Complete order and plate review")
    editable_until: datetime | None = Field(None, description="Cutoff for edits; 1 hour before kitchen day opens")

    model_config = ConfigDict(from_attributes=True)


class DuplicateKitchenDayDetail(BaseModel):
    """Structured 409 response when user tries to reserve a second plate for same kitchen day"""

    code: Literal["DUPLICATE_KITCHEN_DAY"]
    kitchen_day: str
    existing_plate_selection_id: str  # UUID string
    message: str


class NotifyCoworkersRequest(BaseModel):
    """Request body for POST /plate-selections/{id}/notify-coworkers"""

    user_ids: list[UUID] = Field(..., description="List of coworker user_ids to notify")


class CoworkerEligibilityItem(BaseModel):
    """Single coworker with eligibility for pickup notification"""

    user_id: UUID
    first_name: str
    last_initial: str
    eligible: bool
    ineligibility_reason: str | None = (
        None  # When eligible=false: "already_ordered_different_restaurant" | "already_ordered_different_pickup_time"
    )


class CoworkerEligibilityResponse(RootModel[list[CoworkerEligibilityItem]]):
    """Response for GET /plate-selections/{id}/coworkers - list of coworkers with eligibility"""


class NotifyCoworkersResponse(BaseModel):
    """Response for POST /plate-selections/{id}/notify-coworkers"""

    notified_count: int


# =============================================================================
# 6. ADMIN & DISCRETIONARY SCHEMAS
# =============================================================================


class DiscretionaryCreateSchema(BaseModel):
    """Schema for creating a new discretionary request"""

    user_id: UUID | None = None
    restaurant_id: UUID | None = None
    category: DiscretionaryReason  # Classification: Marketing Campaign, Credit Refund, etc.
    reason: str | None = Field(None, max_length=500)  # Free-form explanation
    amount: Decimal = Field(..., gt=0)
    comment: str | None = Field(None, max_length=500)
    institution_id: UUID | None = Field(
        None, description="Optional: validate selected user/restaurant belongs to this institution"
    )
    market_id: UUID | None = Field(
        None, description="Optional: validate selected user/restaurant belongs to this market"
    )

    @model_validator(mode="after")
    def validate_user_or_restaurant(self):
        """Ensure either user_id or restaurant_id is provided (mutually exclusive)"""
        user_id = self.user_id
        restaurant_id = self.restaurant_id

        if not user_id and not restaurant_id:
            raise I18nValueError("validation.discretionary.recipient_required")

        if user_id and restaurant_id:
            raise I18nValueError("validation.discretionary.conflicting_recipients")

        return self

    @model_validator(mode="after")
    def validate_restaurant_requirement(self):
        """Validate that restaurant_id is provided for restaurant-specific categories"""
        restaurant_id = self.restaurant_id
        category = self.category

        if category:
            restaurant_required = [DiscretionaryReason.ORDER_INCORRECTLY_MARKED, DiscretionaryReason.FULL_ORDER_REFUND]

            if category in restaurant_required and not restaurant_id:
                raise I18nValueError("validation.discretionary.restaurant_required")

        return self


class DiscretionaryUpdateSchema(BaseModel):
    """Schema for updating discretionary request information"""

    user_id: UUID | None = None
    restaurant_id: UUID | None = None
    category: DiscretionaryReason | None = None  # Classification enum
    reason: str | None = Field(None, max_length=500)  # Free-form explanation
    amount: Decimal | None = Field(None, gt=0)
    comment: str | None = Field(None, max_length=500)


class DiscretionaryResponseSchema(BaseModel):
    """Schema for discretionary request response data"""

    discretionary_id: UUID
    user_id: UUID | None = None  # NULL for Supplier requests, required for Client requests
    restaurant_id: UUID | None = None  # NULL for Client requests, required for Supplier requests
    approval_id: UUID | None
    category: DiscretionaryReason  # Classification enum
    reason: str | None  # Free-form explanation
    amount: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    comment: str | None
    is_archived: bool
    status: str = Field(..., description="DiscretionaryStatus: Pending, Cancelled, Approved, Rejected")
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class DiscretionaryEnrichedResponseSchema(BaseModel):
    """Schema for enriched discretionary request response data with user, restaurant, institution, and market information"""

    discretionary_id: UUID
    user_id: UUID | None = None  # NULL for Supplier requests
    user_full_name: str | None = None  # For Customer requests (recipient)
    user_username: str | None = None  # For Customer requests (recipient)
    restaurant_id: UUID | None = None  # NULL for Client requests
    restaurant_name: str | None = None  # For Supplier requests
    institution_id: UUID
    institution_name: str
    currency_metadata_id: UUID | None = None  # NULL for Client requests (no restaurant)
    currency_name: str | None = None
    currency_code: str | None = None
    market_id: UUID | None = None  # Via currency_metadata_id → market_info; NULL for Client
    market_name: str | None = None  # country_name from market_info
    country_code: str | None = None  # from market_info
    approval_id: UUID | None
    category: DiscretionaryReason  # Classification enum
    reason: str | None  # Free-form explanation
    amount: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    comment: str | None
    is_archived: bool
    status: str = Field(..., description="DiscretionaryStatus: Pending, Cancelled, Approved, Rejected")
    created_date: datetime
    modified_date: datetime
    created_by: UUID | None = None  # user_id of creator (derived from discretionary_history CREATE row)
    created_by_name: str | None = None  # display name of creator for table

    model_config = ConfigDict(from_attributes=True)


class DiscretionaryResolutionCreateSchema(BaseModel):
    """Schema for creating discretionary resolutions"""

    discretionary_id: UUID = Field(..., description="ID of the discretionary request")
    resolution: str = Field(..., description="Resolution: 'Approved' or 'Rejected'")
    resolution_comment: str | None = Field(None, description="Comment on the resolution")


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
    resolution_comment: str | None = None


class DiscretionaryApprovalSchema(BaseModel):
    """Schema for approving discretionary requests"""

    resolution_comment: str | None = Field(None, description="Comment on the approval")


class DiscretionaryRejectionSchema(BaseModel):
    """Schema for rejecting discretionary requests"""

    resolution_comment: str = Field(..., description="Reason for rejection")


class DiscretionarySummarySchema(BaseModel):
    """Schema for discretionary request summary (dashboard view). Enriched fields from super-admin endpoints."""

    discretionary_id: UUID
    user_id: UUID | None = None  # NULL for Supplier requests, required for Client requests
    restaurant_id: UUID | None = None  # NULL for Supplier requests, required for Client requests
    category: DiscretionaryReason  # Classification enum
    reason: str | None  # Free-form explanation
    amount: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    status: str = Field(..., description="DiscretionaryStatus: Pending, Cancelled, Approved, Rejected")
    created_date: datetime
    resolved_date: datetime | None = None
    resolved_by: UUID | None = None
    resolution_comment: str | None = None
    # Enriched (super-admin pending-requests / requests): creator and recipient
    created_by: UUID | None = None  # user_id of creator (from discretionary_history CREATE)
    created_by_name: str | None = None  # display name of creator
    user_full_name: str | None = None  # recipient (Customer requests)
    user_username: str | None = None  # recipient (Customer requests)
    restaurant_name: str | None = None  # recipient (Supplier requests)


# =============================================================================
# 6. INSTITUTION ENTITY SCHEMAS
# =============================================================================


class InstitutionEntityCreateSchema(BaseModel):
    """Schema for creating a new institution entity"""

    institution_id: UUID
    address_id: UUID
    tax_id: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    email_domain: str | None = Field(
        None, max_length=255, description="Email domain for enrollment gating (employer) or SSO (all types)"
    )
    is_archived: bool = False


class InstitutionEntityUpdateSchema(BaseModel):
    """Schema for updating institution entity information"""

    institution_id: UUID | None = None
    address_id: UUID | None = None
    tax_id: str | None = Field(None, max_length=50)
    name: str | None = Field(None, max_length=100)
    email_domain: str | None = Field(
        None, max_length=255, description="Email domain for enrollment gating (employer) or SSO (all types)"
    )
    is_archived: bool | None = None
    status: Status | None = None


class InstitutionEntityResponseSchema(BaseModel):
    """Schema for institution entity response data"""

    institution_entity_id: UUID
    institution_id: UUID
    address_id: UUID
    currency_metadata_id: UUID
    tax_id: str
    name: str
    payout_provider_account_id: str | None = None
    payout_aggregator: str | None = None
    payout_onboarding_status: str | None = None
    email_domain: str | None = None
    canonical_key: str | None = Field(None, description="Stable seed/fixture identifier. Null for ad-hoc entities.")
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionEntityUpsertByKeySchema(BaseModel):
    """Schema for idempotent institution entity upsert by canonical_key.

    If an institution entity with the given canonical_key already exists it is
    updated in-place; otherwise a new entity is inserted with that canonical_key.
    Use this endpoint for Postman seed runs and fixture data — never for
    ad-hoc entity creation (use POST /institution-entities instead).

    Auth: Internal only (get_employee_user dependency). Returns 403 for
    Customer/Supplier roles.

    Immutable fields on UPDATE: ``institution_id`` is locked after insert and
    ignored on the update path (entities cannot move between institutions after
    creation). ``currency_metadata_id`` is always derived from the address
    country code on both INSERT and UPDATE — do not send it directly.
    """

    canonical_key: str = Field(
        ...,
        max_length=200,
        description="Stable human-readable identifier, e.g. 'E2E_INSTITUTION_ENTITY_SUPPLIER'",
    )
    institution_id: UUID = Field(..., description="FK to core.institution_info — the owning institution")
    address_id: UUID = Field(..., description="FK to core.address_info — registered office address for this entity")
    tax_id: str = Field(..., max_length=50, description="Tax identification number for the entity's jurisdiction")
    name: str = Field(..., max_length=100, description="Legal entity name as registered with the tax authority")
    email_domain: str | None = Field(
        None,
        max_length=255,
        description="Email domain for domain-gated employer enrollment (employer) or SSO (all types). NULL for suppliers.",
    )
    is_archived: bool = False
    status: Status = Status.ACTIVE
    payout_onboarding_status: str | None = Field(
        None,
        max_length=50,
        description=(
            "Stripe Connect onboarding status. Pass 'complete' on seed/fixture entities "
            "that need to be activatable downstream — restaurant activation gates on this "
            "(see app/services/restaurant_visibility.py). Real entities are written by the "
            "Stripe webhook on completion (app/routes/webhooks.py); leave NULL for those."
        ),
    )


class InstitutionEntityEnrichedResponseSchema(BaseModel):
    """Schema for enriched institution entity response data with institution, address, and market details"""

    institution_entity_id: UUID
    institution_id: UUID
    institution_name: str
    institution_type: RoleType
    currency_metadata_id: UUID
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
    payout_provider_account_id: str | None = None
    payout_aggregator: str | None = None
    payout_onboarding_status: str | None = None
    email_domain: str | None = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierTermsCreateSchema(BaseModel):
    """Schema for creating supplier terms for an institution."""

    no_show_discount: int = Field(0, ge=0, le=100, description="Percentage 0-100 deducted on no-show")
    payment_frequency: PaymentFrequency = Field(
        PaymentFrequency.DAILY, description="daily, weekly, biweekly, or monthly"
    )
    kitchen_open_time: str | None = Field(
        None, description="Pickup available time (HH:MM, e.g. 09:00). NULL = inherit from market default."
    )
    kitchen_close_time: str | None = Field(
        None, description="Order cutoff time (HH:MM, e.g. 13:30). NULL = inherit from market default."
    )
    require_invoice: bool | None = Field(None, description="NULL = inherit from market; TRUE/FALSE = override")
    invoice_hold_days: int | None = Field(None, gt=0, description="NULL = inherit from market default")


class SupplierTermsUpdateSchema(BaseModel):
    """Schema for updating supplier terms."""

    no_show_discount: int | None = Field(None, ge=0, le=100)
    payment_frequency: PaymentFrequency | None = None
    kitchen_open_time: str | None = Field(
        None, description="HH:MM format (e.g. 09:00). NULL = inherit from market default."
    )
    kitchen_close_time: str | None = Field(
        None, description="HH:MM format (e.g. 13:30). NULL = inherit from market default."
    )
    require_invoice: bool | None = None
    invoice_hold_days: int | None = Field(None, gt=0)


class SupplierTermsResponseSchema(BaseModel):
    """Schema for supplier terms response with resolved effective values."""

    supplier_terms_id: UUID
    institution_id: UUID
    institution_entity_id: UUID | None = None
    no_show_discount: int
    payment_frequency: PaymentFrequency
    kitchen_open_time: str | None = None
    kitchen_close_time: str | None = None
    effective_kitchen_open_time: str
    effective_kitchen_close_time: str
    require_invoice: bool | None
    invoice_hold_days: int | None
    effective_require_invoice: bool
    effective_invoice_hold_days: int
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
    provider_transfer_id: str | None = None
    amount: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    currency_code: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class BillPayoutEnrichedResponseSchema(BaseModel):
    """Enriched payout with institution, entity, and billing period context. Entity-level view."""

    bill_payout_id: UUID
    institution_bill_id: UUID
    institution_id: UUID
    institution_name: str
    institution_entity_id: UUID
    institution_entity_name: str
    provider: str
    provider_transfer_id: str | None = None
    amount: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    currency_code: str
    billing_period_start: datetime
    billing_period_end: datetime
    status: str
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class MarketBillingConfigEmbedSchema(BaseModel):
    """Optional embedded billing config for composite market creation.
    All fields have defaults — an empty object is treated as absent."""

    aggregator: str = Field("stripe", max_length=50, description="Payout provider: 'stripe' or 'none'")
    is_active: bool = Field(True, description="Whether payouts are enabled for this market")
    require_invoice: bool = Field(False, description="Whether invoices are required before payout")
    max_unmatched_bill_days: int = Field(30, ge=1, description="Max days for unmatched bills before hold")
    kitchen_open_time: str = Field(
        "09:00", description="Market default pickup available time (HH:MM). Suppliers inherit if not overridden."
    )
    kitchen_close_time: str = Field(
        "13:30", description="Market default order cutoff time (HH:MM). Suppliers inherit if not overridden."
    )
    notes: str | None = Field(None, description="Admin notes")


class MarketBillingConfigUpdateSchema(BaseModel):
    """Schema for updating market billing config. All fields optional."""

    aggregator: str | None = Field(None, max_length=50)
    is_active: bool | None = None
    require_invoice: bool | None = None
    max_unmatched_bill_days: int | None = Field(None, ge=1)
    kitchen_open_time: str | None = Field(None, description="Market default pickup available time (HH:MM).")
    kitchen_close_time: str | None = Field(None, description="Market default order cutoff time (HH:MM).")
    notes: str | None = None


class MarketPayoutAggregatorResponseSchema(BaseModel):
    """Schema for the payout aggregator configured for a market."""

    market_id: UUID
    aggregator: str
    is_active: bool
    require_invoice: bool
    max_unmatched_bill_days: int
    kitchen_open_time: str
    kitchen_close_time: str
    notes: str | None = None
    is_archived: bool = False
    status: Status = Status.ACTIVE
    created_date: datetime | None = None
    modified_by: UUID | None = None
    modified_date: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SupplierInvoiceEnrichedResponseSchema(BaseModel):
    """Enriched supplier invoice with entity name, institution name, created-by user name, and country details."""

    supplier_invoice_id: UUID
    institution_entity_id: UUID
    institution_entity_name: str
    institution_name: str
    country_code: str
    invoice_type: str
    external_invoice_number: str | None = None
    issued_date: date
    amount: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    currency_code: str
    tax_amount: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    tax_rate: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    # Document
    document_url: str | None = None
    document_format: str | None = None
    # Country-specific details (populated based on country_code)
    ar_details: dict | None = None
    pe_details: dict | None = None
    us_details: dict | None = None
    # Review
    status: str
    rejection_reason: str | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    # Created by
    created_by_name: str | None = None
    # Audit
    is_archived: bool
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# 8. NATIONAL HOLIDAYS SCHEMAS
# =============================================================================


class NationalHolidayCreateSchema(BaseModel):
    """Schema for creating a national holiday"""

    country_code: str = Field(
        ..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code (e.g., 'US', 'AR')"
    )
    holiday_name: str = Field(..., max_length=100, description="Name of the holiday")
    holiday_date: date = Field(..., description="Date of the holiday")
    is_recurring: bool = Field(False, description="Whether this holiday recurs annually")
    recurring_month: int | None = Field(None, ge=1, le=12, description="Month for recurring holidays (1-12)")
    recurring_day: int | None = Field(None, ge=1, le=31, description="Day for recurring holidays (1-31)")
    status: Status | None = Field(
        default=None, description="Optional; omit or null and backend assigns default (Active)"
    )

    @model_validator(mode="after")
    def validate_recurring_complete(self):
        """Ensure both recurring_month and recurring_day are provided when is_recurring is True"""
        if self.is_recurring and (self.recurring_month is None or self.recurring_day is None):
            raise I18nValueError("validation.holiday.recurring_fields_required")
        return self


class NationalHolidayUpdateSchema(BaseModel):
    """Schema for updating a national holiday"""

    country_code: str | None = Field(None, min_length=2, max_length=2)
    holiday_name: str | None = Field(None, max_length=100)
    holiday_date: date | None = None
    is_recurring: bool | None = None
    recurring_month: int | None = Field(None, ge=1, le=12)
    recurring_day: int | None = Field(None, ge=1, le=31)
    status: Status | None = Field(None, description="Status of the holiday")

    @model_validator(mode="after")
    def validate_recurring_complete(self):
        """Ensure both recurring_month and recurring_day are provided when is_recurring is set to True"""
        if self.is_recurring is True and (self.recurring_month is None or self.recurring_day is None):
            raise I18nValueError("validation.holiday.recurring_fields_required")
        return self


class NationalHolidayResponseSchema(BaseModel):
    """Schema for national holiday response data"""

    # filter-registry:exempt reason="primary key; route param not filter param"
    holiday_id: UUID
    country_code: str
    # filter-registry:exempt reason="free-text label; covered by search if needed"
    holiday_name: str
    # filter-registry:exempt reason="range-bound; use holiday_date_from / holiday_date_to filter params"
    holiday_date: date
    is_recurring: bool
    recurring_month: int | None
    # filter-registry:exempt reason="paired with recurring_month; rarely filtered alone"
    recurring_day: int | None
    status: Status
    # filter-registry:exempt reason="soft-delete flag; server filters by default"
    is_archived: bool
    source: NationalHolidaySource = Field(
        ..., description="'manual' | 'nager_date' -- client creates are always manual"
    )

    model_config = ConfigDict(from_attributes=True)


class NationalHolidayBulkCreateSchema(BaseModel):
    """Schema for bulk creating national holidays"""

    holidays: list[NationalHolidayCreateSchema] = Field(..., min_length=1, description="List of holidays to create")

    @field_validator("holidays")
    @classmethod
    def validate_holidays_not_empty(cls, v):
        """Ensure at least one holiday is provided"""
        if not v:
            raise I18nValueError("validation.holiday.list_empty")
        return v


class NationalHolidaySyncFromProviderSchema(BaseModel):
    """Optional body for POST /national-holidays/sync-from-provider (Nager.Date import)."""

    years: list[int] | None = Field(
        None,
        description="UTC-bounded calendar years to import; omit for default (current + next year, clamped)",
    )


# ============================================================================
# Restaurant Staff Schemas
# ============================================================================


class DailyOrderItemSchema(BaseModel):
    """Schema for a single order item in daily orders / kiosk view"""

    plate_pickup_id: UUID | None = Field(
        None, description="Pickup ID for POST /plate-pickup/{id}/hand-out or /complete"
    )
    customer_name: str = Field(..., description="Privacy-safe customer initials (M.G.)")
    plate_name: str = Field(..., description="Name of the plate ordered")
    confirmation_code: str | None = Field(None, description="6-digit numeric confirmation code for kiosk verification")
    status: str = Field(..., description="Order status: Pending, Arrived, Handed Out, Completed, Cancelled")
    arrival_time: datetime | None = Field(None, description="When customer scanned QR")
    expected_completion_time: datetime | None = Field(
        None, description="Authoritative pickup deadline (arrival_time + countdown_seconds)"
    )
    completion_time: datetime | None = Field(None, description="When order was completed")
    countdown_seconds: int = Field(300, description="Configured pickup countdown duration")
    extensions_used: int = Field(0, description="Timer extensions used by customer")
    was_collected: bool = Field(False, description="Whether plate was actually picked up")
    pickup_time_range: str = Field(..., description="Expected pickup time range (HH:MM-HH:MM)")
    kitchen_day: str = Field(..., description="Kitchen day for the order")
    pickup_type: str | None = Field(None, description="self / offer / request — from pickup preferences")
    is_no_show: bool = Field(False, description="True when status is Pending and the order's pickup window has passed")

    model_config = ConfigDict(from_attributes=True)


class OrderSummarySchema(BaseModel):
    """Schema for order summary statistics"""

    total_orders: int = Field(..., description="Total number of orders")
    pending: int = Field(..., description="Number of pending orders (not yet arrived)")
    arrived: int = Field(..., description="Number of arrived orders (waiting for pickup)")
    handed_out: int = Field(0, description="Number of orders handed out (waiting for customer confirmation)")
    completed: int = Field(..., description="Number of completed orders")
    no_show: int = Field(0, description="Number of no-show orders (Pending after pickup window closed)")

    model_config = ConfigDict(from_attributes=True)


class RestaurantDailyOrdersSchema(BaseModel):
    """Schema for a restaurant's daily orders"""

    restaurant_id: UUID = Field(..., description="Restaurant UUID")
    restaurant_name: str = Field(..., description="Restaurant name")
    require_kiosk_code_verification: bool = Field(
        False, description="Whether this restaurant requires code entry on kiosk"
    )
    pickup_window_start: str | None = Field(None, description="Earliest pickup time (HH:MM)")
    pickup_window_end: str | None = Field(None, description="Latest pickup time (HH:MM)")
    orders: list[DailyOrderItemSchema] = Field(..., description="List of orders for this restaurant")
    summary: OrderSummarySchema = Field(..., description="Summary statistics for this restaurant")

    model_config = ConfigDict(from_attributes=True)


class DailyOrdersResponseSchema(BaseModel):
    """Schema for daily orders response"""

    order_date: date = Field(..., description="Date of the orders")
    server_time: datetime = Field(..., description="Server timestamp for timer sync (avoids client clock drift)")
    restaurants: list[RestaurantDailyOrdersSchema] = Field(..., description="List of restaurants with their orders")

    model_config = ConfigDict(from_attributes=True)


class VerifyAndHandoffRequest(BaseModel):
    """Request schema for kiosk code verification + handoff"""

    confirmation_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit numeric confirmation code from customer's phone",
    )
    restaurant_id: UUID = Field(..., description="Restaurant where the handoff is happening")

    model_config = ConfigDict(from_attributes=True)


class VerifyCodePlateSchema(BaseModel):
    """Plate info in verify-and-handoff response"""

    plate_name: str
    quantity: int

    model_config = ConfigDict(from_attributes=True)


class VerifyAndHandoffResponse(BaseModel):
    """Response from kiosk code verification + handoff"""

    match: bool = Field(..., description="Whether a matching order was found")
    customer_initials: str | None = Field(None, description="Customer initials (M.G.)")
    plate_pickup_ids: list[UUID] | None = Field(None, description="Matched pickup IDs")
    plates: list[VerifyCodePlateSchema] | None = Field(None, description="Plates in this order")
    status: str | None = Field(None, description="New status after handoff (Handed Out)")
    arrival_time: datetime | None = Field(None, description="When customer scanned QR")
    expected_completion_time: datetime | None = Field(None, description="Pickup deadline")
    handed_out_time: datetime | None = Field(None, description="When handoff was recorded")
    countdown_seconds: int | None = Field(None, description="Timer duration reference")
    extensions_used: int | None = Field(None, description="Timer extensions used")
    max_extensions: int | None = Field(None, description="Max extensions allowed")
    message: str | None = Field(None, description="Error message when match=false")

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Market Schemas
# =============================================================================


class MarketResponseSchema(BaseModel):
    """Schema for market response (country-based subscription markets)"""

    market_id: UUID = Field(..., description="Unique identifier for the market")
    country_name: str = Field(..., description="Full country name (e.g., 'Argentina')")
    country_code: str = Field(
        ..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code (e.g., 'AR')"
    )
    currency_metadata_id: UUID = Field(..., description="FK to currency_metadata")
    currency_code: str | None = Field(None, description="Currency code (enriched from JOIN)")
    currency_name: str | None = Field(None, description="Currency name (enriched from JOIN)")
    credit_value_supplier_local: NullableMoneyDecimal = Field(  # serialises as JSON number; see app/schemas/types.py
        None,
        description="Stable per-credit fiat payout to suppliers (from currency_metadata.credit_value_supplier_local). Use for plan form preview: credit_cost_local_currency = price / credit.",
    )
    currency_conversion_usd: NullableMoneyDecimal = Field(  # serialises as JSON number; see app/schemas/types.py
        None,
        description="Local units per 1 USD (from currency_metadata). Use for plan form preview: credit_cost_usd = credit_cost_local_currency / currency_conversion_usd.",
    )
    timezone: str | None = Field(
        None,
        description="DEPRECATED (PR2) — operational timezone now lives on address_info per-restaurant. Responses return None. Callers that need a runtime tz should look it up on the restaurant's address.",
    )
    language: str = Field("en", description="Default UI locale for this market: en, es, pt")
    phone_dial_code: str | None = Field(
        None,
        description="E.164 dial code prefix for this market (e.g. '+54'). Use as default country in phone input fields.",
    )
    phone_local_digits: int | None = Field(
        None,
        description="Max digits in the national number after the dial code. Use as maxLength hint for phone input (e.g. 10).",
    )
    tax_id_label: str | None = Field(
        None,
        description="Country-specific label for tax ID field (e.g. 'CUIT', 'RUC', 'EIN'). Use as form field label.",
    )
    tax_id_mask: str | None = Field(
        None,
        description="Display mask for tax ID input (e.g. '##-#######'). '#' = digit slot. Frontend auto-inserts literal characters as user types, but must strip them before sending the API payload.",
    )
    tax_id_regex: str | None = Field(
        None,
        description="Regex pattern for raw-digit tax ID validation (e.g. '^\\d{9}$'). Validates digits only — no dashes or separators.",
    )
    tax_id_example: str | None = Field(
        None, description="Example tax ID in raw digits for placeholder text (e.g. '123456789')."
    )
    min_credit_spread_pct: NullableMoneyDecimal = Field(  # serialises as JSON number; see app/schemas/types.py
        None,
        description=(
            "Minimum % spread floor between the cheapest customer per-credit price and credit_value_supplier_local. "
            "Example: 0.20 = 20% floor. Super Admin only to modify. "
            "Null on non-enriched endpoints that do not query market_info."
        ),
    )
    canonical_key: str | None = Field(None, description="Stable seed/fixture identifier. Null for ad-hoc markets.")
    is_archived: bool = Field(..., description="Whether this market is archived")
    status: Status = Field(..., description="Market status (Active/Inactive)")
    created_date: datetime = Field(..., description="When this market was created")
    modified_date: datetime = Field(..., description="When this market was last modified")
    is_ready_for_signup: bool | None = Field(
        None,
        description=(
            "Computed at read time. True when market.status='active' AND the market has at least one "
            "active restaurant with active plate_kitchen_days and an active QR code. "
            "Null on plain (non-enriched) endpoints that do not compute this field. "
            "Do not add a DB column or constraint — the readiness rules may evolve."
        ),
    )
    missing: list[str] | None = Field(
        None,
        description=(
            "Subset of ['ready_restaurant'] listing unmet market-level prerequisites. "
            "['ready_restaurant'] when no ready restaurant exists in this market; "
            "[] when is_ready_for_signup is True. "
            "Null on plain (non-enriched) endpoints that do not compute this field."
        ),
    )

    @computed_field
    @property
    def locale(self) -> str:
        """BCP 47 locale derived from language + country_code (e.g. es-AR)."""
        return f"{self.language}-{self.country_code}"

    model_config = ConfigDict(from_attributes=True)


class LeadsFeaturedRestaurantSchema(BaseModel):
    """Schema for GET /leads/featured-restaurant — single localized values, no _i18n maps."""

    restaurant_id: UUID
    name: str
    cuisine_name: str | None = None
    tagline: str | None = None
    average_rating: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    review_count: int = 0
    cover_image_url: str | None = None
    spotlight_label: str | None = None
    verified_badge: bool = False
    member_perks: list[str] | None = None

    model_config = ConfigDict(from_attributes=True)


class LeadsRestaurantSchema(BaseModel):
    """GET /leads/restaurants — limited public projection of restaurant_info."""

    restaurant_id: UUID
    name: str
    cuisine_name: str | None = None
    tagline: str | None = None
    average_rating: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    review_count: int = 0
    cover_image_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class LeadsPlanSchema(BaseModel):
    """GET /leads/plans — limited public projection of plan_info. All prices are monthly."""

    plan_id: UUID
    name: str
    marketing_description: str | None = None
    features: list[str] = []
    cta_label: str | None = None
    credit: int
    price: float
    highlighted: bool = False
    currency: str

    model_config = ConfigDict(from_attributes=True)


class LeadsCountrySchema(BaseModel):
    """GET /leads/countries and /leads/supplier-countries — one launched or configured country."""

    code: str = Field(..., description="ISO 3166-1 alpha-2 (e.g. 'AR')")
    name: str = Field(..., description="Country name, localized per `language` query param")
    currency: str = Field(..., description="ISO 4217 currency code used by the market (e.g. 'ARS')")
    phone_prefix: str | None = Field(None, description="E.164 dial code (e.g. '+54'); null for pseudo-markets")
    default_locale: str = Field(..., description="Market default UI locale — one of 'en', 'es', 'pt'")

    model_config = ConfigDict(from_attributes=True)


class LeadsCountriesResponseSchema(BaseModel):
    """Envelope for GET /leads/countries and /leads/supplier-countries.

    Wraps the country list and adds a geo-suggested country for the visitor.
    ``suggested_country_code`` is the ISO 3166-1 alpha-2 of the visitor's
    country, resolved from the ``cf-ipcountry`` request header (set by
    Cloudflare when CF fronts the deploy). It is ``null`` when:
    - the header is absent (no Cloudflare in front),
    - the resolved code is not present in the returned ``countries`` list, or
    - the header value is invalid / unresolvable.

    NOTE: Cloudflare is not currently in the kitchen deploy chain (Cloud Run
    direct). This field will return ``null`` for all requests until CF is added.
    It is safe to deploy now; the frontend should treat ``null`` as "no
    suggestion" and fall back to its own default.
    """

    countries: list[LeadsCountrySchema] = Field(
        ..., description="Active (or supplier-configured) markets, same items as the former list response"
    )
    suggested_country_code: str | None = Field(
        None,
        description=(
            "ISO 3166-1 alpha-2 of the visitor's country inferred from the cf-ipcountry header. "
            "null when unresolvable, when the header is absent, or when the code is not in "
            "the returned countries list."
        ),
    )

    model_config = ConfigDict(from_attributes=True)


class LeadInterestCreateSchema(BaseModel):
    """POST /leads/interest — notify-me request from marketing site or B2C app."""

    email: str = Field(..., description="Contact email")
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    city_name: str | None = Field(None, max_length=100)
    zipcode: str | None = Field(None, max_length=20)
    zipcode_only: bool = Field(False, description="Only alert for this zipcode")
    interest_type: str = Field("customer", description="customer, employer, or supplier")
    business_name: str | None = Field(None, max_length=200)
    message: str | None = Field(None, max_length=1000)
    cuisine_id: UUID | None = Field(None, description="Cuisine preference (customer/supplier)")
    employee_count_range: str | None = Field(None, max_length=20, description="Company size range (employer)")


class LeadInterestResponseSchema(BaseModel):
    """Response for lead interest endpoints."""

    lead_interest_id: UUID
    email: str
    country_code: str
    city_name: str | None = None
    zipcode: str | None = None
    zipcode_only: bool = False
    interest_type: str
    business_name: str | None = None
    message: str | None = None
    cuisine_id: UUID | None = None
    employee_count_range: str | None = None
    status: str
    source: str
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


class RestaurantLeadCreateSchema(BaseModel):
    """POST /leads/restaurant-interest — restaurant supplier application."""

    business_name: str = Field(..., max_length=200)
    contact_name: str = Field(..., max_length=200)
    contact_email: str = Field(..., description="Contact email")
    contact_phone: str = Field(..., max_length=30)
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    city_name: str = Field(..., max_length=100)
    cuisine_ids: list[UUID] = Field(..., min_length=1, description="At least one cuisine")
    years_in_operation: int = Field(..., ge=0)
    employee_count_range: str = Field(..., max_length=20, description="e.g. 1-5, 6-15, 16-50, 50+")
    kitchen_capacity_daily: int = Field(..., ge=1, description="Estimated daily meal output")
    website_url: str | None = Field(None, max_length=500)
    referral_source: str = Field(..., description="ad, referral, search, or other")
    message: str | None = Field(None, max_length=2000)
    vetting_answers: dict | None = Field(
        default_factory=dict, description="Country-specific vetting question answers (JSONB)"
    )
    # Ad click tracking (captured from URL params by frontend)
    gclid: str | None = Field(None, max_length=255)
    fbclid: str | None = Field(None, max_length=255)
    fbc: str | None = Field(None, max_length=500)
    fbp: str | None = Field(None, max_length=255)
    event_id: str | None = Field(None, max_length=255)
    source_platform: str | None = Field(None, max_length=20, description="google, meta, organic, referral")


class RestaurantLeadResponseSchema(BaseModel):
    """Response for POST /leads/restaurant-interest."""

    restaurant_lead_id: UUID
    business_name: str
    contact_email: str
    country_code: str
    lead_status: str
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadsCuisineSchema(BaseModel):
    """GET /leads/cuisines — public cuisine list for interest form dropdowns."""

    cuisine_id: UUID
    cuisine_name: str

    model_config = ConfigDict(from_attributes=True)


class EmployeeCountRangeSchema(BaseModel):
    """GET /leads/employee-count-ranges — predefined company size ranges."""

    range_id: str
    label: str


class MarketPublicMinimalSchema(BaseModel):
    """Minimal schema for public GET /leads/markets (no auth). country_code, country_name, language, and phone prefix for B2C pre-auth locale and signup form."""

    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 (e.g. AR)")
    country_name: str = Field(..., description="Full country name (e.g. Argentina)")
    language: str = Field(..., min_length=2, max_length=5, description="Default UI locale for this market: en, es, pt")
    phone_dial_code: str | None = Field(
        None, description="E.164 dial code prefix (e.g. '+54'). Use as default country in phone input fields."
    )
    phone_local_digits: int | None = Field(
        None,
        description="Max digits in the national number after the dial code. Use as maxLength hint for phone input (e.g. 10).",
    )
    has_active_kitchens: bool = Field(
        ...,
        description="True when this market has at least one active institution → restaurant → plate → plate_kitchen_days chain. Use to gate subscribable markets on the marketing site.",
    )

    @computed_field
    @property
    def locale(self) -> str:
        """BCP 47 locale derived from language + country_code (e.g. es-AR)."""
        return f"{self.language}-{self.country_code}"


class MarketPublicResponseSchema(BaseModel):
    """Full market schema for authenticated endpoints. For unauthenticated /leads/markets use MarketPublicMinimalSchema."""

    market_id: UUID = Field(..., description="Unique identifier for the market")
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 (e.g. AR)")
    country_name: str = Field(..., description="Full country name (e.g. Argentina)")
    timezone: str | None = Field(
        None, description="DEPRECATED (PR2) — operational timezone now per-restaurant. Responses return None."
    )
    kitchen_close_time: str = Field(..., description="Kitchen close time template (HH:MM naive wall-clock, e.g. 13:30)")
    language: str = Field("en", description="Default UI locale for this market: en, es, pt")
    phone_dial_code: str | None = Field(
        None, description="E.164 dial code prefix (e.g. '+54'). Use as default country in phone input fields."
    )
    phone_local_digits: int | None = Field(
        None,
        description="Max digits in the national number after the dial code. Use as maxLength hint for phone input (e.g. 10).",
    )
    tax_id_label: str | None = Field(
        None,
        description="Country-specific label for tax ID field (e.g. 'CUIT', 'RUC', 'EIN'). Use as form field label.",
    )
    tax_id_mask: str | None = Field(
        None, description="Display mask for tax ID input (e.g. '##-#######'). '#' = digit slot."
    )
    tax_id_regex: str | None = Field(
        None, description="Regex pattern for raw-digit tax ID validation (e.g. '^\\d{9}$')."
    )
    tax_id_example: str | None = Field(None, description="Example tax ID in raw digits for placeholder text.")
    currency_code: str | None = Field(None, description="Currency code")
    currency_name: str | None = Field(None, description="Currency name")

    @computed_field
    @property
    def locale(self) -> str:
        """BCP 47 locale derived from language + country_code (e.g. es-AR)."""
        return f"{self.language}-{self.country_code}"

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

    country_code: str = Field(
        ...,
        description="ISO 3166-1 alpha-2 or alpha-3 (e.g. AR, ARG, DE, DEU). API normalizes to alpha-2.",
        min_length=2,
        max_length=3,
    )
    currency_metadata_id: UUID = Field(..., description="FK to currency_metadata")
    timezone: str = Field(..., description="Timezone (e.g., 'America/Argentina/Buenos_Aires')", max_length=50)
    status: Status | None = Field(
        default=None, description="Optional; omit or null and backend assigns default (Active)"
    )
    language: str | None = Field(
        None, min_length=2, max_length=5, description="Default UI locale: en, es, pt; derived from country if omitted"
    )
    phone_dial_code: str | None = Field(
        None, max_length=6, description="E.164 dial code prefix (e.g. '+54'). Derived from country_code if omitted."
    )
    phone_local_digits: int | None = Field(
        None, description="Max digits in the national number after the dial code (e.g. 10)."
    )
    billing_config: MarketBillingConfigEmbedSchema | None = Field(
        None,
        description="Embedded billing configuration. If omitted, defaults are created automatically for non-global markets.",
    )

    @field_validator("country_code")
    @classmethod
    def normalize_country_code_create(cls, v):
        """Normalize country_code at API boundary (uppercase, max 2 chars)."""
        return normalize_country_code(v) if v else v

    @field_validator("language")
    @classmethod
    def validate_market_language_create(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = tuple(settings.SUPPORTED_LOCALES)
        if v not in allowed:
            raise I18nValueError("validation.market.language_unsupported", language=v, allowed=", ".join(allowed))
        return v


class MarketUpdateSchema(BaseModel):
    """Schema for updating a market. When country_code is provided, country_name is derived by the backend."""

    country_code: str | None = Field(
        None, description="ISO 3166-1 alpha-2 or alpha-3. API normalizes to alpha-2.", min_length=2, max_length=3
    )
    currency_metadata_id: UUID | None = Field(None, description="FK to currency_metadata")
    timezone: str | None = Field(None, description="Timezone", max_length=50)
    status: Status | None = Field(None, description="Market status")
    is_archived: bool | None = Field(None, description="Archive status")
    language: str | None = Field(None, min_length=2, max_length=5, description="Default UI locale: en, es, pt")
    phone_dial_code: str | None = Field(None, max_length=6, description="E.164 dial code prefix (e.g. '+54').")
    phone_local_digits: int | None = Field(
        None, description="Max digits in the national number after the dial code (e.g. 10)."
    )
    confirm_deactivate: bool = Field(
        False,
        description=(
            "Second-confirm flag for setting status='inactive' on a market that currently has active "
            "plate coverage. Required (must be True) for that specific case; ignored otherwise. "
            "Prevents accidental customer-facing takedowns."
        ),
    )

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
    def validate_market_language_update(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = tuple(settings.SUPPORTED_LOCALES)
        if v not in allowed:
            raise I18nValueError("validation.market.language_unsupported", language=v, allowed=", ".join(allowed))
        return v


class MarketUpsertByKeySchema(BaseModel):
    """Schema for idempotent market upsert by canonical_key.

    If a market with the given canonical_key already exists it is updated
    in-place; otherwise a new market is inserted with that canonical_key.
    Use this endpoint for Postman seed runs and fixture data — never for
    ad-hoc market creation (use POST /markets instead).

    Auth: Internal only (get_employee_user dependency). Returns 403 for
    Customer/Supplier roles.

    Immutable fields on UPDATE: ``country_code`` is locked after insert and
    ignored on the update path (each market has a unique country_code that
    must not change).
    """

    canonical_key: str = Field(
        ...,
        max_length=200,
        description="Stable human-readable identifier, e.g. 'E2E_MARKET_AR'",
    )
    country_code: str = Field(
        ...,
        description="ISO 3166-1 alpha-2 or alpha-3 (e.g. AR, ARG). API normalizes to alpha-2.",
        min_length=2,
        max_length=3,
    )
    currency_metadata_id: UUID = Field(..., description="FK to core.currency_metadata")
    language: str | None = Field(
        None, min_length=2, max_length=5, description="Default UI locale: en, es, pt; derived from country if omitted"
    )
    phone_dial_code: str | None = Field(
        None, max_length=6, description="E.164 dial code prefix (e.g. '+54'). Derived from country_code if omitted."
    )
    phone_local_digits: int | None = Field(
        None, description="Max digits in the national number after the dial code (e.g. 10)."
    )
    status: Status = Status.ACTIVE

    @field_validator("country_code")
    @classmethod
    def normalize_country_code_upsert(cls, v: str) -> str:
        """Normalize country_code at API boundary (uppercase, max 2 chars)."""
        return normalize_country_code(v) if v else v

    @field_validator("language")
    @classmethod
    def validate_market_language_upsert(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = tuple(settings.SUPPORTED_LOCALES)
        if v not in allowed:
            raise I18nValueError("validation.market.language_unsupported", language=v, allowed=", ".join(allowed))
        return v


# =============================================================================
# MARKET SPREAD FLOOR
# =============================================================================


class MarketSpreadFloorUpdateSchema(BaseModel):
    """Request schema for PATCH /api/v1/markets/{market_id}/spread-floor.

    Super Admin only. Sets the minimum % spread between the cheapest active
    plan's per-credit price and credit_value_supplier_local for the market.

    If the new floor would conflict with any active plan (i.e. the floor is
    being raised above the current observed spread), the same warn-and-ack
    contract applies: set acknowledge_spread_compression=true to accept.
    """

    min_credit_spread_pct: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Minimum spread floor as a decimal fraction (e.g. 0.20 = 20%). Must be between 0 and 1.",
    )
    acknowledge_spread_compression: bool = Field(
        False,
        description="Set to true to acknowledge that the new floor conflicts with an active plan.",
    )
    spread_acknowledgement_justification: str | None = Field(
        None, description="Optional free-text justification for spread compression acknowledgement."
    )


# =============================================================================
# SPREAD READOUT (headroom endpoint)
# =============================================================================


class SpreadReadoutResponseSchema(BaseModel):
    """Response schema for GET /api/v1/markets/{market_id}/spread-readout.

    Returns the current spread between the cheapest active plan's per-credit
    price and the supplier credit value, for finance/admin visibility.
    """

    cheapest_plan_per_credit: NullableMoneyDecimal = Field(  # serialises as JSON number; see app/schemas/types.py
        None,
        description="Cheapest per-credit price across active plans (min plan.price/plan.credit). "
        "Null when no active plans exist.",
    )
    supplier_value: NullableMoneyDecimal = Field(  # serialises as JSON number; see app/schemas/types.py
        None,
        description="credit_value_supplier_local for the market. Null when market has no currency.",
    )
    headroom_pct: MoneyDecimal = Field(  # serialises as JSON number; see app/schemas/types.py
        ...,
        description="Observed spread percentage: min(plan.price/plan.credit)/credit_value_supplier_local - 1. "
        "Negative means below floor.",
    )
    floor_pct: MoneyDecimal = Field(  # serialises as JSON number; see app/schemas/types.py
        ...,
        description="The market's min_credit_spread_pct (the required minimum spread).",
    )
    offending_plan_ids: list[str] = Field(
        default_factory=list,
        description="UUIDs of active plans whose price/credit is below the floor threshold.",
    )


# =============================================================================
# MARGIN REPORT
# =============================================================================


class MarginReportPlanRow(BaseModel):
    """Per-plan-tier margin breakdown row for the margin report response."""

    plan_id: UUID
    plan_name: str
    redemptions: MoneyDecimal = Field(
        ..., description="Total credits redeemed by customers on this plan tier."
    )  # serialises as JSON number; see app/schemas/types.py
    margin_per_credit: MoneyDecimal = Field(  # serialises as JSON number; see app/schemas/types.py
        ...,
        description="credit_cost_local_currency - credit_value_supplier_local for this plan tier.",
    )
    margin_local: MoneyDecimal = Field(
        ..., description="margin_per_credit × redemptions for this plan tier."
    )  # serialises as JSON number; see app/schemas/types.py


class MarginReportResponseSchema(BaseModel):
    """Response schema for GET /internal/margin-report.

    Per-market per-period gross margin aggregation.
    """

    market_id: UUID
    period_start: datetime
    period_end: datetime
    total_margin_local: MoneyDecimal = Field(
        ..., description="Total gross margin in local currency over the period."
    )  # serialises as JSON number; see app/schemas/types.py
    total_credits_redeemed: MoneyDecimal = Field(
        ..., description="Total credits redeemed across all plan tiers."
    )  # serialises as JSON number; see app/schemas/types.py
    by_plan: list[MarginReportPlanRow] = Field(
        default_factory=list,
        description="Per-plan-tier margin breakdown.",
    )
    currency_code: str | None = Field(None, description="ISO currency code for the market.")


# =============================================================================
# PHONE VALIDATION (no auth — real-time form feedback)
# =============================================================================


class PhoneValidateRequestSchema(BaseModel):
    """Request schema for POST /api/v1/phone/validate."""

    mobile_number: str = Field(..., description="Raw phone number string (E.164 or local format)")
    country_code: str | None = Field(
        None,
        min_length=2,
        max_length=3,
        description="ISO 3166-1 alpha-2 hint (e.g. 'AR'). Helps parse local-format numbers without the dial code.",
    )


class PhoneValidateResponseSchema(BaseModel):
    """Response schema for POST /api/v1/phone/validate. Always returns 200; valid indicates whether the number is valid."""

    valid: bool = Field(..., description="True if the number is valid and parseable")
    e164: str | None = Field(
        None, description="Normalized E.164 form (e.g. '+5491112345678'). Present only when valid=true."
    )
    display: str | None = Field(
        None, description="International display form (e.g. '+54 9 11 2345-6789'). Present only when valid=true."
    )
    error: str | None = Field(None, description="Human-readable error message. Present only when valid=false.")


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


class LeadsCityWithCountSchema(BaseModel):
    """Single city entry for GET /api/v1/leads/cities?mode=coverage (vianda-home marketing site)."""

    city: str = Field(..., description="City display name")
    restaurant_count: int = Field(..., ge=0, description="Active restaurants with plate coverage in this city")


class LeadsCitiesResponseSchema(BaseModel):
    """Response for GET /api/v1/leads/cities (unauthenticated lead flow — cities we serve)."""

    cities: list[str] = Field(..., description="City names that have at least one restaurant in the country")


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

    values: list[str] = Field(..., description="Canonical codes stored in DB / API")
    labels: dict[str, str] = Field(
        ..., description="Map of code -> display label for requested language (fallback: en, then code)"
    )


class EnumsResponseSchema(RootModel[dict[str, EnumLabeledValuesSchema]]):
    """
    All system enums as a map of enum name -> { values, labels }.
    Keys vary by role (e.g. Customers omit role_type / role_name).
    """

    root: dict[str, EnumLabeledValuesSchema]

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


# =============================================================================
# INGREDIENT CATALOG SCHEMAS
# =============================================================================


class IngredientSearchResultSchema(BaseModel):
    """Single result item from GET /ingredients/search or POST /ingredients/custom."""

    ingredient_id: UUID
    name_display: str
    name_en: str | None = None
    off_taxonomy_id: str | None = None
    image_url: str | None = None  # null while unenriched → show generic icon
    source: str
    is_verified: bool
    image_enriched: bool  # True once Wikidata image cron has run for this entry


class IngredientCustomCreateSchema(BaseModel):
    """Request body for POST /ingredients/custom."""

    name: str = Field(..., min_length=2, max_length=150)
    lang: str | None = Field(None, pattern="^(es|en|pt)$")


class ProductIngredientResponseSchema(BaseModel):
    """Single ingredient row from GET /products/{id}/ingredients."""

    product_ingredient_id: UUID
    ingredient_id: UUID
    name_display: str
    name_en: str | None = None
    image_url: str | None = None
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class ProductIngredientsSetSchema(BaseModel):
    """Request body for POST /products/{id}/ingredients (full replacement)."""

    ingredient_ids: list[UUID] = Field(..., max_length=30)


# =============================================================================
# Referral Schemas
# =============================================================================


class ReferralConfigUpdateSchema(BaseModel):
    """Schema for updating referral configuration for a market"""

    is_enabled: bool | None = None
    referrer_bonus_rate: int | None = Field(None, ge=1, le=100)
    referrer_bonus_cap: Decimal | None = Field(None, ge=0)
    referrer_monthly_cap: int | None = Field(None, ge=1)
    min_plan_price_to_qualify: Decimal | None = Field(None, ge=0)
    cooldown_days: int | None = Field(None, ge=0)
    held_reward_expiry_hours: int | None = Field(None, ge=1)
    pending_expiry_days: int | None = Field(None, ge=1)


class ReferralConfigResponseSchema(BaseModel):
    """Schema for referral configuration response"""

    referral_config_id: UUID
    market_id: UUID
    is_enabled: bool
    referrer_bonus_rate: int
    referrer_bonus_cap: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    referrer_monthly_cap: int | None = None
    min_plan_price_to_qualify: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    cooldown_days: int
    held_reward_expiry_hours: int
    pending_expiry_days: int
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ReferralConfigEnrichedResponseSchema(BaseModel):
    """Schema for enriched referral config response with market name and country code"""

    referral_config_id: UUID
    market_id: UUID
    market_name: str
    country_code: str
    is_enabled: bool
    referrer_bonus_rate: int
    referrer_bonus_cap: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    referrer_monthly_cap: int | None = None
    min_plan_price_to_qualify: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    cooldown_days: int
    held_reward_expiry_hours: int
    pending_expiry_days: int
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ReferralInfoResponseSchema(BaseModel):
    """Schema for referral info response"""

    referral_id: UUID
    referrer_user_id: UUID
    referee_user_id: UUID
    referral_code_used: str
    market_id: UUID
    referral_status: str
    bonus_credits_awarded: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    bonus_plan_price: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    bonus_rate_applied: int | None = None
    qualified_date: datetime | None = None
    rewarded_date: datetime | None = None
    is_archived: bool
    status: Status
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ReferralTransactionCreateSchema(BaseModel):
    """Schema for creating a referral-transaction bridge row"""

    referral_id: UUID
    transaction_id: UUID


class ReferralTransactionResponseSchema(BaseModel):
    """Schema for referral-transaction bridge row response"""

    referral_transaction_id: UUID
    referral_id: UUID
    transaction_id: UUID
    is_archived: bool
    status: Status
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ReferralMyCodeResponseSchema(BaseModel):
    """Schema for the user's own referral code"""

    referral_code: str


class ReferralStatsResponseSchema(BaseModel):
    """Schema for referral stats summary"""

    total_referrals: int
    total_credits_earned: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    pending_count: int


# =============================================================================
# AD CLICK TRACKING
# =============================================================================


class AdClickTrackingCreateSchema(BaseModel):
    """POST body when capturing click identifiers from frontend."""

    subscription_id: UUID | None = None
    gclid: str | None = Field(None, max_length=255)
    wbraid: str | None = Field(None, max_length=255)
    gbraid: str | None = Field(None, max_length=255)
    fbclid: str | None = Field(None, max_length=255)
    fbc: str | None = Field(None, max_length=500)
    fbp: str | None = Field(None, max_length=255)
    event_id: str | None = Field(None, max_length=255)
    landing_url: str | None = Field(None, max_length=2000)
    source_platform: str | None = Field(None, max_length=20)


class AdClickTrackingResponseSchema(BaseModel):
    """Response for ad click tracking records."""

    id: UUID
    user_id: UUID
    subscription_id: UUID | None = None
    source_platform: str | None = None
    google_upload_status: str
    meta_upload_status: str
    captured_at: datetime
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# AD ZONES (GEOGRAPHIC FLYWHEEL)
# =============================================================================


class AdZoneCreateSchema(BaseModel):
    """POST body for operator-created zones."""

    name: str = Field(..., max_length=100)
    country_code: str = Field(..., min_length=2, max_length=2)
    city_name: str = Field(..., max_length=100)
    neighborhood: str | None = Field(None, max_length=100)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(default=2.0, ge=1.0, le=50.0)
    flywheel_state: str | None = Field(
        "monitoring", description="Initial state. Operator can set directly for cold start."
    )
    daily_budget_cents: int | None = Field(None, ge=0)
    budget_allocation: dict | None = None


class AdZoneUpdateSchema(BaseModel):
    """PATCH body for updating zone state, budget, or metrics."""

    name: str | None = Field(None, max_length=100)
    neighborhood: str | None = Field(None, max_length=100)
    flywheel_state: str | None = None
    daily_budget_cents: int | None = Field(None, ge=0)
    budget_allocation: dict | None = None
    radius_km: float | None = Field(None, ge=1.0, le=50.0)


class AdZoneResponseSchema(BaseModel):
    """Response for ad zone records."""

    id: UUID
    name: str
    country_code: str
    city_name: str
    neighborhood: str | None = None
    latitude: float
    longitude: float
    radius_km: float
    flywheel_state: str
    state_changed_at: datetime
    notify_me_lead_count: int
    active_restaurant_count: int
    active_subscriber_count: int
    estimated_mau: int | None = None
    budget_allocation: dict | None = None
    daily_budget_cents: int | None = None
    created_by: str
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# WORKPLACE GROUP SCHEMAS
# =============================================================================


class WorkplaceGroupCreateSchema(BaseModel):
    """Schema for creating a workplace group."""

    name: str = Field(..., min_length=1, max_length=100)
    email_domain: str | None = Field(None, max_length=255)
    require_domain_verification: bool = False


class WorkplaceGroupUpdateSchema(BaseModel):
    """Schema for updating a workplace group."""

    name: str | None = Field(None, min_length=1, max_length=100)
    email_domain: str | None = Field(None, max_length=255)
    require_domain_verification: bool | None = None
    status: Status | None = None


class WorkplaceGroupResponseSchema(BaseModel):
    """Response schema for workplace group."""

    workplace_group_id: UUID
    name: str
    email_domain: str | None = None
    require_domain_verification: bool
    is_archived: bool
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkplaceGroupSearchResultSchema(BaseModel):
    """Search result for workplace group fuzzy search."""

    workplace_group_id: UUID
    name: str
    sim: float
    member_count: int

    model_config = ConfigDict(from_attributes=True)


class WorkplaceGroupEnrichedResponseSchema(BaseModel):
    """Enriched response for workplace group with member count."""

    workplace_group_id: UUID
    name: str
    email_domain: str | None = None
    require_domain_verification: bool
    is_archived: bool
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime
    member_count: int

    model_config = ConfigDict(from_attributes=True)


class AssignWorkplaceRequest(BaseModel):
    """Schema for PUT /users/me/workplace — assign workplace group and address to current user."""

    workplace_group_id: UUID = Field(..., description="Workplace group to join")
    address_id: UUID = Field(..., description="Workplace group address where user picks up")


# =============================================================================
# BILLING — PAYMENT ATTEMPT (multi-provider, issue #74)
# =============================================================================


class PaymentAttemptCreateSchema(BaseModel):
    """Request body for creating a new billing.payment_attempt row.
    Callers: subscription renewal cron (status=pending) and manual admin flows.
    Webhook handlers update the row via PaymentAttemptUpdateSchema, not create."""

    provider: PaymentProvider
    amount_cents: int = Field(..., ge=0, description="Charge amount in smallest currency unit")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 3-letter code")
    provider_payment_id: str | None = Field(None, description="Provider-assigned ID (e.g. Stripe pi_…)")
    idempotency_key: str | None = Field(None, description="Idempotency key sent to the provider")
    provider_status: str | None = Field(None, description="Raw provider status string")


class PaymentAttemptUpdateSchema(BaseModel):
    """Partial update for billing.payment_attempt. Used by webhook handlers to record
    outcome after the provider responds. Only the fields being updated need to be supplied."""

    payment_status: PaymentAttemptStatus | None = None
    provider_payment_id: str | None = None
    provider_status: str | None = None
    failure_reason: str | None = None
    provider_fee_cents: int | None = None


class PaymentAttemptResponseSchema(BaseModel):
    """Response shape for a billing.payment_attempt row. Returned by GET endpoints
    that surface payment attempt details to internal/admin callers."""

    payment_attempt_id: UUID
    provider: PaymentProvider
    provider_payment_id: str | None
    idempotency_key: str | None
    amount_cents: int
    currency: str
    payment_status: PaymentAttemptStatus
    provider_status: str | None
    failure_reason: str | None
    provider_fee_cents: int | None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)
