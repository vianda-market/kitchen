# app/routes/webhooks.py
"""
Stripe webhook endpoint. Verifies signature; processes payment_intent.succeeded, payment_method.*.
No authentication — verification is via Stripe-Signature header.
After successful verification, always return 200 for accepted events (even on internal failure)
so Stripe does not retry for days.
"""
from uuid import UUID

import psycopg2.extensions
import stripe
from fastapi import APIRouter, Request, Depends, HTTPException

from app.config.settings import settings
from app.dependencies.database import get_db
from app.services.stripe_customer_payment_method_sync import (
    handle_payment_method_attached,
    handle_payment_method_detached,
)
from app.services.subscription_action_service import (
    activate_subscription_after_payment,
    create_and_process_bill_for_subscription_payment,
)
from app.utils.db import db_read
from app.utils.log import log_info, log_warning, log_error

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def _handle_payment_intent_succeeded(
    event: stripe.Event,
    db: psycopg2.extensions.connection,
) -> None:
    """Activate subscription on succeeded payment; log + swallow errors (return 200 to Stripe)."""
    obj = event.data.object
    metadata = obj.metadata or {}
    subscription_id_str = metadata.get("subscription_id")
    if not subscription_id_str:
        log_warning("payment_intent.succeeded missing metadata.subscription_id; skipping")
        return

    try:
        subscription_id = UUID(subscription_id_str)
    except (ValueError, TypeError):
        log_warning(f"payment_intent.succeeded invalid subscription_id: {subscription_id_str}")
        return

    payment_intent_id = obj.id if hasattr(obj, "id") else None
    if not payment_intent_id:
        log_warning("payment_intent.succeeded missing PaymentIntent id")
        return

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
        return

    if sp_row["status"] == "succeeded":
        log_info(f"Stripe webhook: subscription {subscription_id} already succeeded (idempotent)")
        return

    if sp_row["subscription_status"] == "active":
        log_info(f"Stripe webhook: subscription {subscription_id} already Active (idempotent)")
        return

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
        # Best-effort referral reward processing (non-blocking)
        try:
            from app.services.referral_service import process_referral_reward
            process_referral_reward(UUID(str(user_id)), db)
        except Exception as ref_err:
            log_warning(f"Referral reward processing failed for user {user_id}: {ref_err}")
        # Best-effort ads conversion tracking (non-blocking)
        try:
            import asyncio
            from app.services.ads.subscription_ads_hook import notify_ads_subscription_activated
            asyncio.get_event_loop().create_task(
                notify_ads_subscription_activated(subscription_id, db)
            )
        except Exception as ads_err:
            log_warning(f"Ads conversion tracking failed for subscription {subscription_id}: {ads_err}")
    except Exception as e:
        db.rollback()
        log_warning(
            f"Stripe webhook payment_intent.succeeded processing failed (returning 200): {e}"
        )
    finally:
        cursor.close()


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Handle Stripe webhooks. Verifies signature first (400 on failure).
    After verify: 200 + {"received": true} for all handled event types, including DB failures.
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

    event_type = event.type
    try:
        if event_type == "payment_intent.succeeded":
            _handle_payment_intent_succeeded(event, db)
        elif event_type == "payment_method.attached":
            handle_payment_method_attached(event.data.object, db)
        elif event_type == "payment_method.detached":
            handle_payment_method_detached(event.data.object, db)
        else:
            pass
    except Exception as e:
        log_warning(f"Stripe webhook unexpected error on {event_type} (returning 200): {e}")

    return {"received": True}


# =============================================================================
# STRIPE CONNECT WEBHOOK (separate secret; separate endpoint)
# =============================================================================

def _handle_account_updated(
    event: stripe.Event,
    db: psycopg2.extensions.connection,
) -> None:
    """Sync payout_onboarding_status on entity when Stripe confirms onboarding is complete."""
    from app.services.entity_service import get_institution_entity_by_payout_account_id
    from app.services.crud_service import institution_entity_service
    account = event.data.object
    connect_id = account.id if hasattr(account, "id") else None
    if not connect_id:
        return
    entity = get_institution_entity_by_payout_account_id(connect_id, db)
    payouts_enabled = getattr(account, "payouts_enabled", False)
    details_submitted = getattr(account, "details_submitted", False)
    entity_id = entity.get("institution_entity_id") if entity else None
    log_info(
        f"Connect account.updated: {connect_id} entity={entity_id} "
        f"payouts_enabled={payouts_enabled} details_submitted={details_submitted}"
    )
    if entity_id and details_submitted:
        try:
            institution_entity_service.update(
                str(entity_id),
                {"payout_onboarding_status": "complete"},
                db,
            )
            db.commit()
            log_info(f"Set payout_onboarding_status=complete for entity {entity_id}")
        except Exception as e:
            db.rollback()
            log_error(f"Connect account.updated: failed to update onboarding status for entity {entity_id}: {e}")


