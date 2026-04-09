"""
Subscription renewal cron job.

Time-based renewal: find active subscriptions where renewal_date <= now (UTC)
and apply renewal (balance = rolled + plan.credit, renewal_date += 30 days).
No client_bill is created for this path. Safe to run repeatedly (idempotent).
"""

from datetime import datetime, timezone
from typing import Dict, Any
from uuid import UUID

from app.utils.db import db_read, get_db_connection, close_db_connection
from app.utils.log import log_info, log_warning, log_error
from app.config.enums.subscription_status import SubscriptionStatus
from app.services.billing.client_bill import apply_subscription_renewal

# System user for automated operations
SYSTEM_USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def run_subscription_renewals() -> Dict[str, Any]:
    """
    For each active subscription with renewal_date <= now (UTC), apply renewal:
    balance = rolled (capped by plan.rollover_cap) + plan.credit, renewal_date += 30 days.
    Does not create or process client_bill rows.
    """
    now_utc = datetime.now(timezone.utc)
    result: Dict[str, Any] = {
        "cron_job": "subscription_renewals",
        "run_at_utc": now_utc.isoformat(),
        "renewed_count": 0,
        "errors": [],
        "success": True,
    }
    connection = get_db_connection()
    try:
        rows = db_read(
            """
            SELECT subscription_id
            FROM subscription_info
            WHERE is_archived = FALSE
              AND subscription_status = %s
              AND renewal_date <= %s
            """,
            (SubscriptionStatus.ACTIVE.value, now_utc),
            connection=connection,
        )
        if not rows:
            log_info("Subscription renewal cron: no subscriptions due for renewal.")
            return result

        for row in rows:
            subscription_id = row["subscription_id"]
            try:
                apply_subscription_renewal(
                    subscription_id,
                    connection,
                    modified_by=SYSTEM_USER_ID,
                    commit=True,
                )
                result["renewed_count"] += 1
                # Best-effort ads conversion tracking (non-blocking)
                try:
                    import asyncio
                    from app.services.ads.subscription_ads_hook import notify_ads_subscription_renewed
                    asyncio.get_event_loop().create_task(
                        notify_ads_subscription_renewed(subscription_id, connection)
                    )
                except Exception as ads_err:
                    log_warning(f"Ads renewal tracking failed for {subscription_id}: {ads_err}")
            except Exception as e:
                log_error(f"Subscription renewal failed for {subscription_id}: {e}")
                result["errors"].append(f"{subscription_id}: {e}")
                result["success"] = False

        log_info(f"Subscription renewal cron completed: {result}")
        return result
    finally:
        close_db_connection(connection)
