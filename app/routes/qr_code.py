"""
Custom QR Code Router

This router provides atomic QR code operations with automatic image generation.
Replaces the generic CRUD routes for QR codes with specialized business logic.
"""

from typing import Optional
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse

from app.auth.dependencies import get_current_user, get_resolved_locale
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    QRCodeCreateSchema,
    QRCodeEnrichedResponseSchema,
    QRCodeResponseSchema,
    QRCodeUpdateSchema,
)
from app.security.entity_scoping import ENTITY_QR_CODE, ENTITY_RESTAURANT, EntityScopingService
from app.services.crud_service import qr_code_service, restaurant_service
from app.services.entity_service import (
    get_enriched_qr_code_by_id,
    get_enriched_qr_codes,
    get_qr_code_print_context_by_id,
)
from app.services.error_handling import handle_business_operation
from app.services.qr_code_print_service import qr_code_print_response
from app.services.qr_code_service import AtomicQRCodeService
from app.utils.error_messages import entity_not_found
from app.utils.log import log_error
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers

router = APIRouter(prefix="/qr-codes", tags=["QR Codes"])

# Initialize atomic service
atomic_qr_service = AtomicQRCodeService()


@router.post("", response_model=QRCodeResponseSchema, status_code=status.HTTP_201_CREATED)
def create_qr_code_atomic(
    payload: QRCodeCreateSchema,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Create QR code with automatic image generation"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)
    restaurant_scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)

    restaurant = restaurant_service.get_by_id(payload.restaurant_id, db, scope=restaurant_scope)
    if not restaurant:
        raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=404, locale=locale)

    def _create_qr_code():
        return atomic_qr_service.create_qr_code_atomic(payload.restaurant_id, current_user["user_id"], db, scope=scope)

    return handle_business_operation(_create_qr_code, "QR code creation", "QR code created successfully with image")


