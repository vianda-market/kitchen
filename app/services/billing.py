import math
from datetime import datetime, timedelta, timezone
from uuid import UUID
import psycopg2.extensions
from app.dto.models import ClientBillDTO, SubscriptionDTO, CreditCurrencyDTO
from app.services.crud_service import client_bill_service, subscription_service, credit_currency_service
from app.utils.log import log_info, log_warning
from app.config import Status

def process_completed_bill(bill_id: UUID, db: psycopg2.extensions.connection):
    bill = client_bill_service.get_by_id(bill_id, db)
    if not bill or bill.status != Status.COMPLETE:
        return

    subscription = subscription_service.get_by_id(bill.subscription_id, db)
    if not subscription:
        raise Exception("Subscription not found")

    credit_currency = credit_currency_service.get_by_id(bill.credit_currency_id, db)
    if not credit_currency:
        raise Exception("Credit currency not found")

    credits_to_add = math.ceil(float(bill.amount) / float(credit_currency.credit_value))
    new_balance = float(subscription.balance) + credits_to_add

    # Calculate new renewal_date: today (UTC) + 30 days, rounded up to next day at 00:00 UTC
    now_utc = datetime.now(timezone.utc)
    next_utc_midnight = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    new_renewal_date = next_utc_midnight + timedelta(days=29)  # total 30 days from now, rounded up

    subscription_service.update(
        bill.subscription_id,
        {"balance": new_balance, "renewal_date": new_renewal_date},
        db
    )

    # Note: Subscription status activation (Pending -> Active) is handled automatically
    # by the database trigger subscription_status_activation_trigger() when balance
    # transitions from <= 0 to > 0 for Pending subscriptions.

    log_info(f"Added {credits_to_add} credits to subscription {bill.subscription_id}. New balance: {new_balance}. Renewal date set to {new_renewal_date}")
