# app/routes/webhooks.py
"""
Stripe webhook endpoint. Receives payment_intent.succeeded and activates subscriptions.
No authentication — verification is via Stripe-Signature header.
"""
from uuid import UUID

import psycopg2.extensions
import stripe
from fastapi import APIRouter, Request, Depends, HTTPException

from app.config.settings import settings
from app.dependencies.database import get_db
from app.services.subscription_action_service import (
    activate_subscription_after_payment,
    create_and_process_bill_for_subscription_payment,
)
from app.utils.db import db_read
from app.utils.log import log_info, log_warning

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Handle Stripe webhooks. Verifies signature, processes payment_intent.succeeded
    to activate subscription and create bill. Idempotent for retries.
    """
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    secret = (settings.STRIPE_WEBHOOK_SECRET or "").strip()
    if not secret:
        log_warning("STRIPE_WEBHOOK_SECRET not set; cannot verify Stripe webhook")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(payload, signature, secret)
    except ValueError as e:
        log_warning(f"Stripe webhook invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError as e:
        log_warning(f"Stripe webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event.type != "payment_intent.succeeded":
        return {"received": True}

    obj = event.data.object
    metadata = obj.metadata or {}
    subscription_id_str = metadata.get("subscription_id")
    if not subscription_id_str:
        log_warning("payment_intent.succeeded missing metadata.subscription_id; skipping")
        return {"received": True}

    try:
        subscription_id = UUID(subscription_id_str)
    except (ValueError, TypeError):
        log_warning(f"payment_intent.succeeded invalid subscription_id: {subscription_id_str}")
        return {"received": True}

    payment_intent_id = obj.id if hasattr(obj, "id") else None
    if not payment_intent_id:
        log_warning("payment_intent.succeeded missing id")
        return {"received": True}

    # Idempotency: check if already processed
    sp_row = db_read(
        """
        SELECT sp.subscription_payment_id, sp.status, s.user_id, s.subscription_status
        FROM subscription_payment sp
        JOIN subscription_info s ON sp.subscription_id = s.subscription_id
        WHERE sp.external_payment_id = %s AND sp.subscription_id = %s::uuid
        """,
        (payment_intent_id, str(subscription_id)),
        connection=db,
        fetch_one=True,
    )
    if not sp_row:
        log_warning(f"No subscription_payment found for pi={payment_intent_id} sub={subscription_id}")
        return {"received": True}

    if sp_row["status"] == "succeeded":
        log_info(f"Stripe webhook: subscription {subscription_id} already succeeded (idempotent)")
        return {"received": True}

    if sp_row["subscription_status"] == "Active":
        log_info(f"Stripe webhook: subscription {subscription_id} already Active (idempotent)")
        return {"received": True}

    user_id = sp_row["user_id"]
    sp_id = sp_row["subscription_payment_id"]
    modified_by = UUID(str(user_id)) if user_id else subscription_id

    cursor = db.cursor()
    try:
        activate_subscription_after_payment(
            subscription_id, modified_by=modified_by, db=db, commit=False
        )
        cursor.execute(
            "UPDATE subscription_payment SET status = %s WHERE subscription_payment_id = %s::uuid",
            ("succeeded", str(sp_id)),
        )
        create_and_process_bill_for_subscription_payment(
            subscription_id, UUID(str(sp_id)), modified_by, db
        )
        db.commit()
        log_info(f"Stripe webhook: activated subscription {subscription_id}")
    except Exception as e:
        db.rollback()
        log_warning(f"Stripe webhook failed for subscription {subscription_id}: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")
    finally:
        cursor.close()

    return {"received": True}
