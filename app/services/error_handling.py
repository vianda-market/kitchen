# app/services/error_handling.py
"""
Centralized error handling service.

This module provides dedicated error handling functions that can be used
across the application to handle common error scenarios without cluttering
business logic with try/except blocks.

Benefits:
- Clean separation of error handling from business logic
- Consistent error handling patterns
- Easier testing of error scenarios
- Reusable error handling functions
"""

from collections.abc import Callable
from typing import TypeVar
from uuid import UUID

import psycopg2.extensions
from fastapi import HTTPException

from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.utils.log import log_error, log_info

T = TypeVar("T")


# =============================================================================
# GENERIC ERROR HANDLING FUNCTIONS
# =============================================================================


def handle_service_call(
    service_func: Callable[..., T], error_message: str, http_status: int = 500, *args, **kwargs
) -> T | None:
    """
    Generic error handler for service calls.

    Args:
        service_func: The service function to call
        error_message: Error message to log and return
        http_status: HTTP status code for HTTPException
        *args, **kwargs: Arguments to pass to service_func

    Returns:
        Result of service_func or None if error

    Raises:
        HTTPException if http_status is provided and error occurs
    """
    try:
        return service_func(*args, **kwargs)
    except HTTPException:
        # Re-raise HTTPExceptions (these are intentional)
        raise
    except Exception as e:
        log_error(f"{error_message}: {e}")
        if http_status:
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=http_status, locale="en") from None
        return None


def handle_database_operation(
    operation_func: Callable[..., T],
    operation_name: str,
    entity_id: UUID | None = None,
    http_status: int = 500,
    *args,
    **kwargs,
) -> T | None:
    """
    Generic error handler for database operations.

    Args:
        operation_func: The database operation function to call
        operation_name: Name of the operation (e.g., "fetching user")
        entity_id: Optional entity ID for logging
        http_status: HTTP status code for HTTPException
        *args, **kwargs: Arguments to pass to operation_func

    Returns:
        Result of operation_func or None if error

    Raises:
        HTTPException if http_status is provided and error occurs
    """
    entity_context = f" for {entity_id}" if entity_id else ""
    error_message = f"Error {operation_name}{entity_context}"

    try:
        return operation_func(*args, **kwargs)
    except HTTPException:
        # Re-raise HTTPExceptions (these are intentional)
        raise
    except Exception as e:
        log_error(f"{error_message}: {e}")
        if http_status:
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=http_status, locale="en") from None
        return None


# =============================================================================
# ENTITY-SPECIFIC ERROR HANDLERS
# =============================================================================


def handle_get_by_id(
    service_func: Callable[[UUID, psycopg2.extensions.connection], T | None],
    entity_id: UUID,
    db: psycopg2.extensions.connection,
    entity_name: str,
    extra_kwargs: dict | None = None,
) -> T | None:
    """
    Handle get_by_id operations with consistent error handling.
    Always returns only non-archived records.

    Args:
        service_func: The get_by_id service function
        entity_id: ID of the entity to fetch
        db: Database connection
        entity_name: Name of the entity (e.g., "user", "product")
        extra_kwargs: Optional kwargs to pass to service_func (e.g. scope)

    Returns:
        Entity DTO or None if not found

    Raises:
        HTTPException with 404 status if entity not found
    """
    extra_kwargs = extra_kwargs or {}

    try:
        # Use get_by_id_non_archived if available, otherwise use get_by_id
        if hasattr(service_func, "__self__"):
            service_instance = service_func.__self__
            if hasattr(service_instance, "get_by_id_non_archived"):
                entity = service_instance.get_by_id_non_archived(entity_id, db, **extra_kwargs)
            else:
                entity = service_func(entity_id, db, **extra_kwargs)
        else:
            entity = service_func(entity_id, db, **extra_kwargs)
        log_info(f"Queried non-archived {entity_name} by id: {entity_id}")

        if entity is None:
            raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale="en", entity=entity_name.title())

        return entity
    except HTTPException:
        # Re-raise HTTPExceptions (these are intentional)
        raise
    except Exception as e:
        log_error(f"Error fetching {entity_name} {entity_id}: {e}")
        raise envelope_exception(
            ErrorCode.ENTITY_NOT_FOUND, status=404, locale="en", entity=entity_name.title()
        ) from None


