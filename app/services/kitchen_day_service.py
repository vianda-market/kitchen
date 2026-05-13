"""
Kitchen Day Service - Centralized kitchen day logic.

Provides a single source of truth for:
- Effective current day (with cutoff, configurable via supplier_terms / market_payout_aggregator)
- Kitchen closed checks
- Pickup availability (kitchen_open_time gating)
- Date-to-kitchen-day mapping
- Timezone-aware kitchen day resolution

Resolution order for kitchen_close_time / kitchen_open_time:
1. supplier_terms (per-supplier override, if institution_id provided)
2. market_payout_aggregator (market-level default via country_code)
3. MarketConfiguration.kitchen_day_config[day].kitchen_close
4. Hardcoded time(9, 0) / time(13, 30)
"""

from datetime import date, datetime, time, timedelta
from uuid import UUID

import pytz

from app.config import KitchenDay
from app.config.settings import settings

# Re-export for backward compatibility
VALID_KITCHEN_DAYS = tuple(KitchenDay.values())
WEEKDAY_NUM_TO_NAME = ("monday", "tuesday", "wednesday", "thursday", "friday")

DEFAULT_KITCHEN_OPEN = time(9, 0)
DEFAULT_KITCHEN_CLOSE = time(13, 30)


def _parse_time(v) -> time | None:
    """Convert a time object or HH:MM string to a time. Returns None on failure."""
    if v is None:
        return None
    if isinstance(v, time):
        return v
    if isinstance(v, str):
        try:
            return datetime.strptime(v.strip(), "%H:%M").time()
        except ValueError:
            return None
    return None


def _get_kitchen_time(
    field: str,
    country_code: str | None = None,
    institution_id: UUID | None = None,
    db=None,
    day_name: str | None = None,
) -> time:
    """
    Resolve kitchen_open_time or kitchen_close_time.
    Resolution: supplier_terms → market_payout_aggregator → MarketConfiguration → hardcoded.
    """
    default = DEFAULT_KITCHEN_OPEN if field == "kitchen_open_time" else DEFAULT_KITCHEN_CLOSE

    # 1. Supplier-level override (requires institution_id + db)
    if institution_id and db:
        try:
            from app.services.crud_service import supplier_terms_service

            terms = supplier_terms_service.get_by_field("institution_id", institution_id, db)
            if terms:
                val = _parse_time(getattr(terms, field, None))
                if val is not None:
                    return val
        except Exception:
            pass

    # 2. Market-level default via market_payout_aggregator
    if country_code and str(country_code).strip():
        try:
            from app.utils.db import db_read as _db_read

            if db:
                row = _db_read(
                    f"SELECT mpa.{field} FROM market_payout_aggregator mpa "
                    "JOIN market_info m ON mpa.market_id = m.market_id "
                    "WHERE m.country_code = %s AND mpa.is_archived = FALSE",
                    (country_code.upper(),),
                    connection=db,
                    fetch_one=True,
                )
                if row:
                    val = _parse_time(row.get(field))
                    if val is not None:
                        return val
        except Exception:
            pass

    # 3. MarketConfiguration fallback (kitchen_close only)
    if field == "kitchen_close_time" and country_code and str(country_code).strip():
        try:
            from app.config.market_config import MarketConfiguration

            config = MarketConfiguration.get_market_config(country_code.upper())
            if config and config.kitchen_day_config:
                day = day_name or "monday"
                day_config = config.kitchen_day_config.get(day)
                if day_config and day_config.get("kitchen_close"):
                    return day_config["kitchen_close"]
                for d in WEEKDAY_NUM_TO_NAME:
                    dc = config.kitchen_day_config.get(d)
                    if dc and dc.get("kitchen_close"):
                        return dc["kitchen_close"]
        except Exception:
            pass

    return default


def _get_kitchen_close_time(
    country_code: str | None,
    day_name: str | None = None,
    institution_id: UUID | None = None,
    db=None,
) -> time:
    """Resolve kitchen close time. Backward-compatible wrapper."""
    return _get_kitchen_time("kitchen_close_time", country_code, institution_id, db, day_name)


def _get_kitchen_open_time(
    country_code: str | None,
    institution_id: UUID | None = None,
    db=None,
) -> time:
    """Resolve kitchen open time."""
    return _get_kitchen_time("kitchen_open_time", country_code, institution_id, db)


def get_effective_current_day(
    timezone_str: str = "America/Argentina/Buenos_Aires",
    country_code: str | None = None,
    institution_id: UUID | None = None,
    db=None,
) -> str:
    """
    Get the effective current kitchen day, considering cutoff time and dev overrides.

    Before kitchen_close (e.g. 1:30 PM local): previous day's window.
    After kitchen_close: current day's window.

    Args:
        timezone_str: IANA timezone for the market
        country_code: Optional country code for market-specific kitchen_close_time
        institution_id: Optional institution UUID for supplier-specific override
        db: Database connection (required when institution_id is provided)

    Returns:
        Day name (e.g., "monday", "tuesday")
    """
    if settings.DEV_OVERRIDE_DAY and settings.DEV_OVERRIDE_DAY.strip():
        override_day = settings.DEV_OVERRIDE_DAY.strip().lower()
        valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if override_day in valid_days:
            return override_day

    try:
        tz = pytz.timezone(timezone_str or "UTC")
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.timezone("America/Argentina/Buenos_Aires")

    now = datetime.now(tz)
    close_time = _get_kitchen_close_time(country_code, now.strftime("%A").lower(), institution_id, db)

    if now.time() < close_time:
        current_day = (now - timedelta(days=1)).strftime("%A").lower()
    else:
        current_day = now.strftime("%A").lower()

    # DEV_MODE: treat weekends as the nearest weekday so Postman E2E collections and
    # dev testing work any day of the week. Production (DEV_MODE=False) is unaffected.
    if settings.DEV_MODE and current_day not in VALID_KITCHEN_DAYS:
        # Saturday → friday, Sunday → friday (most recent completed kitchen day)
        current_day = "friday"

    return current_day


