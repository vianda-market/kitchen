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

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.config import BillPayoutStatus, DiscretionaryReason, RoleName, RoleType, Status
from app.config.enums import (
    PaymentAttemptStatus,
    PaymentFrequency,
    PaymentProvider,
    SupplierInvoiceStatus,
    SupplierInvoiceType,
)

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
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    mobile_number: str | None = None
    mobile_number_verified: bool = False
    mobile_number_verified_at: datetime | None = None
    email_verified: bool = False
    email_verified_at: datetime | None = None
    employer_entity_id: UUID | None = None
    employer_address_id: UUID | None = None
    workplace_group_id: UUID | None = None
    support_email_suppressed_until: datetime | None = None
    last_support_email_date: datetime | None = None
    market_id: UUID
    city_metadata_id: UUID | None = None
    locale: str = "en"
    referral_code: str | None = None
    referred_by_code: str | None = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionDTO(BaseModel):
    """Pure DTO for institution data"""

    institution_id: UUID
    name: str
    institution_type: RoleType  # Internal, Customer, Supplier, or Employer
    # market_id removed — institution markets now in core.institution_market junction
    support_email_suppressed_until: datetime | None = None
    last_support_email_date: datetime | None = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


# RoleDTO removed - role_info table deprecated, roles stored directly on user_info as enums


class ProductDTO(BaseModel):
    """Pure DTO for product data"""

    product_id: UUID
    institution_id: UUID
    name: str
    name_i18n: dict | None = None
    ingredients: str | None = None
    ingredients_i18n: dict | None = None
    description: str | None = None
    description_i18n: dict | None = None
    dietary: list[str] | None = None
    is_archived: bool = False
    status: Status
    image_url: str
    image_storage_path: str
    image_thumbnail_url: str
    image_thumbnail_storage_path: str
    image_checksum: str
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class PlateDTO(BaseModel):
    """Pure DTO for plate data. Savings are computed on the fly (e.g. explore by-city) from price, credit, and user plan credit_cost_local_currency. expected_payout_local_currency set by DB trigger."""

    plate_id: UUID
    product_id: UUID
    restaurant_id: UUID
    price: Decimal
    credit: Decimal
    expected_payout_local_currency: Decimal
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
    would_order_again: bool | None = None
    comment: str | None = None
    is_archived: bool = False
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationBannerDTO(BaseModel):
    """Pure DTO for in-app notification banner data."""

    notification_id: UUID
    user_id: UUID
    notification_type: str
    priority: str
    payload: dict
    action_type: str
    action_label: str
    client_types: list[str]
    action_status: str
    expires_at: datetime
    acknowledged_at: datetime | None = None
    dedup_key: str
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class PortionComplaintDTO(BaseModel):
    """Pure DTO for portion complaint data. Filed when customer rates portion size as 1 and chooses to complain."""

    complaint_id: UUID
    plate_pickup_id: UUID
    plate_review_id: UUID | None = None
    user_id: UUID
    restaurant_id: UUID
    photo_storage_path: str | None = None
    complaint_text: str | None = None
    resolution_status: str = "open"
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


