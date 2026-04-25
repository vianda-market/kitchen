# app/services/subscription_action_service.py
"""
Business logic for B2C subscription actions: cancel, put on hold, resume.
Also reconciles subscriptions that have passed hold_end_date (On Hold -> Active).

Archived subscriptions (is_archived=True) are treated as cancelled: not billed,
not usable for plate collection, and excluded from get_by_id (404). On cancel we
set subscription_status = Cancelled, status = Cancelled, and is_archived = True,
so the user can re-subscribe in the same market (unique index is WHERE is_archived = FALSE).
"""

from datetime import UTC, datetime
from uuid import UUID

import psycopg2.extensions

from app.config import Status
from app.config.enums.subscription_status import SubscriptionStatus
from app.dto.models import SubscriptionDTO
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.services.crud_service import subscription_service
from app.utils.db import db_update


def cancel_subscription(
    subscription_id: UUID,
    user_id: UUID,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> SubscriptionDTO:
    """Cancel a subscription (Active or On Hold). Only owner can cancel; only non-cancelled can be cancelled.
    Sets subscription_status = Cancelled, status = Cancelled, is_archived = True so the user can re-subscribe."""
    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
    if not subscription:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_FOUND, status=404, locale=locale)
    if subscription.user_id != user_id:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_ACCESS_DENIED, status=403, locale=locale)
    if subscription.subscription_status == SubscriptionStatus.CANCELLED.value:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_ALREADY_CANCELLED, status=400, locale=locale)

    row_count = db_update(
        "subscription_info",
        {
            "subscription_status": SubscriptionStatus.CANCELLED.value,
            "status": Status.CANCELLED.value,
            "is_archived": True,
            "modified_by": user_id,
            "modified_date": datetime.now(),
        },
        {"subscription_id": str(subscription_id)},
        connection=db,
        commit=True,
    )
    if row_count == 0:
        raise envelope_exception(ErrorCode.ENTITY_UPDATE_FAILED, status=500, locale=locale, entity="subscription")

    # Build return DTO (get_by_id excludes archived, so we merge updated fields into existing subscription)
    result = SubscriptionDTO(
        subscription_id=subscription.subscription_id,
        user_id=subscription.user_id,
        market_id=subscription.market_id,
        plan_id=subscription.plan_id,
        renewal_date=subscription.renewal_date,
        balance=subscription.balance,
        subscription_status=SubscriptionStatus.CANCELLED.value,
        hold_start_date=subscription.hold_start_date,
        hold_end_date=subscription.hold_end_date,
        early_renewal_threshold=subscription.early_renewal_threshold,
        is_archived=True,
        status=Status.CANCELLED,
        created_date=subscription.created_date,
        created_by=subscription.created_by,
        modified_by=user_id,
        modified_date=datetime.now(),
    )
    return result


def put_subscription_on_hold(
    subscription_id: UUID,
    user_id: UUID,
    hold_start_date: datetime,
    hold_end_date: datetime,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> SubscriptionDTO:
    """Put a subscription on hold. Only owner; only Active (or Pending) can be put on hold. Hold max 3 months.
    Archived subscriptions are excluded by get_by_id so we return 404 for them."""
    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
    if not subscription:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_FOUND, status=404, locale=locale)
    if subscription.user_id != user_id:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_ACCESS_DENIED, status=403, locale=locale)
    if subscription.subscription_status == SubscriptionStatus.ON_HOLD.value:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_ALREADY_ON_HOLD, status=400, locale=locale)
    if subscription.subscription_status == SubscriptionStatus.CANCELLED.value:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_CANNOT_HOLD_CANCELLED, status=400, locale=locale)

    if hold_end_date <= hold_start_date:
        raise envelope_exception(ErrorCode.VALIDATION_SUBSCRIPTION_WINDOW_INVALID, status=400, locale=locale)
    delta = hold_end_date - hold_start_date
    if delta.days > 90:
        raise envelope_exception(ErrorCode.VALIDATION_SUBSCRIPTION_WINDOW_TOO_LONG, status=400, locale=locale)

    updated = subscription_service.update(
        subscription_id,
        {
            "subscription_status": SubscriptionStatus.ON_HOLD.value,
            "hold_start_date": hold_start_date,
            "hold_end_date": hold_end_date,
            "modified_by": user_id,
        },
        db,
        scope=None,
    )
    if not updated:
        raise envelope_exception(ErrorCode.ENTITY_UPDATE_FAILED, status=500, locale=locale, entity="subscription")
    return updated


