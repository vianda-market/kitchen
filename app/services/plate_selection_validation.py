# app/services/plate_selection_validation.py
"""
Validation logic for plate selection operations.

This module contains all validation functions for plate selection,
extracted from the main route to improve testability and maintainability.
"""

from typing import Optional
from uuid import UUID
from fastapi import HTTPException
from app.dto.models import PlateDTO, RestaurantDTO
from app.utils.log import log_info, log_warning
from app.config import Status


def validate_plate_selection_data(payload: dict) -> None:
    """
    Validate the plate selection payload data.
    
    Raises HTTPException if validation fails.
    """
    # Validate plate_id is a valid UUID
    try:
        from uuid import UUID
        UUID(str(payload.get("plate_id")))
    except (ValueError, TypeError):
        log_warning(f"Invalid plate_id format: {payload.get('plate_id')}")
        raise HTTPException(status_code=422, detail="Invalid plate_id format")


def validate_restaurant_status(restaurant: RestaurantDTO) -> None:
    """
    Validate that the restaurant is available for plate selection (status only).
    
    This is a convenience function that only checks restaurant status.
    For comprehensive validation including holidays, use validate_restaurant().
    
    Args:
        restaurant: Restaurant DTO to validate
        
    Raises:
        HTTPException: If restaurant status is not 'Active'
    """
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    
    # Only 'Active' restaurants can accept plate selections
    if restaurant.status != Status.ACTIVE:
        status_message = {
            'Inactive': 'is currently inactive',
            'Closed': 'is currently closed',
            'Suspended': 'is currently suspended',
            'Maintenance': 'is under maintenance'
        }.get(restaurant.status, f'has status "{restaurant.status}"')
        
        log_warning(f"Restaurant {restaurant.restaurant_id} ({restaurant.name}) {status_message} - cannot accept plate selections")
        raise HTTPException(
            status_code=403,
            detail=f"Restaurant '{restaurant.name}' {status_message} and cannot accept new orders. Please try another restaurant."
        )


def validate_restaurant(
    restaurant: RestaurantDTO,
    target_date: Optional[str] = None,
    country_code: Optional[str] = None,
    db=None
) -> None:
    """
    Comprehensive restaurant validation including status and holidays.
    
    This function performs restaurant validation including:
    1. Restaurant Status - must be 'Active'
    2. National Holiday Validation - restaurant cannot accept orders on national holidays
    3. Restaurant Holiday Validation - restaurant cannot accept orders on restaurant-specific holidays
    
    Args:
        restaurant: Restaurant DTO to validate
        target_date: Optional target date in YYYY-MM-DD format for holiday checking
        country_code: Optional country code (2-letter ISO) for national holiday checking
        db: Optional database connection for holiday queries
        
    Raises:
        HTTPException: If restaurant is not available for plate selection
        
    Note:
        - Status validation is always performed
        - Holiday validation is only performed if target_date, country_code, and db are provided
        - National holidays take precedence (checked first)
    """
    # 1. Status validation (always check)
    validate_restaurant_status(restaurant)
    
    # 2. Holiday validation (only if target_date provided)
    if target_date and country_code and db:
        # Check national holidays first (takes precedence)
        if _is_date_national_holiday(target_date, country_code, db):
            raise HTTPException(
                status_code=403,
                detail=f"Restaurant '{restaurant.name}' cannot accept orders on {target_date} due to a national holiday. Please select another date."
            )
        
        # Check restaurant holidays
        if _is_date_restaurant_holiday(target_date, restaurant.restaurant_id, db):
            raise HTTPException(
                status_code=403,
                detail=f"Restaurant '{restaurant.name}' is closed on {target_date} due to a restaurant holiday. Please select another date."
            )


def determine_target_kitchen_day(
    target_day: Optional[str],
    plate: PlateDTO,
    current_day: str,
    available_kitchen_days: list,
    country_code: str = None,
    db=None
) -> str:
    """
    Determine the target kitchen day for the plate selection.
    
    Args:
        target_day: Customer-specified target day (optional)
        plate: Plate DTO
        current_day: Current day of the week
        available_kitchen_days: List of available kitchen days for the plate
        
    Returns:
        The determined target kitchen day
        
    Raises:
        HTTPException if no valid target day can be determined
    """
    if target_day:
        return _validate_customer_specified_day(target_day, available_kitchen_days, current_day)
    else:
        return _find_next_available_day(available_kitchen_days, current_day, country_code, db)


def _validate_customer_specified_day(
    target_day: str,
    available_kitchen_days: list,
    current_day: str
) -> str:
    """
    Validate a customer-specified target day.
    """
    # Check if the target day is valid for kitchen operations (weekdays only)
    valid_kitchen_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    if target_day not in valid_kitchen_days:
        raise HTTPException(
            status_code=400, 
            detail=f"Kitchen is not operational on {target_day}. Available days: {', '.join(valid_kitchen_days)}"
        )
    
    # Check if the target day is in the plate's available kitchen days
    if target_day not in available_kitchen_days:
        raise HTTPException(
            status_code=400, 
            detail=f"Plate is not available for {target_day}. Available days: {', '.join(available_kitchen_days)}"
        )
    
    # Check if the target day is in the remainder of the week
    if not _is_day_in_remainder_of_week(current_day, target_day):
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot order for {target_day} from {current_day}. Orders are only allowed for the remainder of the current week."
        )
    
    return target_day