class CuisineDTO(BaseModel):
    """Pure DTO for cuisine lookup table data."""

    cuisine_id: UUID
    cuisine_name: str
    cuisine_name_i18n: dict | None = None
    slug: str
    parent_cuisine_id: UUID | None = None
    description: str | None = None
    origin_source: str = "seed"
    display_order: int | None = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class CuisineSuggestionDTO(BaseModel):
    """Pure DTO for cuisine suggestion workflow data."""

    suggestion_id: UUID
    suggested_name: str
    suggested_by: UUID
    restaurant_id: UUID | None = None
    suggestion_status: str = "pending"
    reviewed_by: UUID | None = None
    reviewed_date: datetime | None = None
    review_notes: str | None = None
    resolved_cuisine_id: UUID | None = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class RestaurantDTO(BaseModel):
    """Pure DTO for restaurant data. credit_currency comes from institution_entity."""

    restaurant_id: UUID
    institution_id: UUID
    institution_entity_id: UUID
    address_id: UUID
    name: str
    cuisine_id: UUID | None = None
    pickup_instructions: str | None = None
    tagline: str | None = None
    tagline_i18n: dict | None = None
    is_featured: bool = False
    cover_image_url: str | None = None
    average_rating: Decimal | None = None
    review_count: int = 0
    verified_badge: bool = False
    spotlight_label: str | None = None
    spotlight_label_i18n: dict | None = None
    member_perks: list[str] | None = None
    member_perks_i18n: dict | None = None
    require_kiosk_code_verification: bool = False
    # NOTE: location (PostGIS geometry) is intentionally excluded from this DTO.
    # The CRUD layer uses SELECT * which returns raw WKB bytes — incompatible with
    # Pydantic's dict type. Location is only served via the enriched endpoints
    # which explicitly project ST_AsGeoJSON(r.location)::jsonb → dict.
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
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
    currency_metadata_id: UUID
    transaction_count: int | None = None
    amount: Decimal | None = None
    currency_code: str | None = None
    period_start: datetime
    period_end: datetime
    is_archived: bool = False
    status: Status
    resolution: str
    tax_doc_external_id: str | None = None
    created_date: datetime
    created_by: UUID | None = None
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
    currency_metadata_id: UUID
    transaction_count: int
    balance_event_id: UUID | None = None
    settlement_number: str
    settlement_run_id: UUID | None = None
    institution_bill_id: UUID | None = None
    country_code: str
    status: Status
    is_archived: bool = False
    created_at: datetime
    created_by: UUID | None = None
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
    currency_metadata_id: UUID
    amount: Decimal
    currency_code: str
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentAttemptDTO(BaseModel):
    """Pure DTO for billing.payment_attempt. Financial record for a single payment attempt.
    Provider-specific: one row per attempt regardless of provider (Stripe, Mercado Pago, etc.).
    Written by webhook handlers; read by subscription lifecycle services."""

    payment_attempt_id: UUID
    provider: PaymentProvider
    provider_payment_id: str | None = None
    idempotency_key: str | None = None
    amount_cents: int
    currency: str
    payment_status: PaymentAttemptStatus
    provider_status: str | None = None
    failure_reason: str | None = None
    provider_fee_cents: int | None = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class CreditCurrencyDTO(BaseModel):
    """Pure DTO for core.currency_metadata (Vianda pricing policy).

    Two-tier split: external.iso4217_currency holds raw ISO 4217 name/numeric/minor_unit;
    core.currency_metadata holds Vianda-owned pricing fields below. The DTO class name
    is kept as `CreditCurrencyDTO` to minimize churn across ~15 importers; the underlying
    table and column are named currency_metadata / currency_metadata_id. Display name
    resolves via JOIN external.iso4217_currency ic ON ic.code = cm.currency_code (no
    longer a column on this table — dropped in PR2a).
    """

    currency_metadata_id: UUID
    currency_code: str
    credit_value_local_currency: Decimal
    currency_conversion_usd: Decimal
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
    """Pure DTO for address data. user_id nullable (Supplier/Internal/Employer); floor, apartment_unit, is_default from address_subpremise."""

    address_id: UUID
    institution_id: UUID
    user_id: UUID | None = (
        None  # Required only for Customer Comensal home/other; nullable for Supplier, Internal, Employer
    )
    workplace_group_id: UUID | None = None
    address_type: list[str]
    is_default: bool = False
    floor: str | None = None
    city_metadata_id: UUID  # PR4c: required; source of truth for timezone via geonames_city JOIN
    country_name: str
    country_code: str
    province: str
    city: str
    postal_code: str
    street_type: str
    street_name: str
    building_number: str
    apartment_unit: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class AddressSubpremiseDTO(BaseModel):
    """Pure DTO for address_subpremise (floor, unit, is_default, map_center_label per user at an address)."""

    subpremise_id: UUID
    address_id: UUID
    user_id: UUID
    floor: str | None = None
    apartment_unit: str | None = None
    is_default: bool = False
    map_center_label: str | None = None
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


