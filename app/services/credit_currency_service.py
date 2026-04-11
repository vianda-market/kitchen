"""
Credit Currency Service

Centralized service for resolving currency_code from currency_metadata_id.
This ensures consistency across all tables that store both currency_id and currency_code.
"""

from uuid import UUID
from typing import Dict, Any
from fastapi import HTTPException, status
import psycopg2.extensions

from app.services.crud_service import credit_currency_service
from app.utils.log import log_info, log_error
from app.utils.error_messages import credit_currency_not_found


def resolve_currency_code(
    data: Dict[str, Any],
    db: psycopg2.extensions.connection,
    currency_id_field: str = "currency_metadata_id"
) -> None:
    """
    Resolve currency_code from currency_metadata_id and add it to the data dictionary.
    
    This function should be called before creating or updating records in tables
    that have both currency_metadata_id and currency_code fields. The currency_code
    is resolved from the currency_metadata table and added to the data dict.
    
    Args:
        data: Data dictionary (modified in place) - must contain currency_metadata_id
        db: Database connection
        currency_id_field: Name of the currency ID field (default: "currency_metadata_id")
        
    Raises:
        HTTPException: If currency_id is missing or currency not found
    """
    currency_id = data.get(currency_id_field)
    
    log_info(f"[resolve_currency_code] Starting resolution for {currency_id_field}={currency_id}")
    
    if not currency_id:
        log_error(f"[resolve_currency_code] Missing required field: {currency_id_field}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required field: {currency_id_field}"
        )
    
    # Get currency from database
    log_info(f"[resolve_currency_code] Looking up currency with ID: {currency_id}")
    currency = credit_currency_service.get_by_id(currency_id, db)
    
    if not currency:
        log_error(f"[resolve_currency_code] Currency not found for ID: {currency_id}")
        raise credit_currency_not_found()
    
    # Set currency code in data
    data["currency_code"] = currency.currency_code
    log_info(f"[resolve_currency_code] Successfully resolved currency_code='{currency.currency_code}' for currency_id={currency_id}")
    log_info(f"[resolve_currency_code] Data dict after resolution: {list(data.keys())}")

