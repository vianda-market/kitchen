"""
Favorite Service

Business logic for user favorites (plates and restaurants).
Users can flag plates and restaurants as favorites; favorites are surfaced at the top of explore results.
"""

from uuid import UUID

import psycopg2.extensions

from app.config.enums import FavoriteEntityType
from app.dto.models import UserFavoriteDTO
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.utils.db import db_insert, db_read
from app.utils.log import log_info


def add_favorite(
    user_id: UUID,
    entity_type: str,
    entity_id: UUID,
    db: psycopg2.extensions.connection,
) -> UserFavoriteDTO:
    """
    Add a favorite. Validates that the plate or restaurant exists.

    Args:
        user_id: Current user (Customer)
        entity_type: 'plate' or 'restaurant'
        entity_id: plate_id or restaurant_id
        db: Database connection

    Returns:
        UserFavoriteDTO of the created favorite

    Raises:
        HTTPException: 400 if invalid entity_type, already favorited, or entity not found
    """
    if not FavoriteEntityType.is_valid(entity_type):
        raise envelope_exception(ErrorCode.FAVORITE_ENTITY_TYPE_INVALID, status=400, locale="en")

    # Validate entity exists
    if entity_type == "plate":
        row = db_read(
            "SELECT plate_id FROM plate_info WHERE plate_id = %s AND is_archived = FALSE",
            (str(entity_id),),
            connection=db,
            fetch_one=True,
        )
    else:
        row = db_read(
            "SELECT restaurant_id FROM restaurant_info WHERE restaurant_id = %s AND is_archived = FALSE",
            (str(entity_id),),
            connection=db,
            fetch_one=True,
        )
    if not row:
        raise envelope_exception(ErrorCode.FAVORITE_NOT_FOUND, status=404, locale="en")

    # Check not already favorited
    existing = db_read(
        """
        SELECT favorite_id FROM user_favorite_info
        WHERE user_id = %s AND entity_type::text = %s AND entity_id = %s
        """,
        (str(user_id), entity_type, str(entity_id)),
        connection=db,
        fetch_one=True,
    )
    if existing:
        raise envelope_exception(ErrorCode.FAVORITE_ALREADY_ADDED, status=400, locale="en")

    # Insert
    data = {
        "user_id": str(user_id),
        "entity_type": entity_type,
        "entity_id": str(entity_id),
    }
    favorite_id = db_insert("user_favorite_info", data, connection=db)

    row = db_read(
        """
        SELECT favorite_id, user_id, entity_type::text, entity_id, created_date
        FROM user_favorite_info
        WHERE favorite_id = %s
        """,
        (str(favorite_id),),
        connection=db,
        fetch_one=True,
    )
    log_info(f"Added favorite {favorite_id} for user {user_id}: {entity_type}={entity_id}")
    return UserFavoriteDTO(**row)


def remove_favorite(
    user_id: UUID,
    entity_type: str,
    entity_id: UUID,
    db: psycopg2.extensions.connection,
) -> None:
    """
    Remove a favorite. Idempotent (no-op if not favorited).

    Args:
        user_id: Current user (Customer)
        entity_type: 'plate' or 'restaurant'
        entity_id: plate_id or restaurant_id
        db: Database connection
    """
    if not FavoriteEntityType.is_valid(entity_type):
        raise envelope_exception(ErrorCode.FAVORITE_ENTITY_TYPE_INVALID, status=400, locale="en")

    with db.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM user_favorite_info
            WHERE user_id = %s AND entity_type::text = %s AND entity_id = %s
            """,
            (str(user_id), entity_type, str(entity_id)),
        )
        db.commit()
    log_info(f"Removed favorite for user {user_id}: {entity_type}={entity_id}")


def get_favorite_ids(
    user_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict[str, list[UUID]]:
    """
    Get favorite IDs for fast lookup (sorting, is_favorite flags).

    Returns:
        {"plate_ids": [...], "restaurant_ids": [...]}
    """
    rows = (
        db_read(
            """
        SELECT entity_type::text, entity_id
        FROM user_favorite_info
        WHERE user_id = %s
        """,
            (str(user_id),),
            connection=db,
            fetch_one=False,
        )
        or []
    )
    plate_ids = []
    restaurant_ids = []
    for r in rows:
        eid = r["entity_id"]
        if r["entity_type"] == "plate":
            plate_ids.append(eid)
        else:
            restaurant_ids.append(eid)
    return {"plate_ids": plate_ids, "restaurant_ids": restaurant_ids}


def get_favorites_by_user(
    user_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    entity_type: str | None = None,
) -> list[UserFavoriteDTO]:
    """
    List all favorites for the user. Optional filter by entity_type.

    Args:
        user_id: Current user (Customer)
        db: Database connection
        entity_type: Optional 'plate' or 'restaurant' to filter

    Returns:
        List of UserFavoriteDTO
    """
    if entity_type is not None and not FavoriteEntityType.is_valid(entity_type):
        raise envelope_exception(ErrorCode.FAVORITE_ENTITY_TYPE_INVALID, status=400, locale="en")

    if entity_type:
        rows = (
            db_read(
                """
            SELECT favorite_id, user_id, entity_type::text, entity_id, created_date
            FROM user_favorite_info
            WHERE user_id = %s AND entity_type::text = %s
            ORDER BY favorite_id DESC
            """,
                (str(user_id), entity_type),
                connection=db,
                fetch_one=False,
            )
            or []
        )
    else:
        rows = (
            db_read(
                """
            SELECT favorite_id, user_id, entity_type::text, entity_id, created_date
            FROM user_favorite_info
            WHERE user_id = %s
            ORDER BY favorite_id DESC
            """,
                (str(user_id),),
                connection=db,
                fetch_one=False,
            )
            or []
        )

    return [UserFavoriteDTO(**r) for r in rows]