def is_today_kitchen_closed(
    country_code: str,
    timezone_str: str,
    institution_id: UUID | None = None,
    db=None,
) -> bool:
    """
    Return True if today is a weekday and the kitchen has already closed.

    Args:
        country_code: ISO country code (e.g., AR, PE)
        timezone_str: IANA timezone for the market
        institution_id: Optional institution UUID for supplier-specific override
        db: Database connection (required when institution_id is provided)

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

    current_day = get_effective_current_day(timezone_str or "UTC", country_code, institution_id, db)
    if current_day not in VALID_KITCHEN_DAYS:
        return False

    day_config = config.kitchen_day_config.get(current_day)
    if not day_config or not day_config.get("enabled", True):
        return False

    close_time = _get_kitchen_close_time(country_code, current_day, institution_id, db)

    try:
        tz = pytz.timezone(timezone_str or "UTC")
    except Exception:
        tz = pytz.UTC
    now_local = datetime.now(tz)
    return now_local.time() >= close_time


def is_pickup_available(
    country_code: str,
    timezone_str: str,
    institution_id: UUID | None = None,
    db=None,
) -> bool:
    """
    Return True if current local time >= effective kitchen_open_time for this supplier.
    Gates QR code scanning and vianda pickup availability.

    Args:
        country_code: ISO country code
        timezone_str: IANA timezone
        institution_id: Optional institution UUID for supplier-specific override
        db: Database connection

    Returns:
        True if pickup is available (now >= kitchen_open_time), False otherwise
    """
    open_time = _get_kitchen_open_time(country_code, institution_id, db)
    close_time = _get_kitchen_close_time(country_code, institution_id=institution_id, db=db)

    try:
        tz = pytz.timezone(timezone_str or "UTC")
    except Exception:
        tz = pytz.UTC
    now_local = datetime.now(tz).time()

    # Pickup is available between open and close
    return open_time <= now_local <= close_time


def date_to_kitchen_day(target_date: date) -> str:
    """
    Map a date to its kitchen day name. Handles DEV_OVERRIDE_DAY.
    No timezone - used for billing where date is already a closed day.

    In DEV_MODE, weekends map to friday (same as get_effective_current_day).

    Args:
        target_date: The date to map

    Returns:
        Day name (e.g., "monday", "tuesday", "friday")
    """
    if settings.DEV_OVERRIDE_DAY and settings.DEV_OVERRIDE_DAY.strip():
        override_day = settings.DEV_OVERRIDE_DAY.strip().lower()
        valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if override_day in valid_days:
            return override_day

    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    result = day_names[target_date.weekday()]

    # DEV_MODE: map weekends to friday for billing/settlement pipeline
    if settings.DEV_MODE and result not in VALID_KITCHEN_DAYS:
        result = "friday"

    return result


def get_kitchen_day_for_date(
    target_date: date,
    timezone_str: str,
    country_code: str | None = None,
    institution_id: UUID | None = None,
    db=None,
) -> str:
    """
    Get kitchen day for a given date. For today (in timezone), uses get_effective_current_day.
    For other dates, uses date_to_kitchen_day.

    Args:
        target_date: The date to resolve
        timezone_str: IANA timezone (for "today" comparison)
        country_code: Optional for market-specific kitchen_close
        institution_id: Optional institution UUID for supplier-specific override
        db: Database connection

    Returns:
        Day name (e.g., "monday", "tuesday")
    """
    try:
        tz = pytz.timezone(timezone_str or "UTC")
    except Exception:
        tz = pytz.UTC
    today_in_tz = datetime.now(tz).date()

    if target_date == today_in_tz:
        return get_effective_current_day(timezone_str, country_code, institution_id, db)
    return date_to_kitchen_day(target_date)


def get_vianda_selection_editable_until(
    vianda_selection_id,
    db,
) -> datetime | None:
    """
    Get the datetime until which a vianda selection is editable.
    Editable until 1 hour before kitchen day opens (business_hours.open = 11:30, so cutoff = 10:30 AM local).

    Args:
        vianda_selection_id: UUID of the vianda selection
        db: Database connection

    Returns:
        datetime (timezone-aware, UTC) of the cutoff, or None if past cutoff or if resolution fails
    """
    from app.utils.db import db_read

    row = db_read(
        """
        SELECT ps.vianda_selection_id, ps.kitchen_day, ps.pickup_date,
               a.country_code, a.timezone
        FROM vianda_selection_info ps
        JOIN restaurant_info r ON ps.restaurant_id = r.restaurant_id
        JOIN address_info a ON r.address_id = a.address_id
        WHERE ps.vianda_selection_id = %s AND ps.is_archived = FALSE
        """,
        (str(vianda_selection_id),),
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


def is_vianda_selection_editable(vianda_selection_id, db) -> bool:
    """
    Check if a vianda selection is still within the editability window.
    Editable until 1 hour before kitchen day opens.

    In DEV_MODE, always returns True so Postman E2E collections can replace
    vianda selections regardless of time-of-day.

    Args:
        vianda_selection_id: UUID of the vianda selection
        db: Database connection

    Returns:
        True if editable (now < cutoff or DEV_MODE), False otherwise
    """
    if settings.DEV_MODE:
        return True
    editable_until = get_vianda_selection_editable_until(vianda_selection_id, db)
    if editable_until is None:
        return False
    now_utc = datetime.now(pytz.UTC)
    return now_utc < editable_until
