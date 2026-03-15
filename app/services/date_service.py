"""
Date Service - Business Logic for Date and Time Operations

This service contains business logic for date and time calculations,
including timezone handling, business day calculations, and dev overrides.

Business Rules:
- Order cutoff is 1:30 PM local (see app/config/market_config.py kitchen_close).
- Before 1:30 PM: considered previous day's service window
- After 1:30 PM: considered current day's service window
- DEV_OVERRIDE_DAY: allows overriding for testing
"""

from datetime import datetime, timedelta, time
from typing import Optional
import pytz
from app.config.settings import settings

def get_effective_current_day(
    timezone_str: str = 'America/Argentina/Buenos_Aires',
    country_code: Optional[str] = None
) -> str:
    """
    Get the effective current day, considering dev overrides and timezone-aware business hours.
    Delegates to kitchen_day_service for centralized logic.

    Business Rules:
    - Before kitchen_close (e.g. 1:30 PM local): previous day's service window
    - After kitchen_close: current day's service window
    - DEV_OVERRIDE_DAY: allows overriding for testing (e.g., "Monday")

    Args:
        timezone_str: The timezone to use for calculations
        country_code: Optional country code for market-specific kitchen_close_time

    Returns:
        Day name (e.g., "Monday", "Tuesday", etc.)
    """
    from app.services.kitchen_day_service import get_effective_current_day as _get_effective_current_day
    return _get_effective_current_day(timezone_str, country_code)

def is_dev_mode() -> bool:
    """Check if any dev overrides are active"""
    return bool(settings.DEV_OVERRIDE_DAY and settings.DEV_OVERRIDE_DAY.strip())

def get_effective_current_date(timezone_str: str = 'America/Argentina/Buenos_Aires') -> datetime:
    """
    Get the effective current datetime, considering dev overrides.
    Useful for consistent date calculations across the app.
    """
    try:
        tz = pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
    
    now = datetime.now(tz)
    
    # If we have a day override, we might want to adjust the date too
    if settings.DEV_OVERRIDE_DAY and settings.DEV_OVERRIDE_DAY.strip():
        override_day = settings.DEV_OVERRIDE_DAY.strip().title()
        valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        if override_day in valid_days:
            # Find the most recent occurrence of this day
            current_weekday = now.weekday()  # 0=Monday, 6=Sunday
            target_weekday = valid_days.index(override_day)
            days_diff = target_weekday - current_weekday
            
            # If target day is in the future, go to last week's occurrence
            if days_diff > 0:
                days_diff -= 7
                
            override_date = now + timedelta(days=days_diff)
            return override_date.replace(hour=14, minute=0, second=0, microsecond=0)  # 2 PM = active window
    
    return now
