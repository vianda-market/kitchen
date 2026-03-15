from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID
from app.dto.models import ClientBillDTO
from app.services.crud_service import client_bill_service
from app.services.credit_currency_service import resolve_currency_code
from app.services.error_handling import handle_business_operation, handle_get_by_id, handle_get_all, handle_delete
from app.schemas.billing.client_bill import (
    ClientBillUpdateSchema,
    ClientBillResponseSchema,
)
from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning
from app.utils.error_messages import client_bill_not_found
from app.services.billing import process_client_bill_internal
from typing import List, cast
import psycopg2.extensions

router = APIRouter(
    prefix="/client-bills",
    tags=["Client Bills"],
)

# Client bills are never created via a public API. They are created only when a payment
# completes via subscription_payment (confirm-payment or webhook). Every bill has subscription_payment_id.

@router.get("/{client_bill_id}", response_model=ClientBillResponseSchema)
def get_client_bill(
    client_bill_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a client bill by ID"""
    return handle_get_by_id(
        client_bill_service.get_by_id_non_archived,
        client_bill_id,
        db,
        "client bill"
    )

@router.get("", response_model=List[ClientBillResponseSchema])
def list_client_bills(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all client bills"""
    return handle_get_all(client_bill_service.get_all_non_archived, db, "client bills")

@router.put("/{client_bill_id}", response_model=ClientBillResponseSchema)
def update_client_bill(
    client_bill_id: UUID,
    payload: ClientBillUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update a client bill"""
    def _update_client_bill():
        update_data = payload.model_dump(exclude_unset=True)
        update_data["modified_by"] = current_user["user_id"]
        
        # If updating credit_currency_id, also update currency_code using centralized service
        if "credit_currency_id" in update_data:
            resolve_currency_code(update_data, db)
        
        success = client_bill_service.update(client_bill_id, update_data, db)
        if not success:
            raise client_bill_not_found()
            
        updated_client_bill = client_bill_service.get_by_id_non_archived(client_bill_id, db)
        log_info(f"Updated client bill: {updated_client_bill}")
        return updated_client_bill
    
    return handle_business_operation(_update_client_bill, "client bill update")

@router.post("/{client_bill_id}/process")
def process_client_bill(
    client_bill_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Process a client bill: add credits to subscription, set renewal_date, mark Processed."""
    def _process_client_bill():
        client_bill = client_bill_service.get_by_id_non_archived(client_bill_id, db)
        if not client_bill:
            log_warning(f"Client bill not found: {client_bill_id}")
            raise client_bill_not_found()
        modified_by = current_user["user_id"]
        if isinstance(modified_by, str):
            from uuid import UUID
            modified_by = UUID(modified_by)
        success = process_client_bill_internal(client_bill_id, db, modified_by, commit=True)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to process client bill")
        processed_bill = client_bill_service.get_by_id_non_archived(client_bill_id, db)
        log_info(f"Processed client bill {client_bill_id}")
        return {"message": "Client bill processed successfully", "client_bill": processed_bill}
    
    return handle_business_operation(_process_client_bill, "client bill processing")

@router.delete("/{client_bill_id}", response_model=dict)
def delete_client_bill(
    client_bill_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Delete a client bill"""
    handle_delete(client_bill_service.soft_delete, client_bill_id, db, "client bill")
    return {"detail": "Client bill deleted successfully"}