# app/routes/client_payment_attempt_routes.py

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from app.auth.dependencies import oauth2_scheme
from app.dependencies.database import get_db
from uuid import UUID
from app.dto.models import ClientPaymentAttemptDTO
from app.services.crud_service import client_payment_attempt_service
from app.services.error_handling import handle_business_operation
from app.services.credit_currency_service import resolve_currency_code
from app.schemas.payment_methods.client_payment_attempt import ClientPaymentAttemptCreateSchema
from typing import List
from datetime import timedelta, timezone, datetime
from app.dto.models import ClientBillDTO, SubscriptionDTO, CreditCurrencyDTO
from app.services.crud_service import client_bill_service, subscription_service
import math
from app.utils.log import log_info, log_warning
import psycopg2.extensions

router = APIRouter(
    prefix="/client-payment-attempts",
    tags=["Client Payment Attempts"],
    dependencies=[Depends(oauth2_scheme)]
)

@router.post("/", response_model=ClientPaymentAttemptDTO)
def create_client_payment_attempt(
    payload: ClientPaymentAttemptCreateSchema,
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Create a new client payment attempt"""
    # #region agent log
    import json
    import os
    log_path = "/Users/cdeachaval/Library/Mobile Documents/com~apple~CloudDocs/Desktop/local/kitchen/.cursor/debug.log"
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({"sessionId": "debug-session", "runId": "post-fix", "hypothesisId": "B", "location": "client_payment_attempt.py:26", "message": "POST /api/v1/client-payment-attempts handler called", "data": {"router_prefix": router.prefix, "full_path": router.prefix + "/"}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
    except: pass
    # #endregion
    def _create_client_payment_attempt():
        data = payload.dict()
        log_info(f"[create_client_payment_attempt] Initial data keys: {list(data.keys())}")
        data["status"] = "Pending"
        
        # Resolve currency_code from credit_currency_id using centralized service
        resolve_currency_code(data, db)
        log_info(f"[create_client_payment_attempt] Data keys after currency resolution: {list(data.keys())}")
        log_info(f"[create_client_payment_attempt] currency_code value: {data.get('currency_code')}")
        
        client_payment_attempt = client_payment_attempt_service.create(data, db)
        return client_payment_attempt
    
    return handle_business_operation(
        _create_client_payment_attempt,
        "client payment attempt creation",
        "Client payment attempt created successfully"
    )

@router.get("/{payment_id}", response_model=ClientPaymentAttemptDTO)
def get_client_payment_attempt_by_id(
    payment_id: UUID,
    db: psycopg2.extensions.connection = Depends(get_db)
):
    return client_payment_attempt_service.get_by_id(payment_id, db)

@router.get("/", response_model=List[ClientPaymentAttemptDTO])
def get_all_client_payment_attempts(
    db: psycopg2.extensions.connection = Depends(get_db)
):
    return client_payment_attempt_service.get_all_non_archived(db)

@router.patch("/{payment_id}")
def update_client_payment_attempt(
    payment_id: UUID, 
    payload: dict, 
    background_tasks: BackgroundTasks,
    db: psycopg2.extensions.connection = Depends(get_db)
):
    updated_attempt = client_payment_attempt_service.update(payment_id, payload, db)
    if not updated_attempt:
        raise HTTPException(status_code=404, detail=f"Client payment attempt not found: {payment_id}")
    
    # Only trigger if just marked as completed and not archived
    if updated_attempt.status == "Completed" and not updated_attempt.is_archived:
        background_tasks.add_task(process_successful_payment, payment_id, db)
    return updated_attempt

def process_successful_payment(payment_id: UUID, db: psycopg2.extensions.connection):
    payment = client_payment_attempt_service.get_by_id(payment_id, db)
    if not payment or payment.is_archived or payment.status != "Completed":
        log_warning(f"Payment {payment_id} not eligible for processing.")
        return

    bill = client_bill_service.get_by_payment(payment_id, db)
    if not bill:
        log_warning(f"No client bill found for payment {payment_id}")
        return

    subscription = subscription_service.get_by_id(bill.subscription_id, db)
    if not subscription:
        log_warning(f"No subscription found for bill {bill.client_bill_id}")
        return

    credit_currency = credit_currency_service.get_by_id(payment.credit_currency_id, db)
    if not credit_currency:
        log_warning(f"No credit currency found for id {payment.credit_currency_id}")
        return

    # Use math.ceil for added_credits
    added_credits = math.ceil(payment.amount / credit_currency.credit_value)
    new_balance = subscription.balance + added_credits

    # Ensure renewal_date is timezone-aware UTC
    renewal_date = subscription.renewal_date
    if renewal_date.tzinfo is None:
        renewal_date = renewal_date.replace(tzinfo=timezone.utc)
    else:
        renewal_date = renewal_date.astimezone(timezone.utc)
    new_renewal_date = renewal_date + timedelta(days=30)
    new_renewal_date = new_renewal_date.astimezone(timezone.utc)

    subscription_service.update(subscription.subscription_id, {
        "balance": new_balance,
        "renewal_date": new_renewal_date
    }, db)
    client_payment_attempt_service.update(payment_id, {"is_archived": False}, db)  # Archive per retention policy (180 days)
    log_info(f"Processed payment {payment_id}: balance updated to {new_balance}, renewal_date set to {new_renewal_date.isoformat()}, payment processed.")

# DELETE /client-payment-attempts/{payment_id} – Delete (soft-delete) a client payment attempt
@router.delete("/{payment_id}", response_model=dict)
def delete_client_payment_attempt(
    payment_id: UUID,
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Delete (soft-delete) a client payment attempt"""
    handle_delete(client_payment_attempt_service.soft_delete, payment_id, db, "client payment attempt")
    return {"detail": "Client payment attempt deleted successfully"}
