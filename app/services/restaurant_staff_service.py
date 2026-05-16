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
from datetime import UTC, date, datetime, time
from typing import Any
from uuid import UUID

import psycopg2.extensions

from app.services.kitchen_day_service import get_kitchen_day_for_date
from app.utils.db import db_read
from app.utils.log import log_info, log_warning


def get_daily_orders(
    user_institution_entity_id: UUID,
    order_date: date,
    restaurant_id: UUID | None,
    db: psycopg2.extensions.connection,
    status_filter: list[str] | None = None,
    is_no_show_filter: bool | None = None,
) -> dict[str, Any]:
    """
    Get today's orders for restaurant(s) within an institution entity.

    Args:
        user_institution_entity_id: User's institution entity ID for scoping
        order_date: Date to query orders for
        restaurant_id: Optional specific restaurant filter
        db: Database connection
        status_filter: Optional list of status values to include (e.g. ['pending', 'arrived']).
            Accepted values: pending, arrived, handed_out, completed, cancelled, active.
            Applied at SQL level.
        is_no_show_filter: Optional boolean to filter by is_no_show derived field.
            True = only no-show orders; False = exclude no-shows; None = all orders.
            Applied in the service layer after query, since is_no_show is derived.

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

    # 2. Query all orders for the institution_entity (optionally filtered by restaurant/status)
    base_query = """
        SELECT
            ppl.vianda_pickup_id,
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
            prod.name AS vianda_name,
            r.restaurant_id,
            r.name AS restaurant_name,
            r.require_kiosk_code_verification,
            pp.pickup_type
        FROM vianda_pickup_live ppl
        INNER JOIN vianda_selection_info ps ON ppl.vianda_selection_id = ps.vianda_selection_id AND ps.is_archived = FALSE
        INNER JOIN user_info u ON ppl.user_id = u.user_id
        INNER JOIN vianda_info pl ON ppl.vianda_id = pl.vianda_id
        INNER JOIN product_info prod ON pl.product_id = prod.product_id
        INNER JOIN restaurant_info r ON ppl.restaurant_id = r.restaurant_id
        LEFT JOIN pickup_preferences pp ON ppl.vianda_selection_id = pp.vianda_selection_id
        WHERE r.institution_entity_id = %s
          AND ps.kitchen_day = %s
          AND ppl.is_archived = FALSE
          AND (r.restaurant_id = %s OR %s IS NULL)
    """

    params = [
        str(user_institution_entity_id),
        kitchen_day,
        str(restaurant_id) if restaurant_id else None,
        str(restaurant_id) if restaurant_id else None,
    ]

    # Apply optional status filter at SQL level
    if status_filter:
        base_query += "          AND ppl.status = ANY(%s)\n"
        params.append(status_filter)  # type: ignore[arg-type]

    base_query += "        ORDER BY r.name ASC, ps.pickup_time_range ASC, u.last_name ASC\n"

    # 3. Execute query
    rows = db_read(base_query, params, db)

    if not rows:
        log_info(f"No orders found for institution_entity_id={user_institution_entity_id}, kitchen_day={kitchen_day}")
        return {"order_date": order_date, "server_time": datetime.now(UTC), "restaurants": []}

    # 4. Group orders by restaurant and calculate summary statistics
    restaurants_data = _group_orders_by_restaurant(rows, is_no_show_filter=is_no_show_filter)

    # 5. Add reservations_by_vianda and live_locked_count per restaurant
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


def _compute_is_no_show(status_lower: str, arrival_time: Any, pickup_time_range: str | None, now_time: time) -> bool:
    """
    Return True when an order is pending and its pickup window end has passed.

    A row is considered pending when its status is 'pending', or when its status
    is 'active' with no recorded arrival_time (not yet promoted to a live pickup).
    """
    is_pending = status_lower == "pending" or (status_lower == "active" and arrival_time is None)
    if not is_pending:
        return False
    ptr = pickup_time_range or ""
    if "-" not in ptr:
        return False
    try:
        end_str = ptr.split("-")[1].strip()
        end_h, end_m = int(end_str.split(":")[0]), int(end_str.split(":")[1])
        return now_time > time(end_h, end_m)
    except (ValueError, IndexError):
        return False


def _classify_order_status(is_no_show: bool, status_lower: str, arrival_time: Any) -> str:
    """
    Map an order's runtime state to its summary-bucket key.

    Returns one of: 'no_show', 'pending', 'arrived', 'handed_out', 'completed'.
    Falls back to 'pending' for unrecognised statuses.
    """
    if is_no_show:
        return "no_show"
    if status_lower == "pending":
        return "pending"
    if status_lower == "arrived":
        return "arrived"
    if status_lower in ("handed_out", "handed out"):
        return "handed_out"
    if status_lower in ("complete", "completed"):
        return "completed"
    if status_lower == "active" and arrival_time is None:
        return "pending"
    if status_lower == "active" and arrival_time is not None:
        return "arrived"
    return "pending"


def _build_order_row(row: dict[str, Any], is_no_show: bool, countdown_seconds: int) -> dict[str, Any]:
    """
    Build a single order dict from a DB row, ready to append to a restaurant's order list.

    Privacy: customer name is formatted as initials only ("M.G.").
    """
    customer_name = f"{row['first_initial']}.{row['last_initial']}."
    return {
        "vianda_pickup_id": row["vianda_pickup_id"],
        "customer_name": customer_name,
        "vianda_name": row["vianda_name"],
        "confirmation_code": row["confirmation_code"],
        "status": row["status"],
        "arrival_time": row["arrival_time"],
        "expected_completion_time": row["expected_completion_time"],
        "completion_time": row["completion_time"],
        "countdown_seconds": countdown_seconds,
        "extensions_used": row.get("extensions_used") or 0,
        "was_collected": row.get("was_collected") or False,
        "pickup_time_range": row["pickup_time_range"],
        "kitchen_day": row["kitchen_day"],
        "pickup_type": row.get("pickup_type"),
        "is_no_show": is_no_show,
    }


def _compute_pickup_window_for_restaurant(rest: dict[str, Any]) -> None:
    """
    Derive pickup_window_start and pickup_window_end from the restaurant's order list.

    Mutates ``rest`` in place, adding 'pickup_window_start' and 'pickup_window_end'.
    Both are None when no order has a parseable pickup_time_range.
    """
    ranges = [
        o["pickup_time_range"] for o in rest["orders"] if o.get("pickup_time_range") and "-" in o["pickup_time_range"]
    ]
    if ranges:
        starts = [r.split("-")[0].strip() for r in ranges]
        ends = [r.split("-")[1].strip() for r in ranges]
        rest["pickup_window_start"] = min(starts)
        rest["pickup_window_end"] = max(ends)
    else:
        rest["pickup_window_start"] = None
        rest["pickup_window_end"] = None


def _group_orders_by_restaurant(
    rows: list[dict[str, Any]], is_no_show_filter: bool | None = None
) -> list[dict[str, Any]]:
    """
    Group orders by restaurant and calculate summary statistics.

    Args:
        rows: List of order rows from database query
        is_no_show_filter: When set, include only orders matching this is_no_show value.
            True = no-show orders only; False = non-no-show orders only; None = all orders.

    Returns:
        List of restaurant dictionaries with orders and summary
    """
    from app.config.settings import settings

    now_time = datetime.now().time()
    restaurants_dict: defaultdict[Any, dict[str, Any]] = defaultdict(
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

        # Seed restaurant header fields on first encounter
        if restaurants_dict[restaurant_id]["restaurant_id"] is None:
            restaurants_dict[restaurant_id]["restaurant_id"] = restaurant_id
            restaurants_dict[restaurant_id]["restaurant_name"] = row["restaurant_name"]
            restaurants_dict[restaurant_id]["require_kiosk_code_verification"] = row.get(
                "require_kiosk_code_verification", False
            )

        status_lower = (row["status"] or "").lower()
        is_no_show = _compute_is_no_show(status_lower, row.get("arrival_time"), row.get("pickup_time_range"), now_time)

        # Apply is_no_show filter at service layer (derived field, cannot be pushed to SQL)
        if is_no_show_filter is not None and is_no_show != is_no_show_filter:
            continue

        order = _build_order_row(row, is_no_show, settings.PICKUP_COUNTDOWN_SECONDS)
        restaurants_dict[restaurant_id]["orders"].append(order)

        summary = restaurants_dict[restaurant_id]["summary"]
        summary["total_orders"] += 1
        bucket = _classify_order_status(is_no_show, status_lower, row.get("arrival_time"))
        summary[bucket] += 1

    for rest in restaurants_dict.values():
        _compute_pickup_window_for_restaurant(rest)

    # Exclude restaurants that ended up with no orders after is_no_show filtering
    restaurants_list = [r for r in restaurants_dict.values() if r["orders"]]
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
    """Add reservations_by_vianda and live_locked_count to each restaurant."""
    if not restaurants_data:
        return

    for rest in restaurants_data:
        rid = rest["restaurant_id"]
        # reservations_by_vianda: count from vianda_selection_info for this restaurant, kitchen_day, pickup_date
        # Also derive completed_count (orders with status in completed/handed_out) per vianda
        res_query = """
            SELECT
                pl.vianda_id,
                prod.name AS vianda_name,
                COUNT(*) AS count,
                COUNT(ppl.vianda_pickup_id) FILTER (
                    WHERE ppl.status IN ('completed', 'handed_out') AND ppl.is_archived = FALSE
                ) AS completed_count
            FROM vianda_selection_info ps
            JOIN vianda_info pl ON ps.vianda_id = pl.vianda_id
            JOIN product_info prod ON pl.product_id = prod.product_id
            LEFT JOIN vianda_pickup_live ppl ON ppl.vianda_selection_id = ps.vianda_selection_id
            WHERE ps.restaurant_id = %s
              AND ps.kitchen_day = %s
              AND ps.pickup_date = %s
              AND ps.is_archived = FALSE
            GROUP BY pl.vianda_id, prod.name
        """
        raw_res = db_read(res_query, (str(rid), kitchen_day, order_date.isoformat()), connection=db)
        reservation_rows: list[dict[str, Any]] = raw_res if isinstance(raw_res, list) else []
        rest["reservations_by_vianda"] = [
            {
                "vianda_id": str(r["vianda_id"]),
                "vianda_name": r["vianda_name"],
                "count": r["count"],
                "completed_count": r["completed_count"] or 0,
            }
            for r in reservation_rows
        ]
        # live_locked_count: count of vianda_pickup_live for this restaurant (today's promoted orders)
        live_query = """
            SELECT COUNT(*) AS count
            FROM vianda_pickup_live ppl
            JOIN vianda_selection_info ps ON ppl.vianda_selection_id = ps.vianda_selection_id AND ps.is_archived = FALSE
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
        SELECT ppl.vianda_pickup_id, ppl.user_id, ppl.arrival_time, ppl.expected_completion_time,
               ppl.extensions_used,
               UPPER(SUBSTRING(u.first_name, 1, 1)) AS first_initial,
               UPPER(SUBSTRING(u.last_name, 1, 1)) AS last_initial,
               prod.name AS vianda_name, r.name AS restaurant_name
        FROM vianda_pickup_live ppl
        INNER JOIN vianda_selection_info ps ON ppl.vianda_selection_id = ps.vianda_selection_id AND ps.is_archived = FALSE
        INNER JOIN user_info u ON ppl.user_id = u.user_id
        INNER JOIN vianda_info pl ON ppl.vianda_id = pl.vianda_id
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
    pickup_ids = [row["vianda_pickup_id"] for row in rows]
    for pid in pickup_ids:
        db_write(
            """
            UPDATE vianda_pickup_live
            SET status = 'handed_out', handed_out_time = %s,
                code_verified = TRUE, code_verified_time = %s,
                modified_by = %s, modified_date = CURRENT_TIMESTAMP
            WHERE vianda_pickup_id = %s
            """,
            (now, now, str(current_user_id), str(pid)),
            connection=db,
        )
    db.commit()

    # Build response
    first_row = rows[0]
    customer_initials = f"{first_row['first_initial']}.{first_row['last_initial']}."

    # Aggregate viandas by name
    vianda_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        vianda_counts[row["vianda_name"]] += 1

    viandas = [{"vianda_name": name, "quantity": count} for name, count in vianda_counts.items()]

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
        "vianda_pickup_ids": pickup_ids,
        "viandas": viandas,
        "status": "handed_out",
        "arrival_time": first_row["arrival_time"],
        "expected_completion_time": first_row["expected_completion_time"],
        "handed_out_time": now,
        "countdown_seconds": settings.PICKUP_COUNTDOWN_SECONDS,
        "extensions_used": first_row.get("extensions_used") or 0,
        "max_extensions": settings.PICKUP_MAX_EXTENSIONS,
    }


