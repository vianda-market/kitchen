"""
Coworker service for post-reservation pickup flow.

Provides get_coworkers_with_eligibility for the "Offer to pick up" flow:
- List coworkers (same employer) with eligibility for notification
- Eligible: no plate selection for same kitchen_day
- Ineligible: has order for different restaurant or conflicting pickup time
"""

from typing import List, Dict, Any
from uuid import UUID
import psycopg2.extensions
from fastapi import HTTPException

from app.utils.db import db_read
from app.utils.log import log_info, log_warning


def get_coworkers_with_eligibility(
    plate_selection_id: UUID,
    current_user_id: UUID,
    db: psycopg2.extensions.connection,
) -> List[Dict[str, Any]]:
    """
    Get coworkers (same employer) with eligibility for pickup notification.

    Eligibility:
    - Eligible: coworker has no plate_selection for the same kitchen_day (any restaurant)
    - Ineligible: coworker has a plate_selection for a different restaurant or conflicting pickup time

    Args:
        plate_selection_id: The plate selection (offer) to scope coworkers for
        current_user_id: Current user (must have employer_entity_id)
        db: Database connection

    Returns:
        List of { user_id, first_name, last_initial, eligible: bool, ineligibility_reason: str | None }

    Raises:
        HTTPException 403 if current user has no employer_entity_id
    """
    # Get current user's employer_entity_id, employer_address_id, and plate_selection details
    ps_row = db_read(
        """
        SELECT ps.kitchen_day, ps.restaurant_id, ps.pickup_time_range,
               u.employer_entity_id, u.employer_address_id, u.workplace_group_id
        FROM plate_selection_info ps
        JOIN user_info u ON ps.user_id = u.user_id
        WHERE ps.plate_selection_id = %s AND ps.is_archived = FALSE
        """,
        (str(plate_selection_id),),
        connection=db,
        fetch_one=True,
    )
    if not ps_row:
        raise HTTPException(status_code=404, detail="Plate selection not found")

    workplace_group_id = ps_row.get("workplace_group_id")
    employer_entity_id = ps_row.get("employer_entity_id")

    if workplace_group_id:
        match_field = "workplace_group_id"
        match_value = workplace_group_id
    elif employer_entity_id:
        match_field = "employer_entity_id"
        match_value = employer_entity_id
    else:
        raise HTTPException(
            status_code=403,
            detail="You must have an employer assigned to list coworkers. Assign an employer in your profile.",
        )

    kitchen_day = ps_row.get("kitchen_day")
    restaurant_id = ps_row.get("restaurant_id")
    pickup_time_range = ps_row.get("pickup_time_range") or ""

    # Verify current user owns this plate selection
    owner_check = db_read(
        "SELECT user_id FROM plate_selection_info WHERE plate_selection_id = %s",
        (str(plate_selection_id),),
        connection=db,
        fetch_one=True,
    )
    if owner_check and str(owner_check.get("user_id")) != str(current_user_id):
        raise HTTPException(status_code=403, detail="Not authorized to access this plate selection")

    # Get coworkers (same workplace_group or employer; exclude current user;
    # only include users with can_participate_in_plate_pickups = TRUE)
    employer_address_id = ps_row.get("employer_address_id")

    if match_field == "workplace_group_id":
        # workplace_group_id takes precedence — match all users in the same group
        coworkers = db_read(
            """
            SELECT u.user_id, u.first_name, u.last_name
            FROM user_info u
            INNER JOIN user_messaging_preferences ump ON u.user_id = ump.user_id
            WHERE u.workplace_group_id = %s AND u.user_id != %s
              AND u.is_archived = FALSE AND u.status = 'active'
              AND ump.can_participate_in_plate_pickups = TRUE
            ORDER BY u.first_name, u.last_name
            """,
            (str(match_value), str(current_user_id)),
            connection=db,
        ) or []
    elif employer_address_id is not None:
        coworkers = db_read(
            """
            SELECT u.user_id, u.first_name, u.last_name
            FROM user_info u
            INNER JOIN user_messaging_preferences ump ON u.user_id = ump.user_id
            WHERE u.employer_entity_id = %s AND u.user_id != %s
              AND u.employer_address_id = %s
              AND u.is_archived = FALSE AND u.status = 'active'
              AND ump.can_participate_in_plate_pickups = TRUE
            ORDER BY u.first_name, u.last_name
            """,
            (str(match_value), str(current_user_id), str(employer_address_id)),
            connection=db,
        ) or []
    else:
        # User has no employer_address_id: only match coworkers who also have no employer_address_id
        coworkers = db_read(
            """
            SELECT u.user_id, u.first_name, u.last_name
            FROM user_info u
            INNER JOIN user_messaging_preferences ump ON u.user_id = ump.user_id
            WHERE u.employer_entity_id = %s AND u.user_id != %s
              AND u.employer_address_id IS NULL
              AND u.is_archived = FALSE AND u.status = 'active'
              AND ump.can_participate_in_plate_pickups = TRUE
            ORDER BY u.first_name, u.last_name
            """,
            (str(match_value), str(current_user_id)),
            connection=db,
        ) or []

    # For each coworker, check if they have a plate_selection for same kitchen_day
    # Eligible = no selection for this kitchen_day
    # Ineligible = has selection for different restaurant or conflicting time
    result = []
    for c in coworkers:
        user_id = c["user_id"]
        first_name = (c.get("first_name") or "").strip() or "Unknown"
        last_name = (c.get("last_name") or "").strip() or ""
        last_initial = (last_name[0] + ".") if last_name else ""

        # Check for existing plate_selection on same kitchen_day
        existing = db_read(
            """
            SELECT restaurant_id, pickup_time_range
            FROM plate_selection_info
            WHERE user_id = %s AND kitchen_day = %s AND is_archived = FALSE
            """,
            (str(user_id), kitchen_day),
            connection=db,
            fetch_one=True,
        )

        if not existing:
            eligible = True
            ineligibility_reason = None
        else:
            # Has order for same kitchen_day - ineligible if different restaurant or conflicting time
            other_restaurant = str(existing.get("restaurant_id") or "") != str(restaurant_id)
            other_time = (existing.get("pickup_time_range") or "") != pickup_time_range
            eligible = not other_restaurant and not other_time
            if eligible:
                ineligibility_reason = None
            elif other_restaurant:
                ineligibility_reason = "already_ordered_different_restaurant"
            else:
                ineligibility_reason = "already_ordered_different_pickup_time"

        result.append({
            "user_id": user_id,
            "first_name": first_name,
            "last_initial": last_initial,
            "eligible": eligible,
            "ineligibility_reason": ineligibility_reason,
        })

    return result


