"""
Push Notification Service — Send FCM notifications for pickup events.

Uses firebase-admin SDK when FIREBASE_CREDENTIALS_PATH is configured.
When not configured (dev), logs the notification instead of sending.
"""

from __future__ import annotations

from uuid import UUID

import psycopg2.extensions

from app.config.settings import settings
from app.services.fcm_token_service import delete_fcm_token_by_value, get_user_fcm_tokens
from app.utils.db import db_read
from app.utils.log import log_error, log_info, log_warning

_firebase_initialized = False


def _ensure_firebase():
    """Initialize firebase-admin app if not already done. No-op if credentials not configured."""
    global _firebase_initialized
    if _firebase_initialized:
        return True
    if not settings.FIREBASE_CREDENTIALS_PATH:
        return False
    try:
        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        log_info("Firebase Admin SDK initialized")
        return True
    except Exception as e:
        log_error(f"Failed to initialize Firebase Admin SDK: {e}")
        return False


def send_handed_out_push(
    user_id: UUID,
    plate_pickup_id: UUID,
    restaurant_name: str,
    db: psycopg2.extensions.connection,
) -> None:
    """
    Send push notification when a plate pickup transitions to Handed Out.

    Checks user's messaging preferences before sending. Handles stale tokens.
    Fails silently — push is best-effort, never blocks the handoff flow.
    """
    try:
        # 1. Check messaging preferences
        prefs = db_read(
            "SELECT notify_plate_readiness_alert FROM user_messaging_preferences WHERE user_id = %s",
            (str(user_id),),
            connection=db,
            fetch_one=True,
        )
        if prefs and not prefs.get("notify_plate_readiness_alert", True):
            log_info(f"Push skipped for user {user_id}: plate_readiness_alert disabled")
            return

        # 2. Get user's FCM tokens
        tokens = get_user_fcm_tokens(user_id, db)
        if not tokens:
            log_info(f"No FCM tokens for user {user_id}, skipping push")
            return

        # 3. Check if Firebase is available
        if not _ensure_firebase():
            log_warning(
                f"Firebase not configured — would send 'Handed Out' push to user {user_id} "
                f"for pickup {plate_pickup_id} at {restaurant_name}"
            )
            return

        # 4. Send to each token
        from firebase_admin import messaging

        notification = messaging.Notification(
            title="Plate ready",
            body=f"Did you receive your plate from {restaurant_name}?",
        )
        data = {
            "type": "pickup_handed_out",
            "plate_pickup_id": str(plate_pickup_id),
            "restaurant_name": restaurant_name,
        }

        for token_row in tokens:
            token_str = token_row["token"]
            try:
                message = messaging.Message(
                    notification=notification,
                    data=data,
                    token=token_str,
                )
                messaging.send(message)
                log_info(f"Push sent to user {user_id} on {token_row['platform']}")
            except Exception as send_err:
                err_str = str(send_err)
                if "NotRegistered" in err_str or "InvalidRegistration" in err_str:
                    delete_fcm_token_by_value(token_str, db)
                else:
                    log_error(f"FCM send failed for user {user_id}: {send_err}")

    except Exception as e:
        # Push is best-effort — never block the handoff flow
        log_error(f"Push notification failed for user {user_id}: {e}")
