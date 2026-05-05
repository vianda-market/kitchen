"""
Referenceability test: every ErrorCode enum member must be referenced at
least once in app/ outside of error_codes.py itself.

This prevents codes from being added to the registry and then forgotten —
an unreferenced code is either (a) not yet wired (allowlisted below) or
(b) dead code that should be removed.

ALLOWLIST POLICY:
  All seeds introduced in K2 are allowlisted because their raise sites are
  wired in later PRs:
    - request.*    → wired by K3 (catch-all handlers)
    - legacy.uncoded → removed in K-last (sweep complete)
    - validation.* → wired by K3/K5 (RequestValidationError handler)
    - auth.*       → wired by K6 (auth sweep)
    - subscription.already_active → wired by a K6..KN sweep PR

  Remove a code from the allowlist in the same PR that wires its first raise
  site. The allowlist shrinks monotonically toward zero by K-last.

  Each entry below includes the PR that will remove it so reviewers can
  verify the allowlist is minimal and not growing indefinitely.
"""

from pathlib import Path

import pytest

from app.i18n.error_codes import ErrorCode

# Codes not yet raised at K2 time; wired incrementally by K3..KN.
# Format: ErrorCode member → PR that will remove the allowlist entry.
ALLOWLISTED: dict[str, str] = {
    # K3 — catch-all handlers
    "REQUEST_NOT_FOUND": "K3",
    "REQUEST_METHOD_NOT_ALLOWED": "K3",
    "REQUEST_MALFORMED_BODY": "K3",
    "REQUEST_TOO_LARGE": "K3",
    "REQUEST_RATE_LIMITED": "K3",
    # K3/K5 — RequestValidationError handler + Pydantic 422 refinement
    "VALIDATION_FIELD_REQUIRED": "K5",
    "VALIDATION_INVALID_FORMAT": "K5",
    "VALIDATION_VALUE_TOO_SHORT": "K5",
    "VALIDATION_VALUE_TOO_LONG": "K5",
    "VALIDATION_CUSTOM": "K3",
    # K5 — domain-specific validation codes (wired via I18nValueError string args
    # in app/schemas/; verified by test_validation_codes_parity::test_schema_i18n_codes_are_registered)
    "VALIDATION_USER_INVALID_ROLE_COMBINATION": "K5",
    "VALIDATION_USER_UNSUPPORTED_LOCALE": "K5",
    "VALIDATION_USER_PASSWORDS_DO_NOT_MATCH": "K5",
    "VALIDATION_USER_NEW_PASSWORD_SAME_AS_CURRENT": "K5",
    "VALIDATION_ADDRESS_CITY_REQUIRED": "K5",
    "VALIDATION_ADDRESS_INVALID_ADDRESS_TYPE": "K5",
    "VALIDATION_ADDRESS_DUPLICATE_ADDRESS_TYPE": "K5",
    "VALIDATION_ADDRESS_INVALID_STREET_TYPE": "K5",
    "VALIDATION_ADDRESS_COUNTRY_REQUIRED": "K5",
    "VALIDATION_ADDRESS_FIELD_REQUIRED": "K5",
    "VALIDATION_ADDRESS_CITY_METADATA_ID_REQUIRED": "K5",
    "VALIDATION_PLATE_KITCHEN_DAYS_EMPTY": "K5",
    "VALIDATION_PLATE_KITCHEN_DAYS_DUPLICATE": "K5",
    "VALIDATION_DISCRETIONARY_RECIPIENT_REQUIRED": "K5",
    "VALIDATION_DISCRETIONARY_CONFLICTING_RECIPIENTS": "K5",
    "VALIDATION_DISCRETIONARY_RESTAURANT_REQUIRED": "K5",
    "VALIDATION_HOLIDAY_RECURRING_FIELDS_REQUIRED": "K5",
    "VALIDATION_HOLIDAY_LIST_EMPTY": "K5",
    "VALIDATION_SUBSCRIPTION_WINDOW_INVALID": "K5",
    "VALIDATION_SUBSCRIPTION_WINDOW_TOO_LONG": "K5",
    "VALIDATION_PAYMENT_CONFLICTING_ADDRESS_FIELDS": "K5",
    "VALIDATION_PAYMENT_UNSUPPORTED_BRAND": "K5",
    # K67 — Pydantic 422 envelope handler + domain ValueError refactor
    # VALIDATION_INVALID_VALUE and VALIDATION_INVALID_TYPE are wired directly via
    # ErrorCode.* in application.py (repo root, outside the app/ scan tree).
    # The supplier_invoice.* and market.* codes are wired via I18nValueError string args
    # in app/schemas/; verified by test_validation_codes_parity::test_schema_i18n_codes_are_registered.
    "VALIDATION_INVALID_VALUE": "K67",
    "VALIDATION_INVALID_TYPE": "K67",
    "VALIDATION_SUPPLIER_INVOICE_CAE_FORMAT": "K67",
    "VALIDATION_SUPPLIER_INVOICE_CUIT_FORMAT": "K67",
    "VALIDATION_SUPPLIER_INVOICE_AFIP_DOC_TYPE": "K67",
    "VALIDATION_SUPPLIER_INVOICE_SUNAT_SERIE_FORMAT": "K67",
    "VALIDATION_SUPPLIER_INVOICE_SUNAT_CORRELATIVO_FORMAT": "K67",
    "VALIDATION_SUPPLIER_INVOICE_RUC_FORMAT": "K67",
    "VALIDATION_SUPPLIER_INVOICE_CDR_STATUS": "K67",
    "VALIDATION_SUPPLIER_INVOICE_AR_DETAILS_REQUIRED": "K67",
    "VALIDATION_SUPPLIER_INVOICE_PE_DETAILS_REQUIRED": "K67",
    "VALIDATION_SUPPLIER_INVOICE_US_DETAILS_REQUIRED": "K67",
    "VALIDATION_SUPPLIER_INVOICE_REJECTION_REASON_REQUIRED": "K67",
    "VALIDATION_SUPPLIER_INVOICE_STATUS_CANNOT_RESET": "K67",
    "VALIDATION_SUPPLIER_W9_EIN_FORMAT": "K67",
    "VALIDATION_MARKET_LANGUAGE_UNSUPPORTED": "K67",
    # K7 — auth + security sweep (AUTH_INVALID_TOKEN, AUTH_CAPTCHA_REQUIRED, and all new codes wired in K7)
    # K6..KN — subscription sweep
    "SUBSCRIPTION_ALREADY_ACTIVE": "K6",
    # K6 — entity CRUD factories (entity.not_found wired in K7 via scoping.py; rest wired in K6)
    "ENTITY_NOT_FOUND_OR_OPERATION_FAILED": "K6",
    "ENTITY_CREATION_FAILED": "K6",
    "ENTITY_UPDATE_FAILED": "K6",
    "ENTITY_DELETION_FAILED": "K6",
    # image-pipeline-uploads-atomic — old inline product image upload codes
    # product_image_service.py was deleted; these codes are superseded by
    # the upload.* namespace. Kept in the registry (append-only) but no longer
    # raised at any active call site.
    "PRODUCT_IMAGE_TOO_LARGE": "image-pipeline-uploads-atomic",
    "PRODUCT_IMAGE_EMPTY": "image-pipeline-uploads-atomic",
    "PRODUCT_IMAGE_FORMAT_INVALID": "image-pipeline-uploads-atomic",
    "PRODUCT_IMAGE_CHECKSUM_MISMATCH": "image-pipeline-uploads-atomic",
    "PRODUCT_IMAGE_UNREADABLE": "image-pipeline-uploads-atomic",
    "PRODUCT_IMAGE_UPDATE_FAILED": "image-pipeline-uploads-atomic",
    "PRODUCT_IMAGE_REVERT_FAILED": "image-pipeline-uploads-atomic",
    # K6 — database constraint violation handler
    "DATABASE_DUPLICATE_KEY": "K6",
    "DATABASE_DUPLICATE_EMAIL": "K6",
    "DATABASE_DUPLICATE_USERNAME": "K6",
    "DATABASE_DUPLICATE_MARKET": "K6",
    "DATABASE_DUPLICATE_CURRENCY": "K6",
    "DATABASE_DUPLICATE_INSTITUTION": "K6",
    "DATABASE_DUPLICATE_RESTAURANT": "K6",
    "DATABASE_FOREIGN_KEY_USER": "K6",
    "DATABASE_FOREIGN_KEY_INSTITUTION": "K6",
    "DATABASE_FOREIGN_KEY_CURRENCY": "K6",
    "DATABASE_FOREIGN_KEY_SUBSCRIPTION": "K6",
    "DATABASE_FOREIGN_KEY_PLAN": "K6",
    "DATABASE_FOREIGN_KEY_PAYMENT": "K6",
    "DATABASE_FOREIGN_KEY_VIOLATION": "K6",
    "DATABASE_NOT_NULL_MODIFIED_BY": "K6",
    "DATABASE_NOT_NULL_CURRENCY_CODE": "K6",
    "DATABASE_NOT_NULL_CURRENCY_NAME": "K6",
    "DATABASE_NOT_NULL_USERNAME": "K6",
    "DATABASE_NOT_NULL_EMAIL": "K6",
    "DATABASE_NOT_NULL_VIOLATION": "K6",
    "DATABASE_CHECK_VIOLATION": "K6",
    "DATABASE_INVALID_UUID": "K6",
    "DATABASE_INVALID_FORMAT": "K6",
    "DATABASE_ERROR": "K6",
}