def notify_coworkers(
    plate_selection_id: UUID,
    user_ids: List[UUID],
    current_user_id: UUID,
    db: psycopg2.extensions.connection,
) -> Dict[str, Any]:
    """
    Record coworker pickup notifications. Validates all user_ids are eligible.

    Args:
        plate_selection_id: The plate selection (offer) context
        user_ids: List of coworker user_ids to notify
        current_user_id: Current user (notifier)
        db: Database connection

    Returns:
        { "notified_count": N }

    Raises:
        HTTPException 400 if any user_id is not eligible
    """
    coworkers = get_coworkers_with_eligibility(plate_selection_id, current_user_id, db)
    eligible_ids = {str(c["user_id"]) for c in coworkers if c["eligible"]}

    for uid in user_ids:
        if str(uid) not in eligible_ids:
            raise HTTPException(
                status_code=400,
                detail=f"User {uid} is not an eligible coworker for notification. They may have already ordered for a different restaurant or time.",
            )

    if not user_ids:
        return {"notified_count": 0}

    with db.cursor() as cursor:
        for notified_id in user_ids:
            cursor.execute(
                """
                INSERT INTO coworker_pickup_notification (plate_selection_id, notifier_user_id, notified_user_id)
                VALUES (%s, %s, %s)
                """,
                (str(plate_selection_id), str(current_user_id), str(notified_id)),
            )

    db.commit()
    log_info(f"Notified {len(user_ids)} coworkers for plate_selection {plate_selection_id}")
    return {"notified_count": len(user_ids)}
