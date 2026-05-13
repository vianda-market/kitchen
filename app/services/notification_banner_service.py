"""
Notification Banner Service

Creates, queries, and manages in-app notification banners for B2C clients.
Banners complement push notifications — push for background, banners for foreground.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg2.extensions
import psycopg2.extras
from fastapi import HTTPException

from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.utils.db import db_read
from app.utils.log import log_error, log_info, log_warning

REQUIRED_PAYLOAD_FIELDS = {
    "survey_available": {"vianda_name", "pickup_date", "vianda_selection_id", "vianda_pickup_id"},
    "peer_pickup_volunteer": {"coworker_name", "restaurant_name", "pickup_window", "peer_pickup_id"},
    "reservation_reminder": {"vianda_name", "restaurant_name", "pickup_window", "vianda_selection_id"},
}


def create_notification(
    user_id: UUID,
    notification_type: str,
    priority: str,
    payload: dict,
    action_type: str,
    action_label: str,
    client_types: list[str],
    expires_at: datetime,
    dedup_key: str,
    db: psycopg2.extensions.connection,
) -> str | None:
    """
    Create a notification banner. Deduplicates by (user_id, dedup_key).

    Returns notification_id if created, None if deduplicated.
    """
    required = REQUIRED_PAYLOAD_FIELDS.get(notification_type)
    if required:
        missing = required - set(payload.keys())
        if missing:
            log_warning(f"Notification payload missing fields {missing} for type {notification_type}")
            return None

    sql = """
        INSERT INTO customer.notification_banner (
            user_id, notification_type, priority, payload,
            action_type, action_label, client_types,
            action_status, expires_at, dedup_key
        ) VALUES (
            %s, %s::notification_banner_type_enum, %s::notification_banner_priority_enum,
            %s, %s, %s, %s,
            'active'::notification_banner_action_status_enum, %s, %s
        )
        ON CONFLICT (user_id, dedup_key) DO NOTHING
        RETURNING notification_id
    """
    params = (
        str(user_id),
        notification_type,
        priority,
        psycopg2.extras.Json(payload),
        action_type,
        action_label,
        client_types,
        expires_at,
        dedup_key,
    )

    cursor = db.cursor()
    try:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        db.commit()
        if row:
            notification_id = str(row[0])
            log_info(f"Created notification banner {notification_id} for user {user_id} (type={notification_type})")
            return notification_id
        log_info(f"Notification banner dedup'd for user {user_id} (dedup_key={dedup_key})")
        return None
    except Exception as e:
        db.rollback()
        log_error(f"Failed to create notification banner: {e}")
        raise


def get_active_notifications(
    user_id: UUID,
    client_type: str | None,
    db: psycopg2.extensions.connection,
) -> list[dict[str, Any]]:
    """
    Get active, unexpired notifications for a user, filtered by client type.
    Survey notifications respect a 2-hour grace period after creation.
    Returns max 5, high priority first.
    """
    base_sql = """
        SELECT notification_id, notification_type, priority, payload,
               action_type, action_label, expires_at, created_date
        FROM customer.notification_banner
        WHERE user_id = %s
          AND action_status = 'active'
          AND expires_at > NOW()
          AND (
              notification_type != 'survey_available'
              OR created_date + INTERVAL '2 hours' <= NOW()
          )
    """
    params: list = [str(user_id)]

    if client_type:
        base_sql += " AND client_types @> ARRAY[%s]::varchar[]"
        params.append(client_type)

    base_sql += """
        ORDER BY
            CASE WHEN priority = 'high' THEN 0 ELSE 1 END,
            created_date DESC
        LIMIT 5
    """

    rows = db_read(base_sql, tuple(params), connection=db)

    notifications = []
    for row in rows:
        notifications.append(
            {
                "notification_id": row["notification_id"],
                "notification_type": row["notification_type"],
                "priority": row["priority"],
                "created_at": row["created_date"],
                "expires_at": row["expires_at"],
                "payload": row["payload"],
                "action": {
                    "action_type": row["action_type"],
                    "action_label": row["action_label"],
                },
            }
        )

    return notifications


def acknowledge_notification(
    notification_id: UUID,
    user_id: UUID,
    action_taken: str,
    db: psycopg2.extensions.connection,
) -> bool:
    """
    Mark a notification as dismissed/opened/completed.
    Idempotent: re-acknowledging returns True without update.
    Raises 404 if notification not found or not owned by user.
    """
    sql = """
        UPDATE customer.notification_banner
        SET action_status = %s::notification_banner_action_status_enum,
            acknowledged_at = CURRENT_TIMESTAMP,
            modified_date = CURRENT_TIMESTAMP
        WHERE notification_id = %s
          AND user_id = %s
          AND action_status = 'active'
    """
    cursor = db.cursor()
    try:
        cursor.execute(sql, (action_taken, str(notification_id), str(user_id)))
        updated = cursor.rowcount
        db.commit()

        if updated > 0:
            log_info(f"Notification {notification_id} acknowledged as {action_taken}")
            return True

        # Check if it exists but was already acknowledged (idempotent)
        existing = db_read(
            "SELECT action_status FROM customer.notification_banner WHERE notification_id = %s AND user_id = %s",
            (str(notification_id), str(user_id)),
            connection=db,
            fetch_one=True,
        )
        if existing:
            return True

        raise envelope_exception(ErrorCode.NOTIFICATION_NOT_FOUND, status=404, locale="en")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log_error(f"Failed to acknowledge notification {notification_id}: {e}")
        raise envelope_exception(ErrorCode.NOTIFICATION_ACKNOWLEDGE_FAILED, status=500, locale="en") from None


def expire_stale_notifications(
    db: psycopg2.extensions.connection,
) -> int:
    """
    Bulk-expire notifications past their expires_at timestamp.
    Returns count of expired rows.
    """
    sql = """
        UPDATE customer.notification_banner
        SET action_status = 'expired'::notification_banner_action_status_enum,
            modified_date = CURRENT_TIMESTAMP
        WHERE action_status = 'active'
          AND expires_at <= NOW()
    """
    cursor = db.cursor()
    try:
        cursor.execute(sql)
        count = cursor.rowcount
        db.commit()
        if count > 0:
            log_info(f"Expired {count} stale notification banners")
        return count
    except Exception as e:
        db.rollback()
        log_error(f"Failed to expire stale notifications: {e}")
        raise
