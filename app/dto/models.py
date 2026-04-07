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
from app.config import Status, RoleType, RoleName, DiscretionaryReason, BillPayoutStatus, DietaryFlag
from app.config.enums import SupplierInvoiceStatus, SupplierInvoiceType, PaymentFrequency

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
    mobile_number: Optional[str] = None
    mobile_number_verified: bool = False
    mobile_number_verified_at: Optional[datetime] = None
    email_verified: bool = False
    email_verified_at: Optional[datetime] = None
    employer_id: Optional[UUID] = None
    employer_address_id: Optional[UUID] = None
    support_email_suppressed_until: Optional[datetime] = None
    last_support_email_date: Optional[datetime] = None
    market_id: UUID
    city_id: Optional[UUID] = None
    locale: str = "en"
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
    institution_type: RoleType  # Internal, Customer, Supplier, or Employer
    market_id: Optional[UUID] = None  # v1: NULL or Global = all markets; one UUID = local market
    support_email_suppressed_until: Optional[datetime] = None
    last_support_email_date: Optional[datetime] = None
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
    name_i18n: Optional[dict] = None
    ingredients: Optional[str] = None
    ingredients_i18n: Optional[dict] = None
    description: Optional[str] = None
    description_i18n: Optional[dict] = None
    dietary: Optional[List[str]] = None
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
    would_order_again: Optional[bool] = None
    comment: Optional[str] = None
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
    client_types: List[str]
    action_status: str
    expires_at: datetime
    acknowledged_at: Optional[datetime] = None
    dedup_key: str
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class PortionComplaintDTO(BaseModel):
    """Pure DTO for portion complaint data. Filed when customer rates portion size as 1 and chooses to complain."""
    complaint_id: UUID
    plate_pickup_id: UUID
    plate_review_id: Optional[UUID] = None
    user_id: UUID
    restaurant_id: UUID
    photo_storage_path: Optional[str] = None
    complaint_text: Optional[str] = None
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
    cuisine_name_i18n: Optional[dict] = None
    slug: str
    parent_cuisine_id: Optional[UUID] = None
    description: Optional[str] = None
    origin_source: str = "seed"
    display_order: Optional[int] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class CuisineSuggestionDTO(BaseModel):
    """Pure DTO for cuisine suggestion workflow data."""
    suggestion_id: UUID
    suggested_name: str
    suggested_by: UUID
    restaurant_id: Optional[UUID] = None
    suggestion_status: str = "Pending"
    reviewed_by: Optional[UUID] = None
    reviewed_date: Optional[datetime] = None
    review_notes: Optional[str] = None
    resolved_cuisine_id: Optional[UUID] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
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
    cuisine_id: Optional[UUID] = None
    pickup_instructions: Optional[str] = None
    tagline: Optional[str] = None
    tagline_i18n: Optional[dict] = None
    is_featured: bool = False
    cover_image_url: Optional[str] = None
    average_rating: Optional[Decimal] = None
    review_count: int = 0
    verified_badge: bool = False
    spotlight_label: Optional[str] = None
    spotlight_label_i18n: Optional[dict] = None
    member_perks: Optional[List[str]] = None
    member_perks_i18n: Optional[dict] = None
    require_kiosk_code_verification: bool = False
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
    user_id: Optional[UUID] = None  # Required only for Customer Comensal home/other; nullable for Supplier, Internal, Employer
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
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: str
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class AddressSubpremiseDTO(BaseModel):
    """Pure DTO for address_subpremise (floor, unit, is_default, map_center_label per user at an address)."""
    subpremise_id: UUID
    address_id: UUID
    user_id: UUID
    floor: Optional[str] = None
    apartment_unit: Optional[str] = None
    is_default: bool = False
    map_center_label: Optional[str] = None
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


