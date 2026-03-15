# app/routes/subscription_payment.py
"""
Atomic subscription + payment: POST /subscriptions/with-payment and (mock) POST /subscriptions/{id}/confirm-payment.
When user has Pending in same market, edit in place (update plan, cancel previous payment intent, new payment).
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
import psycopg2.extensions

from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.config import Status
from app.config.enums.subscription_status import SubscriptionStatus
from app.config.settings import settings
from app.services.crud_service import (
    subscription_service,
    plan_service,
    get_subscription_by_user_and_market,
)
from app.services.market_service import market_service
from app.services.payment_provider import (
    create_payment_for_subscription,
    cancel_payment_intent,
    get_client_secret_for_pending_payment,
)
from app.services.subscription_action_service import (
    activate_subscription_after_payment,
    create_and_process_bill_for_subscription_payment,
    cancel_subscription as cancel_subscription_action,
)
from app.utils.db import db_insert, db_read, db_update
from app.schemas.subscription import (
    SubscriptionWithPaymentRequestSchema,
    SubscriptionWithPaymentResponseSchema,
    SubscriptionResponseSchema,
)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


def _require_customer_or_employee(current_user: dict) -> UUID:
    """Raise 403 if not Customer or Employee; return user_id."""
    role_type = (current_user.get("role_type") or "").strip().lower()
    if role_type not in ("customer", "employee"):
        raise HTTPException(status_code=403, detail="Only customers or employees can use subscription payment.")
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token.")
    return UUID(str(user_id)) if isinstance(user_id, str) else user_id


def _get_payment_provider_name() -> str:
    return (getattr(settings, "PAYMENT_PROVIDER", None) or "mock").strip().lower()


@router.post("/with-payment", response_model=SubscriptionWithPaymentResponseSchema)
def create_subscription_with_payment(
    body: SubscriptionWithPaymentRequestSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Create a subscription in Pending status and a payment intent (Stripe or mock).
    If user already has a subscription in this plan's market:
    - Active: returns 409 with code "already_active" so client can show "You already have an active subscription."
    - Pending: edit in place (update plan, cancel previous payment intent, create new payment); returns 200 with same shape.
    Returns subscription_id, payment_id, client_secret for the client to complete payment.
    """
    user_id = _require_customer_or_employee(current_user)
    plan_id = body.plan_id

    plan = plan_service.get_by_id(plan_id, db)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")

    market = market_service.get_by_id(plan.market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found.")
    market_id = plan.market_id
    currency = (market.get("currency_code") or "usd").lower()
    amount_cents = int(round(float(plan.price) * 100))

    existing = get_subscription_by_user_and_market(user_id, market_id, db)
    if existing:
        if existing.subscription_status == SubscriptionStatus.ACTIVE.value:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "already_active",
                    "subscription_id": str(existing.subscription_id),
                    "message": "You already have an active subscription in this market.",
                },
            )
        if existing.subscription_status == SubscriptionStatus.PENDING.value:
            return _edit_pending_subscription_in_place(
                existing_subscription=existing,
                plan_id=plan_id,
                amount_cents=amount_cents,
                currency=currency,
                user_id=user_id,
                db=db,
            )

    create_data = {
        "plan_id": plan_id,
        "user_id": user_id,
        "status": Status.PENDING,
        "subscription_status": SubscriptionStatus.PENDING.value,
        "modified_by": user_id,
    }
    subscription = subscription_service.create(create_data, db, scope=None)
    if not subscription:
        raise HTTPException(status_code=500, detail="Failed to create subscription.")

    subscription_id = subscription.subscription_id
    result = create_payment_for_subscription(
        subscription_id=subscription_id,
        amount_cents=amount_cents,
        currency=currency,
        metadata={"subscription_id": str(subscription_id)},
    )
    external_id = result["id"]
    client_secret = result["client_secret"]

    payment_row = {
        "subscription_id": subscription_id,
        "payment_provider": _get_payment_provider_name(),
        "external_payment_id": external_id,
        "status": "pending",
        "amount_cents": amount_cents,
        "currency": currency,
    }
    payment_id = db_insert("subscription_payment", payment_row, connection=db, commit=True)
    if not payment_id:
        raise HTTPException(status_code=500, detail="Failed to record subscription payment.")

    return {
        "subscription_id": subscription_id,
        "payment_id": payment_id,
        "external_payment_id": external_id,
        "client_secret": client_secret,
        "amount_cents": amount_cents,
        "currency": currency,
    }


