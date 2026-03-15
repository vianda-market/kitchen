"""
Custom QR Code Router

This router provides atomic QR code operations with automatic image generation.
Replaces the generic CRUD routes for QR codes with specialized business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List, Optional

from app.services.qr_code_service import AtomicQRCodeService
from app.services.crud_service import qr_code_service, restaurant_service
from app.services.entity_service import get_enriched_qr_codes, get_enriched_qr_code_by_id
from app.schemas.consolidated_schemas import (
    QRCodeCreateSchema, 
    QRCodeUpdateSchema, 
    QRCodeResponseSchema,
    QRCodeEnrichedResponseSchema
)
from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.services.error_handling import handle_business_operation, handle_get_by_id
from app.utils.error_messages import entity_not_found
from app.utils.log import log_error
from app.security.entity_scoping import EntityScopingService, ENTITY_QR_CODE, ENTITY_RESTAURANT
import psycopg2.extensions

router = APIRouter(prefix="/qr-codes", tags=["QR Codes"])

# Initialize atomic service
atomic_qr_service = AtomicQRCodeService()

@router.post("", response_model=QRCodeResponseSchema, status_code=status.HTTP_201_CREATED)
def create_qr_code_atomic(
    payload: QRCodeCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create QR code with automatic image generation"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)
    restaurant_scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)

    restaurant = restaurant_service.get_by_id(payload.restaurant_id, db, scope=restaurant_scope)
    if not restaurant:
        raise HTTPException(
            status_code=404,
            detail="Restaurant not found for QR code creation. Ensure the restaurant exists and you have access to it (check institution scope).",
        )

    def _create_qr_code():
        return atomic_qr_service.create_qr_code_atomic(
            payload.restaurant_id,
            current_user["user_id"],
            db,
            scope=scope
        )
    
    return handle_business_operation(
        _create_qr_code,
        "QR code creation",
        "QR code created successfully with image"
    )

@router.get("", response_model=List[QRCodeResponseSchema])
def get_all_qr_codes(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all QR codes. Non-archived only."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)

    def _get_qr_codes():
        return qr_code_service.get_all(db, scope=scope, include_archived=False)
    
    return handle_business_operation(_get_qr_codes, "QR codes retrieval")

# =============================================================================
# ENRICHED QR CODE ENDPOINTS (with institution_name, restaurant_name, address details)
# Must be registered before /{qr_code_id} so /enriched is not parsed as qr_code_id.
# =============================================================================

# GET /qr-codes/enriched - List all QR codes with enriched data
@router.get("/enriched", response_model=List[QRCodeEnrichedResponseSchema])
def list_enriched_qr_codes(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all QR codes with enriched data (institution_name, restaurant_name, address details). Non-archived only."""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)
        enriched_qr_codes = get_enriched_qr_codes(
            db,
            scope=scope,
            include_archived=False
        )
        return enriched_qr_codes
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched QR codes: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve enriched QR codes")

# GET /qr-codes/enriched/{qr_code_id} - Get a single QR code with enriched data
@router.get("/enriched/{qr_code_id}", response_model=QRCodeEnrichedResponseSchema)
def get_enriched_qr_code_by_id_route(
    qr_code_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single QR code by ID with enriched data (institution_name, restaurant_name, address details). Non-archived only."""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)
        enriched_qr_code = get_enriched_qr_code_by_id(
            qr_code_id,
            db,
            scope=scope,
            include_archived=False
        )
        if not enriched_qr_code:
            raise entity_not_found("QR code", qr_code_id)
        return enriched_qr_code
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched QR code {qr_code_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve enriched QR code")

@router.get("/{qr_code_id}", response_model=QRCodeResponseSchema)
def get_qr_code(
    qr_code_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get QR code by ID. Non-archived only."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)
    return handle_get_by_id(
        qr_code_service.get_by_id,
        qr_code_id,
        db,
        "QR code",
        extra_kwargs={"scope": scope}
    )

@router.put("/{qr_code_id}", response_model=QRCodeResponseSchema)
def update_qr_code(
    qr_code_id: UUID,
    payload: QRCodeUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update QR code information (status changes only)"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)

    existing_qr = qr_code_service.get_by_id(qr_code_id, db, scope=scope)
    if not existing_qr:
        raise HTTPException(status_code=404, detail="QR code not found")

    def _update_qr_code():
        # Only allow status updates for atomic QR codes
        if payload.status:
            return atomic_qr_service.update_qr_code_status(
                qr_code_id,
                payload.status,
                current_user["user_id"],
                db,
                scope=scope
            )
        else:
            # For other updates, use standard CRUD service
            data = payload.model_dump(exclude_unset=True)
            data["modified_by"] = current_user["user_id"]
            return qr_code_service.update(qr_code_id, data, db, scope=scope)
    
    return handle_business_operation(
        _update_qr_code,
        "QR code update",
        "QR code updated successfully"
    )

@router.delete("/{qr_code_id}")
def delete_qr_code_atomic(
    qr_code_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Delete QR code and its associated image"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)

    existing_qr = qr_code_service.get_by_id(qr_code_id, db, scope=scope)
    if not existing_qr:
        raise HTTPException(status_code=404, detail="QR code not found")

    def _delete_qr_code():
        success = atomic_qr_service.delete_qr_code_atomic(qr_code_id, db, scope=scope)
        if success:
            return {"message": "QR code deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete QR code")
    
    return handle_business_operation(
        _delete_qr_code,
        "QR code deletion",
        "QR code deleted successfully"
    )

@router.get("/restaurant/{restaurant_id}", response_model=Optional[QRCodeResponseSchema])
def get_qr_code_by_restaurant(
    restaurant_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get QR code by restaurant ID"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)
    restaurant_scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)

    restaurant = restaurant_service.get_by_id(restaurant_id, db, scope=restaurant_scope)
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    def _get_qr_code_by_restaurant():
        return qr_code_service.get_by_field("restaurant_id", restaurant_id, db, scope=scope)
    
    return handle_business_operation(_get_qr_code_by_restaurant, "QR code retrieval by restaurant")
