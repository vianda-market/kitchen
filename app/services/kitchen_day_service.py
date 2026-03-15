"""
Kitchen Day Service - Centralized kitchen day logic.

Provides a single source of truth for:
- Effective current day (with 1:30 PM cutoff, configurable via market_info.kitchen_close_time)
- Kitchen closed checks
- Date-to-kitchen-day mapping
- Timezone-aware kitchen day resolution

Resolution order for kitchen_close_time:
1. market_info.kitchen_close_time (DB, B2B manageable)
2. MarketConfiguration.kitchen_day_config[day].kitchen_close
3. Hardcoded time(13, 30)
"""

from datetime import datetime, date, time, timedelta
from typing import Optional
import pytz

from app.config import KitchenDay
from app.config.settings import settings

# Re-export for backward compatibility
VALID_KITCHEN_DAYS = tuple(KitchenDay.values())
WEEKDAY_NUM_TO_NAME = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")


def _get_kitchen_close_time(country_code: Optional[str], day_name: Optional[str] = None) -> time:
    """
    Resolve kitchen close time for a market.
    Order: market_info.kitchen_close_time -> MarketConfiguration -> time(13, 30).
    """
    if country_code and str(country_code).strip():
        # 1. Try DB via market_service
        try:
            from app.services.market_service import market_service
            market = market_service.get_by_country_code(country_code.upper())
            if market and market.get("kitchen_close_time"):
                kct = market["kitchen_close_time"]
                if isinstance(kct, time):
                    return kct
                if isinstance(kct, str):
                    return datetime.strptime(kct, "%H:%M").time()
        except Exception:
            pass

        # 2. Fall back to MarketConfiguration
        try:
            from app.config.market_config import MarketConfiguration
            config = MarketConfiguration.get_market_config(country_code.upper())
            if config and config.kitchen_day_config:
                # Use provided day or Monday as default (all same in config)
                day = day_name or "Monday"
                day_config = config.kitchen_day_config.get(day)
                if day_config and day_config.get("kitchen_close"):
                    return day_config["kitchen_close"]
                # Try any weekday
                for d in WEEKDAY_NUM_TO_NAME:
                    dc = config.kitchen_day_config.get(d)
                    if dc and dc.get("kitchen_close"):
                        return dc["kitchen_close"]
        except Exception:
            pass

    return time(13, 30)


def get_effective_current_day(
    timezone_str: str = "America/Argentina/Buenos_Aires",
    country_code: Optional[str] = None
) -> str:
    """
    Get the effective current kitchen day, considering cutoff time and dev overrides.

    Before kitchen_close (e.g. 1:30 PM local): previous day's window.
    After kitchen_close: current day's window.

    Args:
        timezone_str: IANA timezone for the market
        country_code: Optional country code for market-specific kitchen_close_time

    Returns:
        Day name (e.g., "Monday", "Tuesday")
    """
    if settings.DEV_OVERRIDE_DAY and settings.DEV_OVERRIDE_DAY.strip():
        override_day = settings.DEV_OVERRIDE_DAY.strip().title()
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if override_day in valid_days:
            return override_day

    try:
        tz = pytz.timezone(timezone_str or "UTC")
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.timezone("America/Argentina/Buenos_Aires")

    now = datetime.now(tz)
    close_time = _get_kitchen_close_time(country_code, now.strftime("%A"))

    if now.time() < close_time:
        current_day = (now - timedelta(days=1)).strftime("%A")
    else:
        current_day = now.strftime("%A")

    return current_day


def is_today_kitchen_closed(country_code: str, timezone_str: str) -> bool:
    """
    Return True if today is a weekday and the kitchen has already closed in the market.

    Args:
        country_code: ISO country code (e.g., AR, PE)
        timezone_str: IANA timezone for the market

    Returns:
        True if kitchen is closed (weekday and now >= kitchen_close), False otherwise
    """
    if not country_code or not str(country_code).strip():
        return False

    try:
        from app.config.market_config import MarketConfiguration
        config = MarketConfiguration.get_market_config((country_code or "").upper())
        if not config or not config.kitchen_day_config:
            return False
    except Exception:
        return False

    current_day = get_effective_current_day(timezone_str or "UTC", country_code)
    if current_day not in VALID_KITCHEN_DAYS:
        return False

    day_config = config.kitchen_day_config.get(current_day)
    if not day_config or not day_config.get("enabled", True):
        return False

    close_time = _get_kitchen_close_time(country_code, current_day)

    try:
        tz = pytz.timezone(timezone_str or "UTC")
    except Exception:
        tz = pytz.UTC
    now_local = datetime.now(tz)
    return now_local.time() >= close_time


