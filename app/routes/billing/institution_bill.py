# app/routes/billing/institution_bill.py
from typing import List, Optional
from uuid import UUID
from datetime import date, datetime
from fastapi import APIRouter, HTTPException, Depends
from app.dto.models import InstitutionBillDTO
from app.services.crud_service import institution_bill_service, get_bills_by_restaurant_and_period
from app.services.entity_service import get_pending_bills_by_institution, get_bills_by_status, get_enriched_institution_bills
from app.config.enums import BillResolution
from app.schemas.billing.institution_bill import (
    InstitutionBillUpdateSchema, 
    InstitutionBillResponseSchema,
)
from app.schemas.consolidated_schemas import InstitutionBillEnrichedResponseSchema
from app.security.entity_scoping import EntityScopingService, ENTITY_INSTITUTION_BILL
from fastapi import Query
from app.services.billing.institution_billing import InstitutionBillingService
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning, log_error
from app.services.error_handling import handle_business_operation, handle_get_by_id, handle_get_all, handle_update, handle_delete
import psycopg2.extensions

router = APIRouter(prefix="/institution-bills", tags=["Institution Bills"])

@router.get("", response_model=List[InstitutionBillResponseSchema])
def get_institution_bills(
    institution_id: Optional[UUID] = None,
    restaurant_id: Optional[UUID] = None,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get institution bills with optional filtering by status and date range
    
    Examples:
    - GET /institution-bills/?institution_id=123&status=Pending (all pending bills)
    - GET /institution-bills/?institution_id=123&status=Paid (all paid bills)
    - GET /institution-bills/?institution_id=123 (all bills)
    - GET /institution-bills/?institution_id=123&status=Pending&start_date=2025-09-01&end_date=2025-09-30
    """
    """Get institution bills with optional filtering"""
    def _get_institution_bills():
        if institution_id:
            # Use the business logic service method with status and date filtering
            if status:
                bills = get_bills_by_status(institution_id, status, db)
            else:
                bills = get_pending_bills_by_institution(institution_id, db)
        elif restaurant_id:
            # Get bills for specific restaurant (via institution_settlement; bills no longer have restaurant_id)
            if not start_date or not end_date:
                raise HTTPException(status_code=400, detail="start_date and end_date required for restaurant filter")
            
            period_start = datetime.combine(start_date, datetime.min.time())
            period_end = datetime.combine(end_date, datetime.max.time())
            
            bills = get_bills_by_restaurant_and_period(restaurant_id, period_start, period_end, db)
        else:
            # Get all pending bills across all institutions (default behavior when no institution_id)
            bills = InstitutionBillingService.get_pending_bills(connection=db)
        
        return bills
    
    return handle_business_operation(_get_institution_bills, "institution bills retrieval")

@router.get("/enriched", response_model=List[InstitutionBillEnrichedResponseSchema])
def get_enriched_institution_bills_endpoint(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all institution bills with enriched data (institution name, entity name, restaurant name).
    Returns an array of enriched institution bill records. Non-archived only.

    Scoping:
    - Employees: See all institution bills
    - Suppliers: See bills for restaurants in their institution
    - Customers: See bills for restaurants in their institution (if applicable)"""
    
    def _get_enriched_bills():
        scope = EntityScopingService.get_scope_for_entity(ENTITY_INSTITUTION_BILL, current_user)
        return get_enriched_institution_bills(
            db,
            scope=scope,
            include_archived=False
        )
    
    return handle_business_operation(_get_enriched_bills, "enriched institution bills retrieval")

@router.get("/{bill_id}", response_model=InstitutionBillResponseSchema)
def get_institution_bill(
    bill_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a specific institution bill by ID"""
    return handle_get_by_id(
        institution_bill_service.get_by_id,
        bill_id,
        db,
        "institution bill"
    )

@router.put("/{bill_id}", response_model=InstitutionBillResponseSchema)
def update_institution_bill(
    bill_id: UUID,
    payload: InstitutionBillUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update an institution bill"""
    def _update_institution_bill():
        # Prepare update data (institution_bill_info has no payment_id; payments are via pipeline)
        update_data = {}
        if payload.transaction_count is not None:
            update_data["transaction_count"] = payload.transaction_count
        if payload.amount is not None:
            update_data["amount"] = payload.amount
        if payload.status is not None:
            update_data["status"] = payload.status
        if payload.resolution is not None:
            update_data["resolution"] = payload.resolution.value if hasattr(payload.resolution, 'value') else payload.resolution
        
        update_data["modified_by"] = current_user["user_id"]
        update_data["modified_date"] = datetime.now()
        
        success = institution_bill_service.update(bill_id, update_data, db)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update institution bill")
        
        # Return updated bill
        updated_bill = institution_bill_service.get_by_id(bill_id, db)
        if not updated_bill:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated bill")
        
        log_info(f"Institution bill updated: {bill_id}")
        return updated_bill
    
    return handle_business_operation(
        _update_institution_bill,
        "institution bill update",
        "Institution bill updated successfully"
    )

@router.post("/{bill_id}/cancel")
def cancel_bill(
    bill_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Cancel a bill (MVP - administrative corrections)"""
    def _cancel_bill():
        result = InstitutionBillingService.cancel_bill(
            bill_id=bill_id,
            user_id=current_user["user_id"],
            connection=db
        )
        
        log_info(f"Cancelled bill {bill_id}")
        return result
    
    return handle_business_operation(_cancel_bill, "bill cancellation")

@router.post("/generate-daily-bills")
def generate_daily_bills(
    bill_date: Optional[date] = Query(None, description="Bill date (default: today)"),
    country_code: Optional[str] = Query(None, description="Country code (e.g. US); auto-detected if omitted"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Run the settlement → bill → payout pipeline for a date. All bill creation goes through this pipeline."""
    from datetime import timezone
    if bill_date is None:
        bill_date = datetime.now(timezone.utc).date()
    log_info(f"Generate daily bills (pipeline) for {bill_date} (country_code={country_code})")

    def _run():
        result = InstitutionBillingService.run_daily_settlement_bill_and_payout(
            bill_date=bill_date,
            system_user_id=current_user["user_id"],
            country_code=country_code,
            connection=db,
        )
        log_info(f"Daily bill pipeline completed for {bill_date}: {result}")
        return {
            "message": "Daily bills (settlement pipeline) completed",
            "date": bill_date.isoformat(),
            "country_code": country_code,
            "statistics": {
                "settlements_created": result.get("settlements_created", 0),
                "bills_created": result.get("bills_created", 0),
                "bills_paid": result.get("bills_paid", 0),
                "total_amount": result.get("total_amount", 0.0),
                "restaurants_processed": result.get("settlements_created", 0),
            },
        }
    return handle_business_operation(_run, "daily bill generation")


@router.post("/run-settlement-pipeline")
def run_settlement_pipeline(
    bill_date: Optional[date] = Query(None, description="Bill date (default: today)"),
    country_code: Optional[str] = Query(None, description="Country code (e.g. US); auto-detected if omitted"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Run the atomic settlement → bill → payout pipeline for a given date.
    This is the intended supplier payment flow: Phase 1 settlements (one per restaurant with balance),
    Phase 2 one bill per entity, then tax doc stub, payout (mock/live), mark_paid.
    Normally triggered by cron; this endpoint allows manual/test runs.
    """
    from datetime import timezone
    if bill_date is None:
        bill_date = datetime.now(timezone.utc).date()
    log_info(f"Running settlement pipeline for {bill_date} (country_code={country_code})")

    def _run():
        result = InstitutionBillingService.run_daily_settlement_bill_and_payout(
            bill_date=bill_date,
            system_user_id=current_user["user_id"],
            country_code=country_code,
            connection=db,
        )
        return {
            "message": "Settlement pipeline completed",
            "bill_date": bill_date.isoformat(),
            "country_code": country_code,
            **result,
        }

    return handle_business_operation(_run, "settlement pipeline")

@router.get("/summary/{institution_id}")
def get_billing_summary(
    institution_id: UUID,
    start_date: date,
    end_date: date,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get billing summary for an institution"""
    def _get_billing_summary():
        summary = InstitutionBillingService.get_bill_summary_by_institution(institution_id, start_date, end_date, connection=db)
        
        if not summary:
            raise HTTPException(status_code=404, detail="No billing data found for institution")
        
        return summary
    
    return handle_business_operation(_get_billing_summary, "billing summary retrieval")

# DELETE /institution-bills/{bill_id} – Delete (soft-delete) an institution bill
@router.delete("/{bill_id}", response_model=dict)
def delete_institution_bill(
    bill_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Delete an institution bill"""
    handle_delete(institution_bill_service.soft_delete, bill_id, db, "institution bill")
    return {"detail": "Institution bill deleted successfully"} 