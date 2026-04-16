# app/services/cron/referral_cron.py
"""
Referral cron job.

Retries held rewards for referrers who now have active subscriptions,
and expires stale pending referrals past their market's expiry window.
"""

from typing import Any

from app.services.referral_service import expire_stale_pending_referrals, retry_held_rewards
from app.utils.db import close_db_connection, get_db_connection
from app.utils.log import log_error, log_info


def _cleanup_expired_assignments(connection) -> int:
    """Delete referral_code_assignment rows older than 48 hours. Returns count deleted."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            "DELETE FROM referral_code_assignment WHERE created_at < (CURRENT_TIMESTAMP - INTERVAL '48 hours')"
        )
        deleted = cursor.rowcount
        connection.commit()
        return deleted
    finally:
        cursor.close()


def run_referral_cron() -> dict[str, Any]:
    """Retry held rewards, expire stale pending referrals, clean up expired code assignments."""
    result: dict[str, Any] = {
        "cron_job": "referral_rewards",
        "success": True,
        "held_retried": 0,
        "pending_expired": 0,
        "assignments_cleaned": 0,
        "errors": [],
    }
    connection = get_db_connection()
    try:
        held_count = retry_held_rewards(connection)
        result["held_retried"] = held_count

        expired_count = expire_stale_pending_referrals(connection)
        result["pending_expired"] = expired_count

        cleaned = _cleanup_expired_assignments(connection)
        result["assignments_cleaned"] = cleaned

        log_info(
            f"Referral cron completed: {held_count} held retried, {expired_count} pending expired, {cleaned} assignments cleaned"
        )
    except Exception as e:
        result["success"] = False
        result["errors"].append(str(e))
        log_error(f"Referral cron failed: {e}")
    finally:
        close_db_connection(connection)
    return result
