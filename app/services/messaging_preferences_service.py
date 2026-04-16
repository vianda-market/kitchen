"""
Messaging preferences service for user notification toggles.

Provides get and update for messaging preference booleans.
On first GET, creates default row (all True) if missing.
"""

from datetime import UTC, datetime
from uuid import UUID

import psycopg2.extensions

from app.dto.models import MessagingPreferencesDTO
from app.utils.db import db_insert, db_read, db_update


def get_messaging_preferences(
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> MessagingPreferencesDTO:
    """
    Get user's messaging preferences. Creates default row (all True) if missing.

    Args:
        user_id: User ID
        db: Database connection

    Returns:
        MessagingPreferencesDTO with all preference booleans
    """
    row = db_read(
        """
        SELECT user_id, notify_coworker_pickup_alert, notify_plate_readiness_alert,
               notify_promotions_push, notify_promotions_email,
               coworkers_can_see_my_orders, can_participate_in_plate_pickups,
               created_date, modified_date
        FROM user_messaging_preferences
        WHERE user_id = %s
        """,
        (str(user_id),),
        connection=db,
        fetch_one=True,
    )
    if not row:
        # Create default row
        datetime.now(UTC)
        db_insert(
            "user_messaging_preferences",
            {
                "user_id": user_id,
                "notify_coworker_pickup_alert": True,
                "notify_plate_readiness_alert": True,
                "notify_promotions_push": True,
                "notify_promotions_email": True,
                "coworkers_can_see_my_orders": True,
                "can_participate_in_plate_pickups": True,
            },
            connection=db,
        )
        row = db_read(
            """
            SELECT user_id, notify_coworker_pickup_alert, notify_plate_readiness_alert,
                   notify_promotions_push, notify_promotions_email,
                   coworkers_can_see_my_orders, can_participate_in_plate_pickups,
                   created_date, modified_date
            FROM user_messaging_preferences
            WHERE user_id = %s
            """,
            (str(user_id),),
            connection=db,
            fetch_one=True,
        )
    return MessagingPreferencesDTO(**row)


def update_messaging_preferences(
    user_id: UUID,
    update_data: dict,
    db: psycopg2.extensions.connection,
) -> MessagingPreferencesDTO:
    """
    Update user's messaging preferences. Only updates fields present in update_data.

    Args:
        user_id: User ID
        update_data: Dict with optional preference booleans (notify_*, coworkers_can_see_my_orders, can_participate_in_plate_pickups)
        db: Database connection

    Returns:
        Updated MessagingPreferencesDTO
    """
    # Ensure row exists
    get_messaging_preferences(user_id, db)

    # Filter to only allowed fields and non-None values
    allowed = {
        "notify_coworker_pickup_alert",
        "notify_plate_readiness_alert",
        "notify_promotions_push",
        "notify_promotions_email",
        "coworkers_can_see_my_orders",
        "can_participate_in_plate_pickups",
    }
    to_update = {k: v for k, v in update_data.items() if k in allowed and v is not None}
    if not to_update:
        return get_messaging_preferences(user_id, db)

    # Cascade: when can_participate_in_plate_pickups is set to False, also set coworkers_can_see_my_orders
    # and notify_coworker_pickup_alert to False (user won't receive coworker pickup messages if not participating)
    if to_update.get("can_participate_in_plate_pickups") is False:
        to_update["coworkers_can_see_my_orders"] = False
        to_update["notify_coworker_pickup_alert"] = False

    to_update["modified_date"] = datetime.now(UTC)

    db_update(
        "user_messaging_preferences",
        to_update,
        {"user_id": user_id},
        connection=db,
    )
    return get_messaging_preferences(user_id, db)
