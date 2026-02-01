"""
Centralized Error Messages and Database Exception Handling

This module provides standardized error messages and database exception handling
to eliminate duplication and ensure consistency across the application.

This module handles:
1. High-level business logic errors (404 Not Found, 500 Internal Server Error)
2. Low-level database constraint violations (409 Conflict, 400 Bad Request)
3. Consistent error messaging across all operations
"""

from fastapi import HTTPException
from uuid import UUID
from app.utils.log import log_warning

def entity_not_found(entity_name: str, entity_id: UUID = None) -> HTTPException:
    """
    Generate a standardized "entity not found" error.
    
    Args:
        entity_name: The name of the entity (e.g., "User", "Bank account")
        entity_id: Optional entity ID for more specific error messages
        
    Returns:
        HTTPException with 404 status code
    """
    if entity_id:
        message = f"{entity_name} with ID {entity_id} not found"
    else:
        message = f"{entity_name} not found"
    
    return HTTPException(status_code=404, detail=message)

def entity_not_found_or_operation_failed(entity_name: str, operation: str = None) -> HTTPException:
    """
    Generate a standardized "entity not found or operation failed" error.
    
    Args:
        entity_name: The name of the entity
        operation: Optional operation description
        
    Returns:
        HTTPException with 404 status code
    """
    if operation:
        message = f"{entity_name} not found or {operation} failed"
    else:
        message = f"{entity_name} not found or operation failed"
    
    return HTTPException(status_code=404, detail=message)

def entity_creation_failed(entity_name: str) -> HTTPException:
    """
    Generate a standardized "entity creation failed" error.
    
    Args:
        entity_name: The name of the entity
        
    Returns:
        HTTPException with 500 status code
    """
    return HTTPException(status_code=500, detail=f"Failed to create {entity_name}")

def entity_update_failed(entity_name: str) -> HTTPException:
    """
    Generate a standardized "entity update failed" error.
    
    Args:
        entity_name: The name of the entity
        
    Returns:
        HTTPException with 500 status code
    """
    return HTTPException(status_code=500, detail=f"Failed to update {entity_name}")

def entity_deletion_failed(entity_name: str) -> HTTPException:
    """
    Generate a standardized "entity deletion failed" error.
    
    Args:
        entity_name: The name of the entity
        
    Returns:
        HTTPException with 500 status code
    """
    return HTTPException(status_code=500, detail=f"Failed to delete {entity_name}")

# Common entity-specific helpers
def user_not_found(user_id: UUID = None):
    return entity_not_found("User", user_id)

def bank_account_not_found(account_id: UUID = None):
    return entity_not_found("Bank account", account_id)

def employer_not_found(employer_id: UUID = None):
    return entity_not_found("Employer", employer_id)

def address_not_found(address_id: UUID = None):
    return entity_not_found("Address", address_id)

def client_bill_not_found(bill_id: UUID = None):
    return entity_not_found("Client bill", bill_id)

def plate_selection_not_found(selection_id: UUID = None):
    return entity_not_found("Plate selection", selection_id)

def pickup_record_not_found(pickup_id: UUID = None):
    return entity_not_found("Pickup record", pickup_id)

def archival_config_not_found(config_id: UUID = None):
    return entity_not_found("Archival configuration", config_id)

def institution_entity_not_found(entity_id: UUID = None):
    return entity_not_found("Institution entity", entity_id)

def credit_currency_not_found(currency_id: UUID = None):
    return entity_not_found("Credit currency", currency_id)

def plate_not_found(plate_id: UUID = None):
    return entity_not_found("Plate", plate_id)


# =============================================================================
# DATABASE EXCEPTION HANDLING
# =============================================================================

