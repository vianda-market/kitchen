"""
Restaurant Staff Service - Business Logic for Restaurant Staff Operations

This service provides functionality for restaurant staff to view and manage
daily orders, including privacy-safe customer information and order aggregation.

Business Rules:
- Customer names displayed as "First L." format for privacy
- Orders filtered by institution_entity_id for Suppliers
- Orders grouped by restaurant with summary statistics
- Only active (non-archived) orders shown
"""

from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import psycopg2.extensions

from app.services.kitchen_day_service import get_kitchen_day_for_date
from app.utils.db import db_read
from app.utils.log import log_info, log_warning


def get_daily_orders(
    user_institution_entity_id: UUID, order_date: date, restaurant_id: UUID | None, db: psycopg2.extensions.connection
) -> dict[str, Any]:
    """
    Get today's orders for restaurant(s) within an institution entity.

    Args:
        user_institution_entity_id: User's institution entity ID for scoping
        order_date: Date to query orders for
        restaurant_id: Optional specific restaurant filter
        db: Database connection

    Returns:
        Dictionary with date and list of restaurants with their orders

    Example:
        {
            "date": "2026-02-04",
            "restaurants": [
                {
                    "restaurant_id": "uuid",
                    "restaurant_name": "Cambalache Palermo",
                    "orders": [...],
                    "summary": {"total_orders": 15, "pending": 10, ...}
                }
            ]
        }
    """

    # 1. Determine kitchen_day from date (using first restaurant's timezone)
    kitchen_day = _get_kitchen_day_for_date(order_date, user_institution_entity_id, db)

    # kitchen_day_enum only has Monday-Friday; weekends have no kitchen days
    if kitchen_day not in ("monday", "tuesday", "wednesday", "thursday", "friday"):
        log_info(f"No kitchen days on {kitchen_day}; returning empty orders for date={order_date}")
        return {"order_date": order_date, "server_time": datetime.now(UTC), "restaurants": []}

    log_info(
        f"Fetching daily orders for institution_entity_id={user_institution_entity_id}, "
        f"date={order_date}, kitchen_day={kitchen_day}, restaurant_id={restaurant_id}"
    )

    # 2. Query all orders for the institution_entity (optionally filtered by restaurant)
    query = """
        SELECT
            ppl.plate_pickup_id,
            ppl.confirmation_code,
            ppl.status,
            ppl.arrival_time,
            ppl.expected_completion_time,
            ppl.completion_time,
            ppl.was_collected,
            ppl.extensions_used,
            ppl.code_verified,
            ppl.handed_out_time,
            ps.pickup_time_range,
            ps.kitchen_day,
            UPPER(SUBSTRING(u.first_name, 1, 1)) AS first_initial,
            UPPER(SUBSTRING(u.last_name, 1, 1)) AS last_initial,
            prod.name AS plate_name,
            r.restaurant_id,
            r.name AS restaurant_name,
            r.require_kiosk_code_verification,
            pp.pickup_type
        FROM plate_pickup_live ppl
        INNER JOIN plate_selection_info ps ON ppl.plate_selection_id = ps.plate_selection_id AND ps.is_archived = FALSE
        INNER JOIN user_info u ON ppl.user_id = u.user_id
        INNER JOIN plate_info pl ON ppl.plate_id = pl.plate_id
        INNER JOIN product_info prod ON pl.product_id = prod.product_id
        INNER JOIN restaurant_info r ON ppl.restaurant_id = r.restaurant_id
        LEFT JOIN pickup_preferences pp ON ppl.plate_selection_id = pp.plate_selection_id
        WHERE r.institution_entity_id = %s
          AND ps.kitchen_day = %s
          AND ppl.is_archived = FALSE
          AND (r.restaurant_id = %s OR %s IS NULL)
        ORDER BY r.name ASC, ps.pickup_time_range ASC, u.last_name ASC
    """

    params = [
        str(user_institution_entity_id),
        kitchen_day,
        str(restaurant_id) if restaurant_id else None,
        str(restaurant_id) if restaurant_id else None,
    ]

    # 3. Execute query
    rows = db_read(query, params, db)

    if not rows:
        log_info(f"No orders found for institution_entity_id={user_institution_entity_id}, kitchen_day={kitchen_day}")
        return {"order_date": order_date, "server_time": datetime.now(UTC), "restaurants": []}

    # 4. Group orders by restaurant and calculate summary statistics
    restaurants_data = _group_orders_by_restaurant(rows)

    # 5. Add reservations_by_plate and live_locked_count per restaurant
    _add_reservations_and_live_metrics(
        restaurants_data, user_institution_entity_id, order_date, kitchen_day, restaurant_id, db
    )

    log_info(f"Retrieved {len(rows)} orders across {len(restaurants_data)} restaurant(s)")

    return {"order_date": order_date, "server_time": datetime.now(UTC), "restaurants": restaurants_data}


