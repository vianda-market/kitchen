# app/services/ads/click_tracking_service.py
"""
Ad click tracking: capture and query click identifiers from frontend.

Click identifiers (gclid, fbclid, fbc, fbp, etc.) are captured by the
frontend on landing and passed to the backend when the user subscribes.
These are stored in ad_click_tracking and used by the conversion upload
pipeline to attribute conversions to ad clicks.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

import psycopg2.extensions

from app.utils.db import db_read

logger = logging.getLogger(__name__)


def create_click_tracking(
    user_id: UUID,
    data: dict,
    db: psycopg2.extensions.connection,
) -> dict:
    """
    Store ad click identifiers captured by the frontend.

    Called when the frontend submits click IDs (typically during subscription creation).
    Idempotent: if a record already exists for this user + subscription_id, returns existing.

    Args:
        user_id: The authenticated user.
        data: Fields from AdClickTrackingCreateSchema.
        db: DB connection.

    Returns:
        The created or existing click tracking record.
    """
    subscription_id = data.get("subscription_id")

    # Idempotency: check if we already have a record for this subscription
    if subscription_id:
        existing = db_read(
            "SELECT * FROM core.ad_click_tracking WHERE user_id = %s::uuid AND subscription_id = %s::uuid",
            (str(user_id), str(subscription_id)),
            connection=db,
            fetch_one=True,
        )
        if existing:
            return existing

    now = datetime.now(timezone.utc)
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO core.ad_click_tracking (
                user_id, subscription_id,
                gclid, wbraid, gbraid,
                fbclid, fbc, fbp,
                event_id, landing_url, source_platform,
                captured_at, created_date, modified_date
            ) VALUES (
                %s::uuid, %s::uuid,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            ) RETURNING id
            """,
            (
                str(user_id),
                str(subscription_id) if subscription_id else None,
                data.get("gclid"), data.get("wbraid"), data.get("gbraid"),
                data.get("fbclid"), data.get("fbc"), data.get("fbp"),
                data.get("event_id"), data.get("landing_url"), data.get("source_platform"),
                now, now, now,
            ),
        )
        row = cursor.fetchone()
        db.commit()
        tracking_id = row[0] if row else None
        logger.info(
            "click_tracking_created",
            extra={
                "tracking_id": str(tracking_id),
                "user_id": str(user_id),
                "source_platform": data.get("source_platform"),
            },
        )
        return get_click_tracking_by_id(tracking_id, db)
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()


def get_click_tracking_by_id(
    tracking_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict | None:
    """Get a click tracking record by ID."""
    return db_read(
        "SELECT * FROM core.ad_click_tracking WHERE id = %s::uuid",
        (str(tracking_id),),
        connection=db,
        fetch_one=True,
    )


def get_click_tracking_for_subscription(
    subscription_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict | None:
    """Get the most recent click tracking record for a subscription."""
    return db_read(
        """
        SELECT * FROM core.ad_click_tracking
        WHERE subscription_id = %s::uuid
        ORDER BY captured_at DESC
        LIMIT 1
        """,
        (str(subscription_id),),
        connection=db,
        fetch_one=True,
    )
