"""
Notification Banner Routes

In-app notification banners for B2C clients (mobile + web).
Frontends poll GET /active on a 60-second interval.
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_client_user, get_employee_user
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    ActiveNotificationsResponseSchema,
    NotificationAcknowledgeSchema,
    NotificationActionSchema,
    NotificationBannerResponseSchema,
)
from app.services.notification_banner_service import (
    acknowledge_notification,
    expire_stale_notifications,
    get_active_notifications,
)
from app.utils.log import log_error

router = APIRouter(
    prefix="/notifications",
    tags=["Notification Banners"],
)


@router.get("/active", response_model=ActiveNotificationsResponseSchema)
def get_active(
    client_type: str | None = Query(None, description="Filter by client type: b2c-mobile or b2c-web"),
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Return active notification banners for the authenticated user."""
    try:
        user_id = current_user["user_id"]
        rows = get_active_notifications(user_id, client_type, db)

        notifications = [
            NotificationBannerResponseSchema(
                notification_id=row["notification_id"],
                notification_type=row["notification_type"],
                priority=row["priority"],
                created_at=row["created_at"],
                expires_at=row["expires_at"],
                payload=row["payload"],
                action=NotificationActionSchema(
                    action_type=row["action"]["action_type"],
                    action_label=row["action"]["action_label"],
                ),
            )
            for row in rows
        ]

        return ActiveNotificationsResponseSchema(notifications=notifications)
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error fetching active notifications: {e}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None


@router.post("/{notification_id}/acknowledge")
def acknowledge(
    notification_id: UUID,
    payload: NotificationAcknowledgeSchema,
    current_user: dict = Depends(get_client_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Mark a notification as dismissed, opened, or completed."""
    try:
        user_id = current_user["user_id"]
        acknowledge_notification(notification_id, user_id, payload.action_taken, db)
        return {"status": "acknowledged"}
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error acknowledging notification {notification_id}: {e}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None


@router.post("/expire")
def expire_notifications(
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Bulk-expire stale notifications. Internal only (cron trigger)."""
    try:
        count = expire_stale_notifications(db)
        return {"expired_count": count}
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error expiring notifications: {e}")
        raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale="en") from None


@router.post("/generate-reminders", status_code=200)
def generate_reminders(
    current_user: dict = Depends(get_employee_user),
):
    """Run notification banner cron: generate reservation reminders + expire stale. Internal only."""
    from app.services.cron.notification_banner_cron import run_notification_banner_cron

    return run_notification_banner_cron()