def _get_kitchen_day_for_date(order_date: date, institution_entity_id: UUID, db: psycopg2.extensions.connection) -> str:
    """
    Get kitchen_day enum value for a given date using restaurant timezone.

    Args:
        order_date: The date to convert to kitchen_day
        institution_entity_id: Institution entity ID to get timezone from
        db: Database connection

    Returns:
        Uppercase day name (e.g., 'TUESDAY')
    """

    # Get timezone and country_code from first restaurant's address
    query = """
        SELECT a.timezone, a.country_code
        FROM restaurant_info r
        INNER JOIN address_info a ON r.address_id = a.address_id
        WHERE r.institution_entity_id = %s
          AND r.is_archived = FALSE
        LIMIT 1
    """

    result = db_read(query, [str(institution_entity_id)], db)

    if not result or not result[0].get("timezone"):
        log_warning(f"No timezone found for institution_entity_id={institution_entity_id}, using default timezone")
        timezone_str = "America/Argentina/Buenos_Aires"
    else:
        timezone_str = result[0]["timezone"]

    country_code = result[0].get("country_code") if result else None

    return get_kitchen_day_for_date(order_date, timezone_str, country_code)


def _group_orders_by_restaurant(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Group orders by restaurant and calculate summary statistics.

    Args:
        rows: List of order rows from database query

    Returns:
        List of restaurant dictionaries with orders and summary
    """

    from datetime import time as time_type

    from app.config.settings import settings

    # Group by restaurant_id
    now_time = datetime.now().time()
    restaurants_dict = defaultdict(
        lambda: {
            "restaurant_id": None,
            "restaurant_name": None,
            "require_kiosk_code_verification": False,
            "orders": [],
            "summary": {"total_orders": 0, "pending": 0, "arrived": 0, "handed_out": 0, "completed": 0, "no_show": 0},
        }
    )

    for row in rows:
        restaurant_id = row["restaurant_id"]

        # Set restaurant info (first time we see this restaurant)
        if restaurants_dict[restaurant_id]["restaurant_id"] is None:
            restaurants_dict[restaurant_id]["restaurant_id"] = restaurant_id
            restaurants_dict[restaurant_id]["restaurant_name"] = row["restaurant_name"]
            restaurants_dict[restaurant_id]["require_kiosk_code_verification"] = row.get(
                "require_kiosk_code_verification", False
            )

        # Format customer name for privacy: initials only "M.G."
        customer_name = f"{row['first_initial']}.{row['last_initial']}."

        # Add order to restaurant's order list
        order = {
            "plate_pickup_id": row["plate_pickup_id"],
            "customer_name": customer_name,
            "plate_name": row["plate_name"],
            "confirmation_code": row["confirmation_code"],
            "status": row["status"],
            "arrival_time": row["arrival_time"],
            "expected_completion_time": row["expected_completion_time"],
            "completion_time": row["completion_time"],
            "countdown_seconds": settings.PICKUP_COUNTDOWN_SECONDS,
            "extensions_used": row.get("extensions_used") or 0,
            "was_collected": row.get("was_collected") or False,
            "pickup_time_range": row["pickup_time_range"],
            "kitchen_day": row["kitchen_day"],
            "pickup_type": row.get("pickup_type"),
        }

        # Compute is_no_show: Pending order whose pickup_time_range end has passed
        is_no_show = False
        status_lower = (row["status"] or "").lower()
        is_pending = status_lower == "pending" or (status_lower == "active" and row.get("arrival_time") is None)
        if is_pending:
            ptr = row.get("pickup_time_range") or ""
            if "-" in ptr:
                try:
                    end_str = ptr.split("-")[1].strip()
                    end_h, end_m = int(end_str.split(":")[0]), int(end_str.split(":")[1])
                    if now_time > time_type(end_h, end_m):
                        is_no_show = True
                except (ValueError, IndexError):
                    pass
        order["is_no_show"] = is_no_show

        restaurants_dict[restaurant_id]["orders"].append(order)

        # Update summary statistics
        summary = restaurants_dict[restaurant_id]["summary"]
        summary["total_orders"] += 1

        # Categorize by status
        if is_no_show:
            summary["no_show"] += 1
        elif status_lower == "pending":
            summary["pending"] += 1
        elif status_lower == "arrived":
            summary["arrived"] += 1
        elif status_lower in ("handed_out", "handed out"):
            summary["handed_out"] += 1
        elif status_lower in ("complete", "completed"):
            summary["completed"] += 1
        elif status_lower == "active" and row["arrival_time"] is None:
            summary["pending"] += 1
        elif status_lower == "active" and row["arrival_time"] is not None:
            summary["arrived"] += 1
        else:
            summary["pending"] += 1

    # Compute pickup_window per restaurant from pickup_time_range values
    for rest in restaurants_dict.values():
        ranges = [
            o["pickup_time_range"]
            for o in rest["orders"]
            if o.get("pickup_time_range") and "-" in o["pickup_time_range"]
        ]
        if ranges:
            starts = [r.split("-")[0].strip() for r in ranges]
            ends = [r.split("-")[1].strip() for r in ranges]
            rest["pickup_window_start"] = min(starts)
            rest["pickup_window_end"] = max(ends)
        else:
            rest["pickup_window_start"] = None
            rest["pickup_window_end"] = None

    # Convert to list and maintain alphabetical order by restaurant name
    restaurants_list = list(restaurants_dict.values())
    restaurants_list.sort(key=lambda x: x["restaurant_name"])

    return restaurants_list


def _add_reservations_and_live_metrics(
    restaurants_data: list[dict[str, Any]],
    institution_entity_id: UUID,
    order_date: date,
    kitchen_day: str,
    restaurant_id: UUID | None,
    db: psycopg2.extensions.connection,
) -> None:
    """Add reservations_by_plate and live_locked_count to each restaurant."""
    if not restaurants_data:
        return

    for rest in restaurants_data:
        rid = rest["restaurant_id"]
        # reservations_by_plate: count from plate_selection_info for this restaurant, kitchen_day, pickup_date
        res_query = """
            SELECT pl.plate_id, prod.name AS plate_name, COUNT(*) AS count
            FROM plate_selection_info ps
            JOIN plate_info pl ON ps.plate_id = pl.plate_id
            JOIN product_info prod ON pl.product_id = prod.product_id
            WHERE ps.restaurant_id = %s
              AND ps.kitchen_day = %s
              AND ps.pickup_date = %s
              AND ps.is_archived = FALSE
            GROUP BY pl.plate_id, prod.name
        """
        res_rows = db_read(res_query, (str(rid), kitchen_day, order_date.isoformat()), connection=db)
        rest["reservations_by_plate"] = [
            {"plate_id": str(r["plate_id"]), "plate_name": r["plate_name"], "count": r["count"]}
            for r in (res_rows or [])
        ]
        # live_locked_count: count of plate_pickup_live for this restaurant (today's promoted orders)
        live_query = """
            SELECT COUNT(*) AS count
            FROM plate_pickup_live ppl
            JOIN plate_selection_info ps ON ppl.plate_selection_id = ps.plate_selection_id AND ps.is_archived = FALSE
            WHERE ppl.restaurant_id = %s
              AND ps.kitchen_day = %s
              AND ps.pickup_date = %s
              AND ppl.is_archived = FALSE
        """
        live_row = db_read(live_query, (str(rid), kitchen_day, order_date.isoformat()), connection=db, fetch_one=True)
        rest["live_locked_count"] = live_row["count"] if live_row else 0


def verify_and_handoff(
    confirmation_code: str,
    restaurant_id: UUID,
    current_user_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict[str, Any]:
    """
    Verify a confirmation code and transition matching orders to Handed Out.
    Used by Layer 2 kiosk code verification.

    Returns:
        Dict with match=True and order details, or match=False with message
    """
    from app.config.settings import settings
    from app.utils.db import db_write

    # Find matching arrived orders for this code + restaurant (today only)
    kitchen_day = _get_kitchen_day_for_date(date.today(), _get_institution_entity_for_restaurant(restaurant_id, db), db)

    rows = db_read(
        """
        SELECT ppl.plate_pickup_id, ppl.user_id, ppl.arrival_time, ppl.expected_completion_time,
               ppl.extensions_used,
               UPPER(SUBSTRING(u.first_name, 1, 1)) AS first_initial,
               UPPER(SUBSTRING(u.last_name, 1, 1)) AS last_initial,
               prod.name AS plate_name, r.name AS restaurant_name
        FROM plate_pickup_live ppl
        INNER JOIN plate_selection_info ps ON ppl.plate_selection_id = ps.plate_selection_id AND ps.is_archived = FALSE
        INNER JOIN user_info u ON ppl.user_id = u.user_id
        INNER JOIN plate_info pl ON ppl.plate_id = pl.plate_id
        INNER JOIN product_info prod ON pl.product_id = prod.product_id
        INNER JOIN restaurant_info r ON ppl.restaurant_id = r.restaurant_id
        WHERE ppl.confirmation_code = %s
          AND ppl.restaurant_id = %s
          AND ppl.status = 'arrived'
          AND ppl.is_archived = FALSE
          AND ps.kitchen_day = %s
        """,
        (confirmation_code, str(restaurant_id), kitchen_day),
        connection=db,
    )

    if not rows:
        return {"match": False, "message": "No order found with this confirmation code"}

    # Transition all matching pickups to Handed Out
    now = datetime.now()
    pickup_ids = [row["plate_pickup_id"] for row in rows]
    for pid in pickup_ids:
        db_write(
            """
            UPDATE plate_pickup_live
            SET status = 'handed_out', handed_out_time = %s,
                code_verified = TRUE, code_verified_time = %s,
                modified_by = %s, modified_date = CURRENT_TIMESTAMP
            WHERE plate_pickup_id = %s
            """,
            (now, now, str(current_user_id), str(pid)),
            connection=db,
        )
    db.commit()

    # Build response
    first_row = rows[0]
    customer_initials = f"{first_row['first_initial']}.{first_row['last_initial']}."

    # Aggregate plates by name
    plate_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        plate_counts[row["plate_name"]] += 1

    plates = [{"plate_name": name, "quantity": count} for name, count in plate_counts.items()]

    log_info(f"Verify-and-handoff: code={confirmation_code}, restaurant={restaurant_id}, pickups={len(pickup_ids)}")

    # Send push notification to customer (best-effort, non-blocking)
    try:
        from app.services.push_notification_service import send_handed_out_push

        customer_user_id = UUID(str(first_row["user_id"]))
        restaurant_name = first_row.get("restaurant_name", "your restaurant")
        send_handed_out_push(customer_user_id, pickup_ids[0], restaurant_name, db)
    except Exception as push_err:
        log_warning(f"Push notification failed for verify-and-handoff: {push_err}")

    return {
        "match": True,
        "customer_initials": customer_initials,
        "plate_pickup_ids": pickup_ids,
        "plates": plates,
        "status": "handed_out",
        "arrival_time": first_row["arrival_time"],
        "expected_completion_time": first_row["expected_completion_time"],
        "handed_out_time": now,
        "countdown_seconds": settings.PICKUP_COUNTDOWN_SECONDS,
        "extensions_used": first_row.get("extensions_used") or 0,
        "max_extensions": settings.PICKUP_MAX_EXTENSIONS,
    }


def hand_out_pickup(
    plate_pickup_id: UUID,
    current_user_id: UUID,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> dict[str, Any]:
    """
    Manual one-tap handoff: transition a single pickup from Arrived to Handed Out.
    Used by Layer 1 kiosk.
    """
    from app.i18n.envelope import envelope_exception
    from app.i18n.error_codes import ErrorCode
    from app.utils.db import db_write

    # Verify the pickup exists and is in Arrived status
    row = db_read(
        """SELECT ppl.plate_pickup_id, ppl.status, ppl.user_id, ppl.restaurant_id, r.name AS restaurant_name
           FROM plate_pickup_live ppl
           JOIN restaurant_info r ON ppl.restaurant_id = r.restaurant_id
           WHERE ppl.plate_pickup_id = %s AND ppl.is_archived = FALSE""",
        (str(plate_pickup_id),),
        connection=db,
        fetch_one=True,
    )
    if not row:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Pickup")
    if row["status"] != "arrived":
        raise envelope_exception(
            ErrorCode.PLATE_PICKUP_INVALID_STATUS, status=400, locale=locale, pickup_status=row["status"]
        )

    now = datetime.now()
    db_write(
        """
        UPDATE plate_pickup_live
        SET status = 'handed_out', handed_out_time = %s,
            modified_by = %s, modified_date = CURRENT_TIMESTAMP
        WHERE plate_pickup_id = %s
        """,
        (now, str(current_user_id), str(plate_pickup_id)),
        connection=db,
    )
    db.commit()

    # Send push notification to customer (best-effort, non-blocking)
    try:
        from app.services.push_notification_service import send_handed_out_push

        send_handed_out_push(UUID(str(row["user_id"])), plate_pickup_id, row["restaurant_name"], db)
    except Exception as push_err:
        log_warning(f"Push notification failed for hand-out {plate_pickup_id}: {push_err}")

    log_info(f"Hand-out: pickup={plate_pickup_id}, handed_out_time={now}")
    return {"status": "handed_out", "handed_out_time": now}


def _get_institution_entity_for_restaurant(
    restaurant_id: UUID,
    db: psycopg2.extensions.connection,
    locale: str = "en",
) -> UUID:
    """Get institution_entity_id for a restaurant."""
    from app.i18n.envelope import envelope_exception
    from app.i18n.error_codes import ErrorCode

    row = db_read(
        "SELECT institution_entity_id FROM restaurant_info WHERE restaurant_id = %s AND is_archived = FALSE",
        (str(restaurant_id),),
        connection=db,
        fetch_one=True,
    )
    if not row:
        raise envelope_exception(ErrorCode.RESTAURANT_NOT_FOUND, status=404, locale=locale)
    return UUID(str(row["institution_entity_id"]))
