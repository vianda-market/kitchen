"""
Centralized Error Messages and Database Exception Handling

This module provides standardized error messages and database exception handling
to eliminate duplication and ensure consistency across the application.
All detail dicts are resolved via the i18n envelope factory for locale support.

This module handles:
1. High-level business logic errors (404 Not Found, 500 Internal Server Error)
2. Low-level database constraint violations (409 Conflict, 400 Bad Request)
3. Consistent error messaging across all operations
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException

from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.i18n.messages import get_message
from app.utils.log import log_warning


def entity_not_found(entity_name: str, entity_id: UUID | None = None, locale: str = "en") -> HTTPException:
    if entity_id:
        return envelope_exception(
            ErrorCode.ENTITY_NOT_FOUND,
            status=404,
            locale=locale,
            entity=entity_name,
            id=str(entity_id),
        )
    return envelope_exception(
        ErrorCode.ENTITY_NOT_FOUND,
        status=404,
        locale=locale,
        entity=entity_name,
    )


def entity_not_found_or_operation_failed(
    entity_name: str, operation: str | None = None, locale: str = "en"
) -> HTTPException:
    return envelope_exception(
        ErrorCode.ENTITY_NOT_FOUND_OR_OPERATION_FAILED,
        status=404,
        locale=locale,
        entity=entity_name,
        operation=operation or "operation",
    )


def entity_creation_failed(entity_name: str, locale: str = "en") -> HTTPException:
    return envelope_exception(
        ErrorCode.ENTITY_CREATION_FAILED,
        status=500,
        locale=locale,
        entity=entity_name,
    )


def entity_update_failed(entity_name: str, locale: str = "en") -> HTTPException:
    return envelope_exception(
        ErrorCode.ENTITY_UPDATE_FAILED,
        status=500,
        locale=locale,
        entity=entity_name,
    )


def entity_deletion_failed(entity_name: str, locale: str = "en") -> HTTPException:
    return envelope_exception(
        ErrorCode.ENTITY_DELETION_FAILED,
        status=500,
        locale=locale,
        entity=entity_name,
    )


# Common entity-specific helpers
def user_not_found(user_id: UUID | None = None, locale: str = "en") -> HTTPException:
    return entity_not_found("User", user_id, locale=locale)


def employer_not_found(employer_id: UUID | None = None, locale: str = "en") -> HTTPException:
    return entity_not_found("Employer", employer_id, locale=locale)


def address_not_found(address_id: UUID | None = None, locale: str = "en") -> HTTPException:
    return entity_not_found("Address", address_id, locale=locale)


def client_bill_not_found(bill_id: UUID | None = None, locale: str = "en") -> HTTPException:
    return entity_not_found("Client bill", bill_id, locale=locale)


def plate_selection_not_found(selection_id: UUID | None = None, locale: str = "en") -> HTTPException:
    return entity_not_found("Plate selection", selection_id, locale=locale)


def pickup_record_not_found(pickup_id: UUID | None = None, locale: str = "en") -> HTTPException:
    return entity_not_found("Pickup record", pickup_id, locale=locale)


def archival_config_not_found(config_id: UUID | None = None, locale: str = "en") -> HTTPException:
    return entity_not_found("Archival configuration", config_id, locale=locale)


def institution_entity_not_found(entity_id: UUID | None = None, locale: str = "en") -> HTTPException:
    return entity_not_found("Institution entity", entity_id, locale=locale)


def credit_currency_not_found(currency_id: UUID | None = None, locale: str = "en") -> HTTPException:
    return entity_not_found("Credit currency", currency_id, locale=locale)


def plate_not_found(plate_id: UUID | None = None, locale: str = "en") -> HTTPException:
    return entity_not_found("Plate", plate_id, locale=locale)


# =============================================================================
# DATABASE EXCEPTION HANDLING
# =============================================================================


_DUPLICATE_KEY_RULES: list[tuple[list[str], ErrorCode]] = [
    (["market_info_country_name"], ErrorCode.DATABASE_DUPLICATE_MARKET),
    (["market_info", "country_name"], ErrorCode.DATABASE_DUPLICATE_MARKET),
    (["currency_code"], ErrorCode.DATABASE_DUPLICATE_CURRENCY),
    (["email"], ErrorCode.DATABASE_DUPLICATE_EMAIL),
    (["username"], ErrorCode.DATABASE_DUPLICATE_USERNAME),
    (["institution_id", "name"], ErrorCode.DATABASE_DUPLICATE_INSTITUTION),
    (["restaurant_id", "name"], ErrorCode.DATABASE_DUPLICATE_RESTAURANT),
]

_FK_FIELD_TO_CODE: dict[str, ErrorCode] = {
    "modified_by": ErrorCode.DATABASE_FOREIGN_KEY_USER,
    "institution_id": ErrorCode.DATABASE_FOREIGN_KEY_INSTITUTION,
    "currency_metadata_id": ErrorCode.DATABASE_FOREIGN_KEY_CURRENCY,
    "payment_id": ErrorCode.DATABASE_FOREIGN_KEY_PAYMENT,
    "subscription_id": ErrorCode.DATABASE_FOREIGN_KEY_SUBSCRIPTION,
    "plan_id": ErrorCode.DATABASE_FOREIGN_KEY_PLAN,
    "user_id": ErrorCode.DATABASE_FOREIGN_KEY_USER,
}

_NOTNULL_FIELD_TO_CODE: dict[str, ErrorCode] = {
    "modified_by": ErrorCode.DATABASE_NOT_NULL_MODIFIED_BY,
    "currency_code": ErrorCode.DATABASE_NOT_NULL_CURRENCY_CODE,
    "currency_name": ErrorCode.DATABASE_NOT_NULL_CURRENCY_NAME,
    "username": ErrorCode.DATABASE_NOT_NULL_USERNAME,
    "email": ErrorCode.DATABASE_NOT_NULL_EMAIL,
}


def _match_field(error_message: str, field_map: dict[str, ErrorCode], default: ErrorCode) -> ErrorCode:
    for field, code in field_map.items():
        if field in error_message:
            return code
    return default


def handle_database_exception(
    error: Exception, operation_type: str = "database operation", locale: str = "en"
) -> HTTPException:
    """
    Convert database exceptions into appropriate HTTP exceptions.
    All detail dicts resolved via i18n envelope factory.
    """
    error_message = str(error).lower()
    log_warning(f"Database {operation_type} error: {error}")

    if "duplicate key value violates unique constraint" in error_message:
        for keywords, code in _DUPLICATE_KEY_RULES:
            if all(kw in error_message for kw in keywords):
                return envelope_exception(code, status=409, locale=locale)
        return envelope_exception(ErrorCode.DATABASE_DUPLICATE_KEY, status=409, locale=locale)

    if "foreign key constraint" in error_message:
        code = _match_field(error_message, _FK_FIELD_TO_CODE, ErrorCode.DATABASE_FOREIGN_KEY_VIOLATION)
        return envelope_exception(code, status=400, locale=locale)

    if "not null constraint" in error_message:
        code = _match_field(error_message, _NOTNULL_FIELD_TO_CODE, ErrorCode.DATABASE_NOT_NULL_VIOLATION)
        return envelope_exception(code, status=400, locale=locale)

    if "check constraint" in error_message:
        return envelope_exception(ErrorCode.DATABASE_CHECK_VIOLATION, status=400, locale=locale)

    if "invalid input syntax" in error_message:
        if "uuid" in error_message:
            return envelope_exception(ErrorCode.DATABASE_INVALID_UUID, status=400, locale=locale)
        return envelope_exception(ErrorCode.DATABASE_INVALID_FORMAT, status=400, locale=locale)

    return envelope_exception(
        ErrorCode.DATABASE_ERROR,
        status=500,
        locale=locale,
        operation=operation_type,
        detail=str(error),
    )


def get_duplicate_key_error_message(table_name: str, field_name: str, locale: str = "en") -> str:
    key_map = {
        ("currency_metadata", "currency_code"): "error.db_duplicate_currency",
        ("user_info", "username"): "error.db_duplicate_username",
        ("user_info", "email"): "error.db_duplicate_email",
        ("institution_info", "name"): "error.db_duplicate_institution",
        ("restaurant_info", "name"): "error.db_duplicate_restaurant",
    }
    msg_key = key_map.get((table_name, field_name))
    if msg_key:
        return get_message(msg_key, locale)
    return get_message("error.db_duplicate_key", locale)


def get_foreign_key_error_message(table_name: str, field_name: str, locale: str = "en") -> str:
    key_map = {
        "modified_by": "error.db_fk_user",
        "institution_id": "error.db_fk_institution",
        "currency_metadata_id": "error.db_fk_currency",
        "user_id": "error.db_fk_user",
        "restaurant_id": "error.db_fk_generic",
    }
    msg_key = key_map.get(field_name, "error.db_fk_generic")
    return get_message(msg_key, locale)