def _find_next_available_day(available_kitchen_days: list, current_day: str, country_code: str = None, db=None) -> str:
    """
    Find the next available kitchen day in the remainder of the week.
    """
    target_day = _find_next_available_kitchen_day_in_week(current_day, available_kitchen_days, country_code, db)
    
    if not target_day:
        raise HTTPException(
            status_code=400, 
            detail=f"No available kitchen days found for the remainder of the week. Available days: {', '.join(available_kitchen_days)}"
        )
    
    # Log the decision if it's different from current day
    if target_day != current_day:
        log_info(f"Customer ordering on {current_day} for future day {target_day}")
    
    return target_day


def _is_day_in_remainder_of_week(current_day: str, target_day: str) -> bool:
    """
    Check if the target day is in the remainder of the current week.
    
    Args:
        current_day: Current day of the week
        target_day: Target day to check
        
    Returns:
        True if target day is in the remainder of the week, False otherwise
    """
    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    try:
        current_index = days_of_week.index(current_day)
        target_index = days_of_week.index(target_day)
        
        # Target day is valid if it's today or later in the week
        return target_index >= current_index
    except ValueError:
        # Invalid day names
        return False


def _is_date_national_holiday(date_str: str, country_code: str, db) -> bool:
    """
    Check if a specific date is a national holiday in the given country.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        country_code: Country code (e.g., 'AR', 'PE')
        db: Database connection
        
    Returns:
        True if the date is a national holiday, False otherwise
    """
    from app.services.crud_service import national_holiday_service
    
    # Check for exact date match
    query = """
    SELECT COUNT(*) FROM national_holidays 
    WHERE country_code = %s 
    AND holiday_date = %s 
    AND is_archived = FALSE
    """
    from app.utils.db import db_read
    result = db_read(query, (country_code, date_str), connection=db, fetch_one=True)
    
    if result and result.get('count', 0) > 0:
        return True
    
    # Check for recurring holidays (same month and day)
    from datetime import datetime
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        month = date_obj.month
        day = date_obj.day
        
        query = """
        SELECT COUNT(*) FROM national_holidays 
        WHERE country_code = %s 
        AND recurring_month = %s 
        AND recurring_day = %s 
        AND is_recurring = TRUE
        AND is_archived = FALSE
        """
        result = db_read(query, (country_code, month, day), connection=db, fetch_one=True)
        
        return result and result.get('count', 0) > 0
    except ValueError:
        return False


def _find_next_available_kitchen_day_in_week(current_day: str, available_kitchen_days: list, country_code: str = None, db=None) -> Optional[str]:
    """
    Find the next available kitchen day in the remainder of the current week.
    If we're on a weekend, look ahead to next week.
    Considers national holidays when selecting the next available day.
    
    Args:
        current_day: Current day of the week
        available_kitchen_days: List of available kitchen days for the plate
        country_code: Country code to check for national holidays
        db: Database connection for holiday checks
        
    Returns:
        The next available kitchen day or None if none found
    """
    from datetime import datetime, timedelta
    
    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    # Get current date
    today = datetime.now()
    
    try:
        current_index = days_of_week.index(current_day)
        
        # Look for the next available day starting from today
        for i in range(current_index, len(days_of_week)):
            day = days_of_week[i]
            if day in available_kitchen_days:
                # Check if this day is a national holiday
                if country_code and db:
                    # Calculate the date for this day of the week
                    days_ahead = i - current_index
                    target_date = today + timedelta(days=days_ahead)
                    date_str = target_date.strftime('%Y-%m-%d')
                    
                    if _is_date_national_holiday(date_str, country_code, db):
                        continue  # Skip this day if it's a holiday
                
                return day
        
        return None
    except ValueError:
        # Current day is not a weekday (Saturday/Sunday), look ahead to next week
        # Find the first available kitchen day of next week, skipping holidays
        for i, day in enumerate(days_of_week):
            if day in available_kitchen_days:
                # Check if this day is a national holiday
                if country_code and db:
                    # Calculate the date for this day of next week
                    # If today is Saturday (index 5), next Monday is in 2 days
                    # If today is Sunday (index 6), next Monday is in 1 day
                    current_weekday = today.weekday()  # Monday=0, Sunday=6
                    if current_weekday == 5:  # Saturday
                        days_ahead = 2 + i
                    elif current_weekday == 6:  # Sunday
                        days_ahead = 1 + i
                    else:
                        days_ahead = (7 - current_weekday) + i
                    
                    target_date = today + timedelta(days=days_ahead)
                    date_str = target_date.strftime('%Y-%m-%d')
                    
                    if _is_date_national_holiday(date_str, country_code, db):
                        continue  # Skip this day if it's a holiday
                
                return day
        
        return None


def _is_date_restaurant_holiday(
    date_str: str,
    restaurant_id: UUID,
    db
) -> bool:
    """
    Check if a specific date is a restaurant holiday.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        restaurant_id: Restaurant ID
        db: Database connection
        
    Returns:
        True if the date is a restaurant holiday, False otherwise
    """
    from app.utils.db import db_read
    
    # Check exact date match
    query = """
    SELECT COUNT(*) FROM restaurant_holidays 
    WHERE restaurant_id = %s 
    AND holiday_date = %s 
    AND is_archived = FALSE
    """
    result = db_read(query, (str(restaurant_id), date_str), connection=db, fetch_one=True)
    
    if result and result.get('count', 0) > 0:
        return True
    
    # Check recurring holidays (MM-DD format)
    from datetime import datetime
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        month_day = f"{date_obj.month:02d}-{date_obj.day:02d}"
        
        query = """
        SELECT COUNT(*) FROM restaurant_holidays 
        WHERE restaurant_id = %s 
        AND recurring_month_day = %s 
        AND is_recurring = TRUE
        AND is_archived = FALSE
        """
        result = db_read(query, (str(restaurant_id), month_day), connection=db, fetch_one=True)
        
        return result and result.get('count', 0) > 0
    except ValueError:
        return False