pytestmark = pytest.mark.parity


def _collect_references(app_root: Path, registry_file: Path) -> set[str]:
    """
    Return the set of ErrorCode member names referenced in app/ outside
    the registry file itself.

    Uses a plain text search rather than full AST resolution: looks for
    "ErrorCode.<MEMBER_NAME>" in source files. This is fast, grep-friendly,
    and sufficient for the purpose (we want to know a member is *used*
    somewhere, not validate every call site).
    """
    referenced: set[str] = set()
    for py_file in app_root.rglob("*.py"):
        if py_file.resolve() == registry_file.resolve():
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for member in ErrorCode.__members__:
            if f"ErrorCode.{member}" in source:
                referenced.add(member)
    return referenced


def test_error_codes_are_referenced() -> None:
    """
    Every non-allowlisted ErrorCode member is referenced at least once
    outside error_codes.py.
    """
    app_root = Path(__file__).parent.parent.parent  # app/
    registry_file = app_root / "i18n" / "error_codes.py"

    referenced = _collect_references(app_root, registry_file)

    unreferenced_non_allowlisted = [
        member for member in ErrorCode.__members__ if member not in referenced and member not in ALLOWLISTED
    ]

    assert not unreferenced_non_allowlisted, (
        f"ErrorCode members are defined but never referenced outside error_codes.py "
        f"and are not in the allowlist: {unreferenced_non_allowlisted}\n"
        "Either wire the code at a raise site, or add it to ALLOWLISTED with the "
        "PR that will wire it."
    )


def test_allowlist_is_minimal() -> None:
    """
    Every entry in ALLOWLISTED corresponds to an actual ErrorCode member.
    Catches stale allowlist entries after a code is removed or renamed.
    """
    all_members = set(ErrorCode.__members__)
    stale = [name for name in ALLOWLISTED if name not in all_members]
    assert not stale, (
        f"ALLOWLISTED entries do not correspond to any ErrorCode member: {stale}\n"
        "Remove them from the allowlist in this test file."
    )
