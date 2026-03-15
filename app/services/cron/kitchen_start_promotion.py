"""
Kitchen Start Promotion Cron - Promote locked plate selections to live at kitchen start.

Runs periodically (e.g. every 5-15 min). For each market where kitchen has started
(business_hours.open passed), promotes plate_selection_info rows to plate_pickup_live
and restaurant_transaction. Idempotent.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import UUID
import pytz

from app.config.market_config import MarketConfiguration
from app.services.kitchen_day_service import get_kitchen_day_for_date
from app.services.plate_selection_promotion_service import promote_plate_selection_to_live
from app.utils.log import log_info, log_warning, log_error
from app.utils.db import db_read, get_db_connection, close_db_connection

SYSTEM_USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def run_kitchen_start_promotion(
    country_code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Promote locked plate selections to live for markets where kitchen has started.

    For each market (or single market if country_code provided):
    - If now >= business_hours[kitchen_day].open in market timezone for today
    - Find plate_selection_info: kitchen_day, pickup_date=today, is_archived=false,
      NOT EXISTS in plate_pickup_live
    - Promote each to live

    Args:
        country_code: Optional. If provided, only process this market (AR, PE, US).

    Returns:
        Dict with promoted_count, markets_processed, errors, etc.
    """
    result = {
        "cron_job": "kitchen_start_promotion",
        "execution_time": datetime.now(timezone.utc).isoformat(),
        "country_code": country_code,
        "promoted_count": 0,
        "markets_processed": 0,
        "errors": [],
    }

    markets = (
        [(country_code.upper(), MarketConfiguration.get_market_config(country_code))]
        if country_code
        else list(MarketConfiguration.get_all_markets().items())
    )

    for cc, config in markets:
        if not config:
            continue
        try:
            count = _promote_for_market(cc, config, SYSTEM_USER_ID)
            result["promoted_count"] += count
            result["markets_processed"] += 1
        except Exception as e:
            msg = f"Market {cc}: {e}"
            log_error(msg)
            result["errors"].append(msg)

    log_info(f"Kitchen start promotion: promoted {result['promoted_count']} selections "
             f"across {result['markets_processed']} markets")
    return result


def _promote_for_market(country_code: str, config, system_user_id: UUID) -> int:
    """Process one market. Returns count promoted."""
    tz = pytz.timezone(config.timezone)
    now_local = datetime.now(tz)
    today = now_local.date()
    kitchen_day = get_kitchen_day_for_date(today, config.timezone, country_code)

    # kitchen_day enum: Mon-Fri only
    if kitchen_day not in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"):
        log_info(f"Market {country_code}: {kitchen_day} is not a kitchen day, skip")
        return 0

    day_hours = config.business_hours.get(kitchen_day) if config.business_hours else None
    if not day_hours or "open" not in day_hours:
        log_warning(f"Market {country_code}: no business_hours.open for {kitchen_day}")
        return 0

    open_time = day_hours["open"]
    if isinstance(open_time, str):
        from datetime import time as dt_time
        open_time = datetime.strptime(open_time, "%H:%M").time()
    if now_local.time() < open_time:
        log_info(f"Market {country_code}: kitchen not yet open (open={open_time})")
        return 0

    # Find selections to promote: pickup_date=today, kitchen_day, not archived, no pickup yet
    conn = get_db_connection()
    try:
        query = """
            SELECT ps.plate_selection_id
            FROM plate_selection_info ps
            JOIN restaurant_info r ON ps.restaurant_id = r.restaurant_id
            JOIN address_info a ON r.address_id = a.address_id
            WHERE ps.kitchen_day = %s
              AND ps.pickup_date = %s
              AND ps.is_archived = FALSE
              AND UPPER(TRIM(COALESCE(a.country_code, ''))) = %s
              AND NOT EXISTS (
                  SELECT 1 FROM plate_pickup_live ppl
                  WHERE ppl.plate_selection_id = ps.plate_selection_id
                    AND ppl.is_archived = FALSE
              )
        """
        rows = db_read(
            query,
            (kitchen_day, today.isoformat(), country_code.upper()),
            connection=conn,
        )

        if not rows:
            log_info(f"Market {country_code}: no selections to promote")
            return 0

        promoted = 0
        for row in rows:
            try:
                plate_selection_id = UUID(str(row["plate_selection_id"]))
                pid = promote_plate_selection_to_live(
                    plate_selection_id, system_user_id, conn, commit=False
                )
                if pid:
                    promoted += 1
                    conn.commit()
            except Exception as e:
                log_error(f"Failed to promote {row['plate_selection_id']}: {e}")
                conn.rollback()
        return promoted
    finally:
        close_db_connection(conn)
