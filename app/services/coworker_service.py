"""
Coworker service for post-reservation pickup flow.

Provides get_coworkers_with_eligibility for the "Offer to pick up" flow:
- List coworkers (same employer) with eligibility for notification
- Eligible: no vianda selection for same kitchen_day
- Ineligible: has order for different restaurant or conflicting pickup time
"""

from typing import Any
from uuid import UUID

import psycopg2.extensions

from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.utils.db import db_read
from app.utils.log import log_info


def _fetch_vianda_selection_context(
    vianda_selection_id: UUID,
    current_user_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict[str, Any]:
    """
    Fetch the vianda selection row joined to user context and verify ownership.

    Returns the combined ps + user row on success.
    Raises HTTPException 404 if not found, 403 if owned by another user.
    """
    ps_row = db_read(
        """
        SELECT ps.kitchen_day, ps.restaurant_id, ps.pickup_time_range,
               u.employer_entity_id, u.employer_address_id, u.workplace_group_id
        FROM vianda_selection_info ps
        JOIN user_info u ON ps.user_id = u.user_id
        WHERE ps.vianda_selection_id = %s AND ps.is_archived = FALSE
        """,
        (str(vianda_selection_id),),
        connection=db,
        fetch_one=True,
    )
    if not ps_row:
        raise envelope_exception(ErrorCode.VIANDA_SELECTION_NOT_FOUND, status=404, locale="en")

    owner_check = db_read(
        "SELECT user_id FROM vianda_selection_info WHERE vianda_selection_id = %s",
        (str(vianda_selection_id),),
        connection=db,
        fetch_one=True,
    )
    if owner_check and str(owner_check.get("user_id")) != str(current_user_id):
        raise envelope_exception(ErrorCode.VIANDA_SELECTION_ACCESS_DENIED, status=403, locale="en")

    return ps_row  # type: ignore[return-value]


def _resolve_coworker_match_key(
    ps_row: dict[str, Any],
) -> tuple[str, Any]:
    """
    Determine the coworker matching field and value from the vianda selection context.

    Returns (match_field, match_value): field is 'workplace_group_id' or 'employer_entity_id'.
    Raises HTTPException 403 if neither is set.
    """
    workplace_group_id = ps_row.get("workplace_group_id")
    employer_entity_id = ps_row.get("employer_entity_id")

    if workplace_group_id:
        return "workplace_group_id", workplace_group_id
    if employer_entity_id:
        return "employer_entity_id", employer_entity_id
    raise envelope_exception(ErrorCode.COWORKER_EMPLOYER_REQUIRED, status=403, locale="en")


def _fetch_coworkers_by_scope(
    match_field: str,
    match_value: Any,
    employer_address_id: Any,
    current_user_id: UUID,
    db: psycopg2.extensions.connection,
) -> list[dict[str, Any]]:
    """
    Fetch coworkers scoped to the same workplace group, employer+address, or employer-no-address.

    Only active, non-archived users who opt in to vianda pickup participation are returned.
    """
    if match_field == "workplace_group_id":
        rows = db_read(
            """
            SELECT u.user_id, u.first_name, u.last_name
            FROM user_info u
            INNER JOIN user_messaging_preferences ump ON u.user_id = ump.user_id
            WHERE u.workplace_group_id = %s AND u.user_id != %s
              AND u.is_archived = FALSE AND u.status = 'active'
              AND ump.can_participate_in_vianda_pickups = TRUE
            ORDER BY u.first_name, u.last_name
            """,
            (str(match_value), str(current_user_id)),
            connection=db,
        )
        return rows or []  # type: ignore[return-value]

    if employer_address_id is not None:
        rows = db_read(
            """
            SELECT u.user_id, u.first_name, u.last_name
            FROM user_info u
            INNER JOIN user_messaging_preferences ump ON u.user_id = ump.user_id
            WHERE u.employer_entity_id = %s AND u.user_id != %s
              AND u.employer_address_id = %s
              AND u.is_archived = FALSE AND u.status = 'active'
              AND ump.can_participate_in_vianda_pickups = TRUE
            ORDER BY u.first_name, u.last_name
            """,
            (str(match_value), str(current_user_id), str(employer_address_id)),
            connection=db,
        )
        return rows or []  # type: ignore[return-value]

    # No employer_address_id: only coworkers who also have none
    rows = db_read(
        """
        SELECT u.user_id, u.first_name, u.last_name
        FROM user_info u
        INNER JOIN user_messaging_preferences ump ON u.user_id = ump.user_id
        WHERE u.employer_entity_id = %s AND u.user_id != %s
          AND u.employer_address_id IS NULL
          AND u.is_archived = FALSE AND u.status = 'active'
          AND ump.can_participate_in_vianda_pickups = TRUE
        ORDER BY u.first_name, u.last_name
        """,
        (str(match_value), str(current_user_id)),
        connection=db,
    )
    return rows or []  # type: ignore[return-value]


def _evaluate_coworker_eligibility(
    user_id: Any,
    kitchen_day: Any,
    restaurant_id: Any,
    pickup_time_range: str,
    db: psycopg2.extensions.connection,
) -> tuple[bool, str | None]:
    """
    Determine eligibility for a single coworker on the given kitchen day.

    Returns (eligible, ineligibility_reason).
    Eligible when the coworker has no vianda selection for the same kitchen day.
    """
    existing = db_read(
        """
        SELECT restaurant_id, pickup_time_range
        FROM vianda_selection_info
        WHERE user_id = %s AND kitchen_day = %s AND is_archived = FALSE
        """,
        (str(user_id), kitchen_day),
        connection=db,
        fetch_one=True,
    )

    if not existing:
        return True, None

    other_restaurant = str(existing.get("restaurant_id") or "") != str(restaurant_id)
    other_time = (existing.get("pickup_time_range") or "") != pickup_time_range
    if not other_restaurant and not other_time:
        return True, None
    if other_restaurant:
        return False, "already_ordered_different_restaurant"
    return False, "already_ordered_different_pickup_time"


def _build_coworker_results(
    coworkers: list[dict[str, Any]],
    kitchen_day: Any,
    restaurant_id: Any,
    pickup_time_range: str,
    db: psycopg2.extensions.connection,
) -> list[dict[str, Any]]:
    """
    Build the eligibility-annotated result list from a coworker roster.

    Calls _evaluate_coworker_eligibility per row and shapes the output dict.
    """
    result = []
    for c in coworkers:
        user_id = c["user_id"]
        first_name = (c.get("first_name") or "").strip() or "Unknown"
        last_name = (c.get("last_name") or "").strip() or ""
        last_initial = (last_name[0] + ".") if last_name else ""

        eligible, ineligibility_reason = _evaluate_coworker_eligibility(
            user_id, kitchen_day, restaurant_id, pickup_time_range, db
        )
        result.append(
            {
                "user_id": user_id,
                "first_name": first_name,
                "last_initial": last_initial,
                "eligible": eligible,
                "ineligibility_reason": ineligibility_reason,
            }
        )
    return result


def get_coworkers_with_eligibility(
    vianda_selection_id: UUID,
    current_user_id: UUID,
    db: psycopg2.extensions.connection,
) -> list[dict[str, Any]]:
    """
    Get coworkers (same employer) with eligibility for pickup notification.

    Eligibility:
    - Eligible: coworker has no vianda_selection for the same kitchen_day (any restaurant)
    - Ineligible: coworker has a vianda_selection for a different restaurant or conflicting pickup time

    Args:
        vianda_selection_id: The vianda selection (offer) to scope coworkers for
        current_user_id: Current user (must have employer_entity_id)
        db: Database connection

    Returns:
        List of { user_id, first_name, last_initial, eligible: bool, ineligibility_reason: str | None }

    Raises:
        HTTPException 403 if current user has no employer_entity_id
    """
    ps_row = _fetch_vianda_selection_context(vianda_selection_id, current_user_id, db)

    match_field, match_value = _resolve_coworker_match_key(ps_row)

    kitchen_day = ps_row.get("kitchen_day")
    restaurant_id = ps_row.get("restaurant_id")
    pickup_time_range = ps_row.get("pickup_time_range") or ""
    employer_address_id = ps_row.get("employer_address_id")

    coworkers = _fetch_coworkers_by_scope(match_field, match_value, employer_address_id, current_user_id, db)

    return _build_coworker_results(coworkers, kitchen_day, restaurant_id, pickup_time_range, db)


def notify_coworkers(
    vianda_selection_id: UUID,
    user_ids: list[UUID],
    current_user_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict[str, Any]:
    """
    Record coworker pickup notifications. Validates all user_ids are eligible.

    Args:
        vianda_selection_id: The vianda selection (offer) context
        user_ids: List of coworker user_ids to notify
        current_user_id: Current user (notifier)
        db: Database connection

    Returns:
        { "notified_count": N }

    Raises:
        HTTPException 400 if any user_id is not eligible
    """
    coworkers = get_coworkers_with_eligibility(vianda_selection_id, current_user_id, db)
    eligible_ids = {str(c["user_id"]) for c in coworkers if c["eligible"]}

    for uid in user_ids:
        if str(uid) not in eligible_ids:
            raise envelope_exception(ErrorCode.COWORKER_USER_INELIGIBLE, status=400, locale="en")

    if not user_ids:
        return {"notified_count": 0}

    with db.cursor() as cursor:
        for notified_id in user_ids:
            cursor.execute(
                """
                INSERT INTO coworker_pickup_notification (vianda_selection_id, notifier_user_id, notified_user_id)
                VALUES (%s, %s, %s)
                """,
                (str(vianda_selection_id), str(current_user_id), str(notified_id)),
            )

    db.commit()
    log_info(f"Notified {len(user_ids)} coworkers for vianda_selection {vianda_selection_id}")
    return {"notified_count": len(user_ids)}
