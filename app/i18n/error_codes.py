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

    # ── legacy.* ───────────────────────────────────────────────────────────
    # Transitional. Applied by the wrapping handler to bare-string raises
    # that have not yet been migrated to typed codes (K6..KN sweep).
    # Removed from active use in K-last once the sweep is complete.
    LEGACY_UNCODED = "legacy.uncoded"

    # ── validation.* ───────────────────────────────────────────────────────
    # Emitted by the RequestValidationError handler (K3/K5).
    VALIDATION_FIELD_REQUIRED = "validation.field_required"
    VALIDATION_INVALID_FORMAT = "validation.invalid_format"
    VALIDATION_VALUE_TOO_SHORT = "validation.value_too_short"
    VALIDATION_VALUE_TOO_LONG = "validation.value_too_long"
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

    # ── auth.* ─────────────────────────────────────────────────────────────
    # Seeded to prove parity tooling; fully wired in K6 (auth sweep).
    AUTH_INVALID_TOKEN = "auth.invalid_token"
    AUTH_CAPTCHA_REQUIRED = "auth.captcha_required"  # migrated from ad-hoc dict-detail

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