## EmployerDTO REMOVED — employer identity is institution_info (type=employer) + institution_entity_info.
## See docs/plans/MULTINATIONAL_INSTITUTIONS.md


class EmployerBenefitsProgramDTO(BaseModel):
    """Pure DTO for employer benefits program configuration"""

    program_id: UUID
    institution_id: UUID
    institution_entity_id: UUID | None = None  # NULL = institution-level defaults; set = entity-level override
    benefit_rate: int
    benefit_cap: Decimal | None = None
    benefit_cap_period: str
    price_discount: int = 0
    minimum_monthly_fee: Decimal | None = None
    billing_cycle: str
    billing_day: int | None = 1
    billing_day_of_week: int | None = None
    enrollment_mode: str
    allow_early_renewal: bool = False
    stripe_customer_id: str | None = None
    stripe_payment_method_id: str | None = None
    payment_method_type: str | None = None
    is_active: bool = True
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployerBillDTO(BaseModel):
    """Pure DTO for employer bill data"""

    employer_bill_id: UUID
    institution_id: UUID
    institution_entity_id: UUID  # bills are per-entity (per-country/currency)
    billing_period_start: datetime
    billing_period_end: datetime
    billing_cycle: str
    total_renewal_events: int = 0
    gross_employer_share: Decimal = Decimal("0")
    price_discount: int = 0
    discounted_amount: Decimal = Decimal("0")
    minimum_fee_applied: bool = False
    billed_amount: Decimal = Decimal("0")
    currency_code: str
    stripe_invoice_id: str | None = None
    payment_status: str = "pending"
    paid_date: datetime | None = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployerBillLineDTO(BaseModel):
    """Pure DTO for employer bill line item data"""

    line_id: UUID
    employer_bill_id: UUID
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    plan_price: Decimal
    benefit_rate: int
    benefit_cap: Decimal | None = None
    benefit_cap_period: str | None = None
    employee_benefit: Decimal
    renewal_date: datetime
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


## EmployerDomainDTO REMOVED — replaced by email_domain column on institution_entity_info.


