# app/routes/payment_methods/fintech_link_assignment.py
from fastapi import APIRouter, HTTPException, Depends, Query
from app.auth.dependencies import get_current_user, get_employee_or_customer_user
from app.dependencies.database import get_db
from app.utils.query_params import include_archived_optional_query
from uuid import UUID
from typing import Optional, List
from app.dto.models import FintechLinkAssignmentDTO
from app.services.crud_service import fintech_link_assignment_service
from app.services.error_handling import handle_business_operation, handle_delete
from app.services.entity_service import (
    get_enriched_fintech_link_assignments,
    get_enriched_fintech_link_assignment_by_id
)
from app.schemas.payment_methods.fintech_link_assignment import (
    FintechLinkAssignmentCreateSchema,
    FintechLinkAssignmentResponseSchema,
    FintechLinkAssignmentEnrichedResponseSchema
)
from app.security.scoping import get_user_scope, UserScope
import psycopg2.extensions

router = APIRouter(
    prefix="/fintech-link-assignment",
    tags=["Fintech Link Assignment"]
)

# =============================================================================
# BASE ENDPOINTS
# =============================================================================

@router.post("/", response_model=FintechLinkAssignmentDTO, status_code=201)
def create_fintech_link_assignment(
    payload: FintechLinkAssignmentCreateSchema,
    current_user: dict = Depends(get_employee_or_customer_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Create a new fintech link assignment.
    
    Request Body:
    - payment_method_id (UUID, required): The payment method ID
    - fintech_link_id (UUID, required): The fintech link ID
    
    Access Control:
    - Employees: Can create assignments for any user
    - Customers: Can create assignments for themselves only (via payment_method.user_id)
    """
    def _create_fintech_link_assignment():
        data = payload.dict()
        data["status"] = "Active"
        
        # For customers, verify payment_method belongs to them
        user_scope = get_user_scope(current_user)
        if user_scope.is_customer:
            # Verify payment_method ownership
            from app.services.crud_service import payment_method_service
            from app.security.scoping import _normalize
            payment_method = payment_method_service.get_by_id(payload.payment_method_id, db)
            if not payment_method:
                raise HTTPException(status_code=404, detail="Payment method not found")
            # Normalize both user_ids to strings for comparison (UserScope.user_id is normalized to string)
            if _normalize(payment_method.user_id) != user_scope.user_id:
                raise HTTPException(status_code=403, detail="Forbidden: Cannot create assignment for another user's payment method")
        
        fintech_link_assignment = fintech_link_assignment_service.create(data, db)
        
        # Link payment_method to fintech_link and activate it
        from app.services.payment_method_service import link_payment_method_to_type
        try:
            link_payment_method_to_type(
                payment_method_id=payload.payment_method_id,
                method_type="Fintech Link",
                type_id=payload.fintech_link_id,
                current_user_id=user_scope.user_id,
                db=db
            )
        except (ValueError, Exception) as e:
            # Log but don't fail transaction creation
            from app.utils.log import log_warning
            log_warning(f"Failed to link payment method to fintech link: {e}")
        
        return fintech_link_assignment
    
    return handle_business_operation(
        _create_fintech_link_assignment,
        "fintech link assignment creation",
        "Fintech link assignment created successfully"
    )

@router.get("/", response_model=List[FintechLinkAssignmentResponseSchema])
def list_fintech_link_assignments(
    include_archived: bool = Query(False, description="Include archived records"),
    current_user: dict = Depends(get_employee_or_customer_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    List all fintech link assignments.
    
    Access Control:
    - Employees: See all assignments
    - Customers: See only their own assignments (via payment_method.user_id)
    """
    user_scope = get_user_scope(current_user)
    
    if user_scope.is_customer:
        # For customers, filter by their user_id through payment_method
        from app.services.entity_service import get_enriched_fintech_link_assignments
        assignments = get_enriched_fintech_link_assignments(
            db,
            user_id=UUID(user_scope.user_id),
            include_archived=include_archived
        )
        # Convert enriched to base response schema
        return [
            FintechLinkAssignmentResponseSchema(
                fintech_link_assignment_id=a.fintech_link_assignment_id,
                payment_method_id=a.payment_method_id,
                fintech_link_id=a.fintech_link_id,
                is_archived=a.is_archived,
                status=a.status,
                created_date=a.created_date
            )
            for a in assignments
        ]
    else:
        # For employees, get all assignments
        return fintech_link_assignment_service.get_all(
            db,
            include_archived=include_archived
        )


@router.get("/{fintech_link_assignment_id}", response_model=FintechLinkAssignmentResponseSchema)
def get_fintech_link_assignment_by_id(
    fintech_link_assignment_id: UUID,
    include_archived: bool = Query(False, description="Include archived records"),
    current_user: dict = Depends(get_employee_or_customer_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get a single fintech link assignment by ID.
    
    Access Control:
    - Employees: Can access any assignment
    - Customers: Can only access their own assignments (via payment_method.user_id)
    """
    user_scope = get_user_scope(current_user)
    
    assignment = fintech_link_assignment_service.get_by_id(
        fintech_link_assignment_id,
        db,
        include_archived=include_archived
    )
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Fintech link assignment not found")
    
    # For customers, verify ownership through payment_method
    if user_scope.is_customer:
        from app.services.crud_service import payment_method_service
        from app.security.scoping import _normalize
        payment_method = payment_method_service.get_by_id(assignment.payment_method_id, db)
        if not payment_method:
            raise HTTPException(status_code=404, detail="Payment method not found")
        if _normalize(payment_method.user_id) != user_scope.user_id:
            raise HTTPException(status_code=403, detail="Forbidden: Cannot access another user's assignment")
    
    return assignment

@router.delete("/{fintech_link_assignment_id}", response_model=dict)
def delete_fintech_link_assignment(
    fintech_link_assignment_id: UUID,
    current_user: dict = Depends(get_employee_or_customer_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Delete (soft-delete) a fintech link assignment.
    
    Access Control:
    - Employees: Can delete any assignment
    - Customers: Can only delete their own assignments (via payment_method.user_id)
    """
    user_scope = get_user_scope(current_user)
    
    # For customers, verify ownership before deletion
    if user_scope.is_customer:
        assignment = fintech_link_assignment_service.get_by_id(fintech_link_assignment_id, db)
        if not assignment:
            raise HTTPException(status_code=404, detail="Fintech link assignment not found")
        
        from app.services.crud_service import payment_method_service
        from app.security.scoping import _normalize
        payment_method = payment_method_service.get_by_id(assignment.payment_method_id, db)
        if not payment_method:
            raise HTTPException(status_code=404, detail="Payment method not found")
        if _normalize(payment_method.user_id) != user_scope.user_id:
            raise HTTPException(status_code=403, detail="Forbidden: Cannot delete another user's assignment")
    
    handle_delete(
        fintech_link_assignment_service.soft_delete,
        fintech_link_assignment_id,
        db,
        "fintech link assignment"
    )
    return {"detail": "Fintech link assignment deleted successfully"}

# =============================================================================
# ENRICHED ENDPOINTS
# =============================================================================

@router.get("/enriched/", response_model=List[FintechLinkAssignmentEnrichedResponseSchema])
def list_enriched_fintech_link_assignments(
    include_archived: bool = Query(False, description="Include archived records"),
    current_user: dict = Depends(get_employee_or_customer_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    List all fintech link assignments with enriched data.
    
    Enriched fields include:
    - provider (from fintech_link_info)
    - plan_name, credit, price (from plan_info)
    - full_name, username, email, cellphone (from user_info via payment_method)
    
    Access Control:
    - Employees: See all assignments
    - Customers: See only their own assignments (via payment_method.user_id)
    """
    user_scope = get_user_scope(current_user)
    
    if user_scope.is_customer:
        # For customers, filter by their user_id
        assignments = get_enriched_fintech_link_assignments(
            db,
            user_id=UUID(user_scope.user_id),
            include_archived=include_archived
        )
    else:
        # For employees, get all assignments
        assignments = get_enriched_fintech_link_assignments(
            db,
            user_id=None,
            include_archived=include_archived
        )
    
    return assignments


@router.get("/enriched/{fintech_link_assignment_id}", response_model=FintechLinkAssignmentEnrichedResponseSchema)
def get_enriched_fintech_link_assignment_by_id(
    fintech_link_assignment_id: UUID,
    include_archived: bool = Query(False, description="Include archived records"),
    current_user: dict = Depends(get_employee_or_customer_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get a single fintech link assignment by ID with enriched data.
    
    Enriched fields include:
    - provider (from fintech_link_info)
    - plan_name, credit, price (from plan_info)
    - full_name, username, email, cellphone (from user_info via payment_method)
    
    Access Control:
    - Employees: Can access any assignment
    - Customers: Can only access their own assignments (via payment_method.user_id)
    """
    user_scope = get_user_scope(current_user)
    
    if user_scope.is_customer:
        # For customers, filter by their user_id and verify ownership
        assignment = get_enriched_fintech_link_assignment_by_id(
            fintech_link_assignment_id,
            db,
            user_id=UUID(user_scope.user_id),
            include_archived=include_archived
        )
    else:
        # For employees, get any assignment
        assignment = get_enriched_fintech_link_assignment_by_id(
            fintech_link_assignment_id,
            db,
            user_id=None,
            include_archived=include_archived
        )
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Fintech link assignment not found")
    
    return assignment

