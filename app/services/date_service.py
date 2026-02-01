"""
Date Service - Business Logic for Date and Time Operations

This service contains business logic for date and time calculations,
including timezone handling, business day calculations, and dev overrides.

Business Rules:
- Before 1 PM: considered previous day's service window
- After 1 PM: considered current day's service window
- DEV_OVERRIDE_DAY: allows overriding for testing
"""

from datetime import datetime, timedelta, time
import pytz
from app.config.settings import settings

def get_effective_current_day(timezone_str: str = 'America/Argentina/Buenos_Aires') -> str:
    """
    Get the effective current day, considering dev overrides and timezone-aware business hours.
    
    Business Rules:
    - Before 1 PM: considered previous day's service window
    - After 1 PM: considered current day's service window
    - DEV_OVERRIDE_DAY: allows overriding for testing (e.g., "Monday")
    
    Args:
        timezone_str: The timezone to use for calculations
        
    Returns:
        Day name (e.g., "Monday", "Tuesday", etc.)
    """
    
    # Check for dev override first
    if settings.DEV_OVERRIDE_DAY and settings.DEV_OVERRIDE_DAY.strip():
        override_day = settings.DEV_OVERRIDE_DAY.strip().title()
        valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        if override_day in valid_days:
            return override_day
    
    # Normal business logic
    try:
        tz = pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        # Fallback to default timezone if invalid
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
    
    now = datetime.now(tz)
    
    # Determine the current day window based on time
    if now.time() < time(13, 0):
        # Still in yesterday's window (5pm yesterday to 1pm today)
        current_day = (now - timedelta(days=1)).strftime('%A')
    else:
        # In today's window (5pm today to 1pm tomorrow)
        current_day = now.strftime('%A')
    
    return current_day

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