class LeadInterestDTO(BaseModel):
    """Pure DTO for lead interest data (notify-me requests from marketing site / B2C app)."""

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
    notified_date: datetime | None = None
    is_archived: bool = False
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class RestaurantLeadDTO(BaseModel):
    """Pure DTO for restaurant lead data (vetting pipeline applications)."""

    restaurant_lead_id: UUID
    business_name: str
    contact_name: str
    contact_email: str
    contact_phone: str
    country_code: str
    city_name: str
    years_in_operation: int
    employee_count_range: str
    kitchen_capacity_daily: int
    website_url: str | None = None
    referral_source: str
    message: str | None = None
    vetting_answers: dict = {}
    lead_status: str
    rejection_reason: str | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    institution_id: UUID | None = None
    gclid: str | None = None
    fbclid: str | None = None
    fbc: str | None = None
    fbp: str | None = None
    event_id: str | None = None
    source_platform: str | None = None
    is_archived: bool = False
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class CityDTO(BaseModel):
    """Pure DTO for core.city_metadata (Vianda metadata layer on top of external.geonames_city).

    Renamed from the old city_info-backed CityDTO. Field shape matches the new
    city_metadata table; `name` is NOT on this DTO because it lives on external.geonames_city
    (look up via `cm.geonames_id → gc.name` when you need the display string).

    The class name is kept as `CityDTO` to avoid churning ~15 importers; callers
    that need the display name should use a helper that JOINs external.geonames_city
    or call place_name_resolver (PR2b).
    """

    city_metadata_id: UUID
    geonames_id: int
    country_iso: str
    display_name_override: str | None = None
    display_name_i18n: dict | None = None
    show_in_signup_picker: bool = False
    show_in_supplier_form: bool = False
    show_in_customer_form: bool = False
    is_served: bool = False
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class GeolocationDTO(BaseModel):
    """Pure DTO for geolocation data"""

    geolocation_id: UUID
    latitude: float
    longitude: float
    address_id: UUID | None = None
    place_id: str | None = None
    viewport: dict | None = None
    formatted_address_google: str | None = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
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
    plate_selection_id: UUID | None = None
    discretionary_id: UUID | None = None
    currency_metadata_id: UUID
    was_collected: bool = False
    ordered_timestamp: datetime
    collected_timestamp: datetime | None = None
    arrival_time: datetime | None = None
    completion_time: datetime | None = None
    expected_completion_time: datetime | None = None
    transaction_type: str
    credit: Decimal
    no_show_discount: Decimal | None = None
    currency_code: str | None = None
    final_amount: Decimal
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ClientTransactionDTO(BaseModel):
    """Pure DTO for client transaction data"""

    transaction_id: UUID
    user_id: UUID
    source: str
    plate_selection_id: UUID | None = None
    discretionary_id: UUID | None = None
    credit: int
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
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
    flexible_on_time: bool | None = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class PickupPreferencesDTO(BaseModel):
    """Pure DTO for pickup preferences data"""

    preference_id: UUID
    plate_selection_id: UUID
    user_id: UUID
    pickup_type: str
    target_pickup_time: datetime | None = None
    time_window_minutes: int = 30
    is_matched: bool = False
    matched_with_preference_id: UUID | None = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
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


class UserFcmTokenDTO(BaseModel):
    """Pure DTO for FCM device token. Ephemeral — tokens rotate and are deleted on logout."""

    fcm_token_id: UUID
    user_id: UUID
    token: str
    platform: str
    created_date: datetime
    updated_date: datetime

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
    subscription_status: str | None = None  # Specific subscription status (Active/On Hold/Pending/Cancelled)
    hold_start_date: datetime | None = None  # When subscription was put on hold
    hold_end_date: datetime | None = None  # When subscription is expected to resume
    early_renewal_threshold: int | None = 10  # None = no early renewal; period-end only
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanDTO(BaseModel):
    """Pure DTO for plan data"""

    plan_id: UUID
    market_id: UUID  # Market (country) this plan belongs to
    name: str
    name_i18n: dict | None = None
    marketing_description: str | None = None
    marketing_description_i18n: dict | None = None
    features: list[str] | None = None
    features_i18n: dict | None = None
    cta_label: str | None = None
    cta_label_i18n: dict | None = None
    credit: int
    price: Decimal
    highlighted: bool = False
    credit_cost_local_currency: Decimal  # price / credit (local currency per credit), set by DB trigger
    credit_cost_usd: Decimal  # credit_cost_local_currency / currency_conversion_usd, set by DB trigger
    rollover: bool
    rollover_cap: Decimal | None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# INSTITUTION ENTITY DTOs
# =============================================================================


