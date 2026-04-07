"""
Centralized Error Messages and Database Exception Handling

This module provides standardized error messages and database exception handling
to eliminate duplication and ensure consistency across the application.
All detail strings are resolved via the i18n message catalog for locale support.

This module handles:
1. High-level business logic errors (404 Not Found, 500 Internal Server Error)
2. Low-level database constraint violations (409 Conflict, 400 Bad Request)
3. Consistent error messaging across all operations
"""

from fastapi import HTTPException
from uuid import UUID
from app.i18n.messages import get_message
from app.utils.log import log_warning

def entity_not_found(entity_name: str, entity_id: UUID = None, locale: str = "en") -> HTTPException:
    if entity_id:
        message = get_message("error.entity_not_found_by_id", locale, entity=entity_name, id=entity_id)
    else:
        message = get_message("error.entity_not_found", locale, entity=entity_name)
    return HTTPException(status_code=404, detail=message)

def entity_not_found_or_operation_failed(entity_name: str, operation: str = None, locale: str = "en") -> HTTPException:
    if operation:
        message = get_message("error.entity_operation_failed", locale, entity=entity_name, operation=operation)
    else:
        message = get_message("error.entity_operation_failed", locale, entity=entity_name, operation="operation")
    return HTTPException(status_code=404, detail=message)

def entity_creation_failed(entity_name: str, locale: str = "en") -> HTTPException:
    return HTTPException(status_code=500, detail=get_message("error.entity_creation_failed", locale, entity=entity_name))

def entity_update_failed(entity_name: str, locale: str = "en") -> HTTPException:
    return HTTPException(status_code=500, detail=get_message("error.entity_update_failed", locale, entity=entity_name))

def entity_deletion_failed(entity_name: str, locale: str = "en") -> HTTPException:
    return HTTPException(status_code=500, detail=get_message("error.entity_deletion_failed", locale, entity=entity_name))

# Common entity-specific helpers
def user_not_found(user_id: UUID = None, locale: str = "en"):
    return entity_not_found("User", user_id, locale=locale)

def employer_not_found(employer_id: UUID = None, locale: str = "en"):
    return entity_not_found("Employer", employer_id, locale=locale)

def address_not_found(address_id: UUID = None, locale: str = "en"):
    return entity_not_found("Address", address_id, locale=locale)

def client_bill_not_found(bill_id: UUID = None, locale: str = "en"):
    return entity_not_found("Client bill", bill_id, locale=locale)

def plate_selection_not_found(selection_id: UUID = None, locale: str = "en"):
    return entity_not_found("Plate selection", selection_id, locale=locale)

def pickup_record_not_found(pickup_id: UUID = None, locale: str = "en"):
    return entity_not_found("Pickup record", pickup_id, locale=locale)

def archival_config_not_found(config_id: UUID = None, locale: str = "en"):
    return entity_not_found("Archival configuration", config_id, locale=locale)

def institution_entity_not_found(entity_id: UUID = None, locale: str = "en"):
    return entity_not_found("Institution entity", entity_id, locale=locale)

def credit_currency_not_found(currency_id: UUID = None, locale: str = "en"):
    return entity_not_found("Credit currency", currency_id, locale=locale)

def plate_not_found(plate_id: UUID = None, locale: str = "en"):
    return entity_not_found("Plate", plate_id, locale=locale)


# =============================================================================
# DATABASE EXCEPTION HANDLING
# =============================================================================

def handle_database_exception(error: Exception, operation_type: str = "database operation", locale: str = "en") -> HTTPException:
    """
    Convert database exceptions into appropriate HTTP exceptions.
    All detail strings resolved via i18n message catalog.
    """
    error_message = str(error).lower()
    log_warning(f"Database {operation_type} error: {error}")

    if 'duplicate key value violates unique constraint' in error_message:
        if 'market_info_country_name' in error_message or ('market_info' in error_message and 'country_name' in error_message):
            return HTTPException(status_code=409, detail=get_message("error.db_duplicate_market", locale))
        elif 'currency_code' in error_message:
            return HTTPException(status_code=409, detail=get_message("error.db_duplicate_currency", locale))
        elif 'email' in error_message:
            return HTTPException(status_code=409, detail=get_message("error.db_duplicate_email", locale))
        elif 'username' in error_message:
            return HTTPException(status_code=409, detail=get_message("error.db_duplicate_username", locale))
        elif 'institution_id' in error_message and 'name' in error_message:
            return HTTPException(status_code=409, detail=get_message("error.db_duplicate_institution", locale))
        elif 'restaurant_id' in error_message and 'name' in error_message:
            return HTTPException(status_code=409, detail=get_message("error.db_duplicate_restaurant", locale))
        else:
            return HTTPException(status_code=409, detail=get_message("error.db_duplicate_key", locale))

    elif 'foreign key constraint' in error_message:
        if 'modified_by' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_fk_user", locale))
        elif 'institution_id' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_fk_institution", locale))
        elif 'credit_currency_id' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_fk_currency", locale))
        elif 'payment_id' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_fk_payment", locale))
        elif 'subscription_id' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_fk_subscription", locale))
        elif 'plan_id' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_fk_plan", locale))
        elif 'user_id' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_fk_user", locale))
        else:
            return HTTPException(status_code=400, detail=get_message("error.db_fk_generic", locale))

    elif 'not null constraint' in error_message:
        if 'modified_by' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_notnull_modified_by", locale))
        elif 'currency_code' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_notnull_currency_code", locale))
        elif 'currency_name' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_notnull_currency_name", locale))
        elif 'username' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_notnull_username", locale))
        elif 'email' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_notnull_email", locale))
        else:
            return HTTPException(status_code=400, detail=get_message("error.db_notnull_generic", locale))

    elif 'check constraint' in error_message:
        return HTTPException(status_code=400, detail=get_message("error.db_check_violation", locale))

    elif 'invalid input syntax' in error_message:
        if 'uuid' in error_message:
            return HTTPException(status_code=400, detail=get_message("error.db_invalid_uuid", locale))
        else:
            return HTTPException(status_code=400, detail=get_message("error.db_invalid_format", locale))

    else:
        return HTTPException(status_code=500, detail=get_message("error.db_generic", locale, operation=operation_type, detail=str(error)))


def get_duplicate_key_error_message(table_name: str, field_name: str, locale: str = "en") -> str:
    key_map = {
        ('credit_currency_info', 'currency_code'): "error.db_duplicate_currency",
        ('user_info', 'username'): "error.db_duplicate_username",
        ('user_info', 'email'): "error.db_duplicate_email",
        ('institution_info', 'name'): "error.db_duplicate_institution",
        ('restaurant_info', 'name'): "error.db_duplicate_restaurant",
    }
    msg_key = key_map.get((table_name, field_name))
    if msg_key:
        return get_message(msg_key, locale)
    return get_message("error.db_duplicate_key", locale)


def get_foreign_key_error_message(table_name: str, field_name: str, locale: str = "en") -> str:
    key_map = {
        'modified_by': "error.db_fk_user",
        'institution_id': "error.db_fk_institution",
        'credit_currency_id': "error.db_fk_currency",
        'user_id': "error.db_fk_user",
        'restaurant_id': "error.db_fk_generic",
    }
    msg_key = key_map.get(field_name, "error.db_fk_generic")
    return get_message(msg_key, locale)