def handle_database_exception(error: Exception, operation_type: str = "database operation") -> HTTPException:
    """
    Convert database exceptions into appropriate HTTP exceptions.
    
    Args:
        error: The original database exception
        operation_type: Type of operation being performed (for logging)
        
    Returns:
        HTTPException with appropriate status code and message
    """
    error_message = str(error).lower()
    log_warning(f"Database {operation_type} error: {error}")
    
    # Handle specific database constraint violations
    if 'duplicate key value violates unique constraint' in error_message:
        if 'currency_code' in error_message:
            return HTTPException(status_code=409, detail="Credit currency with this code already exists")
        elif 'email' in error_message:
            return HTTPException(status_code=409, detail="User with this email already exists")
        elif 'username' in error_message:
            return HTTPException(status_code=409, detail="User with this username already exists")
        elif 'institution_id' in error_message and 'name' in error_message:
            return HTTPException(status_code=409, detail="Institution with this name already exists")
        elif 'restaurant_id' in error_message and 'name' in error_message:
            return HTTPException(status_code=409, detail="Restaurant with this name already exists")
        else:
            return HTTPException(status_code=409, detail="Record with this value already exists")
    
    elif 'foreign key constraint' in error_message:
        if 'modified_by' in error_message:
            return HTTPException(status_code=400, detail="Referenced user does not exist")
        elif 'institution_id' in error_message:
            return HTTPException(status_code=400, detail="Referenced institution does not exist")
        # role_id foreign key check removed - role_id column deprecated, using role_type/role_name enums
        elif 'credit_currency_id' in error_message:
            return HTTPException(status_code=400, detail="Referenced credit currency does not exist")
        elif 'payment_id' in error_message:
            return HTTPException(status_code=400, detail="Referenced payment attempt does not exist")
        elif 'subscription_id' in error_message:
            return HTTPException(status_code=400, detail="Referenced subscription does not exist")
        elif 'plan_id' in error_message:
            return HTTPException(status_code=400, detail="Referenced plan does not exist")
        elif 'user_id' in error_message:
            return HTTPException(status_code=400, detail="Referenced user does not exist")
        else:
            return HTTPException(status_code=400, detail="Referenced record does not exist")
    
    elif 'not null constraint' in error_message:
        if 'modified_by' in error_message:
            return HTTPException(status_code=400, detail="Modified by field is required")
        elif 'currency_code' in error_message:
            return HTTPException(status_code=400, detail="Currency code is required")
        elif 'currency_name' in error_message:
            return HTTPException(status_code=400, detail="Currency name is required")
        elif 'username' in error_message:
            return HTTPException(status_code=400, detail="Username is required")
        elif 'email' in error_message:
            return HTTPException(status_code=400, detail="Email is required")
        else:
            return HTTPException(status_code=400, detail="Required field is missing")
    
    elif 'check constraint' in error_message:
        return HTTPException(status_code=400, detail="Invalid data provided violates business rules")
    
    elif 'invalid input syntax' in error_message:
        if 'uuid' in error_message:
            return HTTPException(status_code=400, detail="Invalid UUID format")
        else:
            return HTTPException(status_code=400, detail="Invalid data format")
    
    # Default case for unhandled database errors
    else:
        return HTTPException(status_code=500, detail=f"Database error during {operation_type}: {str(error)}")


def get_duplicate_key_error_message(table_name: str, field_name: str) -> str:
    """
    Get appropriate error message for duplicate key violations.
    
    Args:
        table_name: Name of the table where the violation occurred
        field_name: Name of the field that caused the violation
        
    Returns:
        Appropriate error message for the duplicate key violation
    """
    error_messages = {
        ('credit_currency_info', 'currency_code'): "Credit currency with this code already exists",
        ('user_info', 'username'): "User with this username already exists",
        ('user_info', 'email'): "User with this email already exists",
        ('institution_info', 'name'): "Institution with this name already exists",
        ('restaurant_info', 'name'): "Restaurant with this name already exists",
        # role_info error message removed - table deprecated
    }
    
    return error_messages.get((table_name, field_name), f"Record with this {field_name} already exists")


def get_foreign_key_error_message(table_name: str, field_name: str) -> str:
    """
    Get appropriate error message for foreign key constraint violations.
    
    Args:
        table_name: Name of the table where the violation occurred
        field_name: Name of the foreign key field that caused the violation
        
    Returns:
        Appropriate error message for the foreign key violation
    """
    error_messages = {
        'modified_by': "Referenced user does not exist",
        'institution_id': "Referenced institution does not exist",
        # role_id removed - role_id column deprecated, using role_type/role_name enums
        'credit_currency_id': "Referenced credit currency does not exist",
        'user_id': "Referenced user does not exist",
        'restaurant_id': "Referenced restaurant does not exist",
    }
    
    return error_messages.get(field_name, f"Referenced record does not exist")
