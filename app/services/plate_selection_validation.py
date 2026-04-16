# app/services/plate_selection_validation.py
"""
Validation logic for plate selection operations.

This module contains all validation functions for plate selection,
extracted from the main route to improve testability and maintainability.
"""

from datetime import date, timedelta
from uuid import UUID

from fastapi import HTTPException

from app.config import Status
from app.dto.models import PlateDTO, RestaurantDTO
from app.services.kitchen_day_service import VALID_KITCHEN_DAYS
from app.utils.log import log_info, log_warning


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
        raise HTTPException(status_code=422, detail="Invalid plate_id format") from None


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

    if getattr(restaurant, "is_archived", False) is True:
        raise HTTPException(
            status_code=403,
            detail=f"Restaurant '{restaurant.name}' is archived and cannot accept new orders.",
        )

    # Only 'Active' restaurants can accept plate selections
    if restaurant.status != Status.ACTIVE:
        status_message = {
            "inactive": "is currently inactive",
            "closed": "is currently closed",
            "suspended": "is currently suspended",
            "maintenance": "is under maintenance",
        }.get(restaurant.status, f'has status "{restaurant.status}"')

        log_warning(
            f"Restaurant {restaurant.restaurant_id} ({restaurant.name}) {status_message} - cannot accept plate selections"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Restaurant '{restaurant.name}' {status_message} and cannot accept new orders. Please try another restaurant.",
        )


def validate_pickup_time_range(
    country_code: str,
    kitchen_day: str,
    target_date: date,
    pickup_time_range: str,
) -> None:
    """
    Validate that pickup_time_range is within the market's allowed pickup windows
    for the given kitchen day.

    Uses get_pickup_windows_for_kitchen_day to obtain allowed windows and rejects
    values outside that list.

    Args:
        country_code: ISO country code (e.g. AR, US, PE)
        kitchen_day: Weekday name (Monday–Friday)
        target_date: The date for the kitchen day
        pickup_time_range: User-provided window in "HH:MM-HH:MM" format

    Raises:
        HTTPException: If pickup_time_range is not in the allowed windows
    """
    from datetime import date

    from app.services.restaurant_explorer_service import get_pickup_windows_for_kitchen_day

    if not pickup_time_range or not pickup_time_range.strip():
        raise HTTPException(
            status_code=422,
            detail="pickup_time_range is required and must be in HH:MM-HH:MM format (e.g. 11:30-11:45)",
        )
    date_obj = target_date if isinstance(target_date, date) else date.fromisoformat(str(target_date))
    allowed = get_pickup_windows_for_kitchen_day(
        (country_code or "").strip().upper(),
        kitchen_day,
        date_obj,
    )
    if not allowed:
        raise HTTPException(
            status_code=400,
            detail=f"No pickup windows available for {kitchen_day} in this market. Please select another day.",
        )
    normalized = pickup_time_range.strip()
    if normalized not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"pickup_time_range '{pickup_time_range}' is not a valid pickup window for {kitchen_day}. "
            f"Allowed windows: {', '.join(allowed[:5])}{'...' if len(allowed) > 5 else ''}",
        )


def validate_restaurant(
    restaurant: RestaurantDTO, target_date: str | None = None, country_code: str | None = None, db=None
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
    # 1. Status + is_archived validation (always check)
    validate_restaurant_status(restaurant)

    # 1b. Entity archival check (requires db)
    if db and restaurant.institution_entity_id:
        from app.utils.db import db_read

        entity_row = db_read(
            "SELECT is_archived FROM institution_entity_info WHERE institution_entity_id = %s",
            (str(restaurant.institution_entity_id),),
            connection=db,
            fetch_one=True,
        )
        if entity_row and entity_row["is_archived"]:
            raise HTTPException(
                status_code=403,
                detail=f"Restaurant '{restaurant.name}' belongs to an archived entity and cannot accept new orders.",
            )

    # 2. Holiday validation (only if target_date provided)
    if target_date and country_code and db:
        # Check national holidays first (takes precedence)
        if _is_date_national_holiday(target_date, country_code, db):
            raise HTTPException(
                status_code=403,
                detail=f"Restaurant '{restaurant.name}' cannot accept orders on {target_date} due to a national holiday. Please select another date.",
            )

        # Check restaurant holidays
        if _is_date_restaurant_holiday(target_date, restaurant.restaurant_id, db):
            raise HTTPException(
                status_code=403,
                detail=f"Restaurant '{restaurant.name}' is closed on {target_date} due to a restaurant holiday. Please select another date.",
            )


def determine_target_kitchen_day(
    target_day: str | None,
    plate: PlateDTO,
    current_day: str,
    available_kitchen_days: list,
    country_code: str = None,
    db=None,
    timezone_str: str | None = None,
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
        return _validate_customer_specified_day(
            target_day, available_kitchen_days, current_day, timezone_str=timezone_str
        )
    return _find_next_available_day(available_kitchen_days, current_day, country_code, db, timezone_str)


def _is_target_day_within_order_window(target_day: str, timezone_str: str | None) -> bool:
    """
    Check if the target day's next occurrence is within the allowed order window (today through today+7 days).

    Args:
        target_day: Target weekday name (Monday–Friday)
        timezone_str: IANA timezone for date resolution

    Returns:
        True if the next occurrence of target_day is within the window, False otherwise
    """
    if not timezone_str:
        return False
    try:
        from app.services.restaurant_explorer_service import resolve_weekday_to_next_occurrence

        target_date = resolve_weekday_to_next_occurrence(target_day, timezone_str)
    except ValueError:
        return False
    from datetime import datetime

    try:
        import pytz

        today = datetime.now(pytz.timezone(timezone_str)).date()
    except Exception:
        today = datetime.now().date()
    return today <= target_date <= today + timedelta(days=7)


def _validate_customer_specified_day(
    target_day: str, available_kitchen_days: list, current_day: str, *, timezone_str: str | None = None
) -> str:
    """
    Validate a customer-specified target day.
    """
    # Check if the target day is valid for kitchen operations (weekdays only)
    if target_day not in VALID_KITCHEN_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Kitchen is not operational on {target_day}. Available days: {', '.join(VALID_KITCHEN_DAYS)}",
        )

    # Check if the target day is in the plate's available kitchen days
    if target_day not in available_kitchen_days:
        raise HTTPException(
            status_code=400,
            detail=f"Plate is not available for {target_day}. Available days: {', '.join(available_kitchen_days)}",
        )

    # Check if the target day is within the 1-week-ahead order window
    if not _is_target_day_within_order_window(target_day, timezone_str):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot order for {target_day} from {current_day}. Orders are only allowed up to 1 week ahead.",
        )

    return target_day


