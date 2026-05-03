"""
Stable machine-readable error-code registry for the Vianda API.

Design rules (see docs/api/i18n.md):
- Codes are append-only. Renames keep the old code as an alias; never delete.
- Values use dotted-namespace form: "<namespace>.<slug>".
- Every member must have en/es/pt entries in messages.py (enforced by
  app/tests/i18n/test_error_codes_parity.py).
- Every member must be referenced at least once outside this file (enforced
  by app/tests/i18n/test_error_codes_referenced.py, with an allowlist for
  seeds that are wired in later PRs).
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    # ── request.* ──────────────────────────────────────────────────────────
    # Pre-route errors set by the catch-all exception handler (K3).
    # These are never raised directly by route handlers.
    REQUEST_NOT_FOUND = "request.not_found"
    REQUEST_METHOD_NOT_ALLOWED = "request.method_not_allowed"
    REQUEST_MALFORMED_BODY = "request.malformed_body"
    REQUEST_TOO_LARGE = "request.too_large"
    REQUEST_RATE_LIMITED = "request.rate_limited"

    # ── validation.* ───────────────────────────────────────────────────────
    # Emitted by the RequestValidationError handler (K3/K5/K67).
    VALIDATION_FIELD_REQUIRED = "validation.field_required"
    VALIDATION_INVALID_FORMAT = "validation.invalid_format"
    VALIDATION_VALUE_TOO_SHORT = "validation.value_too_short"
    VALIDATION_VALUE_TOO_LONG = "validation.value_too_long"
    VALIDATION_INVALID_VALUE = "validation.invalid_value"
    VALIDATION_INVALID_TYPE = "validation.invalid_type"
    VALIDATION_CUSTOM = "validation.custom"

    # ── validation.user.* ──────────────────────────────────────────────────
    # Custom field-validator errors from app/schemas/consolidated_schemas.py
    VALIDATION_USER_INVALID_ROLE_COMBINATION = "validation.user.invalid_role_combination"
    VALIDATION_USER_UNSUPPORTED_LOCALE = "validation.user.unsupported_locale"
    VALIDATION_USER_PASSWORDS_DO_NOT_MATCH = "validation.user.passwords_do_not_match"
    VALIDATION_USER_NEW_PASSWORD_SAME_AS_CURRENT = "validation.user.new_password_same_as_current"

    # ── validation.address.* ───────────────────────────────────────────────
    # Custom field-validator errors from AddressCreateSchema
    VALIDATION_ADDRESS_CITY_REQUIRED = "validation.address.city_required"
    VALIDATION_ADDRESS_INVALID_ADDRESS_TYPE = "validation.address.invalid_address_type"
    VALIDATION_ADDRESS_DUPLICATE_ADDRESS_TYPE = "validation.address.duplicate_address_type"
    VALIDATION_ADDRESS_INVALID_STREET_TYPE = "validation.address.invalid_street_type"
    VALIDATION_ADDRESS_COUNTRY_REQUIRED = "validation.address.country_required"
    VALIDATION_ADDRESS_FIELD_REQUIRED = "validation.address.field_required"
    VALIDATION_ADDRESS_CITY_METADATA_ID_REQUIRED = "validation.address.city_metadata_id_required"

    # ── validation.plate.* ─────────────────────────────────────────────────
    # Custom field-validator errors from PlateKitchenDayCreateSchema
    VALIDATION_PLATE_KITCHEN_DAYS_EMPTY = "validation.plate.kitchen_days_empty"
    VALIDATION_PLATE_KITCHEN_DAYS_DUPLICATE = "validation.plate.kitchen_days_duplicate"

    # ── validation.discretionary.* ─────────────────────────────────────────
    # Custom model-validator errors from DiscretionaryCreateSchema
    VALIDATION_DISCRETIONARY_RECIPIENT_REQUIRED = "validation.discretionary.recipient_required"
    VALIDATION_DISCRETIONARY_CONFLICTING_RECIPIENTS = "validation.discretionary.conflicting_recipients"
    VALIDATION_DISCRETIONARY_RESTAURANT_REQUIRED = "validation.discretionary.restaurant_required"

    # ── validation.holiday.* ───────────────────────────────────────────────
    # Custom model-validator errors from holiday schemas
    VALIDATION_HOLIDAY_RECURRING_FIELDS_REQUIRED = "validation.holiday.recurring_fields_required"
    VALIDATION_HOLIDAY_LIST_EMPTY = "validation.holiday.list_empty"

    # ── validation.subscription.* ──────────────────────────────────────────
    # Custom model-validator errors from SubscriptionHoldRequestSchema
    VALIDATION_SUBSCRIPTION_WINDOW_INVALID = "validation.subscription.window_invalid"
    VALIDATION_SUBSCRIPTION_WINDOW_TOO_LONG = "validation.subscription.window_too_long"

    # ── validation.payment.* ───────────────────────────────────────────────
    # Custom model-validator errors from PaymentMethodCreateSchema
    VALIDATION_PAYMENT_CONFLICTING_ADDRESS_FIELDS = "validation.payment.conflicting_address_fields"
    VALIDATION_PAYMENT_UNSUPPORTED_BRAND = "validation.payment.unsupported_brand"
    VALIDATION_PAYMENT_ADDRESS_REQUIRED = "validation.payment.address_required"

    # ── validation.supplier_invoice.* ─────────────────────────────────────
    # Custom field/model-validator errors from supplier_invoice.py and supplier_w9.py (K67).
    VALIDATION_SUPPLIER_INVOICE_CAE_FORMAT = "validation.supplier_invoice.cae_format"
    VALIDATION_SUPPLIER_INVOICE_CUIT_FORMAT = "validation.supplier_invoice.cuit_format"
    VALIDATION_SUPPLIER_INVOICE_AFIP_DOC_TYPE = "validation.supplier_invoice.afip_doc_type"
    VALIDATION_SUPPLIER_INVOICE_SUNAT_SERIE_FORMAT = "validation.supplier_invoice.sunat_serie_format"
    VALIDATION_SUPPLIER_INVOICE_SUNAT_CORRELATIVO_FORMAT = "validation.supplier_invoice.sunat_correlativo_format"
    VALIDATION_SUPPLIER_INVOICE_RUC_FORMAT = "validation.supplier_invoice.ruc_format"
    VALIDATION_SUPPLIER_INVOICE_CDR_STATUS = "validation.supplier_invoice.cdr_status"
    VALIDATION_SUPPLIER_INVOICE_AR_DETAILS_REQUIRED = "validation.supplier_invoice.ar_details_required"
    VALIDATION_SUPPLIER_INVOICE_PE_DETAILS_REQUIRED = "validation.supplier_invoice.pe_details_required"
    VALIDATION_SUPPLIER_INVOICE_US_DETAILS_REQUIRED = "validation.supplier_invoice.us_details_required"
    VALIDATION_SUPPLIER_INVOICE_REJECTION_REASON_REQUIRED = "validation.supplier_invoice.rejection_reason_required"
    VALIDATION_SUPPLIER_INVOICE_STATUS_CANNOT_RESET = "validation.supplier_invoice.status_cannot_reset"
    VALIDATION_SUPPLIER_W9_EIN_FORMAT = "validation.supplier_invoice.w9_ein_format"

    # ── validation.market.* ───────────────────────────────────────────────
    # Custom field-validator errors from MarketCreateSchema / MarketUpdateSchema (K67).
    VALIDATION_MARKET_LANGUAGE_UNSUPPORTED = "validation.market.language_unsupported"

    # ── auth.* ─────────────────────────────────────────────────────────────
    # Seeded in K2; fully wired in K7 (auth + security sweep).
    AUTH_INVALID_TOKEN = "auth.invalid_token"
    AUTH_CAPTCHA_REQUIRED = "auth.captcha_required"  # migrated from ad-hoc dict-detail
    AUTH_CAPTCHA_VERIFICATION_FAILED = "auth.captcha_verification_failed"
    AUTH_CAPTCHA_ACTION_MISMATCH = "auth.captcha_action_mismatch"
    AUTH_CAPTCHA_SCORE_TOO_LOW = "auth.captcha_score_too_low"
    AUTH_CAPTCHA_TOKEN_MISSING = "auth.captcha_token_missing"
    AUTH_CREDENTIALS_INVALID = "auth.credentials_invalid"
    AUTH_ACCOUNT_INACTIVE = "auth.account_inactive"
    AUTH_CUSTOMER_APP_ONLY = "auth.customer_app_only"  # migrated from ad-hoc dict-detail
    AUTH_DUMMY_ADMIN_NOT_CONFIGURED = "auth.dummy_admin_not_configured"
    AUTH_TOKEN_USER_ID_INVALID = "auth.token_user_id_invalid"
    AUTH_TOKEN_INSTITUTION_ID_INVALID = "auth.token_institution_id_invalid"
    AUTH_TOKEN_MISSING_FIELDS = "auth.token_missing_fields"

    # ── security.* ─────────────────────────────────────────────────────────
    # Wired in K7 (auth + security sweep).
    SECURITY_INSTITUTION_MISMATCH = "security.institution_mismatch"
    SECURITY_INSUFFICIENT_PERMISSIONS = "security.insufficient_permissions"
    SECURITY_FORBIDDEN = "security.forbidden"
    SECURITY_TOKEN_USER_ID_MISSING = "security.token_user_id_missing"
    SECURITY_TOKEN_USER_ID_INVALID = "security.token_user_id_invalid"
    SECURITY_ADDRESS_TYPE_NOT_ALLOWED = "security.address_type_not_allowed"
    SECURITY_ADDRESS_TYPE_INSTITUTION_MISMATCH = "security.address_type_institution_mismatch"
    SECURITY_USER_ROLE_TYPE_NOT_ALLOWED = "security.user_role_type_not_allowed"
    SECURITY_USER_ROLE_NAME_NOT_ALLOWED = "security.user_role_name_not_allowed"
    SECURITY_OPERATOR_CANNOT_CREATE_USERS = "security.operator_cannot_create_users"
    SECURITY_CANNOT_ASSIGN_ROLE = "security.cannot_assign_role"
    SECURITY_CANNOT_EDIT_USER = "security.cannot_edit_user"
    SECURITY_CUSTOMER_CANNOT_EDIT_EMPLOYER_ADDRESS = "security.customer_cannot_edit_employer_address"
    SECURITY_SUPPLIER_ADDRESS_MUTATION_DENIED = "security.supplier_address_mutation_denied"
    SECURITY_SUPPLIER_USER_MUTATION_DENIED = "security.supplier_user_mutation_denied"
    SECURITY_SUPPLIER_MANAGEMENT_DENIED = "security.supplier_management_denied"
    SECURITY_SUPPLIER_ADMIN_ONLY = "security.supplier_admin_only"
    SECURITY_SUPPLIER_PASSWORD_RESET_DENIED = "security.supplier_password_reset_denied"
    SECURITY_INSTITUTION_TYPE_MISMATCH = "security.institution_type_mismatch"
    SECURITY_SUPPLIER_INSTITUTION_ONLY = "security.supplier_institution_only"
    SECURITY_SUPPLIER_INSTITUTION_REQUIRED = "security.supplier_institution_required"
    SECURITY_EMPLOYER_NOT_FOR_SUPPLIER = "security.employer_not_for_supplier"
    SECURITY_SUPPLIER_TERMS_EDIT_DENIED = "security.supplier_terms_edit_denied"

    # ── subscription.* ─────────────────────────────────────────────────────
    # Seeded to prove parity tooling; fully wired in a later sweep PR.
    SUBSCRIPTION_ALREADY_ACTIVE = "subscription.already_active"  # migrated from ad-hoc dict-detail

    # ── entity.* ───────────────────────────────────────────────────────────
    # Generic entity CRUD errors. All entity-specific factories (user_not_found,
    # employer_not_found, etc.) delegate to entity_not_found which uses these
    # codes. The `entity` param carries the entity name; `id` carries the UUID.
    # Wired in K6 (factory envelopification).
    ENTITY_NOT_FOUND = "entity.not_found"
    ENTITY_NOT_FOUND_OR_OPERATION_FAILED = "entity.not_found_or_operation_failed"
    ENTITY_CREATION_FAILED = "entity.creation_failed"
    ENTITY_UPDATE_FAILED = "entity.update_failed"
    ENTITY_DELETION_FAILED = "entity.deletion_failed"
    # Wired in K8 (route_factory sweep).
    ENTITY_FIELD_IMMUTABLE = "entity.field_immutable"

    # ── product.* ──────────────────────────────────────────────────────────
    # Product-specific errors. Wired in K8 (route_factory sweep).
    PRODUCT_IMAGE_TOO_LARGE = "product.image_too_large"

    # ── credit_currency.* ──────────────────────────────────────────────────
    # Credit-currency management errors. Wired in K8 (route_factory sweep).
    CREDIT_CURRENCY_NAME_NOT_SUPPORTED = "credit_currency.name_not_supported"
    CREDIT_CURRENCY_RATE_UNAVAILABLE = "credit_currency.rate_unavailable"

    # ── employer.* ─────────────────────────────────────────────────────────
    # Employer benefit program errors. Wired in K8 (route_factory sweep).
    EMPLOYER_BENEFIT_PROGRAM_NOT_FOUND = "employer.benefit_program_not_found"

    # ── user.* (non-auth) ──────────────────────────────────────────────────
    # User profile / account state errors. Wired in K8 (route_factory sweep).
    USER_MARKET_NOT_ASSIGNED = "user.market_not_assigned"

    # ── institution.* ──────────────────────────────────────────────────────
    # Institution management errors. Wired in K8 (route_factory sweep).
    INSTITUTION_SYSTEM_PROTECTED = "institution.system_protected"
    INSTITUTION_SUPPLIER_TERMS_INVALID = "institution.supplier_terms_invalid"

    # ── institution_entity.* ───────────────────────────────────────────────
    # Institution entity management errors. Wired in K8 (route_factory sweep).
    INSTITUTION_ENTITY_MARKET_MISMATCH = "institution_entity.market_mismatch"

    # ── user.signup.* ─────────────────────────────────────────────────────
    # User signup and account validation errors. Wired in K9 (user identity sweep).
    USER_CITY_NOT_FOUND = "user.city_not_found"
    USER_CITY_ARCHIVED = "user.city_archived"
    USER_CITY_MUST_BE_SPECIFIC = "user.city_must_be_specific"
    USER_CITY_REQUIRED = "user.city_required"
    USER_CITY_COUNTRY_MISMATCH = "user.city_country_mismatch"
    USER_MARKET_NOT_FOUND = "user.market_not_found"
    USER_MARKET_ARCHIVED = "user.market_archived"
    USER_MARKET_GLOBAL_NOT_ALLOWED = "user.market_global_not_allowed"
    USER_MARKET_ID_INVALID = "user.market_id_invalid"
    USER_SIGNUP_CODE_INVALID = "user.signup_code_invalid"
    USER_SIGNUP_COUNTRY_REQUIRED = "user.signup_country_required"
    USER_SIGNUP_INSTITUTION_REQUIRED = "user.signup_institution_required"
    USER_LOOKUP_PARAM_REQUIRED = "user.lookup_param_required"
    USER_ADDRESS_NOT_FOUND = "user.address_not_found"
    USER_ADDRESS_ARCHIVED = "user.address_archived"
    USER_ADDRESS_INSTITUTION_MISMATCH = "user.address_institution_mismatch"
    USER_WORKPLACE_GROUP_NOT_FOUND = "user.workplace_group_not_found"
    USER_WORKPLACE_GROUP_ARCHIVED = "user.workplace_group_archived"
    USER_INVITE_NO_EMAIL = "user.invite_no_email"
    USER_ONBOARDING_CUSTOMER_ONLY = "user.onboarding_customer_only"

    # ── subscription.* (extended) ──────────────────────────────────────────
    # Subscription lifecycle errors. Wired in K10 (subscription + payment sweep).
    SUBSCRIPTION_NOT_FOUND = "subscription.not_found"
    SUBSCRIPTION_NOT_PENDING = "subscription.not_pending"
    SUBSCRIPTION_NOT_ON_HOLD = "subscription.not_on_hold"
    SUBSCRIPTION_ALREADY_ON_HOLD = "subscription.already_on_hold"
    SUBSCRIPTION_ALREADY_CANCELLED = "subscription.already_cancelled"
    SUBSCRIPTION_CANNOT_HOLD_CANCELLED = "subscription.cannot_hold_cancelled"
    SUBSCRIPTION_CONFIRM_MOCK_ONLY = "subscription.confirm_mock_only"
    SUBSCRIPTION_PAYMENT_NOT_FOUND = "subscription.payment_not_found"
    SUBSCRIPTION_PAYMENT_RECORD_NOT_FOUND = "subscription.payment_record_not_found"
    SUBSCRIPTION_PAYMENT_PROVIDER_UNAVAILABLE = "subscription.payment_provider_unavailable"
    SUBSCRIPTION_ACCESS_DENIED = "subscription.access_denied"

    # ── plate_selection.* ─────────────────────────────────────────────────
    # Plate selection lifecycle errors. Wired in K10.
    PLATE_SELECTION_NOT_FOUND = "plate_selection.not_found"
    PLATE_SELECTION_IMMUTABLE_FIELDS = "plate_selection.immutable_fields"
    PLATE_SELECTION_ACCESS_DENIED = "plate_selection.access_denied"
    PLATE_SELECTION_NOT_EDITABLE = "plate_selection.not_editable"
    PLATE_SELECTION_NOT_CANCELLABLE = "plate_selection.not_cancellable"
    PLATE_SELECTION_DUPLICATE_KITCHEN_DAY = "plate_selection.duplicate_kitchen_day"

    # ── plate_pickup.* ────────────────────────────────────────────────────
    # Plate pickup errors. Wired in K10.
    PLATE_PICKUP_ACCESS_DENIED = "plate_pickup.access_denied"
    PLATE_PICKUP_INVALID_QR_CODE = "plate_pickup.invalid_qr_code"
    PLATE_PICKUP_WRONG_RESTAURANT = "plate_pickup.wrong_restaurant"
    PLATE_PICKUP_NO_ACTIVE_RESERVATION = "plate_pickup.no_active_reservation"
    PLATE_PICKUP_INVALID_STATUS = "plate_pickup.invalid_status"
    PLATE_PICKUP_INVALID_SIGNATURE = "plate_pickup.invalid_signature"
    PLATE_PICKUP_CANNOT_DELETE = "plate_pickup.cannot_delete"

    # ── plate_review.* ────────────────────────────────────────────────────
    # Plate review errors. Wired in K10.
    PLATE_REVIEW_NOT_FOUND = "plate_review.not_found"
    PLATE_REVIEW_ACCESS_DENIED = "plate_review.access_denied"
    PLATE_REVIEW_NOT_ELIGIBLE = "plate_review.not_eligible"
    PLATE_REVIEW_PICKUP_ARCHIVED = "plate_review.pickup_archived"
    PLATE_REVIEW_ALREADY_EXISTS = "plate_review.already_exists"
    PLATE_REVIEW_INVALID_PORTION_RATING = "plate_review.invalid_portion_rating"
    PLATE_REVIEW_COMPLAINT_EXISTS = "plate_review.complaint_exists"

    # ── payment_provider.* ────────────────────────────────────────────────
    # Payment provider (Stripe Connect) errors. Wired in K10.
    PAYMENT_PROVIDER_ONBOARDING_REQUIRED = "payment_provider.onboarding_required"
    PAYMENT_PROVIDER_NOT_READY = "payment_provider.not_ready"
    PAYMENT_PROVIDER_PAYOUT_EXISTS = "payment_provider.payout_exists"
    PAYMENT_PROVIDER_UNAVAILABLE = "payment_provider.unavailable"
    PAYMENT_PROVIDER_RATE_LIMITED = "payment_provider.rate_limited"
    PAYMENT_PROVIDER_AUTH_FAILED = "payment_provider.auth_failed"
    PAYMENT_PROVIDER_ERROR = "payment_provider.error"
    PAYMENT_PROVIDER_BILL_NOT_PENDING = "payment_provider.bill_not_pending"

    # ── mercado_pago.* ────────────────────────────────────────────────────
    # Mercado Pago OAuth errors. Wired in K10.
    MERCADO_PAGO_AUTH_CODE_MISSING = "mercado_pago.auth_code_missing"
    MERCADO_PAGO_AUTH_FAILED = "mercado_pago.auth_failed"

    # ── server.* ───────────────────────────────────────────────────────────
    # Generic server-side errors used when suppressing internal-ops jargon
    # per Decision F (K9 sweep). The original detail is logged server-side.
    SERVER_INTERNAL_ERROR = "server.internal_error"

    # ── restaurant_balance.* ─────────────────────────────────────────────────
    # Restaurant balance read-only errors. Wired in #87-d (404 hijack sweep).
    RESTAURANT_BALANCE_NOT_FOUND = "restaurant_balance.not_found"

    # ── restaurant_transaction.* ─────────────────────────────────────────────
    # Restaurant transaction read-only errors. Wired in #87-d (404 hijack sweep).
    RESTAURANT_TRANSACTION_NOT_FOUND = "restaurant_transaction.not_found"

    # ── restaurant.* ─────────────────────────────────────────────────────
    # Restaurant management errors. Wired in K11 (restaurant + ops sweep).
    RESTAURANT_NOT_FOUND = "restaurant.not_found"
    RESTAURANT_ENTITY_ID_REQUIRED = "restaurant.entity_id_required"
    RESTAURANT_MARKET_REQUIRED = "restaurant.market_required"
    RESTAURANT_MARKET_ACCESS_DENIED = "restaurant.market_access_denied"
    RESTAURANT_ACTIVE_REQUIRES_SETUP = "restaurant.active_requires_setup"
    RESTAURANT_ACTIVE_REQUIRES_PLATE_DAYS = "restaurant.active_requires_plate_days"
    RESTAURANT_ACTIVE_REQUIRES_QR = "restaurant.active_requires_qr"
    RESTAURANT_ACTIVE_REQUIRES_ENTITY_PAYOUTS = "restaurant.active_requires_entity_payouts"

    # ── restaurant_holiday.* ──────────────────────────────────────────────
    # Restaurant holiday management errors. Wired in K11.
    RESTAURANT_HOLIDAY_NOT_FOUND = "restaurant_holiday.not_found"
    RESTAURANT_HOLIDAY_DUPLICATE = "restaurant_holiday.duplicate"
    RESTAURANT_HOLIDAY_ON_NATIONAL_HOLIDAY = "restaurant_holiday.on_national_holiday"

    # ── national_holiday.* ────────────────────────────────────────────────
    # National holiday management errors. Wired in K11.
    NATIONAL_HOLIDAY_NOT_FOUND = "national_holiday.not_found"
    NATIONAL_HOLIDAY_UPDATE_EMPTY = "national_holiday.update_empty"

    # ── market.* ─────────────────────────────────────────────────────────
    # Market management errors. Wired in K12 (admin + billing sweep).
    MARKET_NOT_FOUND = "market.not_found"
    MARKET_COUNTRY_NOT_SUPPORTED = "market.country_not_supported"
    MARKET_SUPER_ADMIN_ONLY = "market.super_admin_only"
    MARKET_NO_COVERAGE_TO_ACTIVATE = "market.no_coverage_to_activate"
    MARKET_HAS_COVERAGE_CONFIRM_DEACTIVATE = "market.has_coverage_confirm_deactivate"
    MARKET_GLOBAL_CANNOT_BE_ARCHIVED = "market.global_cannot_be_archived"
    MARKET_BILLING_CONFIG_NOT_FOUND = "market.billing_config_not_found"

    # ── ad_zone.* ────────────────────────────────────────────────────────
    # Ad zone management errors. Wired in K12.
    AD_ZONE_NOT_FOUND = "ad_zone.not_found"

    # ── cuisine.* ────────────────────────────────────────────────────────
    # Cuisine management errors. Wired in K12.
    CUISINE_NOT_FOUND = "cuisine.not_found"
    CUISINE_SUGGESTION_NOT_FOUND = "cuisine.suggestion_not_found"

    # ── archival.* ───────────────────────────────────────────────────────
    # Archival management errors. Wired in K12.
    ARCHIVAL_NO_RECORDS_PROVIDED = "archival.no_records_provided"
    ARCHIVAL_TOO_MANY_RECORDS = "archival.too_many_records"
    ARCHIVAL_CONFIG_NOT_FOUND = "archival_config.not_found"
    ARCHIVAL_CONFIG_ALREADY_EXISTS = "archival_config.already_exists"

    # ── referral_config.* ────────────────────────────────────────────────
    # Referral config management errors. Wired in K12.
    REFERRAL_CONFIG_NOT_FOUND = "referral_config.not_found"

    # ── supplier_invoice.* ───────────────────────────────────────────────
    # Supplier invoice errors. Wired in K12.
    SUPPLIER_INVOICE_NOT_FOUND = "supplier_invoice.not_found"
    SUPPLIER_INVOICE_INVALID_STATUS = "supplier_invoice.invalid_status"

    # ── billing.* ────────────────────────────────────────────────────────
    # Billing management errors. Wired in K12.
    BILLING_BILL_NOT_FOUND = "billing.bill_not_found"
    BILLING_BILL_ALREADY_PAID = "billing.bill_already_paid"
    BILLING_BILL_ALREADY_CANCELLED = "billing.bill_already_cancelled"
    BILLING_PLAN_NO_CREDITS = "billing.plan_no_credits"
    BILLING_NO_DATA_FOUND = "billing.no_data_found"

    # ── discretionary.* ──────────────────────────────────────────────────
    # Discretionary request errors. Wired in K12.
    DISCRETIONARY_NOT_FOUND = "discretionary.not_found"
    DISCRETIONARY_NOT_PENDING = "discretionary.not_pending"
    # Additional discretionary errors. Wired in K13.
    DISCRETIONARY_RECIPIENT_INSTITUTION_MISMATCH = "discretionary.recipient_institution_mismatch"
    DISCRETIONARY_RECIPIENT_MARKET_MISMATCH = "discretionary.recipient_market_mismatch"
    DISCRETIONARY_INVALID_AMOUNT = "discretionary.invalid_amount"
    DISCRETIONARY_INVALID_CATEGORY = "discretionary.invalid_category"
    DISCRETIONARY_CATEGORY_REQUIRES_RESTAURANT = "discretionary.category_requires_restaurant"

    # ── user.market.* ─────────────────────────────────────────────────────
    # User market assignment errors. Wired in K14 (plate-ops + entity sweep).
    USER_MARKET_IDS_EMPTY = "user.market_ids_empty"
    USER_MARKET_IDS_INVALID = "user.market_ids_invalid"
    USER_MARKET_NOT_IN_INSTITUTION = "user.market_not_in_institution"
    USER_DUPLICATE_USERNAME = "user.duplicate_username"
    USER_DUPLICATE_EMAIL_IN_SYSTEM = "user.duplicate_email_in_system"

    # ── enrollment.* ─────────────────────────────────────────────────────
    # Employer benefits enrollment errors. Wired in K13.
    ENROLLMENT_NO_ACTIVE_PROGRAM = "enrollment.no_active_program"
    ENROLLMENT_EMAIL_ALREADY_REGISTERED = "enrollment.email_already_registered"
    ENROLLMENT_CITY_NO_MARKET = "enrollment.city_no_market"
    ENROLLMENT_EMPLOYER_INSTITUTION_ID_REQUIRED = "enrollment.employer_institution_id_required"
    ENROLLMENT_PARTIAL_SUBSIDY_REQUIRES_APP = "enrollment.partial_subsidy_requires_app"

    # ── employer.program.* ───────────────────────────────────────────────
    # Employer benefits program management errors. Wired in K13.
    EMPLOYER_PROGRAM_ALREADY_EXISTS = "employer.program_already_exists"

    # ── entity.archive.* ──────────────────────────────────────────────────
    # Entity / restaurant archival guardrail errors. Wired in K14.
    ENTITY_SEARCH_INVALID_PARAM = "entity.search_invalid_param"
    ENTITY_ARCHIVE_ACTIVE_PICKUPS = "entity.archive_active_pickups"
    ENTITY_ARCHIVE_ACTIVE_RESTAURANTS = "entity.archive_active_restaurants"
    RESTAURANT_ARCHIVE_ACTIVE_PICKUPS = "restaurant.archive_active_pickups"

    # ── plate_kitchen_day.* ───────────────────────────────────────────────
    # Plate kitchen day management errors. Wired in K14.
    PLATE_KITCHEN_DAY_NOT_FOUND = "plate_kitchen_day.not_found"
    PLATE_KITCHEN_DAY_DUPLICATE = "plate_kitchen_day.duplicate"
    PLATE_KITCHEN_DAY_PLATE_ID_IMMUTABLE = "plate_kitchen_day.plate_id_immutable"
    PLATE_KITCHEN_DAY_ARCHIVE_FAILED = "plate_kitchen_day.archive_failed"
    PLATE_KITCHEN_DAY_UPDATE_FAILED = "plate_kitchen_day.update_failed"
    PLATE_KITCHEN_DAY_DELETE_FAILED = "plate_kitchen_day.delete_failed"

    # ── restaurant.status.* ───────────────────────────────────────────────
    # Restaurant availability errors for plate selection. Wired in K14.
    RESTAURANT_ARCHIVED = "restaurant.archived"
    RESTAURANT_ENTITY_ARCHIVED = "restaurant.entity_archived"
    RESTAURANT_UNAVAILABLE = "restaurant.unavailable"
    RESTAURANT_NATIONAL_HOLIDAY = "restaurant.national_holiday"
    RESTAURANT_HOLIDAY = "restaurant.restaurant_holiday"

    # ── plate_selection.window.* ──────────────────────────────────────────
    # Plate selection kitchen-day and pickup-window validation errors. Wired in K14.
    PLATE_SELECTION_PICKUP_TIME_REQUIRED = "plate_selection.pickup_time_required"
    PLATE_SELECTION_NO_PICKUP_WINDOWS = "plate_selection.no_pickup_windows"
    PLATE_SELECTION_INVALID_PICKUP_WINDOW = "plate_selection.invalid_pickup_window"
    PLATE_SELECTION_KITCHEN_DAY_INVALID = "plate_selection.kitchen_day_invalid"
    PLATE_SELECTION_KITCHEN_DAY_NOT_AVAILABLE = "plate_selection.kitchen_day_not_available"
    PLATE_SELECTION_KITCHEN_DAY_TOO_FAR = "plate_selection.kitchen_day_too_far"
    PLATE_SELECTION_NO_KITCHEN_DAYS = "plate_selection.no_kitchen_days"

    # ── plate_selection.create.* ──────────────────────────────────────────
    # Plate selection create-route validation errors. Wired in K14.
    PLATE_SELECTION_PLATE_ID_REQUIRED = "plate_selection.plate_id_required"
    PLATE_SELECTION_PLATE_ID_INVALID = "plate_selection.plate_id_invalid"

    # ── plate_review.access.* ─────────────────────────────────────────────
    # Plate review access errors not covered by K10. Wired in K14.
    PLATE_REVIEW_CUSTOMER_ONLY = "plate_review.customer_only"
    PLATE_REVIEW_NO_INSTITUTION = "plate_review.no_institution"
    PLATE_REVIEW_BY_PICKUP_NOT_FOUND = "plate_review.by_pickup_not_found"

    # ── ingredient.* ──────────────────────────────────────────────────────
    # Ingredient service errors. Wired in K14.
    INGREDIENT_NOT_FOUND = "ingredient.not_found"

    # ── plate_pickup.staff.* ──────────────────────────────────────────────
    # Plate pickup staff-only access error. Wired in K14.
    PLATE_PICKUP_STAFF_ONLY = "plate_pickup.staff_only"
    PLATE_PICKUP_INVALID_USER_ID = "plate_pickup.invalid_user_id"
    PLATE_PICKUP_INVALID_FILTER = "plate_pickup.invalid_filter"

    # ── locale.* ──────────────────────────────────────────────────────────────
    # Locale/language validation errors. Wired in K15 (misc remainder sweep).
    LOCALE_UNSUPPORTED = "locale.unsupported"

    # ── address.* (business-logic) ────────────────────────────────────────────
    # Address business-logic errors (distinct from validation.address.*). Wired in K15.
    ADDRESS_INSTITUTION_REQUIRED = "address.institution_required"
    ADDRESS_CUSTOMER_INSTITUTION_REQUIRED = "address.customer_institution_required"
    ADDRESS_TARGET_USER_NOT_FOUND = "address.target_user_not_found"
    ADDRESS_USER_INSTITUTION_MISMATCH = "address.user_institution_mismatch"
    ADDRESS_CREATION_FAILED = "address.creation_failed"
    ADDRESS_INVALID_COUNTRY = "address.invalid_country"
    ADDRESS_NOT_FOUND = "address.not_found"
    ADDRESS_MANUAL_ENTRY_NOT_ALLOWED = "address.manual_entry_not_allowed"
    ADDRESS_GLOBAL_MARKET_INVALID = "address.global_market_invalid"
    ADDRESS_CITY_COUNTRY_MISMATCH = "address.city_country_mismatch"
    ADDRESS_PLACE_DETAILS_FAILED = "address.place_details_failed"
    ADDRESS_OUTSIDE_SERVICE_AREA = "address.outside_service_area"
    ADDRESS_CITY_METADATA_UNRESOLVABLE = "address.city_metadata_unresolvable"

    # ── workplace_group.* ─────────────────────────────────────────────────────
    # Workplace group errors. Wired in K15.
    WORKPLACE_GROUP_NOT_FOUND = "workplace_group.not_found"
    WORKPLACE_GROUP_CREATION_FAILED = "workplace_group.creation_failed"
    WORKPLACE_GROUP_UPDATE_FAILED = "workplace_group.update_failed"
    WORKPLACE_GROUP_ARCHIVE_FAILED = "workplace_group.archive_failed"

    # ── supplier_terms.* ──────────────────────────────────────────────────────
    # Supplier terms access errors. Wired in K15.
    SUPPLIER_TERMS_ACCESS_DENIED = "supplier_terms.access_denied"
    SUPPLIER_TERMS_NOT_FOUND = "supplier_terms.not_found"
    SUPPLIER_TERMS_INTERNAL_ONLY = "supplier_terms.internal_only"

    # ── webhook.* ─────────────────────────────────────────────────────────────
    # Stripe webhook processing errors. Wired in K15.
    WEBHOOK_SECRET_NOT_CONFIGURED = "webhook.secret_not_configured"
    WEBHOOK_INVALID_PAYLOAD = "webhook.invalid_payload"
    WEBHOOK_INVALID_SIGNATURE = "webhook.invalid_signature"

    # ── payment_method.* ──────────────────────────────────────────────────────
    # Customer payment method errors. Wired in K15.
    PAYMENT_METHOD_NOT_FOUND = "payment_method.not_found"
    PAYMENT_METHOD_ACCESS_DENIED = "payment_method.access_denied"
    PAYMENT_METHOD_SETUP_URL_REQUIRED = "payment_method.setup_url_required"
    PAYMENT_METHOD_MOCK_ONLY = "payment_method.mock_only"
    PAYMENT_METHOD_PROVIDER_UNAVAILABLE = "payment_method.provider_unavailable"

    # ── referral.* ───────────────────────────────────────────────────────────
    # Referral code errors. Wired in K15.
    REFERRAL_CODE_INVALID = "referral.code_invalid"
    REFERRAL_CODE_NOT_FOUND = "referral.code_not_found"
    REFERRAL_ASSIGNMENT_NOT_FOUND = "referral.assignment_not_found"

    # ── email_change.* ───────────────────────────────────────────────────────
    # Email change service errors. Wired in K15.
    EMAIL_CHANGE_EMAIL_REQUIRED = "email_change.email_required"
    EMAIL_CHANGE_SAME_AS_CURRENT = "email_change.same_as_current"
    EMAIL_CHANGE_ALREADY_TAKEN = "email_change.already_taken"
    EMAIL_CHANGE_PENDING_FOR_EMAIL = "email_change.pending_for_email"
    EMAIL_CHANGE_CODE_EXPIRED = "email_change.code_expired"
    EMAIL_CHANGE_CODE_INVALID = "email_change.code_invalid"
    EMAIL_CHANGE_USER_NOT_FOUND = "email_change.user_not_found"

    # ── credit.* ─────────────────────────────────────────────────────────────
    # Credit loading / validation errors. Wired in K15.
    CREDIT_AMOUNT_MUST_BE_POSITIVE = "credit.amount_must_be_positive"
    CREDIT_CURRENCY_NOT_FOUND = "credit.currency_not_found"

    # ── checksum.* ───────────────────────────────────────────────────────────
    # Checksum utility errors. Wired in K15.
    CHECKSUM_UNSUPPORTED_ALGORITHM = "checksum.unsupported_algorithm"
    CHECKSUM_MISMATCH = "checksum.mismatch"

    # ── country.* ────────────────────────────────────────────────────────────
    # Country utility errors. Wired in K15.
    COUNTRY_INVALID_CODE = "country.invalid_code"

    # ── dev.* ─────────────────────────────────────────────────────────────────
    # Developer-only endpoint guard. Wired in K15.
    DEV_MODE_ONLY = "dev.mode_only"

    # ── institution_entity.* (additional) ────────────────────────────────────
    # Additional institution entity errors. Wired in K15.
    INSTITUTION_ENTITY_NO_MARKETS = "institution_entity.no_markets"
    INSTITUTION_ENTITY_NO_PAYOUT_AGGREGATOR = "institution_entity.no_payout_aggregator"
    INSTITUTION_ENTITY_PAYOUT_SETUP_REQUIRED = "institution_entity.payout_setup_required"

    # ── qr_code.* ────────────────────────────────────────────────────────────
    # QR code management errors. Wired in K15.
    QR_CODE_NO_IMAGE = "qr_code.no_image"
    QR_CODE_LIST_FAILED = "qr_code.list_failed"
    QR_CODE_GET_FAILED = "qr_code.get_failed"
    QR_CODE_DELETE_FAILED = "qr_code.delete_failed"
    # QR code service errors. Wired in K16.
    QR_CODE_CREATE_FAILED = "qr_code.create_failed"
    QR_CODE_UPDATE_FAILED = "qr_code.update_failed"
    QR_CODE_IMAGE_GENERATION_FAILED = "qr_code.image_generation_failed"
    QR_CODE_IMAGE_NOT_FOUND = "qr_code.image_not_found"
    QR_CODE_IMAGE_LOAD_FAILED = "qr_code.image_load_failed"

    # ── restaurant.* ─────────────────────────────────────────────────────────
    # Restaurant operation errors. Wired in K15.
    RESTAURANT_CREATION_FAILED = "restaurant.creation_failed"
    RESTAURANT_BALANCE_CREATION_FAILED = "restaurant.balance_creation_failed"
    RESTAURANT_LIST_FAILED = "restaurant.list_failed"
    RESTAURANT_CITIES_LIST_FAILED = "restaurant.cities_list_failed"
    RESTAURANT_ENRICHED_LIST_FAILED = "restaurant.enriched_list_failed"
    RESTAURANT_ENRICHED_GET_FAILED = "restaurant.enriched_get_failed"
    RESTAURANT_GET_FAILED = "restaurant.get_failed"
    RESTAURANT_UPDATE_FAILED = "restaurant.update_failed"
    RESTAURANT_DELETE_FAILED = "restaurant.delete_failed"

    # ── restaurant_holiday.* ─────────────────────────────────────────────────
    # Restaurant holiday operation errors. Wired in K15.
    RESTAURANT_HOLIDAY_UPDATE_FAILED = "restaurant_holiday.update_failed"
    RESTAURANT_HOLIDAY_DELETE_FAILED = "restaurant_holiday.delete_failed"

    # ── plate_selection.* ─────────────────────────────────────────────────────
    # Plate selection operation errors. Wired in K15.
    PLATE_SELECTION_CREATION_FAILED = "plate_selection.creation_failed"

    # ── product_image.* ──────────────────────────────────────────────────────
    # Product image upload errors. Wired in K15.
    PRODUCT_IMAGE_EMPTY = "product_image.empty"
    PRODUCT_IMAGE_FORMAT_INVALID = "product_image.format_invalid"
    PRODUCT_IMAGE_CHECKSUM_MISMATCH = "product_image.checksum_mismatch"
    PRODUCT_IMAGE_UNREADABLE = "product_image.unreadable"

    # ── leads.* ──────────────────────────────────────────────────────────────
    # Leads route errors. Wired in K15.
    LEADS_COUNTRY_CODE_REQUIRED = "leads.country_code_required"
    LEADS_EMAIL_REQUIRED = "leads.email_required"
    LEADS_INVALID_INTEREST_TYPE = "leads.invalid_interest_type"
    LEADS_INVALID_RESTAURANT_DATA = "leads.invalid_restaurant_data"

    # ── timezone.* ───────────────────────────────────────────────────────────
    # Timezone service errors. Wired in K15.
    TIMEZONE_COUNTRY_CODE_REQUIRED = "timezone.country_code_required"
    TIMEZONE_NOT_FOUND = "timezone.not_found"

    # ── ad_zone.* extended ───────────────────────────────────────────────────
    # Ads zone service errors. Wired in K15.
    AD_ZONE_INVALID_FLYWHEEL_STATE = "ad_zone.invalid_flywheel_state"

    # ── coworker.* ───────────────────────────────────────────────────────────
    # Coworker service errors. Wired in K15.
    COWORKER_EMPLOYER_REQUIRED = "coworker.employer_required"
    COWORKER_USER_INELIGIBLE = "coworker.user_ineligible"

    # ── enrollment.* extended ────────────────────────────────────────────────
    # Enrollment service operation errors. Wired in K15.
    ENROLLMENT_BENEFIT_EMPLOYEE_CREATION_FAILED = "enrollment.benefit_employee_creation_failed"
    ENROLLMENT_SUBSCRIPTION_CREATION_FAILED = "enrollment.subscription_creation_failed"

    # ── employer.* extended ──────────────────────────────────────────────────
    # Employer service operation errors. Wired in K15.
    EMPLOYER_BILL_CREATION_FAILED = "employer.bill_creation_failed"
    EMPLOYER_BENEFITS_PROGRAM_CREATION_FAILED = "employer.benefits_program_creation_failed"

    # ── discretionary.* ──────────────────────────────────────────────────────
    # Discretionary service operation errors. Wired in K15.
    DISCRETIONARY_REQUEST_CREATION_FAILED = "discretionary.request_creation_failed"
    DISCRETIONARY_REQUEST_APPROVAL_FAILED = "discretionary.request_approval_failed"
    DISCRETIONARY_REQUEST_REJECTION_FAILED = "discretionary.request_rejection_failed"
    DISCRETIONARY_LIST_FAILED = "discretionary.list_failed"
    DISCRETIONARY_TRANSACTION_CREATION_FAILED = "discretionary.transaction_creation_failed"

    # ── credit.* extended ────────────────────────────────────────────────────
    # Credit service operation errors. Wired in K15.
    CREDIT_TRANSACTION_CREATION_FAILED = "credit.transaction_creation_failed"
    CREDIT_VALIDATION_FAILED = "credit.validation_failed"

    # ── currency_refresh.* ───────────────────────────────────────────────────
    # Currency refresh cron errors. Wired in K15.
    CURRENCY_REFRESH_RATE_UNAVAILABLE = "currency_refresh.rate_unavailable"

    # ── user.me.* ────────────────────────────────────────────────────────────
    # User self-endpoint redirect hint. Wired in K15.
    USER_USE_ME_ENDPOINT = "user.use_me_endpoint"

    # ── subscription.* ───────────────────────────────────────────────────────
    # Subscription payment creation/recording errors. Wired in K15.
    SUBSCRIPTION_CREATION_FAILED = "subscription.creation_failed"
    SUBSCRIPTION_PAYMENT_RECORD_FAILED = "subscription.payment_record_failed"

    # ── plate_review.operation.* ──────────────────────────────────────────────
    # Plate review operation failures. Wired in K15.
    PLATE_REVIEW_CREATION_FAILED = "plate_review.creation_failed"
    PLATE_REVIEW_COMPLAINT_FAILED = "plate_review.complaint_failed"

    # ── plate_kitchen_days.* ─────────────────────────────────────────────────
    # Plate kitchen days operation errors. Wired in K15.
    PLATE_KITCHEN_DAYS_LIST_FAILED = "plate_kitchen_days.list_failed"
    PLATE_KITCHEN_DAYS_ENRICHED_LIST_FAILED = "plate_kitchen_days.enriched_list_failed"
    PLATE_KITCHEN_DAYS_ENRICHED_GET_FAILED = "plate_kitchen_days.enriched_get_failed"

    # ── national_holiday.* ───────────────────────────────────────────────────
    # National holiday operation failures. Wired in K15.
    NATIONAL_HOLIDAY_UPDATE_FAILED = "national_holiday.update_failed"
    NATIONAL_HOLIDAY_DELETE_FAILED = "national_holiday.delete_failed"

    # ── favorite.* ───────────────────────────────────────────────────────────
    # Favorite service errors. Wired in K15.
    FAVORITE_ENTITY_TYPE_INVALID = "favorite.entity_type_invalid"
    FAVORITE_NOT_FOUND = "favorite.not_found"
    FAVORITE_ALREADY_ADDED = "favorite.already_added"

    # ── notification.* ───────────────────────────────────────────────────────
    # Notification banner service errors. Wired in K15.
    NOTIFICATION_NOT_FOUND = "notification.not_found"

    # ── billing.payout.* ─────────────────────────────────────────────────────
    # Billing payout (mock + live) errors. Wired in K15.
    BILLING_PAYOUT_BILL_NOT_PENDING = "billing.payout_bill_not_pending"

    # ── plate_selection.* extended ───────────────────────────────────────────
    # Plate selection validation errors. Wired in K15.
    PLATE_SELECTION_PICKUP_INTENT_INVALID = "plate_selection.pickup_intent_invalid"

    # ── institution.* ────────────────────────────────────────────────────────
    # Institution constraint errors. Wired in K15.
    INSTITUTION_RESTRICTED = "institution.restricted"

    # ── tax_id.* ─────────────────────────────────────────────────────────────
    # Tax ID validation errors. Wired in K15.
    TAX_ID_FORMAT_INVALID = "tax_id.format_invalid"

    # ── api.* ─────────────────────────────────────────────────────────────────
    # API versioning errors. Wired in K15.
    API_VERSION_UNSUPPORTED = "api.version_unsupported"

    # ── market.* extended ────────────────────────────────────────────────────
    # Market global sentinel errors. Wired in K15.
    MARKET_GLOBAL_ENTITY_INVALID = "market.global_entity_invalid"

    # ── database.* ─────────────────────────────────────────────────────────
    # Database constraint violation errors. Wired in K6 via handle_database_exception.
    DATABASE_DUPLICATE_KEY = "database.duplicate_key"
    DATABASE_DUPLICATE_EMAIL = "database.duplicate_email"
    DATABASE_DUPLICATE_USERNAME = "database.duplicate_username"
    DATABASE_DUPLICATE_MARKET = "database.duplicate_market"
    DATABASE_DUPLICATE_CURRENCY = "database.duplicate_currency"
    DATABASE_DUPLICATE_INSTITUTION = "database.duplicate_institution"
    DATABASE_DUPLICATE_RESTAURANT = "database.duplicate_restaurant"
    DATABASE_FOREIGN_KEY_USER = "database.foreign_key_user"
    DATABASE_FOREIGN_KEY_INSTITUTION = "database.foreign_key_institution"
    DATABASE_FOREIGN_KEY_CURRENCY = "database.foreign_key_currency"
    DATABASE_FOREIGN_KEY_SUBSCRIPTION = "database.foreign_key_subscription"
    DATABASE_FOREIGN_KEY_PLAN = "database.foreign_key_plan"
    DATABASE_FOREIGN_KEY_PAYMENT = "database.foreign_key_payment"
    DATABASE_FOREIGN_KEY_VIOLATION = "database.foreign_key_violation"
    DATABASE_NOT_NULL_MODIFIED_BY = "database.not_null_modified_by"
    DATABASE_NOT_NULL_CURRENCY_CODE = "database.not_null_currency_code"
    DATABASE_NOT_NULL_CURRENCY_NAME = "database.not_null_currency_name"
    DATABASE_NOT_NULL_USERNAME = "database.not_null_username"
    DATABASE_NOT_NULL_EMAIL = "database.not_null_email"
    DATABASE_NOT_NULL_VIOLATION = "database.not_null_violation"
    DATABASE_CHECK_VIOLATION = "database.check_violation"
    DATABASE_INVALID_UUID = "database.invalid_uuid"
    DATABASE_INVALID_FORMAT = "database.invalid_format"
    DATABASE_ERROR = "database.error"

    # ── product.* (operation failures) ───────────────────────────────────────
    # Product service/route operation errors. Wired in K16 (services sweep).
    PRODUCT_ENRICHED_LIST_FAILED = "product.enriched_list_failed"
    PRODUCT_ENRICHED_GET_FAILED = "product.enriched_get_failed"
    PRODUCT_CREATION_FAILED = "product.creation_failed"
    PRODUCT_UPDATE_FAILED = "product.update_failed"
    PRODUCT_IMAGE_UPDATE_FAILED = "product.image_update_failed"
    PRODUCT_IMAGE_REVERT_FAILED = "product.image_revert_failed"

    # ── plan.* (operation failures) ───────────────────────────────────────────
    # Plan service/route operation errors. Wired in K16.
    PLAN_ENRICHED_LIST_FAILED = "plan.enriched_list_failed"
    PLAN_ENRICHED_GET_FAILED = "plan.enriched_get_failed"

    # ── institution.* (operation failures) ────────────────────────────────────
    # Institution service/route operation errors. Wired in K16.
    INSTITUTION_CREATION_FAILED = "institution.creation_failed"
    INSTITUTION_UPDATE_FAILED = "institution.update_failed"
    INSTITUTION_SUPPLIER_TERMS_CREATION_FAILED = "institution.supplier_terms_creation_failed"

    # ── ingredient.* (operation failures) ─────────────────────────────────────
    # Ingredient service operation errors. Wired in K16.
    INGREDIENT_CREATION_FAILED = "ingredient.creation_failed"
    INGREDIENT_PRODUCT_UPDATE_FAILED = "ingredient.product_update_failed"

    # ── notification.* (operation failures) ───────────────────────────────────
    # Notification banner service operation errors. Wired in K16.
    NOTIFICATION_ACKNOWLEDGE_FAILED = "notification.acknowledge_failed"

    # ── subscription.* (operation failures) ───────────────────────────────────
    # Subscription renewal update failure. Wired in K16.
    SUBSCRIPTION_RENEWAL_UPDATE_FAILED = "subscription.renewal_update_failed"

    # ── user.* (service operation failures) ───────────────────────────────────
    # User entity-service operation errors. Wired in K16.
    USER_GET_FAILED = "user.get_failed"
    USER_CREATION_FAILED = "user.creation_failed"
    USER_LIST_FAILED = "user.list_failed"
    USER_ENRICHED_GET_FAILED = "user.enriched_get_failed"
    USER_MARKET_UPDATE_FAILED = "user.market_update_failed"

    # ── service.product.* ─────────────────────────────────────────────────────
    # Product entity-service operation errors. Wired in K16.
    SERVICE_PRODUCT_LIST_FAILED = "service.product_list_failed"
    SERVICE_PRODUCT_SEARCH_FAILED = "service.product_search_failed"
    SERVICE_PLATE_LIST_FAILED = "service.plate_list_failed"
    SERVICE_BILL_LIST_FAILED = "service.bill_list_failed"
    SERVICE_GEOLOCATION_GET_FAILED = "service.geolocation_get_failed"
