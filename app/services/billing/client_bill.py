# app/services/billing/client_bill.py
"""Client bill processing: process_client_bill_internal and process_completed_bill."""
from datetime import datetime, timedelta, timezone
from uuid import UUID
import psycopg2.extensions
from fastapi import HTTPException
from app.dto.models import ClientBillDTO, SubscriptionDTO, CreditCurrencyDTO
from app.services.crud_service import (
    client_bill_service,
    subscription_service,
    credit_currency_service,
    plan_service,
    update_balance,
)
from app.utils.log import log_info, log_warning
from app.config import Status

# Threshold below which we may trigger early renewal at order time (low-balance guardrail is renewal_date in future)
LOW_BALANCE_RENEWAL_THRESHOLD = 10


def _compute_rolled_credits(balance: float, plan) -> float:
    """Rolled credits for renewal: if rollover true, min(balance, rollover_cap) or balance; else 0."""
    if not getattr(plan, "rollover", True):
        return 0.0
    rolled = float(balance)
    cap = getattr(plan, "rollover_cap", None)
    if cap is not None:
        rolled = min(rolled, float(cap))
    return rolled


def apply_subscription_renewal(
    subscription_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    modified_by: UUID,
    commit: bool = True,
) -> None:
    """
    Apply renewal logic without a bill: set balance = rolled + plan.credit, renewal_date += 30 days.
    Caller is responsible for when to call (e.g. cron when renewal_date <= now, or plate selection when balance < threshold and renewal_date in future).
    """
    subscription = subscription_service.get_by_id(subscription_id, db, scope=None)
    if not subscription:
        raise ValueError("Subscription not found")
    plan = plan_service.get_by_id(subscription.plan_id, db)
    if not plan:
        raise ValueError("Plan not found")
    plan_credit = getattr(plan, "credit", None)
    if plan_credit is None or int(plan_credit) <= 0:
        raise HTTPException(
            status_code=400,
            detail="Plan has no credits; cannot renew.",
        )
    current_balance = float(subscription.balance or 0)
    rolled = _compute_rolled_credits(current_balance, plan)
    new_balance = rolled + float(int(plan_credit))
    renewal_date = subscription.renewal_date
    if renewal_date.tzinfo is None:
        renewal_date = renewal_date.replace(tzinfo=timezone.utc)
    else:
        renewal_date = renewal_date.astimezone(timezone.utc)
    new_renewal_date = renewal_date + timedelta(days=30)
    subscription_service.update(
        subscription_id,
        {
            "balance": new_balance,
            "renewal_date": new_renewal_date,
            "modified_by": modified_by,
        },
        db,
        commit=commit,
    )
    log_info(
        f"Applied subscription renewal {subscription_id}: balance {current_balance} -> {new_balance} (rolled={rolled}, plan.credit={plan_credit}), renewal_date + 30d"
    )


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

    credit_currency = credit_currency_service.get_by_id(bill.credit_currency_id, db)
    if not credit_currency:
        raise Exception("Credit currency not found")

    is_first_period = float(subscription.balance or 0) == 0

    plan = plan_service.get_by_id(bill.plan_id, db)
    if not plan:
        raise HTTPException(status_code=400, detail="Plan not found.")
    plan_credit = getattr(plan, "credit", None)
    if plan_credit is None or int(plan_credit) <= 0:
        raise HTTPException(
            status_code=400,
            detail="Plan has no credits; subscription cannot be activated or renewed.",
        )
    credits_to_add = float(int(plan_credit))
    log_info(f"Granting plan.credit={plan_credit} credits for subscription {bill.subscription_id}")

    now_utc = datetime.now(timezone.utc)
    if is_first_period:
        new_renewal_date = now_utc + timedelta(days=30)
        log_info(f"First period: renewal_date set to activation + 30 days -> {new_renewal_date}")
        update_balance(bill.subscription_id, float(credits_to_add), db, commit=commit)
        subscription_service.update(
            bill.subscription_id,
            {"renewal_date": new_renewal_date},
            db,
            commit=commit,
        )
    else:
        apply_subscription_renewal(
            bill.subscription_id,
            db,
            modified_by=modified_by,
            commit=commit,
        )
    client_bill_service.update(
        client_bill_id,
        {"status": Status.PROCESSED, "modified_by": modified_by},
        db,
        commit=commit,
    )
    if is_first_period:
        log_info(
            f"Processed client bill {client_bill_id}: added {credits_to_add} credits to subscription {bill.subscription_id}"
        )
    else:
        log_info(f"Processed client bill {client_bill_id}: renewal applied for subscription {bill.subscription_id}")
    return True


def process_completed_bill(bill_id: UUID, db: psycopg2.extensions.connection):
    bill = client_bill_service.get_by_id(bill_id, db)
    if not bill or bill.status != Status.COMPLETED:
        return

    subscription = subscription_service.get_by_id(bill.subscription_id, db)
    if not subscription:
        raise Exception("Subscription not found")

    credit_currency = credit_currency_service.get_by_id(bill.credit_currency_id, db)
    if not credit_currency:
        raise Exception("Credit currency not found")

    plan = plan_service.get_by_id(bill.plan_id, db)
    if not plan:
        raise HTTPException(status_code=400, detail="Plan not found.")
    plan_credit = getattr(plan, "credit", None)
    if plan_credit is None or int(plan_credit) <= 0:
        raise HTTPException(
            status_code=400,
            detail="Plan has no credits; subscription cannot be activated or renewed.",
        )
    credits_to_add = float(int(plan_credit))
    new_balance = float(subscription.balance) + credits_to_add

    now_utc = datetime.now(timezone.utc)
    next_utc_midnight = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    new_renewal_date = next_utc_midnight + timedelta(days=29)

    subscription_service.update(
        bill.subscription_id,
        {"balance": new_balance, "renewal_date": new_renewal_date},
        db,
    )
    log_info(f"Added {credits_to_add} credits to subscription {bill.subscription_id}. New balance: {new_balance}. Renewal date set to {new_renewal_date}")
