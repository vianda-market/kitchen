# app/routes/payment_methods/institution_payment_attempt.py

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from uuid import UUID
from app.dto.models import InstitutionPaymentAttemptDTO
from app.services.crud_service import (
    institution_payment_attempt_service,
    institution_entity_service,
    institution_bill_service,
    get_by_institution_entity
)
from app.schemas.payment_methods.institution_payment_attempt import (
    InstitutionPaymentAttemptCreateSchema,
    InstitutionPaymentAttemptUpdateSchema,
    InstitutionPaymentAttemptResponseSchema,
    InstitutionPaymentAttemptMinimalCreateSchema,
    InstitutionPaymentAttemptStatusUpdateSchema,
    InstitutionPaymentAttemptSummarySchema
)
from app.schemas.consolidated_schemas import InstitutionPaymentAttemptEnrichedResponseSchema
from app.services.entity_service import get_enriched_institution_payment_attempts, get_enriched_institution_payment_attempt_by_id
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning, log_error
from app.utils.query_params import include_archived_query, institution_entity_filter
from app.utils.error_messages import institution_entity_not_found
from app.services.error_handling import handle_business_operation
from app.services.credit_currency_service import resolve_currency_code
from app.security.institution_scope import InstitutionScope
from app.security.entity_scoping import EntityScopingService, ENTITY_INSTITUTION_PAYMENT_ATTEMPT
import psycopg2.extensions

router = APIRouter(
    prefix="/institution-payment-attempts",
    tags=["Institution Payment Attempts"],
    dependencies=[Depends(oauth2_scheme)]
)


def _payment_attempt_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment attempt not found")


def _require_entity_access(
    institution_entity_id: UUID,
    db: psycopg2.extensions.connection,
    scope: InstitutionScope
):
    entity = institution_entity_service.get_by_id(institution_entity_id, db, scope=scope)
    if not entity:
        raise institution_entity_not_found()
    return entity


def _require_payment_attempt(
    payment_id: UUID,
    db: psycopg2.extensions.connection,
    scope: InstitutionScope
) -> InstitutionPaymentAttemptDTO:
    attempt = institution_payment_attempt_service.get_by_id(payment_id, db)
    if not attempt:
        raise _payment_attempt_not_found()

    if scope and not scope.is_global:
        _require_entity_access(attempt.institution_entity_id, db, scope)

    return attempt


def _require_bill_access(
    institution_bill_id: UUID,
    db: psycopg2.extensions.connection,
    scope: InstitutionScope
):
    bill = institution_bill_service.get_by_id(institution_bill_id, db)
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution bill not found")

    if scope and not scope.is_global:
        _require_entity_access(bill.institution_entity_id, db, scope)

    return bill


def _list_payment_attempts_for_scope(
    scope: InstitutionScope,
    db: psycopg2.extensions.connection
) -> List[InstitutionPaymentAttemptDTO]:
    if scope.is_global:
        return institution_payment_attempt_service.get_all(db)

    entities = institution_entity_service.get_all(db, scope=scope)
    attempts: List[InstitutionPaymentAttemptDTO] = []
    for entity in entities:
        attempts.extend(get_by_institution_entity(entity.institution_entity_id, db, scope=scope))
    return attempts

