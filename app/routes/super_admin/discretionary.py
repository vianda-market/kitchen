"""
Super-Admin Discretionary Credit Routes

Routes for super-administrators to approve/reject discretionary credit requests.
"""

from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import List
import psycopg2.extensions

from app.dto.models import DiscretionaryDTO, DiscretionaryResolutionDTO
from app.schemas.consolidated_schemas import (
    DiscretionaryResponseSchema,
    DiscretionaryResolutionResponseSchema,
    DiscretionaryApprovalSchema,
    DiscretionaryRejectionSchema,
    DiscretionarySummarySchema
)
from app.services.discretionary_service import DiscretionaryService
from app.auth.dependencies import get_super_admin_user, get_admin_user
from app.dependencies.database import get_db
from app.services.error_handling import handle_business_operation
from app.utils.log import log_info

router = APIRouter(
    prefix="/super-admin/discretionary",
    tags=["Super-Admin Discretionary Credits"]
)

discretionary_service = DiscretionaryService()


@router.get("/requests/{request_id}", response_model=DiscretionaryResponseSchema)
def get_discretionary_request_details(
    request_id: UUID,
    current_user: dict = Depends(get_admin_user),  # Admin and Super Admin can view
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get detailed information about a specific discretionary request.
    
    Admin and Super Admin employees can view any request for approval/rejection decisions.
    """
    log_info(f"Admin {current_user['user_id']} retrieving discretionary request {request_id}")
    
    # Delegate to service layer
    from app.services.crud_service import discretionary_service as crud_service
    request = crud_service.get_by_id(request_id, db)
    
    if not request:
        raise HTTPException(status_code=404, detail="Discretionary request not found")
    
    return request


@router.post("/requests/{request_id}/approve", response_model=DiscretionaryResolutionResponseSchema)
def approve_discretionary_request(
    request_id: UUID,
    approval: DiscretionaryApprovalSchema,
    current_user: dict = Depends(get_super_admin_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Approve a discretionary request and load credits.
    
    Super-admin approves the request, which:
    1. Creates a resolution record
    2. Updates request status to 'Approved'
    3. Creates appropriate transaction (client or restaurant)
    4. Updates balances automatically via existing services
    """
    log_info(f"Super-admin {current_user['user_id']} approving discretionary request {request_id}")
    
    # Delegate to service layer
    resolution = discretionary_service.approve_discretionary_request(
        request_id, current_user, db
    )
    
    return resolution


@router.post("/requests/{request_id}/reject", response_model=DiscretionaryResolutionResponseSchema)
def reject_discretionary_request(
    request_id: UUID,
    rejection: DiscretionaryRejectionSchema,
    current_user: dict = Depends(get_super_admin_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Reject a discretionary request.
    
    Super-admin rejects the request, which:
    1. Creates a resolution record with rejection reason
    2. Updates request status to 'Rejected'
    3. No credits are loaded
    """
    log_info(f"Super-admin {current_user['user_id']} rejecting discretionary request {request_id}")
    
    # Delegate to service layer
    resolution = discretionary_service.reject_discretionary_request(
        request_id, current_user, rejection.resolution_comment, db
    )
    
    return resolution


@router.get("/pending-requests/", response_model=List[DiscretionarySummarySchema])
def get_pending_discretionary_requests(
    current_user: dict = Depends(get_admin_user),  # Admin and Super Admin can view
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get all pending discretionary requests for super-admin dashboard.
    
    Returns all requests with status 'Pending' for approval/rejection.
    Available to Admin and Super Admin employees (role_type='Employee' AND role_name IN ('Admin', 'Super Admin')).
    """
    log_info(f"Super-admin {current_user['user_id']} retrieving pending discretionary requests")
    
    # Delegate to service layer
    pending_requests = discretionary_service.get_pending_requests(db)
    
    # Convert to summary format for dashboard
    summary_requests = []
    for request in pending_requests:
        summary_requests.append(DiscretionarySummarySchema(
            discretionary_id=request.discretionary_id,
            user_id=request.user_id,
            restaurant_id=request.restaurant_id,
            category=request.category,
            reason=request.reason,
            amount=request.amount,
            status=request.status,
            created_date=request.created_date,
            resolved_date=None,
            resolved_by=None,
            resolution_comment=None
        ))
    
    # Sort by creation date (newest first)
    summary_requests.sort(key=lambda x: x.created_date, reverse=True)
    
    return summary_requests


@router.get("/requests/", response_model=List[DiscretionarySummarySchema])
def get_all_discretionary_requests(
    current_user: dict = Depends(get_admin_user),  # Admin and Super Admin can view
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get all discretionary requests for admin overview.
    
    Returns all requests regardless of status for comprehensive view.
    Available to Admin and Super Admin employees.
    """
    log_info(f"Admin {current_user['user_id']} retrieving all discretionary requests")
    
    # Delegate to service layer
    from app.services.crud_service import discretionary_service as crud_service
    all_requests = crud_service.get_all(db)
    
    # Convert to summary format
    summary_requests = []
    for request in all_requests:
        # Get resolution details if exists
        resolved_date = None
        resolved_by = None
        resolution_comment = None
        
        if request.approval_id:
            from app.services.crud_service import discretionary_resolution_service
            resolution = discretionary_resolution_service.get_by_id(request.approval_id, db)
            if resolution:
                resolved_date = resolution.resolved_date
                resolved_by = resolution.resolved_by
                resolution_comment = resolution.resolution_comment
        
        summary_requests.append(DiscretionarySummarySchema(
            discretionary_id=request.discretionary_id,
            user_id=request.user_id,
            restaurant_id=request.restaurant_id,
            category=request.category,
            reason=request.reason,
            amount=request.amount,
            status=request.status,
            created_date=request.created_date,
            resolved_date=resolved_date,
            resolved_by=resolved_by,
            resolution_comment=resolution_comment
        ))
    
    # Sort by creation date (newest first)
    summary_requests.sort(key=lambda x: x.created_date, reverse=True)
    
    return summary_requests
