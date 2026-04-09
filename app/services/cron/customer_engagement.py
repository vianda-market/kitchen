"""
Customer engagement cron job.

Daily job: find Customer users who signed up but haven't subscribed, and send
escalating engagement emails. Distinguishes regular customers from benefit employees.

Rules (regular customers — institution_id = Vianda Customers):
  - no subscription + 2d since signup  → "subscribe to start" email
  - no subscription + 7d since signup  → "you're missing out" email

Rules (benefit employees — institution_id = employer institution):
  - no subscription + 1d since signup  → "your employer benefit is waiting" email
  - no subscription + 5d since signup  → "don't miss your meal benefit" email

Suppression: 3-day cooldown per user via support_email_suppressed_until / last_support_email_date.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from app.services.email_service import email_service
from app.utils.db import db_read, db_update, get_db_connection, close_db_connection
from app.utils.log import log_info, log_warning, log_error
from app.config.settings import get_settings

SYSTEM_USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
EMAIL_COOLDOWN_DAYS = 3


def _is_user_suppressed(user: Dict, now: datetime) -> bool:
    suppressed_until = user.get("support_email_suppressed_until")
    if suppressed_until and suppressed_until > now:
        return True
    last_email = user.get("last_support_email_date")
    if last_email:
        if last_email.tzinfo is None:
            last_email = last_email.replace(tzinfo=timezone.utc)
        if (now - last_email).days < EMAIL_COOLDOWN_DAYS:
            return True
    return False


def _record_user_email_sent(user_id: UUID, now: datetime, connection) -> None:
    cooldown_until = now + timedelta(days=EMAIL_COOLDOWN_DAYS)
    db_update(
        "core.user_info",
        {
            "last_support_email_date": now,
            "support_email_suppressed_until": cooldown_until,
            "modified_by": str(SYSTEM_USER_ID),
            "modified_date": now,
        },
        {"user_id": str(user_id)},
        connection,
        commit=True,
    )


def _get_employer_name(institution_id: UUID, connection) -> Optional[str]:
    """Get the institution name for a benefit employee's employer."""
    row = db_read(
        "SELECT name FROM core.institution_info WHERE institution_id = %s",
        (str(institution_id),),
        connection=connection,
        fetch_one=True,
    )
    return row["name"] if row else None


def _days_since(ref_date: Optional[datetime], now: datetime) -> int:
    if ref_date is None:
        return 0
    if ref_date.tzinfo is None:
        ref_date = ref_date.replace(tzinfo=timezone.utc)
    return (now - ref_date).days


def run_customer_engagement() -> Dict[str, Any]:
    """
    Find customers without active subscriptions and send engagement emails.
    """
    now_utc = datetime.now(timezone.utc)
    settings = get_settings()
    vianda_customers_id = settings.VIANDA_CUSTOMERS_INSTITUTION_ID

    result: Dict[str, Any] = {
        "cron_job": "customer_engagement",
        "run_at_utc": now_utc.isoformat(),
        "users_checked": 0,
        "emails_sent": 0,
        "emails_suppressed": 0,
        "errors": [],
        "success": True,
    }

    connection = get_db_connection()
    try:
        # Find active Customer users without an active subscription
        users = db_read(
            """
            SELECT u.user_id, u.email, u.first_name, u.institution_id,
                   u.created_date, u.email_verified,
                   u.support_email_suppressed_until, u.last_support_email_date,
                   u.locale
            FROM core.user_info u
            WHERE u.role_type = 'customer'
              AND u.status = 'active'
              AND NOT u.is_archived
              AND NOT EXISTS (
                  SELECT 1 FROM customer.subscription_info s
                  WHERE s.user_id = u.user_id
                    AND s.subscription_status = 'active'
                    AND NOT s.is_archived
              )
            """,
            connection=connection,
        )

        if not users:
            log_info("Customer engagement cron: no unsubscribed customers found.")
            return result

        result["users_checked"] = len(users)

        for user in users:
            user_id = user["user_id"]
            email = user["email"]
            first_name = user.get("first_name") or "there"
            institution_id = user["institution_id"]
            days_since_signup = _days_since(user["created_date"], now_utc)
            locale = user.get("locale") or "en"

            try:
                if _is_user_suppressed(user, now_utc):
                    result["emails_suppressed"] += 1
                    continue

                is_benefit_employee = str(institution_id) != vianda_customers_id
                sent = False

                if is_benefit_employee:
                    employer_name = _get_employer_name(institution_id, connection) or "your employer"
                    if days_since_signup >= 5:
                        sent = email_service.send_benefit_reminder_email(
                            to_email=email, user_first_name=first_name,
                            employer_name=employer_name, locale=locale,
                        )
                    elif days_since_signup >= 1:
                        sent = email_service.send_benefit_waiting_email(
                            to_email=email, user_first_name=first_name,
                            employer_name=employer_name, locale=locale,
                        )
                else:
                    if days_since_signup >= 7:
                        sent = email_service.send_customer_missing_out_email(
                            to_email=email, user_first_name=first_name, locale=locale,
                        )
                    elif days_since_signup >= 2:
                        sent = email_service.send_customer_subscribe_email(
                            to_email=email, user_first_name=first_name, locale=locale,
                        )

                if sent:
                    _record_user_email_sent(user_id, now_utc, connection)
                    result["emails_sent"] += 1

            except Exception as e:
                log_error(f"Customer engagement error for user {user_id}: {e}")
                result["errors"].append(f"{user_id}: {e}")
                result["success"] = False

        log_info(f"Customer engagement cron completed: {result}")
        return result

    finally:
        close_db_connection(connection)
