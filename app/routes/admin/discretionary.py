"""
Admin Discretionary Credit Routes

Routes for kitchen administrators to create and manage discretionary credit requests.
"""

from typing import Any
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends

from app.auth.dependencies import get_admin_user, get_employee_user, get_resolved_locale
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    DiscretionaryCreateSchema,
    DiscretionaryResponseSchema,
    DiscretionarySummarySchema,
    DiscretionaryUpdateSchema,
)
from app.services.discretionary_service import DiscretionaryService
from app.utils.log import log_info

router = APIRouter(prefix="/admin/discretionary", tags=["Admin Discretionary Credits"])

discretionary_service = DiscretionaryService()


@router.post("/requests", response_model=DiscretionaryResponseSchema)
def create_discretionary_request(
    request: DiscretionaryCreateSchema,
    current_user: dict[str, Any] = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> Any:
    """
    Create a discretionary credit request.

    Admin users can create requests for client or restaurant credits.
    Requests will be pending until approved by a super-admin.
    """
    log_info(f"Admin {current_user['user_id']} creating discretionary request for user {request.user_id}")

    # Convert Pydantic model to dict for service layer
    request_data = request.model_dump()

    # Delegate to service layer
    discretionary_request = discretionary_service.create_discretionary_request(request_data, current_user, db, locale)

    return discretionary_request


@router.get("/requests", response_model=list[DiscretionaryResponseSchema])
def get_discretionary_requests(
    current_user: dict[str, Any] = Depends(get_employee_user), db: psycopg2.extensions.connection = Depends(get_db)
) -> Any:
    """
    Get all discretionary requests created by the current admin.

    Returns requests created by the authenticated admin user.
    """
    log_info(f"Admin {current_user['user_id']} retrieving their discretionary requests")

    # Delegate to service layer
    requests = discretionary_service.get_requests_by_admin(current_user["user_id"], db)

    return requests


@router.get("/requests/{request_id}", response_model=DiscretionaryResponseSchema)
def get_discretionary_request(
    request_id: UUID,
    current_user: dict[str, Any] = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> Any:
    """
    Get a specific discretionary request by ID.

    Admin users can only view requests they created.
    """
    log_info(f"Admin {current_user['user_id']} retrieving discretionary request {request_id}")

    # Get all admin's requests and filter by ID
    admin_requests = discretionary_service.get_requests_by_admin(current_user["user_id"], db)
    request = next((req for req in admin_requests if req.discretionary_id == request_id), None)

    if not request:
        raise envelope_exception(ErrorCode.DISCRETIONARY_NOT_FOUND, status=404, locale=locale)

    return request


@router.put("/requests/{request_id}", response_model=DiscretionaryResponseSchema)
def update_discretionary_request(
    request_id: UUID,
    request_update: DiscretionaryUpdateSchema,
    current_user: dict[str, Any] = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> Any:
    """
    Update a discretionary request (only if still pending).

    Admin users can only update their own pending requests.
    """
    log_info(f"Admin {current_user['user_id']} updating discretionary request {request_id}")

    # Get the request to verify ownership and status
    admin_requests = discretionary_service.get_requests_by_admin(current_user["user_id"], db)
    request = next((req for req in admin_requests if req.discretionary_id == request_id), None)

    if not request:
        raise envelope_exception(ErrorCode.DISCRETIONARY_NOT_FOUND, status=404, locale=locale)

    if request.status != "pending":
        request_status = request.status.value if hasattr(request.status, "value") else str(request.status)
        raise envelope_exception(
            ErrorCode.DISCRETIONARY_NOT_PENDING, status=400, locale=locale, request_status=request_status
        )

    # Convert Pydantic model to dict for service layer
    update_data = request_update.model_dump(exclude_unset=True)

    # Delegate to service layer
    from app.services.crud_service import discretionary_service as crud_service

    updated_request = crud_service.update(request_id, update_data, db)

    return updated_request


@router.get("/pending-requests", response_model=list[DiscretionarySummarySchema])
def get_pending_discretionary_requests(
    current_user: dict[str, Any] = Depends(get_admin_user),  # Admin and Super Admin can view
    db: psycopg2.extensions.connection = Depends(get_db),
) -> list[DiscretionarySummarySchema]:  # explicitly constructs DiscretionarySummarySchema below
    """
    Get all pending discretionary requests for admin dashboard.

    Returns all requests with status 'pending' for approval/rejection.
    Available to Admin and Super Admin Internal users (role_type='internal' AND role_name IN ('admin', 'super_admin')).
    Admin users can see pending requests to verify their submitted requests have been recorded.
    """
    log_info(f"Admin {current_user['user_id']} retrieving pending discretionary requests")

    # Delegate to service layer
    pending_requests = discretionary_service.get_pending_requests(db)

    # Convert to summary format for dashboard
    summary_requests = []
    for request in pending_requests:
        summary_requests.append(
            DiscretionarySummarySchema(
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
                resolution_comment=None,
            )
        )

    return summary_requests