class InstitutionEntityDTO(BaseModel):
    """Pure DTO for institution entity data. currency_metadata_id from market for entity address country."""

    institution_entity_id: UUID
    institution_id: UUID
    address_id: UUID
    currency_metadata_id: UUID
    tax_id: str
    name: str
    payout_provider_account_id: str | None = None
    payout_aggregator: str | None = None
    payout_onboarding_status: str | None = None
    email_domain: str | None = None  # For domain-gated enrollment (employer entities) and future SSO (all entity types)
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierTermsDTO(BaseModel):
    """Pure DTO for supplier terms — negotiated per-supplier institution."""

    supplier_terms_id: UUID
    institution_id: UUID
    institution_entity_id: UUID | None = None  # NULL = institution-level; set = entity-level override
    no_show_discount: int = 0
    payment_frequency: PaymentFrequency = PaymentFrequency.DAILY
    kitchen_open_time: time | None = None
    kitchen_close_time: time | None = None
    require_invoice: bool | None = None
    invoice_hold_days: int | None = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class MarketPayoutAggregatorDTO(BaseModel):
    """Pure DTO for market-level payout/billing configuration."""

    market_id: UUID
    aggregator: str
    is_active: bool = True
    require_invoice: bool = False
    max_unmatched_bill_days: int = 30
    kitchen_open_time: time = time(9, 0)
    kitchen_close_time: time = time(13, 30)
    notes: str | None = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionBillPayoutDTO(BaseModel):
    """Pure DTO for a single payout attempt on a bill. Append-only — retries insert new rows."""

    bill_payout_id: UUID
    institution_bill_id: UUID
    provider: str
    provider_transfer_id: str | None = None
    amount: Decimal
    currency_code: str
    status: BillPayoutStatus
    idempotency_key: str
    created_at: datetime
    completed_at: datetime | None = None
    modified_by: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class SupplierInvoiceDTO(BaseModel):
    """Pure DTO for core supplier invoice records. Country-specific fields in extension DTOs."""

    supplier_invoice_id: UUID
    institution_entity_id: UUID
    country_code: str
    invoice_type: SupplierInvoiceType
    external_invoice_number: str | None = None
    issued_date: date
    amount: Decimal
    currency_code: str
    tax_amount: Decimal | None = None
    tax_rate: Decimal | None = None
    # Document
    document_storage_path: str | None = None
    document_format: str | None = None
    # Review
    status: SupplierInvoiceStatus
    rejection_reason: str | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    # Audit
    is_archived: bool = False
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierInvoiceARDTO(BaseModel):
    """AR extension: AFIP Factura Electronica fields."""

    supplier_invoice_id: UUID
    cae_code: str
    cae_expiry_date: date
    afip_point_of_sale: str
    supplier_cuit: str
    recipient_cuit: str | None = None
    afip_document_type: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SupplierInvoicePEDTO(BaseModel):
    """PE extension: SUNAT CPE fields."""

    supplier_invoice_id: UUID
    sunat_serie: str
    sunat_correlativo: str
    cdr_status: str | None = None
    cdr_received_at: datetime | None = None
    supplier_ruc: str
    recipient_ruc: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SupplierInvoiceUSDTO(BaseModel):
    """US extension: IRS 1099-NEC fields."""

    supplier_invoice_id: UUID
    tax_year: int

    model_config = ConfigDict(from_attributes=True)