def handle_get_all(
    service_func: Callable[[psycopg2.extensions.connection], list[T]],
    db: psycopg2.extensions.connection,
    entity_name: str,
) -> list[T]:
    """
    Handle get_all operations with consistent error handling.
    Always returns only non-archived records.

    Args:
        service_func: The get_all service function
        db: Database connection
        entity_name: Name of the entity (e.g., "users", "products")

    Returns:
        List of entity DTOs

    Raises:
        HTTPException with 500 status if error occurs
    """
    try:
        entities = service_func(db)
        log_info(f"Retrieved non-archived {entity_name}")
        return entities
    except Exception as e:
        log_error(f"Error retrieving {entity_name}: {e}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None


def handle_create(
    service_func: Callable[[dict, psycopg2.extensions.connection], T | None],
    data: dict,
    db: psycopg2.extensions.connection,
    entity_name: str,
) -> T | None:
    """
    Handle create operations with consistent error handling.

    Args:
        service_func: The create service function
        data: Data to create entity with
        db: Database connection
        entity_name: Name of the entity (e.g., "user", "product")

    Returns:
        Created entity DTO or None if error

    Raises:
        HTTPException with 500 status if error occurs
    """
    try:
        entity = service_func(data, db)
        if entity:
            log_info(f"Successfully created {entity_name}: {entity}")
            return entity
        log_error(f"Failed to create {entity_name}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en")
    except HTTPException:
        # Re-raise HTTPExceptions (these are intentional)
        raise
    except Exception as e:
        log_error(f"Error creating {entity_name}: {e}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None


def handle_update(
    service_func: Callable[[UUID, dict, psycopg2.extensions.connection], T | None],
    entity_id: UUID,
    data: dict,
    db: psycopg2.extensions.connection,
    entity_name: str,
) -> T | None:
    """
    Handle update operations with consistent error handling.

    Args:
        service_func: The update service function
        entity_id: ID of the entity to update
        data: Data to update entity with
        db: Database connection
        entity_name: Name of the entity (e.g., "user", "product")

    Returns:
        Updated entity DTO or None if error

    Raises:
        HTTPException with 500 status if error occurs
    """
    try:
        entity = service_func(entity_id, data, db)
        if entity:
            log_info(f"Successfully updated {entity_name}: {entity_id}")
            return entity
        log_error(f"Failed to update {entity_name}: {entity_id}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en")
    except HTTPException:
        # Re-raise HTTPExceptions (these are intentional)
        raise
    except Exception as e:
        log_error(f"Error updating {entity_name} {entity_id}: {e}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None


def handle_delete(
    service_func: Callable[[UUID, psycopg2.extensions.connection], bool],
    entity_id: UUID,
    db: psycopg2.extensions.connection,
    entity_name: str,
) -> bool:
    """
    Handle delete operations with consistent error handling.

    Args:
        service_func: The delete service function
        entity_id: ID of the entity to delete
        db: Database connection
        entity_name: Name of the entity (e.g., "user", "product")

    Returns:
        True if successful, False otherwise

    Raises:
        HTTPException with 500 status if error occurs
    """
    try:
        success = service_func(entity_id, db)
        if success:
            log_info(f"Successfully deleted {entity_name}: {entity_id}")
            return True
        log_error(f"Failed to delete {entity_name}: {entity_id}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en")
    except HTTPException:
        # Re-raise HTTPExceptions (these are intentional)
        raise
    except Exception as e:
        log_error(f"Error deleting {entity_name} {entity_id}: {e}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None


# =============================================================================
# BUSINESS LOGIC ERROR HANDLERS
# =============================================================================


def handle_business_operation(
    operation_func: Callable[..., T], operation_name: str, success_message: str | None = None, *args, **kwargs
) -> T:
    """
    Handle business logic operations with consistent error handling.

    Args:
        operation_func: The business operation function
        operation_name: Name of the operation
        success_message: Optional success message to log
        *args, **kwargs: Arguments to pass to operation_func

    Returns:
        Result of operation_func

    Raises:
        HTTPException with 500 status if error occurs
    """
    try:
        result = operation_func(*args, **kwargs)
        if success_message and result:
            log_info(success_message)
        return result
    except HTTPException:
        # Re-raise HTTPExceptions (these are intentional)
        raise
    except Exception as e:
        # Safely convert exception to string, handling UUID objects and other types
        import traceback

        error_trace = traceback.format_exc()

        # Safely get error message
        try:
            error_msg = str(e)
        except Exception:
            try:
                error_msg = repr(e)
            except Exception:
                error_msg = f"Error of type {type(e).__name__}"

        # Log with full traceback
        log_error(f"Error in {operation_name}: {error_msg}\nFull traceback:\n{error_trace}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None