def resume_subscription(
    subscription_id: UUID,
    user_id: UUID,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> SubscriptionDTO:
    """Resume a subscription from hold. Only owner; only On Hold can be resumed.
    Archived subscriptions are excluded by get_by_id so we return 404 for them."""
    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
    if not subscription:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_FOUND, status=404, locale=locale)
    if subscription.user_id != user_id:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_ACCESS_DENIED, status=403, locale=locale)
    if subscription.subscription_status != SubscriptionStatus.ON_HOLD.value:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_ON_HOLD, status=400, locale=locale)

    updated = subscription_service.update(
        subscription_id,
        {
            "subscription_status": SubscriptionStatus.ACTIVE.value,
            "hold_start_date": None,
            "hold_end_date": None,
            "modified_by": user_id,
        },
        db,
        scope=None,
    )
    if not updated:
        raise envelope_exception(ErrorCode.ENTITY_UPDATE_FAILED, status=500, locale=locale, entity="subscription")
    return updated


def reconcile_hold_subscriptions(db: psycopg2.extensions.connection) -> None:
    """
    Set subscription_status to Active and clear hold dates for subscriptions
    that are On Hold and whose hold_end_date has passed. Skips archived
    subscriptions (is_archived=TRUE). Called before enriched list/by-id so
    clients see correct status.
    """
    now = datetime.now(UTC)
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            UPDATE subscription_info
            SET subscription_status = %s, hold_start_date = NULL, hold_end_date = NULL, modified_date = CURRENT_TIMESTAMP
            WHERE subscription_status = %s AND hold_end_date IS NOT NULL AND hold_end_date <= %s AND is_archived = FALSE
            """,
            (SubscriptionStatus.ACTIVE.value, SubscriptionStatus.ON_HOLD.value, now),
        )
        db.commit()
    finally:
        cursor.close()


def activate_subscription_after_payment(
    subscription_id: UUID,
    modified_by: UUID,
    db: psycopg2.extensions.connection,
    *,
    commit: bool = True,
    locale: str = "en",
) -> SubscriptionDTO:
    """
    Set subscription to Active after successful payment (mock confirm or Stripe webhook).
    Idempotent: no-op if subscription is already Active. Raises 404 if not found.
    Use commit=False when part of a larger transaction (e.g. confirm-payment + create bill).
    """
    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
    if not subscription:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_FOUND, status=404, locale=locale)
    if subscription.subscription_status == SubscriptionStatus.ACTIVE.value:
        return subscription
    updated = subscription_service.update(
        subscription_id,
        {
            "subscription_status": SubscriptionStatus.ACTIVE.value,
            "status": Status.ACTIVE,
            "modified_by": modified_by,
        },
        db,
        scope=None,
        commit=commit,
    )
    if not updated:
        raise envelope_exception(ErrorCode.ENTITY_UPDATE_FAILED, status=500, locale=locale, entity="subscription")
    return updated


def create_and_process_bill_for_subscription_payment(
    subscription_id: UUID,
    subscription_payment_id: UUID,
    modified_by: UUID,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> None:
    """
    Create a client bill for this subscription payment and process it (credits + renewal, status Processed).
    Idempotent: if a bill already exists for this subscription_payment_id, skip create; if not Processed, process it.
    Caller must commit; this function does not commit (for use in confirm-payment or webhook transaction).
    """
    from app.services.billing import process_client_bill_internal
    from app.services.crud_service import (
        client_bill_service,
        get_client_bill_by_subscription_payment,
        plan_service,
    )
    from app.services.market_service import market_service
    from app.utils.db import db_read

    existing = get_client_bill_by_subscription_payment(subscription_payment_id, db)
    if existing:
        if existing.status == Status.PROCESSED:
            return
        process_client_bill_internal(existing.client_bill_id, db, modified_by, commit=False)
        return

    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
    if not subscription:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_FOUND, status=404, locale=locale)
    plan = plan_service.get_by_id(subscription.plan_id, db)
    if not plan:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Plan")
    market = market_service.get_by_id(plan.market_id)
    if not market:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Market")

    sp_row = db_read(
        "SELECT amount_cents, currency FROM subscription_payment WHERE subscription_payment_id = %s",
        (str(subscription_payment_id),),
        connection=db,
        fetch_one=True,
    )
    if not sp_row:
        raise envelope_exception(ErrorCode.SUBSCRIPTION_PAYMENT_NOT_FOUND, status=404, locale=locale)

    amount = float(sp_row["amount_cents"]) / 100.0
    currency_metadata_id = market["currency_metadata_id"]
    currency_code = (sp_row.get("currency") or "USD").upper()

    bill_data = {
        "subscription_payment_id": subscription_payment_id,
        "subscription_id": subscription_id,
        "user_id": subscription.user_id,
        "plan_id": subscription.plan_id,
        "currency_metadata_id": currency_metadata_id,
        "amount": amount,
        "currency_code": currency_code,
        "modified_by": modified_by,
        "status": Status.ACTIVE,
    }
    created = client_bill_service.create(bill_data, db, scope=None, commit=False)
    if not created:
        raise envelope_exception(ErrorCode.ENTITY_CREATION_FAILED, status=500, locale=locale, entity="client bill")
    process_client_bill_internal(created.client_bill_id, db, modified_by, commit=False)
