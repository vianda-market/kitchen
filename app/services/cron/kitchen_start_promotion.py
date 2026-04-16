"""
Kitchen Start Promotion Cron - Promote locked plate selections to live at kitchen start.

Runs periodically (e.g. every 5-15 min). For each location where kitchen has started
(business_hours.open passed), promotes plate_selection_info rows to plate_pickup_live
and restaurant_transaction. Idempotent.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytz

from app.config.location_config import get_all_locations, get_location_config
from app.config.market_config import MarketConfiguration
from app.services.kitchen_day_service import get_kitchen_day_for_date
from app.services.plate_selection_promotion_service import promote_plate_selection_to_live
from app.utils.db import close_db_connection, db_read, get_db_connection
from app.utils.log import log_error, log_info, log_warning

SYSTEM_USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def run_kitchen_start_promotion(location_id: str | None = None) -> dict[str, Any]:
    """
    Promote locked plate selections to live for locations where kitchen has started.

    For each location (or single location if location_id provided):
    - If now >= business_hours[kitchen_day].open in location timezone for today
    - Find plate_selection_info: kitchen_day, pickup_date=today, is_archived=false,
      NOT EXISTS in plate_pickup_live, address.timezone matches location
    - Promote each to live

    Args:
        location_id: Optional. If provided, only process this location (AR, PE, US-Eastern, etc.).

    Returns:
        Dict with promoted_count, locations_processed, errors, etc.
    """
    result = {
        "cron_job": "kitchen_start_promotion",
        "execution_time": datetime.now(UTC).isoformat(),
        "location_id": location_id,
        "promoted_count": 0,
        "locations_processed": 0,
        "errors": [],
    }

    locations_to_process = [get_location_config(location_id)] if location_id else get_all_locations()
    locations_to_process = [loc for loc in locations_to_process if loc]

    for loc in locations_to_process:
        loc_id = loc["location"]
        timezone_str = loc["timezone"]
        market = loc["market"]
        try:
            count = _promote_for_location(loc_id, timezone_str, market, SYSTEM_USER_ID)
            result["promoted_count"] += count
            result["locations_processed"] += 1
        except Exception as e:
            msg = f"Location {loc_id}: {e}"
            log_error(msg)
            result["errors"].append(msg)

    log_info(
        f"Kitchen start promotion: promoted {result['promoted_count']} selections "
        f"across {result['locations_processed']} location(s)"
    )
    return result


def _promote_for_location(
    location_id: str,
    timezone_str: str,
    market: str,
    system_user_id: UUID,
) -> int:
    """Process one location. Returns count promoted."""
    tz = pytz.timezone(timezone_str)
    now_local = datetime.now(tz)
    today = now_local.date()
    config = MarketConfiguration.get_market_config(market)
    if not config:
        log_warning(f"Location {location_id}: no market config for {market}")
        return 0

    kitchen_day = get_kitchen_day_for_date(today, timezone_str, market)

    # kitchen_day enum values are lowercase (monday–friday)
    valid_days = ("monday", "tuesday", "wednesday", "thursday", "friday")

    # DEV_MODE: treat any day as a valid kitchen day so E2E tests work on weekends
    from app.config.settings import Settings

    _dev_mode = Settings().DEV_MODE
    if not _dev_mode and kitchen_day not in valid_days:
        log_info(f"Location {location_id}: {kitchen_day} is not a kitchen day, skip")
        return 0
    if _dev_mode and kitchen_day not in valid_days:
        kitchen_day = "monday"  # Force a valid kitchen day for dev/test
        log_info(f"Location {location_id}: DEV_MODE — overriding {now_local.strftime('%A').lower()} to {kitchen_day}")

    day_hours = config.business_hours.get(kitchen_day) if config.business_hours else None
    if not day_hours or "open" not in day_hours:
        log_warning(f"Location {location_id}: no business_hours.open for {kitchen_day}")
        return 0

    open_time = day_hours["open"]
    if isinstance(open_time, str):
        open_time = datetime.strptime(open_time, "%H:%M").time()

    # DEV_MODE: skip kitchen hours check so E2E tests can run at any time
    from app.config.settings import Settings

    if not Settings().DEV_MODE and now_local.time() < open_time:
        log_info(f"Location {location_id}: kitchen not yet open (open={open_time})")
        return 0

    # Find selections to promote: pickup_date=today, kitchen_day, not archived,
    # address.timezone matches location, no pickup yet
    conn = get_db_connection()
    try:
        if _dev_mode:
            # DEV_MODE: skip kitchen_day and timezone filters — promote any selection for today
            query = """
                SELECT ps.plate_selection_id
                FROM plate_selection_info ps
                WHERE ps.pickup_date = %s
                  AND ps.is_archived = FALSE
                  AND NOT EXISTS (
                      SELECT 1 FROM plate_pickup_live ppl
                      WHERE ppl.plate_selection_id = ps.plate_selection_id
                        AND ppl.is_archived = FALSE
                  )
            """
            rows = db_read(query, (today.isoformat(),), connection=conn)
        else:
            query = """
                SELECT ps.plate_selection_id
                FROM plate_selection_info ps
                JOIN restaurant_info r ON ps.restaurant_id = r.restaurant_id
                JOIN address_info a ON r.address_id = a.address_id
                WHERE ps.kitchen_day = %s
                  AND ps.pickup_date = %s
                  AND ps.is_archived = FALSE
                  AND TRIM(COALESCE(a.timezone, '')) = %s
                  AND NOT EXISTS (
                      SELECT 1 FROM plate_pickup_live ppl
                      WHERE ppl.plate_selection_id = ps.plate_selection_id
                        AND ppl.is_archived = FALSE
                  )
            """
            rows = db_read(query, (kitchen_day, today.isoformat(), timezone_str), connection=conn)

        if not rows:
            log_info(f"Location {location_id}: no selections to promote")
            return 0

        promoted = 0
        for row in rows:
            try:
                plate_selection_id = UUID(str(row["plate_selection_id"]))
                pid = promote_plate_selection_to_live(plate_selection_id, system_user_id, conn, commit=False)
                if pid:
                    promoted += 1
                    conn.commit()
            except Exception as e:
                log_error(f"Failed to promote {row['plate_selection_id']}: {e}")
                conn.rollback()
        return promoted
    finally:
        close_db_connection(conn)
