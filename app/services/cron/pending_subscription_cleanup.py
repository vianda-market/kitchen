"""
Pending subscription cleanup cron job.

Cancels subscriptions that have been in Pending status for more than 24 hours
and were never paid. Cancels associated Stripe PaymentIntents and marks
subscription_payment rows as cancelled so we do not leave orphan intents.
Safe to run repeatedly (idempotent).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.config import Status
from app.config.enums.subscription_status import SubscriptionStatus
from app.services.payment_provider import cancel_payment_intent
from app.utils.db import close_db_connection, db_read, db_update, get_db_connection
from app.utils.log import log_error, log_info, log_warning

# System user for automated operations
SYSTEM_USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

# How long a Pending subscription can exist before we cancel it (hours)
PENDING_MAX_AGE_HOURS = 24


def run_pending_subscription_cleanup() -> dict[str, Any]:
    """
    Cancel Pending subscriptions older than 24 hours (never paid).
    For each: cancel Stripe PaymentIntents for pending payment rows,
    mark those rows cancelled, set subscription to Cancelled.
    Idempotent; safe to run daily or every few hours.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=PENDING_MAX_AGE_HOURS)
    result = {
        "cron_job": "pending_subscription_cleanup",
        "cutoff_iso": cutoff.isoformat(),
        "subscriptions_cancelled": 0,
        "payment_intents_cancelled": 0,
        "errors": [],
        "success": True,
    }
    connection = get_db_connection()
    try:
        rows = db_read(
            """
            SELECT subscription_id, user_id, market_id, plan_id, created_date
            FROM subscription_info
            WHERE subscription_status = %s AND is_archived = FALSE AND created_date < %s
            """,
            (SubscriptionStatus.PENDING.value, cutoff),
            connection=connection,
        )
        if not rows:
            log_info("Pending subscription cleanup: no stale Pending subscriptions found.")
            return result

        for sub in rows:
            subscription_id = sub["subscription_id"]
            try:
                payment_rows = db_read(
                    """
                    SELECT subscription_payment_id, external_payment_id, status
                    FROM subscription_payment
                    WHERE subscription_id = %s::uuid AND status = 'pending'
                    """,
                    (str(subscription_id),),
                    connection=connection,
                )
                for prow in payment_rows or []:
                    try:
                        cancel_payment_intent(str(prow["external_payment_id"]))
                        result["payment_intents_cancelled"] += 1
                    except Exception as e:
                        log_warning(f"Failed to cancel payment intent {prow.get('external_payment_id')}: {e}")
                        result["errors"].append(f"cancel_intent {subscription_id}: {e}")
                    db_update(
                        "subscription_payment",
                        {"status": "cancelled"},
                        {"subscription_payment_id": str(prow["subscription_payment_id"])},
                        connection=connection,
                        commit=False,
                    )
                db_update(
                    "subscription_info",
                    {
                        "subscription_status": SubscriptionStatus.CANCELLED.value,
                        "status": Status.CANCELLED.value,
                        "is_archived": True,
                        "modified_by": str(SYSTEM_USER_ID),
                    },
                    {"subscription_id": str(subscription_id)},
                    connection=connection,
                    commit=False,
                )
                connection.commit()
                result["subscriptions_cancelled"] += 1
                log_info(f"Cancelled stale Pending subscription {subscription_id}")
            except Exception as e:
                connection.rollback()
                log_error(f"Error cancelling subscription {subscription_id}: {e}")
                result["errors"].append(f"subscription {subscription_id}: {e}")
                result["success"] = False

        return result
    finally:
        close_db_connection(connection)
