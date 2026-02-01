# app/routes/fintech_link_routes.py
from fastapi import APIRouter, HTTPException, Depends
from app.auth.dependencies import oauth2_scheme, get_current_user, get_employee_user, get_client_or_employee_user
from app.dependencies.database import get_db
from uuid import UUID
from typing import List, Optional
from app.dto.models import FintechLinkDTO
from app.services.crud_service import fintech_link_service
from app.services.error_handling import handle_business_operation, handle_delete, handle_update
from app.schemas.payment_methods.fintech_link import FintechLinkCreateSchema, FintechLinkUpdateSchema, FintechLinkEnrichedResponseSchema
from app.services.entity_service import get_enriched_fintech_links, get_enriched_fintech_link_by_id
from app.utils.query_params import include_archived_optional_query, include_archived_query
from app.utils.error_messages import entity_not_found
from app.utils.log import log_info, log_warning, log_error
import psycopg2.extensions

router = APIRouter(
    prefix="/fintech-links",
    tags=["Fintech Links"],
    dependencies=[Depends(oauth2_scheme)]
)

@router.post("/", response_model=FintechLinkDTO)
def create_fintech_link(
    payload: FintechLinkCreateSchema, 
    current_user: dict = Depends(get_employee_user),  # Employee-only
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new fintech link - Employee-only"""
    def _create_fintech_link():
        data = payload.dict()
        data["status"] = "Active"
        data["modified_by"] = current_user["user_id"]
        log_info(f"DEBUG: Inserting fintech link info with data: {data}")
        fintech_link = fintech_link_service.create(data, db)
        return fintech_link
    
    return handle_business_operation(
        _create_fintech_link,
        "fintech link creation",
        "Fintech link created successfully"
    )


@router.get("/", response_model=list[FintechLinkDTO])
def get_all_fintech_link(
    current_user: dict = Depends(get_client_or_employee_user),  # Customers and Employees
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all fintech links - Available to Customers and Employees"""
    links = fintech_link_service.get_all_non_archived(db)
    return links


@router.get("/{fintech_link_id}", response_model=FintechLinkDTO)
def get_fintech_link_by_id(
    fintech_link_id: UUID,
    current_user: dict = Depends(get_client_or_employee_user),  # Customers and Employees
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single fintech link by ID - Available to Customers and Employees"""
    link = fintech_link_service.get_by_id(fintech_link_id, db)
    return link

@router.get("/by_plan/{plan_id}", response_model=list[FintechLinkDTO])
def get_fintech_link_by_plan_id(
    plan_id: UUID,
    current_user: dict = Depends(get_client_or_employee_user),  # Customers and Employees
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get fintech links by plan ID - Available to Customers and Employees"""
    links = fintech_link_service.get_all_non_archived(db)
    filtered_links = [link for link in links if link.plan_id == plan_id]
    return filtered_links

# PUT /fintech-links/{fintech_link_id} – Update a fintech link
@router.put("/{fintech_link_id}", response_model=FintechLinkDTO)
def update_fintech_link(
    fintech_link_id: UUID,
    payload: FintechLinkUpdateSchema,
    current_user: dict = Depends(get_employee_user),  # Employee-only
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update a fintech link - Employee-only"""
    data = payload.dict(exclude_unset=True)
    data["modified_by"] = current_user["user_id"]
    
    return handle_update(
        fintech_link_service.update,
        fintech_link_id,
        data,
        db,
        "fintech link"
    )

# DELETE /fintech-links/{fintech_link_id} – Delete (soft-delete) a fintech link
@router.delete("/{fintech_link_id}", response_model=dict)
def delete_fintech_link(
    fintech_link_id: UUID,
    current_user: dict = Depends(get_employee_user),  # Employee-only
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Delete a fintech link - Employee-only"""
    handle_delete(fintech_link_service.soft_delete, fintech_link_id, db, "fintech link")
    return {"detail": "Fintech link deleted successfully"}

# =============================================================================
# ENRICHED FINTECH LINK ENDPOINTS (with plan_name, plan_price, plan_credit, plan_status, currency_code)
# =============================================================================

@router.get("/enriched/", response_model=List[FintechLinkEnrichedResponseSchema])
def list_enriched_fintech_links(
    include_archived: Optional[bool] = include_archived_optional_query("fintech links"),
    current_user: dict = Depends(get_client_or_employee_user),  # Customers and Employees
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    List all fintech links with enriched data.
    
    Access Control:
    - Employees: Full access (can see all fintech links)
    - Customers: Read-only access (can see all fintech links for payment selection)
    - Suppliers: Blocked (403 Forbidden)
    
    Includes: plan_name, plan_price, plan_credit, plan_status, currency_code.
    """
    try:
        enriched_fintech_links = get_enriched_fintech_links(
            db,
            include_archived=include_archived or False
        )
        return enriched_fintech_links
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched fintech links: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve enriched fintech links")

@router.get("/enriched/{fintech_link_id}", response_model=FintechLinkEnrichedResponseSchema)
def get_enriched_fintech_link_by_id_route(
    fintech_link_id: UUID,
    include_archived: bool = include_archived_query("fintech links"),
    current_user: dict = Depends(get_client_or_employee_user),  # Customers and Employees
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get a single fintech link by ID with enriched data.
    
    Access Control:
    - Employees: Full access (can see any fintech link)
    - Customers: Read-only access (can see any fintech link for payment selection)
    - Suppliers: Blocked (403 Forbidden)
    
    Includes: plan_name, plan_price, plan_credit, plan_status, currency_code.
    """
    try:
        enriched_fintech_link = get_enriched_fintech_link_by_id(
            fintech_link_id,
            db,
            include_archived=include_archived
        )
        if not enriched_fintech_link:
            raise entity_not_found("Fintech link", fintech_link_id)
        return enriched_fintech_link
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched fintech link {fintech_link_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve enriched fintech link")