def _edit_pending_subscription_in_place(
    existing_subscription,
    plan_id: UUID,
    amount_cents: int,
    currency: str,
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict:
    """Update existing Pending subscription (plan, new payment intent); cancel previous intent and payment rows."""
    subscription_id = existing_subscription.subscription_id
    rows = db_read(
        """
        SELECT subscription_payment_id, external_payment_id, status
        FROM subscription_payment
        WHERE subscription_id = %s::uuid AND status = 'pending'
        ORDER BY subscription_payment_id DESC
        """,
        (str(subscription_id),),
        connection=db,
    )
    previous_payments = list(rows) if rows else []

    for row in previous_payments:
        sp_id = row["subscription_payment_id"]
        ext_id = row["external_payment_id"]
        try:
            cancel_payment_intent(str(ext_id))
        except Exception:
            pass
        db_update(
            "subscription_payment",
            {"status": "cancelled"},
            {"subscription_payment_id": str(sp_id)},
            connection=db,
            commit=False,
        )

    subscription_service.update(
        subscription_id,
        {"plan_id": plan_id, "modified_by": user_id},
        db,
        scope=None,
        commit=False,
    )

    result = create_payment_for_subscription(
        subscription_id=subscription_id,
        amount_cents=amount_cents,
        currency=currency,
        metadata={"subscription_id": str(subscription_id)},
    )
    external_id = result["id"]
    client_secret = result["client_secret"]
    payment_row = {
        "subscription_id": subscription_id,
        "payment_provider": _get_payment_provider_name(),
        "external_payment_id": external_id,
        "status": "pending",
        "amount_cents": amount_cents,
        "currency": currency,
    }
    payment_id = db_insert("subscription_payment", payment_row, connection=db, commit=False)
    if not payment_id:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to record subscription payment.")
    db.commit()

    return {
        "subscription_id": subscription_id,
        "payment_id": payment_id,
        "external_payment_id": external_id,
        "client_secret": client_secret,
        "amount_cents": amount_cents,
        "currency": currency,
    }


@router.get("/{subscription_id}/payment-details", response_model=SubscriptionWithPaymentResponseSchema)
def get_payment_details_for_pending_subscription(
    subscription_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Return payment intent details (client_secret, amount_cents, currency) for a Pending subscription.
    Used when the user is on profile-plan and taps "Complete payment" so the client can open the
    same payment screen as after with-payment without calling with-payment again.
    """
    user_id = _require_customer_or_employee(current_user)
    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found.")
    if subscription.user_id != user_id:
        raise HTTPException(status_code=403, detail="You cannot access this subscription.")
    if subscription.subscription_status != SubscriptionStatus.PENDING.value:
        raise HTTPException(
            status_code=400,
            detail="Subscription is not Pending. Only Pending subscriptions have payment details.",
        )

    rows = db_read(
        """
        SELECT subscription_payment_id, external_payment_id, status, amount_cents, currency
        FROM subscription_payment
        WHERE subscription_id = %s::uuid AND status = 'pending'
        ORDER BY subscription_payment_id DESC
        LIMIT 1
        """,
        (str(subscription_id),),
        connection=db,
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No pending payment found for this subscription.",
        )
    row = rows[0]
    payment_id = row["subscription_payment_id"]
    external_payment_id = str(row["external_payment_id"])
    amount_cents = int(row["amount_cents"])
    currency = str(row["currency"])

    try:
        client_secret = get_client_secret_for_pending_payment(external_payment_id, subscription_id)
    except ValueError as e:
        raise HTTPException(
            status_code=501,
            detail="Payment details not available for this provider. " + str(e),
        )

    return {
        "subscription_id": subscription_id,
        "payment_id": payment_id,
        "external_payment_id": external_payment_id,
        "client_secret": client_secret,
        "amount_cents": amount_cents,
        "currency": currency,
    }


@router.post("/{subscription_id}/confirm-payment", response_model=SubscriptionResponseSchema)
def confirm_subscription_payment(
    subscription_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    [Mock only] Simulate successful payment and activate the subscription.

    Process is atomic: on 200 OK the subscription is Active, the bill is created and
    processed (credits and renewal_date updated). The client should treat 200 as success
    and use the returned subscription for the UI. Any 4xx/5xx means the flow failed.

    Only available when PAYMENT_PROVIDER=mock. For real Stripe, use the webhook and
    poll GET /subscriptions/{id} until subscription_status is Active.
    """
    if _get_payment_provider_name() != "mock":
        raise HTTPException(
            status_code=400,
            detail="confirm-payment is only available when PAYMENT_PROVIDER=mock. Use Stripe webhook for live.",
        )
    user_id = _require_customer_or_employee(current_user)

    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found.")
    if subscription.subscription_status != SubscriptionStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Subscription is not Pending.")
    if subscription.user_id != user_id:
        raise HTTPException(status_code=403, detail="You cannot confirm payment for this subscription.")

    cursor = db.cursor()
    try:
        cursor.execute(
            """
            SELECT subscription_payment_id, external_payment_id, status
            FROM subscription_payment
            WHERE subscription_id = %s::uuid
            ORDER BY subscription_payment_id DESC
            LIMIT 1
            """,
            (str(subscription_id),),
        )
        row = cursor.fetchone()
    finally:
        cursor.close()
    if not row:
        raise HTTPException(status_code=400, detail="No subscription payment found for this subscription.")

    _sp_id, external_payment_id, sp_status = row
    if sp_status == "succeeded":
        updated = subscription_service.get_by_id(subscription_id, db, scope=None)
        return _subscription_to_response(updated)

    # Single transaction: activate subscription, mark only this payment row succeeded, create and process client bill
    activate_subscription_after_payment(subscription_id, modified_by=user_id, db=db, commit=False)
    cursor = db.cursor()
    try:
        cursor.execute(
            "UPDATE subscription_payment SET status = %s WHERE subscription_payment_id = %s::uuid",
            ("succeeded", str(_sp_id)),
        )
    finally:
        cursor.close()
    create_and_process_bill_for_subscription_payment(
        subscription_id, UUID(str(_sp_id)), user_id, db
    )
    db.commit()

    updated = subscription_service.get_by_id(subscription_id, db, scope=None)
    return _subscription_to_response(updated)


@router.post("/{subscription_id}/cancel", status_code=200)
def cancel_subscription(
    subscription_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Cancel a subscription (Pending, Active, or On Hold). Only the owning customer can cancel.
    All cancels archive the subscription so the user can re-subscribe in the same market.
    - Pending: cancels Stripe PaymentIntent(s), marks subscription_payment rows cancelled, archives.
    - Active/On Hold: archives via subscription_action_service.
    """
    user_id = _require_customer_or_employee(current_user)
    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found.")
    if subscription.subscription_status == SubscriptionStatus.CANCELLED.value:
        raise HTTPException(status_code=400, detail="Subscription is already cancelled.")
    if subscription.user_id != user_id:
        raise HTTPException(status_code=403, detail="You cannot cancel this subscription.")

    if subscription.subscription_status == SubscriptionStatus.PENDING.value:
        # Pending: cancel PaymentIntent(s), mark subscription_payment cancelled, archive
        rows = db_read(
            """
            SELECT subscription_payment_id, external_payment_id, status
            FROM subscription_payment
            WHERE subscription_id = %s::uuid AND status = 'pending'
            """,
            (str(subscription_id),),
            connection=db,
        )
        for row in rows or []:
            try:
                cancel_payment_intent(str(row["external_payment_id"]))
            except Exception:
                pass
            db_update(
                "subscription_payment",
                {"status": "cancelled"},
                {"subscription_payment_id": str(row["subscription_payment_id"])},
                connection=db,
                commit=False,
            )
        subscription_service.update(
            subscription_id,
            {
                "subscription_status": SubscriptionStatus.CANCELLED.value,
                "status": Status.CANCELLED.value,
                "is_archived": True,
                "modified_by": user_id,
            },
            db,
            scope=None,
            commit=True,
        )
    else:
        # Active or On Hold: use subscription_action_service (archives)
        cancel_subscription_action(subscription_id, user_id, db)

    return {"detail": "Subscription cancelled. You can choose a new plan and subscribe again."}


def _subscription_to_response(subscription) -> SubscriptionResponseSchema:
    """Map subscription DTO to response schema (exclude market_id)."""
    return SubscriptionResponseSchema(
        subscription_id=subscription.subscription_id,
        user_id=subscription.user_id,
        plan_id=subscription.plan_id,
        renewal_date=subscription.renewal_date,
        balance=subscription.balance,
        is_archived=subscription.is_archived,
        status=subscription.status,
        subscription_status=subscription.subscription_status,
        hold_start_date=subscription.hold_start_date,
        hold_end_date=subscription.hold_end_date,
        created_date=subscription.created_date,
        modified_by=subscription.modified_by,
        modified_date=subscription.modified_date,
    )