class BillInvoiceMatchDTO(BaseModel):
    """Pure DTO for bill-to-invoice match records. Append-only junction table."""

    match_id: UUID
    institution_bill_id: UUID
    supplier_invoice_id: UUID
    matched_amount: Decimal
    matched_by: UUID
    matched_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierW9DTO(BaseModel):
    """Pure DTO for US supplier W-9 tax records. One per entity (UNIQUE constraint)."""

    w9_id: UUID
    institution_entity_id: UUID
    legal_name: str
    business_name: str | None = None
    tax_classification: str
    ein_last_four: str
    address_line: str
    document_storage_path: str | None = None
    is_archived: bool = False
    collected_at: datetime
    created_by: UUID | None = None
    modified_date: datetime
    modified_by: UUID

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
    method_type_id: UUID | None = None
    address_id: UUID | None = None
    is_archived: bool
    status: Status = Field(..., max_length=20)
    is_default: bool
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPaymentProviderDTO(BaseModel):
    """Pure DTO for a user's connected external payment provider account."""

    user_payment_provider_id: UUID
    user_id: UUID
    provider: str
    provider_customer_id: str
    is_archived: bool = False
    status: str
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ExternalPaymentMethodDTO(BaseModel):
    """Pure DTO for external (aggregator) payment method link."""

    external_payment_method_id: UUID
    payment_method_id: UUID
    provider: str
    external_id: str
    last4: str | None = None
    brand: str | None = None
    provider_customer_id: str | None = None
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
    qr_code_checksum: str | None = None
    is_archived: bool
    status: Status = Field(..., max_length=20)
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class RestaurantBalanceDTO(BaseModel):
    """Pure DTO for restaurant balance data"""

    restaurant_id: UUID
    currency_metadata_id: UUID
    transaction_count: int = Field(..., ge=0)
    balance: Decimal = Field(..., ge=0)
    currency_code: str = Field(..., max_length=10)
    is_archived: bool = False
    status: Status = Field(..., max_length=20)
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class RestaurantHolidaysDTO(BaseModel):
    """Pure DTO for restaurant holidays data"""

    holiday_id: UUID
    restaurant_id: UUID
    country_code: str = Field(..., max_length=3)
    holiday_date: date
    holiday_name: str = Field(..., max_length=100)
    is_recurring: bool = False
    recurring_month: int | None = Field(None, ge=1, le=12)
    recurring_day: int | None = Field(None, ge=1, le=31)
    status: Status
    is_archived: bool
    source: str = Field(default="manual", max_length=20)
    created_date: datetime
    created_by: UUID | None = None
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
    recurring_month: int | None = Field(None, ge=1, le=12)
    recurring_day: int | None = Field(None, ge=1, le=31)
    status: Status = Field(default=Status.ACTIVE, description="Status of the holiday (defaults to 'active' if not set)")
    is_archived: bool = False
    source: str = Field(default="manual", max_length=20)
    created_date: datetime
    created_by: UUID | None = None
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
    created_by: UUID | None = None
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
    was_collected: bool | None = None
    arrival_time: datetime | None = None
    completion_time: datetime | None = None
    expected_completion_time: datetime | None = None
    confirmation_code: str | None = None
    completion_type: str | None = None
    extensions_used: int = 0
    code_verified: bool = False
    code_verified_time: datetime | None = None
    handed_out_time: datetime | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# DISCRETIONARY CREDIT DTOs
# =============================================================================


class DiscretionaryDTO(BaseModel):
    """Pure DTO for discretionary credit request data"""

    discretionary_id: UUID
    user_id: UUID | None = None  # NULL for Supplier requests, required for Client requests
    restaurant_id: UUID | None = None  # NULL for Client requests, required for Supplier requests
    approval_id: UUID | None = None
    category: DiscretionaryReason  # Classification enum (Marketing Campaign, Credit Refund, etc.)
    reason: str | None = None  # Free-form explanation
    amount: Decimal = Field(..., gt=0)
    comment: str | None = None
    is_archived: bool = False
    status: str = Field(..., max_length=20)  # DiscretionaryStatus: Pending, Cancelled, Approved, Rejected
    created_date: datetime
    created_by: UUID | None = None
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
    resolution_comment: str | None = None

    model_config = ConfigDict(from_attributes=True)


class IngredientCatalogDTO(BaseModel):
    """Pure DTO for ingredient catalog entries (global, not institution-scoped)."""

    ingredient_id: UUID
    name: str
    name_display: str
    name_es: str | None = None
    name_en: str | None = None
    name_pt: str | None = None
    off_taxonomy_id: str | None = None
    off_wikidata_id: str | None = None
    image_url: str | None = None
    image_source: str | None = None
    usda_fdc_id: int | None = None
    food_group: str | None = None
    image_enriched: bool = False
    image_skipped: bool = False
    usda_enriched: bool = False
    usda_skipped: bool = False
    source: str
    is_verified: bool
    created_date: datetime
    modified_date: datetime
    modified_by: UUID

    model_config = ConfigDict(from_attributes=True)