class EmployerBenefitsProgramDTO(BaseModel):
    """Pure DTO for employer benefits program configuration"""
    program_id: UUID
    institution_id: UUID
    benefit_rate: int
    benefit_cap: Optional[Decimal] = None
    benefit_cap_period: str
    price_discount: int = 0
    minimum_monthly_fee: Optional[Decimal] = None
    billing_cycle: str
    billing_day: Optional[int] = 1
    billing_day_of_week: Optional[int] = None
    enrollment_mode: str
    allow_early_renewal: bool = False
    stripe_customer_id: Optional[str] = None
    stripe_payment_method_id: Optional[str] = None
    payment_method_type: Optional[str] = None
    is_active: bool = True
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployerBillDTO(BaseModel):
    """Pure DTO for employer bill data"""
    employer_bill_id: UUID
    institution_id: UUID
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
    stripe_invoice_id: Optional[str] = None
    payment_status: str = "Pending"
    paid_date: Optional[datetime] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
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
    benefit_cap: Optional[Decimal] = None
    benefit_cap_period: Optional[str] = None
    employee_benefit: Decimal
    renewal_date: datetime
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployerDomainDTO(BaseModel):
    """Pure DTO for employer domain data"""
    domain_id: UUID
    institution_id: UUID
    domain: str
    is_active: bool = True
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadInterestDTO(BaseModel):
    """Pure DTO for lead interest data (notify-me requests from marketing site / B2C app)."""
    lead_interest_id: UUID
    email: str
    country_code: str
    city_name: Optional[str] = None
    zipcode: Optional[str] = None
    zipcode_only: bool = False
    interest_type: str
    business_name: Optional[str] = None
    message: Optional[str] = None
    cuisine_id: Optional[UUID] = None
    employee_count_range: Optional[str] = None
    status: str
    source: str
    notified_date: Optional[datetime] = None
    is_archived: bool = False
    created_date: datetime
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
    subscription_status: Optional[str] = None  # Specific subscription status (Active/On Hold/Pending/Cancelled)
    hold_start_date: Optional[datetime] = None  # When subscription was put on hold
    hold_end_date: Optional[datetime] = None  # When subscription is expected to resume
    early_renewal_threshold: Optional[int] = 10  # None = no early renewal; period-end only
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
    name_i18n: Optional[dict] = None
    marketing_description: Optional[str] = None
    marketing_description_i18n: Optional[dict] = None
    features: Optional[List[str]] = None
    features_i18n: Optional[dict] = None
    cta_label: Optional[str] = None
    cta_label_i18n: Optional[dict] = None
    credit: int
    price: Decimal
    highlighted: bool = False
    credit_cost_local_currency: Decimal  # price / credit (local currency per credit), set by DB trigger
    credit_cost_usd: Decimal  # credit_cost_local_currency / currency_conversion_usd, set by DB trigger
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
    payout_provider_account_id: Optional[str] = None
    payout_aggregator: Optional[str] = None
    payout_onboarding_status: Optional[str] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierTermsDTO(BaseModel):
    """Pure DTO for supplier terms — negotiated per-supplier institution."""
    supplier_terms_id: UUID
    institution_id: UUID
    no_show_discount: int = 0
    payment_frequency: PaymentFrequency = PaymentFrequency.DAILY
    require_invoice: Optional[bool] = None
    invoice_hold_days: Optional[int] = None
    is_archived: bool = False
    status: Status
    created_date: datetime
    created_by: Optional[UUID] = None
    modified_by: UUID
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class InstitutionBillPayoutDTO(BaseModel):
    """Pure DTO for a single payout attempt on a bill. Append-only — retries insert new rows."""
    bill_payout_id: UUID
    institution_bill_id: UUID
    provider: str
    provider_transfer_id: Optional[str] = None
    amount: Decimal
    currency_code: str
    status: BillPayoutStatus
    idempotency_key: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    modified_by: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class SupplierInvoiceDTO(BaseModel):
    """Pure DTO for core supplier invoice records. Country-specific fields in extension DTOs."""
    supplier_invoice_id: UUID
    institution_entity_id: UUID
    country_code: str
    invoice_type: SupplierInvoiceType
    external_invoice_number: Optional[str] = None
    issued_date: date
    amount: Decimal
    currency_code: str
    tax_amount: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    # Document
    document_storage_path: Optional[str] = None
    document_format: Optional[str] = None
    # Review
    status: SupplierInvoiceStatus
    rejection_reason: Optional[str] = None
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    # Audit
    is_archived: bool = False
    created_date: datetime
    created_by: Optional[UUID] = None
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
    recipient_cuit: Optional[str] = None
    afip_document_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SupplierInvoicePEDTO(BaseModel):
    """PE extension: SUNAT CPE fields."""
    supplier_invoice_id: UUID
    sunat_serie: str
    sunat_correlativo: str
    cdr_status: Optional[str] = None
    cdr_received_at: Optional[datetime] = None
    supplier_ruc: str
    recipient_ruc: Optional[str] = None

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
    business_name: Optional[str] = None
    tax_classification: str
    ein_last_four: str
    address_line: str
    document_storage_path: Optional[str] = None
    is_archived: bool = False
    collected_at: datetime
    created_by: Optional[UUID] = None
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


class UserPaymentProviderDTO(BaseModel):
    """Pure DTO for a user's connected external payment provider account."""
    user_payment_provider_id: UUID
    user_id: UUID
    provider: str
    provider_customer_id: str
    is_archived: bool = False
    status: str
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
    country_code: str = Field(..., max_length=3)
    holiday_date: date
    holiday_name: str = Field(..., max_length=100)
    is_recurring: bool = False
    recurring_month: Optional[int] = Field(None, ge=1, le=12)
    recurring_day: Optional[int] = Field(None, ge=1, le=31)
    status: Status
    is_archived: bool
    source: str = Field(default="manual", max_length=20)
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
    source: str = Field(default="manual", max_length=20)
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
    completion_type: Optional[str] = None
    extensions_used: int = 0
    code_verified: bool = False
    code_verified_time: Optional[datetime] = None
    handed_out_time: Optional[datetime] = None
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


class IngredientCatalogDTO(BaseModel):
    """Pure DTO for ingredient catalog entries (global, not institution-scoped)."""
    ingredient_id: UUID
    name: str
    name_display: str
    name_es: Optional[str] = None
    name_en: Optional[str] = None
    name_pt: Optional[str] = None
    off_taxonomy_id: Optional[str] = None
    off_wikidata_id: Optional[str] = None
    image_url: Optional[str] = None
    image_source: Optional[str] = None
    usda_fdc_id: Optional[int] = None
    food_group: Optional[str] = None
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
    energy_kcal: Optional[Decimal] = None
    protein_g: Optional[Decimal] = None
    fat_g: Optional[Decimal] = None
    carbohydrates_g: Optional[Decimal] = None
    fiber_g: Optional[Decimal] = None
    sugar_g: Optional[Decimal] = None
    sodium_mg: Optional[Decimal] = None
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
    region_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

