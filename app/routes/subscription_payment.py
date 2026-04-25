# app/routes/subscription_payment.py
"""
Atomic subscription + payment: POST /subscriptions/with-payment and (mock) POST /subscriptions/{id}/confirm-payment.
When user has Pending in same market, edit in place (update plan, cancel previous payment intent, new payment).
"""

from datetime import UTC
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user, get_resolved_locale
from app.config import Status
from app.config.enums.subscription_status import SubscriptionStatus
from app.config.settings import settings
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.subscription import (
    SubscriptionResponseSchema,
    SubscriptionWithPaymentRequestSchema,
    SubscriptionWithPaymentResponseSchema,
)
from app.services.crud_service import (
    get_subscription_by_user_and_market,
    plan_service,
    subscription_service,
)
from app.services.market_service import market_service
from app.services.payment_provider import (
    cancel_payment_intent,
    create_payment_for_subscription,
    get_client_secret_for_pending_payment,
)
from app.services.subscription_action_service import (
    activate_subscription_after_payment,
    create_and_process_bill_for_subscription_payment,
)
from app.services.subscription_action_service import (
    cancel_subscription as cancel_subscription_action,
)
from app.utils.db import db_insert, db_read, db_update

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


def _require_customer_or_employee(current_user: dict, locale: str = "en") -> UUID:
    """Raise 403 if not Customer or Internal; return user_id."""
    role_type = (current_user.get("role_type") or "").strip().lower()
    if role_type not in ("customer", "employee"):
        raise envelope_exception(
            ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS,
            status=403,
            locale=locale,
        )
    user_id = current_user.get("user_id")
    if not user_id:
        raise envelope_exception(
            ErrorCode.SECURITY_TOKEN_USER_ID_MISSING,
            status=401,
            locale=locale,
        )
    return UUID(str(user_id)) if isinstance(user_id, str) else user_id


def _get_payment_provider_name() -> str:
    return (getattr(settings, "PAYMENT_PROVIDER", None) or "mock").strip().lower()


def _compute_employer_benefit(user_id: UUID, plan, db: psycopg2.extensions.connection):
    """Check if user is a benefit employee and compute employer/employee split.
    Returns dict with split info, or None if user is not a benefit employee."""
    from app.services.crud_service import institution_service
    from app.services.employer.billing_service import compute_employee_benefit
    from app.services.employer.program_service import get_program_by_institution

    user = db_read(
        "SELECT institution_id FROM user_info WHERE user_id = %s::uuid AND is_archived = FALSE",
        (str(user_id),),
        connection=db,
        fetch_one=True,
    )
    if not user:
        return None
    institution_id = user["institution_id"]

    inst = institution_service.get_by_id(institution_id, db, scope=None)
    if not inst:
        return None
    inst_type = getattr(inst, "institution_type", None)
    inst_type_str = inst_type.value if hasattr(inst_type, "value") else str(inst_type)
    if inst_type_str != "employer":
        return None

    program = get_program_by_institution(institution_id, db)
    if not program or not program.is_active:
        return None

    plan_price = float(getattr(plan, "price", 0))
    benefit_cap = float(program.benefit_cap) if program.benefit_cap is not None else None

    # Compute monthly cap usage for this user
    already_used = 0.0
    if benefit_cap is not None and program.benefit_cap_period == "monthly":
        from datetime import datetime

        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage_rows = db_read(
            """
            SELECT COALESCE(SUM(ebl.employee_benefit), 0) as total_used
            FROM employer_bill_line ebl
            JOIN employer_bill eb ON ebl.employer_bill_id = eb.employer_bill_id
            WHERE ebl.user_id = %s::uuid
              AND ebl.renewal_date >= %s
            """,
            (str(user_id), month_start),
            connection=db,
            fetch_one=True,
        )
        already_used = float(usage_rows["total_used"]) if usage_rows else 0.0

    employee_benefit, employee_share = compute_employee_benefit(
        plan_price=plan_price,
        benefit_rate=program.benefit_rate,
        benefit_cap=benefit_cap,
        benefit_cap_period=program.benefit_cap_period,
        already_used_this_month=already_used,
    )

    return {
        "employee_share": employee_share,
        "employee_share_cents": int(round(employee_share * 100)),
        "employee_benefit": employee_benefit,
        "institution_id": institution_id,
        "program": program,
    }


