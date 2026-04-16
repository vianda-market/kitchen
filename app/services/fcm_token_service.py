"""
FCM Token Service — Register, upsert, and delete Firebase Cloud Messaging device tokens.

Tokens are ephemeral device data. Each user can have multiple tokens (multiple devices).
A single token can only belong to one user at a time (device changed hands = reassign).
"""

from uuid import UUID

import psycopg2.extensions

from app.utils.db import db_read, db_write
from app.utils.log import log_info


def register_fcm_token(
    user_id: UUID,
    token: str,
    platform: str,
    db: psycopg2.extensions.connection,
) -> None:
    """
    Register or update an FCM device token for a user.

    - If the token already exists for any user, reassign it to this user (device changed hands).
    - If new, insert it.
    """
    # Check if token already exists
    existing = db_read(
        "SELECT fcm_token_id, user_id FROM user_fcm_token WHERE token = %s",
        (token,),
        connection=db,
        fetch_one=True,
    )

    if existing:
        # Token exists — update to current user and refresh timestamp
        db_write(
            """UPDATE user_fcm_token
               SET user_id = %s, platform = %s, updated_date = CURRENT_TIMESTAMP
               WHERE fcm_token_id = %s""",
            (str(user_id), platform, str(existing["fcm_token_id"])),
            connection=db,
        )
        log_info(f"FCM token reassigned to user {user_id} (was {existing['user_id']})")
    else:
        # New token — insert
        db_write(
            """INSERT INTO user_fcm_token (user_id, token, platform)
               VALUES (%s, %s, %s)""",
            (str(user_id), token, platform),
            connection=db,
        )
        log_info(f"FCM token registered for user {user_id} on {platform}")

    db.commit()


def delete_user_fcm_tokens(
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> int:
    """Delete all FCM tokens for a user (called on logout). Returns count deleted."""
    result = db_write(
        "DELETE FROM user_fcm_token WHERE user_id = %s",
        (str(user_id),),
        connection=db,
    )
    db.commit()
    count = result if isinstance(result, int) else 0
    log_info(f"Deleted {count} FCM token(s) for user {user_id}")
    return count


def get_user_fcm_tokens(
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> list:
    """Get all active FCM tokens for a user."""
    rows = db_read(
        "SELECT token, platform FROM user_fcm_token WHERE user_id = %s",
        (str(user_id),),
        connection=db,
    )
    return rows or []


def delete_fcm_token_by_value(
    token: str,
    db: psycopg2.extensions.connection,
) -> None:
    """Delete a single FCM token by its value (used when FCM returns NotRegistered/InvalidRegistration)."""
    db_write(
        "DELETE FROM user_fcm_token WHERE token = %s",
        (token,),
        connection=db,
    )
    db.commit()
    log_info(f"Deleted stale FCM token: {token[:20]}...")