class IngredientNutritionDTO(BaseModel):
    """Pure DTO for per-ingredient nutritional data (Phase 7 — USDA enrichment)."""

    nutrition_id: UUID
    ingredient_id: UUID
    source: str
    per_amount_g: int
    energy_kcal: Decimal | None = None
    protein_g: Decimal | None = None
    fat_g: Decimal | None = None
    carbohydrates_g: Decimal | None = None
    fiber_g: Decimal | None = None
    sugar_g: Decimal | None = None
    sodium_mg: Decimal | None = None
    fetched_date: date
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductIngredientDTO(BaseModel):
    """Pure DTO for product ↔ ingredient junction rows."""

    product_ingredient_id: UUID
    product_id: UUID
    ingredient_id: UUID
    sort_order: int
    created_date: datetime
    modified_by: UUID

    model_config = ConfigDict(from_attributes=True)


class IngredientAliasDTO(BaseModel):
    """Pure DTO for regional ingredient name aliases."""

    alias_id: UUID
    ingredient_id: UUID
    alias: str
    region_code: str | None = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Referral DTOs
# =============================================================================


class ReferralConfigDTO(BaseModel):
    """Pure DTO for referral configuration per market"""

    referral_config_id: UUID
    market_id: UUID
    is_enabled: bool = True
    referrer_bonus_rate: int = 15
    referrer_bonus_cap: Decimal | None = None
    referrer_monthly_cap: int | None = 5
    min_plan_price_to_qualify: Decimal = Decimal("0")
    cooldown_days: int = 0
    held_reward_expiry_hours: int = 48
    pending_expiry_days: int = 90
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ReferralInfoDTO(BaseModel):
    """Pure DTO for individual referral tracking"""

    referral_id: UUID
    referrer_user_id: UUID
    referee_user_id: UUID
    referral_code_used: str
    market_id: UUID
    referral_status: str
    bonus_credits_awarded: Decimal | None = None
    bonus_plan_price: Decimal | None = None
    bonus_rate_applied: int | None = None
    qualified_date: datetime | None = None
    rewarded_date: datetime | None = None
    reward_held_until: datetime | None = None
    expired_date: datetime | None = None
    cancelled_date: datetime | None = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ReferralTransactionDTO(BaseModel):
    """Pure DTO for the referral-transaction bridge row"""

    referral_transaction_id: UUID
    referral_id: UUID
    transaction_id: UUID
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class AdClickTrackingDTO(BaseModel):
    """DTO for ad click tracking records (conversion attribution)."""

    id: UUID
    user_id: UUID
    subscription_id: UUID | None = None
    gclid: str | None = None
    wbraid: str | None = None
    gbraid: str | None = None
    fbclid: str | None = None
    fbc: str | None = None
    fbp: str | None = None
    event_id: str | None = None
    landing_url: str | None = None
    source_platform: str | None = None
    captured_at: datetime
    google_upload_status: str = "pending"
    google_uploaded_at: datetime | None = None
    meta_upload_status: str = "pending"
    meta_uploaded_at: datetime | None = None
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkplaceGroupDTO(BaseModel):
    """DTO for workplace_group (B2C coworker pickup coordination)."""

    workplace_group_id: UUID
    name: str
    email_domain: str | None = None
    require_domain_verification: bool = False
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: UUID | None = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class AdZoneDTO(BaseModel):
    """DTO for geographic ad zones (flywheel engine)."""

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
    state_changed_by: UUID | None = None
    notify_me_lead_count: int = 0
    active_restaurant_count: int = 0
    active_subscriber_count: int = 0
    estimated_mau: int | None = None
    mau_estimated_at: datetime | None = None
    budget_allocation: dict | None = None
    daily_budget_cents: int | None = None
    meta_ad_set_ids: dict | None = None
    google_campaign_ids: dict | None = None
    created_by: str = "operator"
    approved_by: UUID | None = None
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)