def _create_fully_subsidized_subscription(
    user_id: UUID, plan, market_id, benefit_info: dict, db: psycopg2.extensions.connection, locale: str = "en"
):
    """Create a subscription that activates immediately with no payment (100% employer subsidy)."""
    from app.utils.log import log_info

    plan_credit = int(getattr(plan, "credit", 0))
    program = benefit_info["program"]
    early_threshold = None if not program.allow_early_renewal else 10

    # Check for existing subscription in this market
    existing = get_subscription_by_user_and_market(user_id, market_id, db)
    if existing:
        if existing.subscription_status == SubscriptionStatus.ACTIVE.value:
            raise envelope_exception(
                ErrorCode.SUBSCRIPTION_ALREADY_ACTIVE,
                status=409,
                locale=locale,
            )

    create_data = {
        "plan_id": plan.plan_id,
        "user_id": user_id,
        "market_id": market_id,
        "balance": plan_credit,
        "status": Status.ACTIVE,
        "subscription_status": SubscriptionStatus.ACTIVE.value,
        "early_renewal_threshold": early_threshold,
        "modified_by": user_id,
    }
    subscription = subscription_service.create(create_data, db, scope=None)
    if not subscription:
        raise HTTPException(status_code=500, detail="Failed to create subscription.")
    log_info(f"Fully-subsidized subscription {subscription.subscription_id} created for benefit employee {user_id}")

    # Return same shape as with-payment but with no-payment indicators
    return {
        "subscription_id": subscription.subscription_id,
        "payment_id": subscription.subscription_id,  # No real payment — use subscription_id as placeholder
        "external_payment_id": "fully_subsidized",
        "client_secret": "fully_subsidized",
        "amount_cents": 0,
        "currency": "usd",
    }