def _find_next_available_day(
    available_kitchen_days: list, current_day: str, country_code: str = None, db=None, timezone_str: str | None = None
) -> str:
    """
    Find the next available kitchen day within the next 7 calendar days.
    """
    target_day = _find_next_available_kitchen_day_in_week(
        current_day, available_kitchen_days, country_code, db, timezone_str
    )

    if not target_day:
        raise HTTPException(
            status_code=400,
            detail=f"No available kitchen days found within the next week. Available days: {', '.join(available_kitchen_days)}",
        )

    # Log the decision if it's different from current day
    if target_day != current_day:
        log_info(f"Customer ordering on {current_day} for future day {target_day}")

    return target_day


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

    # Check for exact date match
    query = """
    SELECT COUNT(*) FROM national_holidays
    WHERE country_code = %s
    AND holiday_date = %s
    AND is_archived = FALSE
    """
    from app.utils.db import db_read

    result = db_read(query, (country_code, date_str), connection=db, fetch_one=True)

    if result and result.get("count", 0) > 0:
        return True

    # Check for recurring holidays (same month and day)
    from datetime import datetime

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
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

        return result and result.get("count", 0) > 0
    except ValueError:
        return False


def _find_next_available_kitchen_day_in_week(
    current_day: str, available_kitchen_days: list, country_code: str = None, db=None, timezone_str: str | None = None
) -> str | None:
    """
    Find the next available kitchen day within the next 7 calendar days.
    Considers national holidays when selecting the next available day.

    Args:
        current_day: Current day of the week (unused; kept for API compatibility)
        available_kitchen_days: List of available kitchen days for the plate
        country_code: Country code to check for national holidays
        db: Database connection for holiday checks
        timezone_str: Optional IANA timezone for timezone-aware today

    Returns:
        The next available kitchen day or None if none found
    """
    from datetime import datetime, timedelta

    weekday_names = ("monday", "tuesday", "wednesday", "thursday", "friday")

    # Get current date (timezone-aware when timezone_str provided)
    if timezone_str:
        try:
            import pytz

            today = datetime.now(pytz.timezone(timezone_str)).date()
        except Exception:
            today = datetime.now().date()
    else:
        today = datetime.now().date()

    # Iterate over the next 7 calendar days
    from app.config.settings import settings as _settings

    for days_ahead in range(8):  # 0 through 7 inclusive
        d = today + timedelta(days=days_ahead)
        if d.weekday() >= 5:  # Saturday=5, Sunday=6
            if not _settings.DEV_MODE:
                continue  # Production: skip weekends
            # DEV_MODE: map weekend to friday so Postman/dev testing works any day
            day_name = "friday"
        else:
            day_name = weekday_names[d.weekday()]
        if day_name not in available_kitchen_days:
            continue
        if country_code and db:
            date_str = d.strftime("%Y-%m-%d")
            if _is_date_national_holiday(date_str, country_code, db):
                continue
        return day_name

    return None


def _is_date_restaurant_holiday(date_str: str, restaurant_id: UUID, db) -> bool:
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

    if result and result.get("count", 0) > 0:
        return True

    from datetime import datetime

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        month = date_obj.month
        day = date_obj.day

        query = """
        SELECT COUNT(*) FROM restaurant_holidays
        WHERE restaurant_id = %s
        AND recurring_month = %s
        AND recurring_day = %s
        AND is_recurring = TRUE
        AND is_archived = FALSE
        """
        result = db_read(query, (str(restaurant_id), month, day), connection=db, fetch_one=True)

        return result and result.get("count", 0) > 0
    except ValueError:
        return False