@router.get("", response_model=list[QRCodeResponseSchema])
def get_all_qr_codes(
    current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all QR codes with resolved image URLs. Non-archived only."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)

    def _get_qr_codes():
        qr_codes = qr_code_service.get_all(db, scope=scope, include_archived=False)
        from app.utils.gcs import resolve_qr_code_image_url

        return [QRCodeResponseSchema(**resolve_qr_code_image_url(q.model_dump(mode="json"))) for q in qr_codes]

    return handle_business_operation(_get_qr_codes, "QR codes retrieval")


# =============================================================================
# ENRICHED QR CODE ENDPOINTS (with institution_name, restaurant_name, address details)
# Must be registered before /{qr_code_id} so /enriched is not parsed as qr_code_id.
# =============================================================================


# GET /qr-codes/enriched - List all QR codes with enriched data
@router.get("/enriched", response_model=list[QRCodeEnrichedResponseSchema])
def list_enriched_qr_codes(
    response: Response,
    pagination: PaginationParams | None = Depends(get_pagination_params),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List all QR codes with enriched data (institution_name, restaurant_name, address details). Non-archived only."""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)
        enriched_qr_codes = get_enriched_qr_codes(
            db,
            scope=scope,
            include_archived=False,
            page=pagination.page if pagination else None,
            page_size=pagination.page_size if pagination else None,
        )
        set_pagination_headers(response, enriched_qr_codes)
        return enriched_qr_codes
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched QR codes: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve enriched QR codes") from None


# GET /qr-codes/enriched/{qr_code_id} - Get a single QR code with enriched data
@router.get("/enriched/{qr_code_id}", response_model=QRCodeEnrichedResponseSchema)
def get_enriched_qr_code_by_id_route(
    qr_code_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get a single QR code by ID with enriched data (institution_name, restaurant_name, address details). Non-archived only."""
    try:
        scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)
        enriched_qr_code = get_enriched_qr_code_by_id(qr_code_id, db, scope=scope, include_archived=False)
        if not enriched_qr_code:
            raise entity_not_found("QR code", qr_code_id)
        return enriched_qr_code
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched QR code {qr_code_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve enriched QR code") from None


# =============================================================================
# PRINT HTML (supplier B2B): base64 QR, market-aware address, optional autoprint
# Register before /{qr_code_id} and before /restaurant/{restaurant_id}
# =============================================================================


@router.get("/{qr_code_id}/print", response_class=HTMLResponse)
def print_qr_code_html(
    qr_code_id: UUID,
    autoprint: str | None = Query(
        None,
        description="If 'true' (case-insensitive), open print dialog on load. Use str, not bool—FastAPI bool would accept 1/yes.",
    ),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Printable HTML with embedded QR image and restaurant address. Auth required."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)
    ctx = get_qr_code_print_context_by_id(qr_code_id, db, scope=scope, include_archived=False)
    if not ctx:
        raise entity_not_found("QR code", qr_code_id)
    return qr_code_print_response(ctx, autoprint=autoprint)


@router.get("/restaurant/{restaurant_id}/print", response_class=HTMLResponse)
def print_qr_code_html_by_restaurant(
    restaurant_id: UUID,
    autoprint: str | None = Query(
        None,
        description="If 'true' (case-insensitive), open print dialog on load. Use str, not bool—FastAPI bool would accept 1/yes.",
    ),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Same as /{qr_code_id}/print but resolved by restaurant_id."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)
    restaurant_scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)

    restaurant = restaurant_service.get_by_id(restaurant_id, db, scope=restaurant_scope)
    if not restaurant:
        raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=404, locale=locale)

    qr = qr_code_service.get_by_field("restaurant_id", restaurant_id, db, scope=scope)
    if not qr or qr.is_archived:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="QR code")

    ctx = get_qr_code_print_context_by_id(qr.qr_code_id, db, scope=scope, include_archived=False)
    if not ctx:
        raise entity_not_found("QR code", qr.qr_code_id)
    return qr_code_print_response(ctx, autoprint=autoprint)


@router.get("/{qr_code_id}", response_model=QRCodeResponseSchema)
def get_qr_code(
    qr_code_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get QR code by ID with resolved image URL (signed URL when GCS). Non-archived only."""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)
    qr_code = qr_code_service.get_by_id(qr_code_id, db, scope=scope)
    if not qr_code or qr_code.is_archived:
        raise entity_not_found("QR code", qr_code_id)
    data = qr_code.model_dump(mode="json")
    from app.utils.gcs import resolve_qr_code_image_url

    data = resolve_qr_code_image_url(data)
    return QRCodeResponseSchema(**data)


@router.put("/{qr_code_id}", response_model=QRCodeResponseSchema)
def update_qr_code(
    qr_code_id: UUID,
    payload: QRCodeUpdateSchema,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update QR code information (status changes only)"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)

    existing_qr = qr_code_service.get_by_id(qr_code_id, db, scope=scope)
    if not existing_qr:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="QR code")

    def _update_qr_code():
        # Only allow status updates for atomic QR codes
        if payload.status:
            return atomic_qr_service.update_qr_code_status(
                qr_code_id, payload.status, current_user["user_id"], db, scope=scope
            )
        # For other updates, use standard CRUD service
        data = payload.model_dump(exclude_unset=True)
        data["modified_by"] = current_user["user_id"]
        return qr_code_service.update(qr_code_id, data, db, scope=scope)

    return handle_business_operation(_update_qr_code, "QR code update", "QR code updated successfully")


@router.delete("/{qr_code_id}")
def delete_qr_code_atomic(
    qr_code_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Delete QR code and its associated image"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)

    existing_qr = qr_code_service.get_by_id(qr_code_id, db, scope=scope)
    if not existing_qr:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="QR code")

    def _delete_qr_code():
        success = atomic_qr_service.delete_qr_code_atomic(qr_code_id, db, scope=scope)
        if success:
            return {"message": "QR code deleted successfully"}
        raise HTTPException(status_code=500, detail="Failed to delete QR code")

    return handle_business_operation(_delete_qr_code, "QR code deletion", "QR code deleted successfully")


@router.get("/restaurant/{restaurant_id}", response_model=Optional[QRCodeResponseSchema])
def get_qr_code_by_restaurant(
    restaurant_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get QR code by restaurant ID"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_QR_CODE, current_user)
    restaurant_scope = EntityScopingService.get_scope_for_entity(ENTITY_RESTAURANT, current_user)

    restaurant = restaurant_service.get_by_id(restaurant_id, db, scope=restaurant_scope)
    if not restaurant:
        raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=404, locale=locale)

    def _get_qr_code_by_restaurant():
        qr = qr_code_service.get_by_field("restaurant_id", restaurant_id, db, scope=scope)
        if not qr:
            return None
        data = qr.model_dump(mode="json")
        from app.utils.gcs import resolve_qr_code_image_url

        data = resolve_qr_code_image_url(data)
        return QRCodeResponseSchema(**data)

    return handle_business_operation(_get_qr_code_by_restaurant, "QR code retrieval by restaurant")