@router.post("/with-payment", response_model=SubscriptionWithPaymentResponseSchema)
def create_subscription_with_payment(
    body: SubscriptionWithPaymentRequestSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """
    Create a subscription in Pending status and a payment intent (Stripe or mock).
    If user already has a subscription in this plan's market:
    - Active: returns 409 with code "already_active" so client can show "You already have an active subscription."
    - Pending: edit in place (update plan, cancel previous payment intent, create new payment); returns 200 with same shape.
    Returns subscription_id, payment_id, client_secret for the client to complete payment.
    """
    user_id = _require_customer_or_employee(current_user, locale)
    plan_id = body.plan_id

    plan = plan_service.get_by_id(plan_id, db)
    if not plan:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Plan")

    market = market_service.get_by_id(plan.market_id)
    if not market:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Market")
    market_id = plan.market_id
    currency = (market.get("currency_code") or "usd").lower()
    amount_cents = int(round(float(plan.price) * 100))

    # Employer benefit detection: adjust amount if user is a benefit employee
    employer_benefit_info = _compute_employer_benefit(user_id, plan, db)
    if employer_benefit_info is not None:
        if employer_benefit_info["employee_share_cents"] == 0:
            # Fully subsidized — activate immediately, no payment
            return _create_fully_subsidized_subscription(user_id, plan, market_id, employer_benefit_info, db, locale)
        # Partial subsidy — charge employee their share only
        amount_cents = employer_benefit_info["employee_share_cents"]

    existing = get_subscription_by_user_and_market(user_id, market_id, db)
    if existing:
        if existing.subscription_status == SubscriptionStatus.ACTIVE.value:
            raise envelope_exception(
                ErrorCode.SUBSCRIPTION_ALREADY_ACTIVE,
                status=409,
                locale=locale,
            )
        if existing.subscription_status == SubscriptionStatus.PENDING.value:
            return _edit_pending_subscription_in_place(
                existing_subscription=existing,
                plan_id=plan_id,
                amount_cents=amount_cents,
                currency=currency,
                user_id=user_id,
                db=db,
                locale=locale,
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
    locale: str = "en",
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
    locale: str = Depends(get_resolved_locale),
):
    """
    Return payment intent details (client_secret, amount_cents, currency) for a Pending subscription.
    Used when the user is on profile-plan and taps "Complete payment" so the client can open the
    same payment screen as after with-payment without calling with-payment again.
    """
    user_id = _require_customer_or_employee(current_user, locale)
    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
    if not subscription:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_FOUND, status=404, locale=locale)
    if subscription.user_id != user_id:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_ACCESS_DENIED, status=403, locale=locale)
    if subscription.subscription_status != SubscriptionStatus.PENDING.value:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_PENDING, status=400, locale=locale)

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
        raise envelope_exception(ErrorCode.SUBSCRIPTION_PAYMENT_NOT_FOUND, status=404, locale=locale)
    row = rows[0]
    payment_id = row["subscription_payment_id"]
    external_payment_id = str(row["external_payment_id"])
    amount_cents = int(row["amount_cents"])
    currency = str(row["currency"])

    try:
        client_secret = get_client_secret_for_pending_payment(external_payment_id, subscription_id)
    except ValueError:
        raise envelope_exception(
            ErrorCode.SUBSCRIPTION_PAYMENT_PROVIDER_UNAVAILABLE, status=501, locale=locale
        ) from None

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
    locale: str = Depends(get_resolved_locale),
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
        raise envelope_exception(ErrorCode.SUBSCRIPTION_CONFIRM_MOCK_ONLY, status=400, locale=locale)
    user_id = _require_customer_or_employee(current_user, locale)

    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
    if not subscription:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_FOUND, status=404, locale=locale)
    if subscription.subscription_status != SubscriptionStatus.PENDING.value:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_PENDING, status=400, locale=locale)
    if subscription.user_id != user_id:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_ACCESS_DENIED, status=403, locale=locale)

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
        raise envelope_exception(ErrorCode.SUBSCRIPTION_PAYMENT_RECORD_NOT_FOUND, status=400, locale=locale)

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
    create_and_process_bill_for_subscription_payment(subscription_id, UUID(str(_sp_id)), user_id, db)
    db.commit()

    # Best-effort referral reward processing (non-blocking)
    try:
        from app.services.referral_service import process_referral_reward

        process_referral_reward(user_id, db)
    except Exception as e:
        from app.utils.log import log_warning

        log_warning(f"Referral reward processing failed for user {user_id}: {e}")

    updated = subscription_service.get_by_id(subscription_id, db, scope=None)
    return _subscription_to_response(updated)


@router.post("/{subscription_id}/cancel", status_code=200)
def cancel_subscription(
    subscription_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    locale: str = Depends(get_resolved_locale),
):
    """
    Cancel a subscription (Pending, Active, or On Hold). Only the owning customer can cancel.
    All cancels archive the subscription so the user can re-subscribe in the same market.
    - Pending: cancels Stripe PaymentIntent(s), marks subscription_payment rows cancelled, archives.
    - Active/On Hold: archives via subscription_action_service.
    """
    user_id = _require_customer_or_employee(current_user, locale)
    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
    if not subscription:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_FOUND, status=404, locale=locale)
    if subscription.subscription_status == SubscriptionStatus.CANCELLED.value:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_ALREADY_CANCELLED, status=400, locale=locale)
    if subscription.user_id != user_id:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_ACCESS_DENIED, status=403, locale=locale)

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
        # Set status to cancelled FIRST (while row is still visible to get_by_id),
        # then archive via soft_delete. CRUDService.update() with is_archived=True would
        # re-fetch via get_by_id(is_archived=FALSE) → None → silent failure.
        subscription_service.update(
            subscription_id,
            {
                "subscription_status": SubscriptionStatus.CANCELLED.value,
                "status": Status.CANCELLED.value,
                "modified_by": user_id,
            },
            db,
            scope=None,
            commit=False,
        )
        subscription_service.soft_delete(subscription_id, user_id, db, scope=None)
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