def date_to_kitchen_day(target_date: date) -> str:
    """
    Map a date to its kitchen day name. Handles DEV_OVERRIDE_DAY.
    No timezone - used for billing where date is already a closed day.

    Args:
        target_date: The date to map

    Returns:
        Day name (e.g., "Monday", "Tuesday")
    """
    if settings.DEV_OVERRIDE_DAY and settings.DEV_OVERRIDE_DAY.strip():
        override_day = settings.DEV_OVERRIDE_DAY.strip().title()
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if override_day in valid_days:
            return override_day

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return day_names[target_date.weekday()]


def get_kitchen_day_for_date(
    target_date: date,
    timezone_str: str,
    country_code: Optional[str] = None
) -> str:
    """
    Get kitchen day for a given date. For today (in timezone), uses get_effective_current_day.
    For other dates, uses date_to_kitchen_day.

    Args:
        target_date: The date to resolve
        timezone_str: IANA timezone (for "today" comparison)
        country_code: Optional for market-specific kitchen_close

    Returns:
        Day name (e.g., "Monday", "Tuesday")
    """
    try:
        tz = pytz.timezone(timezone_str or "UTC")
    except Exception:
        tz = pytz.UTC
    today_in_tz = datetime.now(tz).date()

    if target_date == today_in_tz:
        return get_effective_current_day(timezone_str, country_code)
    return date_to_kitchen_day(target_date)


def get_plate_selection_editable_until(
    plate_selection_id,
    db,
) -> Optional[datetime]:
    """
    Get the datetime until which a plate selection is editable.
    Editable until 1 hour before kitchen day opens (business_hours.open = 11:30, so cutoff = 10:30 AM local).

    Args:
        plate_selection_id: UUID of the plate selection
        db: Database connection

    Returns:
        datetime (timezone-aware, UTC) of the cutoff, or None if past cutoff or if resolution fails
    """
    from app.utils.db import db_read

    row = db_read(
        """
        SELECT ps.plate_selection_id, ps.kitchen_day, ps.pickup_date,
               a.country_code, a.timezone
        FROM plate_selection_info ps
        JOIN restaurant_info r ON ps.restaurant_id = r.restaurant_id
        JOIN address_info a ON r.address_id = a.address_id
        WHERE ps.plate_selection_id = %s AND ps.is_archived = FALSE
        """,
        (str(plate_selection_id),),
        connection=db,
        fetch_one=True,
    )
    if not row:
        return None

    timezone_str = row.get("timezone") or "America/Argentina/Buenos_Aires"
    country_code = (row.get("country_code") or "").strip().upper()
    kitchen_day = row.get("kitchen_day")
    target_date = row.get("pickup_date")
    if not target_date:
        return None

    try:
        from app.config.market_config import MarketConfiguration
        config = MarketConfiguration.get_market_config(country_code)
        if config and config.business_hours and kitchen_day:
            day_hours = config.business_hours.get(kitchen_day)
            if day_hours and day_hours.get("open"):
                open_time = day_hours["open"]
                cutoff_time = time(open_time.hour - 1, open_time.minute)
                if cutoff_time.hour < 0:
                    cutoff_time = time(23, cutoff_time.minute)
            else:
                cutoff_time = time(10, 30)
        else:
            cutoff_time = time(10, 30)
    except Exception:
        cutoff_time = time(10, 30)

    try:
        tz = pytz.timezone(timezone_str or "UTC")
    except Exception:
        tz = pytz.UTC

    cutoff_dt = datetime.combine(target_date, cutoff_time)
    cutoff_dt = tz.localize(cutoff_dt) if cutoff_dt.tzinfo is None else cutoff_dt
    cutoff_utc = cutoff_dt.astimezone(pytz.UTC)
    return cutoff_utc


def is_plate_selection_editable(plate_selection_id, db) -> bool:
    """
    Check if a plate selection is still within the editability window.
    Editable until 1 hour before kitchen day opens.

    Args:
        plate_selection_id: UUID of the plate selection
        db: Database connection

    Returns:
        True if editable (now < cutoff), False otherwise
    """
    editable_until = get_plate_selection_editable_until(plate_selection_id, db)
    if editable_until is None:
        return False
    now_utc = datetime.now(pytz.UTC)
    return now_utc < editable_until