# GET /institution-payment-attempts/{payment_id}?include_archived={...}
@router.get("/{payment_id}", response_model=InstitutionPaymentAttemptResponseSchema)
def get_payment_attempt(
    payment_id: UUID,
    include_archived: bool = include_archived_query("payment attempts"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a payment attempt by ID with optional archived records"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)
    _ = include_archived
    return _require_payment_attempt(payment_id, db, scope)

# GET /institution-payment-attempts/?include_archived={...}&institution_entity_id={...}&institution_bill_id={...}
@router.get("/", response_model=List[InstitutionPaymentAttemptResponseSchema])
def get_all_payment_attempts(
    include_archived: bool = include_archived_query("payment attempts"),
    institution_entity_id: Optional[UUID] = institution_entity_filter(),
    institution_bill_id: Optional[UUID] = Query(None, description="Filter by institution bill ID"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all payment attempts with optional filtering"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)

    def _get_payment_attempts():
        if institution_entity_id:
            _require_entity_access(institution_entity_id, db, scope)
            payment_attempts = get_by_institution_entity(institution_entity_id, db, scope=scope)
            log_info(f"Retrieved payment attempts for institution entity: {institution_entity_id}")
        elif institution_bill_id:
            _require_bill_access(institution_bill_id, db, scope)
            payment_attempts = institution_payment_attempt_service.get_by_institution_bill(institution_bill_id, db, scope=scope)
            log_info(f"Retrieved payment attempts for institution bill: {institution_bill_id}")
        else:
            payment_attempts = _list_payment_attempts_for_scope(scope, db)
            log_info("Retrieved scoped payment attempts")
        
        return payment_attempts
    
    return handle_business_operation(_get_payment_attempts, "payment attempts retrieval")

# GET /institution-payment-attempts/pending/{institution_entity_id}
@router.get("/pending/{institution_entity_id}", response_model=List[InstitutionPaymentAttemptResponseSchema])
def get_pending_payment_attempts(
    institution_entity_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all pending payment attempts for a specific institution entity"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)
    _require_entity_access(institution_entity_id, db, scope)

    def _get_pending_payment_attempts():
        payment_attempts = institution_payment_attempt_service.get_pending_by_institution_entity(institution_entity_id, db, scope=scope)
        log_info(f"Retrieved pending payment attempts for institution entity: {institution_entity_id}")
        return payment_attempts
    
    return handle_business_operation(_get_pending_payment_attempts, "pending payment attempts retrieval")

# POST /institution-payment-attempts/ – Create a new payment attempt
@router.post("/", response_model=InstitutionPaymentAttemptResponseSchema, status_code=status.HTTP_201_CREATED)
def create_payment_attempt(
    payment_attempt_create: InstitutionPaymentAttemptCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new payment attempt"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)

    def _create_payment_attempt():
        data = payment_attempt_create.dict()
        _require_entity_access(data["institution_entity_id"], db, scope)
        if data.get("institution_bill_id"):
            _require_bill_access(data["institution_bill_id"], db, scope)
        
        # Resolve currency_code from credit_currency_id using centralized service
        resolve_currency_code(data, db)
        
        # Set resolution_date to current time (required field)
        from datetime import datetime
        data["resolution_date"] = datetime.utcnow()
        
        new_payment_attempt = institution_payment_attempt_service.create(data, db, scope=scope)
        if not new_payment_attempt:
            raise HTTPException(status_code=500, detail="Failed to create payment attempt")
        
        log_info(f"Created payment attempt: {new_payment_attempt.payment_id}")
        return new_payment_attempt
    
    return handle_business_operation(
        _create_payment_attempt,
        "payment attempt creation",
        "Payment attempt created successfully"
    )

# POST /institution-payment-attempts/minimal – Create a payment attempt with minimal fields
@router.post("/minimal", response_model=InstitutionPaymentAttemptResponseSchema, status_code=status.HTTP_201_CREATED)
def create_minimal_payment_attempt(
    payment_attempt_create: InstitutionPaymentAttemptMinimalCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a payment attempt with minimal fields"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)

    def _create_minimal_payment_attempt():
        data = payment_attempt_create.dict()
        _require_entity_access(data["institution_entity_id"], db, scope)
        if data.get("institution_bill_id"):
            _require_bill_access(data["institution_bill_id"], db, scope)
        
        # Set resolution_date to current time (required field)
        from datetime import datetime
        data["resolution_date"] = datetime.utcnow()
        
        new_payment_attempt = institution_payment_attempt_service.create(data, db, scope=scope)
        if not new_payment_attempt:
            raise HTTPException(status_code=500, detail="Failed to create payment attempt")
        
        log_info(f"Created minimal payment attempt: {new_payment_attempt.payment_id}")
        return new_payment_attempt
    
    return handle_business_operation(
        _create_minimal_payment_attempt,
        "minimal payment attempt creation",
        "Minimal payment attempt created successfully"
    )

# PUT /institution-payment-attempts/{payment_id} – Update an existing payment attempt
@router.put("/{payment_id}", response_model=InstitutionPaymentAttemptResponseSchema)
def update_payment_attempt(
    payment_id: UUID,
    payment_attempt_update: InstitutionPaymentAttemptUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update an existing payment attempt"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)
    existing_attempt = _require_payment_attempt(payment_id, db, scope)

    def _update_payment_attempt():
        update_data = payment_attempt_update.dict(exclude_unset=True)
        if "institution_entity_id" in update_data:
            new_entity_id = update_data["institution_entity_id"]
            if new_entity_id != existing_attempt.institution_entity_id:
                _require_entity_access(new_entity_id, db, scope)
        if update_data.get("institution_bill_id"):
            _require_bill_access(update_data["institution_bill_id"], db, scope)

        updated = institution_payment_attempt_service.update(payment_id, update_data, db, scope=scope)
        if not updated:
            raise _payment_attempt_not_found()
        log_info(f"Updated payment attempt {payment_id}")
        return updated

    return handle_business_operation(
        _update_payment_attempt,
        "payment attempt update",
        "Payment attempt updated successfully"
    )

# POST /institution-payment-attempts/{payment_id}/complete – Mark payment attempt as complete
@router.post("/{payment_id}/complete", response_model=InstitutionPaymentAttemptResponseSchema)
def mark_payment_complete(
    payment_id: UUID,
    status_update: InstitutionPaymentAttemptStatusUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Mark a payment attempt as complete with transaction result"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)
    _require_payment_attempt(payment_id, db, scope)

    def _mark_payment_complete():
        success = institution_payment_attempt_service.mark_complete(payment_id, db)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to mark payment attempt as complete")
        
        # Return updated payment attempt
        updated_attempt = _require_payment_attempt(payment_id, db, scope)
        
        log_info(f"Payment attempt {payment_id} marked as complete")
        return updated_attempt
    
    return handle_business_operation(_mark_payment_complete, "payment completion marking")

# POST /institution-payment-attempts/{payment_id}/failed – Mark payment attempt as failed
@router.post("/{payment_id}/failed", response_model=InstitutionPaymentAttemptResponseSchema)
def mark_payment_failed(
    payment_id: UUID,
    status_update: InstitutionPaymentAttemptStatusUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Mark a payment attempt as failed"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)
    _require_payment_attempt(payment_id, db, scope)

    def _mark_payment_failed():
        success = institution_payment_attempt_service.mark_failed(payment_id, db)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to mark payment attempt as failed")
        
        # Return updated payment attempt
        updated_attempt = _require_payment_attempt(payment_id, db, scope)
        
        log_info(f"Payment attempt {payment_id} marked as failed")
        return updated_attempt
    
    return handle_business_operation(_mark_payment_failed, "payment failure marking")

# DELETE /institution-payment-attempts/{payment_id} – Delete (soft-delete) a payment attempt
@router.delete("/{payment_id}", response_model=dict)
def delete_payment_attempt(
    payment_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Delete (soft-delete) a payment attempt"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)
    _require_payment_attempt(payment_id, db, scope)

    def _delete():
        success = institution_payment_attempt_service.soft_delete(payment_id, current_user["user_id"], db, scope=scope)
        if not success:
            raise _payment_attempt_not_found()
        log_info(f"Payment attempt {payment_id} deleted")
        return {"detail": "Payment attempt deleted successfully"}

    return handle_business_operation(_delete, "payment attempt deletion")

# POST /institution-payment-attempts/{payment_id}/undelete – Undelete a soft-deleted payment attempt
@router.post("/{payment_id}/undelete", response_model=InstitutionPaymentAttemptResponseSchema)
def undelete_payment_attempt(
    payment_id: UUID, 
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Undelete a soft-deleted payment attempt"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)
    _require_payment_attempt(payment_id, db, scope)

    def _undelete_payment_attempt():
        success = institution_payment_attempt_service.undelete(payment_id, db)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to undelete payment attempt")
        
        # Return the undeleted payment attempt
        undeleted_attempt = _require_payment_attempt(payment_id, db, scope)
        
        log_info(f"Payment attempt {payment_id} undeleted successfully")
        return undeleted_attempt
    
    return handle_business_operation(_undelete_payment_attempt, "payment attempt undeletion")

# GET /institution-payment-attempts/summary/{institution_entity_id} – Get payment attempt summary
@router.get("/summary/{institution_entity_id}", response_model=List[InstitutionPaymentAttemptSummarySchema])
def get_payment_attempt_summary(
    institution_entity_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a summary of payment attempts for a specific institution entity"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)
    _require_entity_access(institution_entity_id, db, scope)

    def _get_payment_attempt_summary():
        payment_attempts = get_by_institution_entity(institution_entity_id, db, scope=scope)
        log_info(f"Retrieved payment attempt summary for institution entity: {institution_entity_id}")
        return payment_attempts
    
    return handle_business_operation(_get_payment_attempt_summary, "payment attempt summary retrieval")

# GET /institution-payment-attempts/enriched/ – Get all enriched payment attempts
@router.get("/enriched/", response_model=List[InstitutionPaymentAttemptEnrichedResponseSchema])
def get_all_enriched_payment_attempts(
    include_archived: bool = include_archived_query("payment attempts"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all payment attempts with enriched data (institution name, entity name, bank name, country, period start, period end)"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)

    def _get_enriched_payment_attempts():
        payment_attempts = get_enriched_institution_payment_attempts(
            db,
            scope=scope,
            include_archived=include_archived
        )
        log_info("Retrieved enriched payment attempts")
        return payment_attempts
    
    return handle_business_operation(_get_enriched_payment_attempts, "enriched payment attempts retrieval")

# GET /institution-payment-attempts/enriched/{payment_id} – Get single enriched payment attempt
@router.get("/enriched/{payment_id}", response_model=InstitutionPaymentAttemptEnrichedResponseSchema)
def get_enriched_payment_attempt(
    payment_id: UUID,
    include_archived: bool = include_archived_query("payment attempts"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single payment attempt by ID with enriched data (institution name, entity name, bank name, country, period start, period end)"""
    scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_PAYMENT_ATTEMPT, current_user)

    def _get_enriched_payment_attempt():
        payment_attempt = get_enriched_institution_payment_attempt_by_id(
            db,
            payment_id,
            scope=scope,
            include_archived=include_archived
        )
        if not payment_attempt:
            raise _payment_attempt_not_found()
        log_info(f"Retrieved enriched payment attempt: {payment_id}")
        return payment_attempt
    
    return handle_business_operation(_get_enriched_payment_attempt, "enriched payment attempt retrieval") 