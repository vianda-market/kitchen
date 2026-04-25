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

    # ── auth.* ─────────────────────────────────────────────────────────────
    # Seeded to prove parity tooling; fully wired in K6 (auth sweep).
    AUTH_INVALID_TOKEN = "auth.invalid_token"
    AUTH_CAPTCHA_REQUIRED = "auth.captcha_required"  # migrated from ad-hoc dict-detail

    # ── subscription.* ─────────────────────────────────────────────────────
    # Seeded to prove parity tooling; fully wired in a later sweep PR.
    SUBSCRIPTION_ALREADY_ACTIVE = "subscription.already_active"  # migrated from ad-hoc dict-detail
