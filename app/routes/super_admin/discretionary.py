"""
Super-Admin Discretionary Credit Routes

Routes for super-administrators to approve/reject discretionary credit requests.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from uuid import UUID
from typing import List, Optional
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
from app.services.entity_service import get_enriched_discretionary_requests
from app.auth.dependencies import get_super_admin_user, get_admin_user
from app.dependencies.database import get_db
from app.services.error_handling import handle_business_operation
from app.utils.log import log_info
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers
from app.config import Status

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
    2. Updates request status to 'approved'
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
    2. Updates request status to 'rejected'
    3. No credits are loaded
    """
    log_info(f"Super-admin {current_user['user_id']} rejecting discretionary request {request_id}")
    
    # Delegate to service layer
    resolution = discretionary_service.reject_discretionary_request(
        request_id, current_user, rejection.resolution_comment, db
    )
    
    return resolution


@router.get("/pending-requests", response_model=List[DiscretionarySummarySchema])
def get_pending_discretionary_requests(
    current_user: dict = Depends(get_admin_user),  # Admin and Super Admin can view
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get all pending discretionary requests for super-admin dashboard.

    Returns enriched summary with created_by, created_by_name, and recipient (user_full_name, user_username, restaurant_name).
    Available to Admin and Super Admin employees.
    """
    log_info(f"Super-admin {current_user['user_id']} retrieving pending discretionary requests")
    all_enriched = get_enriched_discretionary_requests(db, include_archived=False)
    pending = [r for r in all_enriched if (getattr(r.status, "value", r.status) or "") == "pending"]
    summary_requests = [
        DiscretionarySummarySchema(
            discretionary_id=r.discretionary_id,
            user_id=r.user_id,
            restaurant_id=r.restaurant_id,
            category=r.category,
            reason=r.reason,
            amount=r.amount,
            status=r.status,
            created_date=r.created_date,
            resolved_date=None,
            resolved_by=None,
            resolution_comment=None,
            created_by=r.created_by,
            created_by_name=r.created_by_name,
            user_full_name=r.user_full_name,
            user_username=r.user_username,
            restaurant_name=r.restaurant_name,
        )
        for r in pending
    ]
    summary_requests.sort(key=lambda x: x.created_date, reverse=True)
    return summary_requests


@router.get("/requests", response_model=List[DiscretionarySummarySchema])
def get_all_discretionary_requests(
    response: Response,
    pagination: Optional[PaginationParams] = Depends(get_pagination_params),
    current_user: dict = Depends(get_admin_user),  # Admin and Super Admin can view
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get all discretionary requests for admin overview.

    Returns enriched summary with created_by, created_by_name, recipient, and resolution details.
    Available to Admin and Super Admin employees.
    """
    log_info(f"Admin {current_user['user_id']} retrieving all discretionary requests")
    all_enriched = get_enriched_discretionary_requests(
        db, include_archived=False,
        page=pagination.page if pagination else None,
        page_size=pagination.page_size if pagination else None,
    )
    from app.services.crud_service import discretionary_resolution_service
    summary_requests = []
    for r in all_enriched:
        resolved_date = None
        resolved_by = None
        resolution_comment = None
        if r.approval_id:
            resolution = discretionary_resolution_service.get_by_id(r.approval_id, db)
            if resolution:
                resolved_date = getattr(resolution, "resolved_date", None)
                resolved_by = getattr(resolution, "resolved_by", None)
                resolution_comment = getattr(resolution, "resolution_comment", None)
        summary_requests.append(DiscretionarySummarySchema(
            discretionary_id=r.discretionary_id,
            user_id=r.user_id,
            restaurant_id=r.restaurant_id,
            category=r.category,
            reason=r.reason,
            amount=r.amount,
            status=r.status,
            created_date=r.created_date,
            resolved_date=resolved_date,
            resolved_by=resolved_by,
            resolution_comment=resolution_comment,
            created_by=r.created_by,
            created_by_name=r.created_by_name,
            user_full_name=r.user_full_name,
            user_username=r.user_username,
            restaurant_name=r.restaurant_name,
        ))
    summary_requests.sort(key=lambda x: x.created_date, reverse=True)
    set_pagination_headers(response, all_enriched)
    return summary_requests
