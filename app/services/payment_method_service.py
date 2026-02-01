"""
Payment Method Service - Business Logic for Payment Method Linking

This service handles linking payment methods to their type-specific records
(e.g., fintech_link_id, credit_card_id, bank_account_id) and activating them.
"""

from uuid import UUID
from typing import Dict, Any, Optional
import psycopg2.extensions
from app.utils.log import log_info, log_warning
from app.services.crud_service import payment_method_service
from app.dto.models import PaymentMethodDTO
from app.config import Status
from app.security.institution_scope import InstitutionScope

# Payment method types that require address
PAYMENT_METHODS_REQUIRING_ADDRESS = {"Credit Card", "Bank Account"}

# Payment method types that do NOT require address
PAYMENT_METHODS_NOT_REQUIRING_ADDRESS = {"Fintech Link"}


def link_payment_method_to_type(
    payment_method_id: UUID,
    method_type: str,
    type_id: UUID,
    current_user_id: UUID,
    db: psycopg2.extensions.connection
) -> bool:
    """
    Link payment_method to a specific payment type and activate it.
    
    Updates:
    - payment_method.method_type_id = type_id
    - payment_method.status = 'Active' (if currently 'Pending')
    
    IMPORTANT: Only updates if method_type_id IS NULL and status = 'Pending' (idempotent).
    This ensures:
    - First type used is preserved (audit trail)
    - Consistent pattern across all payment method types (immutable once set)
    - If user needs different type, they must create new payment_method
    - Payment method becomes 'Active' once linked
    
    Args:
        payment_method_id: The payment method to link
        method_type: The payment method type (must match payment_method.method_type)
        type_id: The ID of the type-specific record (fintech_link_id, credit_card_id, etc.)
        current_user_id: User performing the action (for modified_by)
        db: Database connection
        
    Returns:
        True if update was successful, False if already linked (idempotent skip)
        
    Raises:
        HTTPException: If payment_method not found or method_type mismatch
    """
    # Verify payment_method exists and matches method_type
    payment_method = payment_method_service.get_by_id(payment_method_id, db)
    if not payment_method:
        log_warning(f"Payment method {payment_method_id} not found")
        raise ValueError(f"Payment method {payment_method_id} not found")
    
    if payment_method.method_type != method_type:
        log_warning(
            f"Payment method {payment_method_id} has method_type '{payment_method.method_type}', "
            f"expected '{method_type}'"
        )
        raise ValueError(
            f"Payment method type mismatch: expected '{method_type}', "
            f"found '{payment_method.method_type}'"
        )
    
    # Idempotent check: only update if method_type_id is NULL and status is 'Pending'
    if payment_method.method_type_id is not None:
        log_info(
            f"Payment method {payment_method_id} already linked to {payment_method.method_type_id} "
            f"(idempotent update skipped)"
        )
        return False
    
    if payment_method.status != Status.PENDING:
        log_info(
            f"Payment method {payment_method_id} status is '{payment_method.status}', "
            f"not 'Pending' (idempotent update skipped)"
        )
        return False
    
    # Update payment_method: link to type and activate
    try:
        with db.cursor() as cursor:
            query = """
                UPDATE payment_method 
                SET method_type_id = %s,
                    status = 'Active',
                    modified_by = %s,
                    modified_date = CURRENT_TIMESTAMP
                WHERE payment_method_id = %s
                  AND method_type = %s
                  AND method_type_id IS NULL
                  AND status = 'Pending'
            """
            cursor.execute(
                query,
                (
                    str(type_id),
                    str(current_user_id),
                    str(payment_method_id),
                    method_type
                )
            )
            rows_updated = cursor.rowcount
            db.commit()
        
        if rows_updated > 0:
            log_info(
                f"Linked payment_method {payment_method_id} to {method_type} {type_id} "
                f"and activated it"
            )
            return True
        else:
            # This shouldn't happen given our checks above, but handle gracefully
            log_warning(
                f"Payment method {payment_method_id} update returned 0 rows "
                f"(may have been updated concurrently)"
            )
            return False
    except Exception as e:
        log_warning(f"Failed to link payment_method {payment_method_id} to {method_type} {type_id}: {e}")
        db.rollback()
        raise


def create_payment_method_with_address(
    payment_method_data: Dict[str, Any],
    address_id: Optional[UUID],
    address_data: Optional[Dict[str, Any]],
    current_user: Dict[str, Any],
    db: psycopg2.extensions.connection,
    scope: Optional[InstitutionScope] = None
) -> PaymentMethodDTO:
    """
    Create payment method with address (atomic transaction).
    
    Validation rules:
    - credit_card and bank_account: address_id OR address_data is REQUIRED
    - fintech_link: address_id and address_data are OPTIONAL (can be None)
    
    Args:
        payment_method_data: Payment method data (method_type, is_default, etc.)
        address_id: Optional UUID of existing address to use
        address_data: Optional address data to create new address
        current_user: Current user information
        db: Database connection
        scope: Optional institution scope
        
    Returns:
        Created payment method DTO
        
    Raises:
        HTTPException: For validation or creation failures
    """
    from app.services.address_service import address_business_service
    from fastapi import HTTPException, status
    
    method_type = payment_method_data.get("method_type")
    requires_address = method_type in PAYMENT_METHODS_REQUIRING_ADDRESS
    
    # Validate: cannot provide both address_id and address_data
    if address_id and address_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot provide both address_id and address_data. Provide one or the other."
        )
    
    # Validate: payment methods requiring address must have address_id or address_data
    if requires_address and not address_id and not address_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment method type '{method_type}' requires an address. Provide address_id or address_data."
        )
    
    try:
        resolved_address_id = None
        
        # Option 1: Create new address (atomic, commit=False)
        if address_data:
            log_info(f"Creating new address for payment method type '{method_type}'")
            address = address_business_service.create_address_with_geocoding(
                address_data,
                current_user,
                db,
                scope=scope,
                commit=False  # Atomic transaction
            )
            resolved_address_id = address.address_id
        elif address_id:
            # Option 2: Use existing address_id
            log_info(f"Using existing address {address_id} for payment method type '{method_type}'")
            resolved_address_id = address_id
        # Option 3: No address (only valid for fintech_link)
        else:
            log_info(f"Payment method type '{method_type}' created without address (not required)")
        
        # Create payment method with address_id (atomic, commit=False)
        payment_method_data["address_id"] = resolved_address_id
        payment_method_data["user_id"] = current_user["user_id"]
        payment_method_data["modified_by"] = current_user["user_id"]
        
        payment_method = payment_method_service.create(
            payment_method_data,
            db,
            commit=False  # Atomic transaction
        )
        
        if not payment_method:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create payment method"
            )
        
        # Commit once at end (both address and payment_method committed together)
        db.commit()
        log_info(f"Payment method {payment_method.payment_method_id} created successfully with address {resolved_address_id}")
        
        return payment_method
        
    except HTTPException:
        # Re-raise HTTP exceptions
        db.rollback()
        raise
    except Exception as e:
        # Rollback on any error
        db.rollback()
        log_warning(f"Failed to create payment method with address: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment method: {str(e)}"
        )

