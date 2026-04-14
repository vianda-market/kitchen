# app/services/cron/notification_banner_cron.py
"""
Notification banner cron job.

Phase 2: Generates reservation_reminder notifications for upcoming pickups
(within 1 hour of their pickup window start) and expires stale notifications.

Intended to run every 15 minutes via Cloud Scheduler.
"""
from typing import Dict, Any
from datetime import datetime

from app.utils.db import get_db_connection, close_db_connection, db_read
from app.utils.log import log_info, log_error, log_warning
from app.services.notification_banner_service import (
    create_notification,
    expire_stale_notifications,
)


def _generate_reservation_reminders(connection) -> int:
    """
    Find active plate selections with a pickup window starting within the next
    hour and create reservation_reminder notifications for each.

    The query joins plate_selection_info with product_info, restaurant_info, and
    the restaurant's address_info to use the **restaurant's** local timezone
    (where the pickup physically happens). This is more accurate than the
    customer's market timezone for multi-TZ countries (US, AR, BR, MX).

    Dedup key ensures each (plate_selection_id, pickup_date) pair only
    generates one notification.
    """
    sql = """
        SELECT
            ps.plate_selection_id,
            ps.user_id,
            ps.pickup_date,
            ps.pickup_time_range,
            p.name  AS plate_name,
            r.name  AS restaurant_name,
            a.timezone
        FROM customer.plate_selection_info ps
        JOIN ops.product_info p   ON p.product_id = ps.product_id
        JOIN ops.restaurant_info r ON r.restaurant_id = ps.restaurant_id
        JOIN core.address_info a  ON a.address_id = r.address_id
        WHERE ps.status = 'active'
          AND ps.is_archived = FALSE
          AND ps.pickup_date = (CURRENT_TIMESTAMP AT TIME ZONE a.timezone)::date
          AND SPLIT_PART(ps.pickup_time_range, '-', 1)::time
              BETWEEN (CURRENT_TIMESTAMP AT TIME ZONE a.timezone)::time
                  AND (CURRENT_TIMESTAMP AT TIME ZONE a.timezone)::time + INTERVAL '1 hour'
    """
    rows = db_read(sql, (), connection=connection)
    created_count = 0

    for row in rows:
        try:
            pickup_window = row["pickup_time_range"]
            pickup_date = row["pickup_date"]
            timezone_str = row["timezone"]

            # Compute expires_at: end of pickup window on pickup_date in market timezone
            end_time_str = pickup_window.split("-")[1] if "-" in pickup_window else "14:30"
            from zoneinfo import ZoneInfo
            end_time = datetime.strptime(end_time_str, "%H:%M").time()
            local_expires = datetime.combine(pickup_date, end_time, tzinfo=ZoneInfo(timezone_str))

            result = create_notification(
                user_id=row["user_id"],
                notification_type="reservation_reminder",
                priority="normal",
                payload={
                    "plate_name": row["plate_name"],
                    "restaurant_name": row["restaurant_name"],
                    "pickup_window": pickup_window,
                    "plate_selection_id": str(row["plate_selection_id"]),
                },
                action_type="view_reservation",
                action_label="View details",
                client_types=["b2c-mobile", "b2c-web"],
                expires_at=local_expires,
                dedup_key=f"reservation_reminder:{row['plate_selection_id']}:{pickup_date}",
                db=connection,
            )
            if result:
                created_count += 1
        except Exception as e:
            log_warning(
                f"Failed to create reservation reminder for selection "
                f"{row['plate_selection_id']}: {e}"
            )

    return created_count


def run_notification_banner_cron() -> Dict[str, Any]:
    """Generate reservation reminders and expire stale notifications."""
    result: Dict[str, Any] = {
        "cron_job": "notification_banners",
        "success": True,
        "reminders_created": 0,
        "notifications_expired": 0,
        "errors": [],
    }
    connection = get_db_connection()
    try:
        reminders = _generate_reservation_reminders(connection)
        result["reminders_created"] = reminders

        expired = expire_stale_notifications(connection)
        result["notifications_expired"] = expired

        log_info(
            f"Notification banner cron completed: "
            f"{reminders} reminders created, {expired} notifications expired"
        )
    except Exception as e:
        result["success"] = False
        result["errors"].append(str(e))
        log_error(f"Notification banner cron failed: {e}")
    finally:
        close_db_connection(connection)
    return result