def hand_out_pickup(
    vianda_pickup_id: UUID,
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
        """SELECT ppl.vianda_pickup_id, ppl.status, ppl.user_id, ppl.restaurant_id, r.name AS restaurant_name
           FROM vianda_pickup_live ppl
           JOIN restaurant_info r ON ppl.restaurant_id = r.restaurant_id
           WHERE ppl.vianda_pickup_id = %s AND ppl.is_archived = FALSE""",
        (str(vianda_pickup_id),),
        connection=db,
        fetch_one=True,
    )
    if not row:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Pickup")
    if row["status"] != "arrived":
        raise envelope_exception(
            ErrorCode.VIANDA_PICKUP_INVALID_STATUS, status=400, locale=locale, pickup_status=row["status"]
        )

    now = datetime.now()
    db_write(
        """
        UPDATE vianda_pickup_live
        SET status = 'handed_out', handed_out_time = %s,
            modified_by = %s, modified_date = CURRENT_TIMESTAMP
        WHERE vianda_pickup_id = %s
        """,
        (now, str(current_user_id), str(vianda_pickup_id)),
        connection=db,
    )
    db.commit()

    # Send push notification to customer (best-effort, non-blocking)
    try:
        from app.services.push_notification_service import send_handed_out_push

        send_handed_out_push(UUID(str(row["user_id"])), vianda_pickup_id, row["restaurant_name"], db)
    except Exception as push_err:
        log_warning(f"Push notification failed for hand-out {vianda_pickup_id}: {push_err}")

    log_info(f"Hand-out: pickup={vianda_pickup_id}, handed_out_time={now}")
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