def _handle_transfer_created(
    event: stripe.Event,
    db: psycopg2.extensions.connection,
) -> None:
    """Confirm provider_transfer_id is written on the payout row (belt-and-suspenders)."""
    transfer = event.data.object
    transfer_id = transfer.id if hasattr(transfer, "id") else None
    if not transfer_id:
        return
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE billing.institution_bill_payout
                SET provider_transfer_id = %s
                WHERE provider = 'stripe' AND (provider_transfer_id IS NULL OR provider_transfer_id = %s)
                  AND idempotency_key LIKE 'bill_%_stripe'
                """,
                (transfer_id, transfer_id),
            )
        db.commit()
        log_info(f"Connect transfer.created: confirmed provider_transfer_id={transfer_id}")
    except Exception as e:
        db.rollback()
        log_error(f"Connect transfer.created: failed to confirm {transfer_id}: {e}")


def _handle_transfer_reversed(
    event: stripe.Event,
    db: psycopg2.extensions.connection,
) -> None:
    """Mark payout as Failed and bill as Failed when a transfer is reversed."""
    transfer = event.data.object
    transfer_id = transfer.id if hasattr(transfer, "id") else None
    if not transfer_id:
        return
    reversals = getattr(transfer, "reversals", None)
    reversal_reason = "unknown"
    if reversals and hasattr(reversals, "data") and reversals.data:
        first = reversals.data[0]
        reversal_reason = getattr(first, "reason", None) or "unknown"
    log_warning(
        f"Connect transfer.reversed: transfer={transfer_id} reason={reversal_reason}"
    )
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE billing.institution_bill_payout
                SET status = 'failed'
                WHERE provider_transfer_id = %s AND status != 'failed'
                RETURNING institution_bill_id
                """,
                (transfer_id,),
            )
            row = cur.fetchone()
            if row:
                bill_id = row[0]
                cur.execute(
                    """
                    UPDATE billing.institution_bill_info
                    SET resolution = 'failed', modified_date = CURRENT_TIMESTAMP
                    WHERE institution_bill_id = %s AND resolution = 'pending'
                    """,
                    (str(bill_id),),
                )
        db.commit()
        log_info(f"Connect transfer.reversed: marked payout/bill Failed for transfer={transfer_id}")
    except Exception as e:
        db.rollback()
        log_error(f"Connect transfer.reversed: failed to update for {transfer_id}: {e}")


def _handle_connect_payout_paid(
    event: stripe.Event,
    db: psycopg2.extensions.connection,
) -> None:
    """Mark payout as Completed and bill as Paid when Stripe confirms funds landed."""
    payout = event.data.object
    # Stripe payout ID — find matching bill_payout row by provider_transfer_id or metadata
    payout_id = payout.id if hasattr(payout, "id") else None
    if not payout_id:
        return
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    try:
        with db.cursor() as cur:
            # Match payout row via provider_transfer_id (the Transfer ID written at creation)
            cur.execute(
                """
                UPDATE billing.institution_bill_payout
                SET status = 'completed', completed_at = %s
                WHERE provider_transfer_id = %s AND status = 'pending'
                RETURNING institution_bill_id
                """,
                (now, payout_id),
            )
            row = cur.fetchone()
            if row:
                bill_id = row[0]
                cur.execute(
                    """
                    UPDATE billing.institution_bill_info
                    SET resolution = 'paid', modified_date = CURRENT_TIMESTAMP
                    WHERE institution_bill_id = %s AND resolution = 'pending'
                    """,
                    (str(bill_id),),
                )
        db.commit()
        log_info(f"Connect payout.paid: Completed payout and Paid bill for payout={payout_id}")
    except Exception as e:
        db.rollback()
        log_error(f"Connect payout.paid: failed for payout={payout_id}: {e}")


def _handle_connect_payout_failed(
    event: stripe.Event,
    db: psycopg2.extensions.connection,
) -> None:
    """Mark payout as Failed and bill as Failed when a payout fails."""
    payout = event.data.object
    payout_id = payout.id if hasattr(payout, "id") else None
    if not payout_id:
        return
    try:
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE billing.institution_bill_payout
                SET status = 'failed'
                WHERE provider_transfer_id = %s AND status = 'pending'
                RETURNING institution_bill_id
                """,
                (payout_id,),
            )
            row = cur.fetchone()
            if row:
                bill_id = row[0]
                cur.execute(
                    """
                    UPDATE billing.institution_bill_info
                    SET resolution = 'failed', modified_date = CURRENT_TIMESTAMP
                    WHERE institution_bill_id = %s AND resolution = 'pending'
                    """,
                    (str(bill_id),),
                )
        db.commit()
        log_info(f"Connect payout.failed: marked Failed for payout={payout_id}")
    except Exception as e:
        db.rollback()
        log_error(f"Connect payout.failed: failed for payout={payout_id}: {e}")


@router.post("/stripe-connect")
async def stripe_connect_webhook(
    request: Request,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Handle Stripe Connect webhooks. Separate endpoint from /stripe (uses STRIPE_CONNECT_WEBHOOK_SECRET).
    Events: account.updated, transfer.created, transfer.reversed, payout.paid, payout.failed.
    Always returns 200 after signature verification — Stripe should not retry on internal errors.
    """
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    secret = (settings.STRIPE_CONNECT_WEBHOOK_SECRET or "").strip()
    if not secret:
        log_warning("STRIPE_CONNECT_WEBHOOK_SECRET not set; cannot verify Connect webhook")
        raise HTTPException(status_code=500, detail="Connect webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(payload, signature, secret)
    except ValueError as e:
        log_warning(f"Connect webhook invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError as e:
        log_warning(f"Connect webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.type
    try:
        if event_type == "account.updated":
            _handle_account_updated(event, db)
        elif event_type == "transfer.created":
            _handle_transfer_created(event, db)
        elif event_type == "transfer.reversed":
            _handle_transfer_reversed(event, db)
        elif event_type == "payout.paid":
            _handle_connect_payout_paid(event, db)
        elif event_type == "payout.failed":
            _handle_connect_payout_failed(event, db)
        else:
            pass
    except Exception as e:
        log_warning(f"Connect webhook unexpected error on {event_type} (returning 200): {e}")

    return {"received": True}
