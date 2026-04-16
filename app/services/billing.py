import math
from datetime import UTC, datetime, timedelta
from uuid import UUID

import psycopg2.extensions

from app.config import Status
from app.services.crud_service import (
    client_bill_service,
    credit_currency_service,
    subscription_service,
    update_balance,
)
from app.utils.log import log_info


def process_client_bill_internal(
    client_bill_id: UUID,
    db: psycopg2.extensions.connection,
    modified_by: UUID,
    *,
    commit: bool = True,
) -> bool:
    """
    Process a client bill: add credits to subscription balance, set renewal_date, mark bill Processed.
    Idempotent: no-op if bill is already Processed. Use commit=False for atomic multi-step transactions.
    """
    bill = client_bill_service.get_by_id(client_bill_id, db)
    if not bill:
        return False
    if bill.status == Status.PROCESSED:
        log_info(f"Client bill {client_bill_id} already Processed, skipping")
        return True

    subscription = subscription_service.get_by_id(bill.subscription_id, db)
    if not subscription:
        raise Exception("Subscription not found")

    credit_currency = credit_currency_service.get_by_id(bill.currency_metadata_id, db)
    if not credit_currency:
        raise Exception("Credit currency not found")

    credits_to_add = math.ceil(float(bill.amount) / float(credit_currency.credit_value_local_currency))
    renewal_date = subscription.renewal_date
    if renewal_date.tzinfo is None:
        renewal_date = renewal_date.replace(tzinfo=UTC)
    else:
        renewal_date = renewal_date.astimezone(UTC)
    new_renewal_date = renewal_date + timedelta(days=30)

    update_balance(bill.subscription_id, float(credits_to_add), db, commit=commit)
    subscription_service.update(
        bill.subscription_id,
        {"renewal_date": new_renewal_date},
        db,
        commit=commit,
    )
    client_bill_service.update(
        client_bill_id,
        {"status": Status.PROCESSED, "modified_by": modified_by},
        db,
        commit=commit,
    )
    log_info(
        f"Processed client bill {client_bill_id}: added {credits_to_add} credits to subscription {bill.subscription_id}"
    )
    return True


def process_completed_bill(bill_id: UUID, db: psycopg2.extensions.connection):
    bill = client_bill_service.get_by_id(bill_id, db)
    if not bill or bill.status != Status.COMPLETED:
        return

    subscription = subscription_service.get_by_id(bill.subscription_id, db)
    if not subscription:
        raise Exception("Subscription not found")

    credit_currency = credit_currency_service.get_by_id(bill.currency_metadata_id, db)
    if not credit_currency:
        raise Exception("Credit currency not found")

    credits_to_add = math.ceil(float(bill.amount) / float(credit_currency.credit_value_local_currency))
    new_balance = float(subscription.balance) + credits_to_add

    # Calculate new renewal_date: today (UTC) + 30 days, rounded up to next day at 00:00 UTC
    now_utc = datetime.now(UTC)
    next_utc_midnight = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    new_renewal_date = next_utc_midnight + timedelta(days=29)  # total 30 days from now, rounded up

    subscription_service.update(bill.subscription_id, {"balance": new_balance, "renewal_date": new_renewal_date}, db)

    # Note: Subscription status activation (Pending -> Active) is handled automatically
    # by the database trigger subscription_status_activation_trigger() when balance
    # transitions from <= 0 to > 0 for Pending subscriptions.

    log_info(
        f"Added {credits_to_add} credits to subscription {bill.subscription_id}. New balance: {new_balance}. Renewal date set to {new_renewal_date}"
    )
