"""
Unit tests for plate selection validation (validate_pickup_time_range, 1-week-ahead order window, etc.).
"""

import pytest
from datetime import date
from unittest.mock import Mock
from fastapi import HTTPException
from freezegun import freeze_time

from app.services.plate_selection_validation import (
    validate_pickup_time_range,
    determine_target_kitchen_day,
)
from app.dto.models import PlateDTO


class TestValidatePickupTimeRange:
    """validate_pickup_time_range rejects values outside market's allowed pickup windows."""

    def test_valid_window_ar_monday_passes(self):
        """AR market Monday: 12:00-12:15 is within 11:30-13:30."""
        validate_pickup_time_range("AR", "Monday", date(2026, 3, 9), "12:00-12:15")

    def test_valid_window_us_friday_passes(self):
        """US market Friday: 11:30-11:45 is valid."""
        validate_pickup_time_range("US", "Friday", date(2026, 3, 13), "11:30-11:45")

    def test_invalid_window_raises_400(self):
        """Window outside allowed range raises 400 with allowed windows in detail."""
        with pytest.raises(HTTPException) as exc_info:
            validate_pickup_time_range("AR", "Monday", date(2026, 3, 9), "08:00-08:15")
        assert exc_info.value.status_code == 400
        assert "08:00-08:15" in str(exc_info.value.detail)
        assert "11:30" in str(exc_info.value.detail) or "Allowed" in str(exc_info.value.detail)

    def test_empty_pickup_time_range_raises_422(self):
        """Empty or missing pickup_time_range raises 422."""
        with pytest.raises(HTTPException) as exc_info:
            validate_pickup_time_range("AR", "Monday", date(2026, 3, 9), "")
        assert exc_info.value.status_code == 422

    def test_unknown_country_raises_400(self):
        """Unknown country returns no windows -> 400."""
        with pytest.raises(HTTPException) as exc_info:
            validate_pickup_time_range("XX", "Monday", date(2026, 3, 9), "12:00-12:15")
        assert exc_info.value.status_code == 400
        assert "No pickup windows" in str(exc_info.value.detail)


class TestOneWeekAheadOrderWindow:
    """1-week-ahead order window: orders allowed from today through today+7 days."""

    def _make_plate(self):
        plate = Mock(spec=PlateDTO)
        plate.plate_id = "00000000-0000-0000-0000-000000000001"
        plate.restaurant_id = "00000000-0000-0000-0000-000000000002"
        return plate

    @freeze_time("2026-03-07 12:00:00")  # Saturday March 7
    def test_saturday_to_monday_allowed(self):
        """From Saturday, ordering for Monday (2 days ahead) is allowed."""
        plate = self._make_plate()
        result = determine_target_kitchen_day(
            target_day="Monday",
            plate=plate,
            current_day="Saturday",
            available_kitchen_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            country_code="AR",
            db=None,
            timezone_str="America/Argentina/Buenos_Aires",
        )
        assert result == "Monday"

    @freeze_time("2026-03-03 12:00:00")  # Tuesday March 3
    def test_tuesday_to_next_monday_allowed(self):
        """From Tuesday, ordering for next Monday (6 days ahead) is allowed."""
        plate = self._make_plate()
        result = determine_target_kitchen_day(
            target_day="Monday",
            plate=plate,
            current_day="Tuesday",
            available_kitchen_days=["Monday", "Wednesday", "Friday"],
            country_code="AR",
            db=None,
            timezone_str="America/Argentina/Buenos_Aires",
        )
        assert result == "Monday"

    @freeze_time("2026-03-03 15:00:00")  # Tuesday March 3, 3pm
    def test_tuesday_to_next_tuesday_allowed(self):
        """From Tuesday 3pm, ordering for next Tuesday (7 days ahead) is allowed."""
        plate = self._make_plate()
        result = determine_target_kitchen_day(
            target_day="Tuesday",
            plate=plate,
            current_day="Tuesday",
            available_kitchen_days=["Tuesday"],
            country_code="AR",
            db=None,
            timezone_str="America/Argentina/Buenos_Aires",
        )
        assert result == "Tuesday"

    @freeze_time("2026-03-07 12:00:00")  # Saturday March 7
    def test_saturday_without_timezone_rejects(self):
        """When timezone_str is None, target day is rejected with 1-week-ahead message."""
        plate = self._make_plate()
        with pytest.raises(HTTPException) as exc_info:
            determine_target_kitchen_day(
                target_day="Monday",
                plate=plate,
                current_day="Saturday",
                available_kitchen_days=["Monday"],
                country_code="AR",
                db=None,
                timezone_str=None,
            )
        assert exc_info.value.status_code == 400
        assert "1 week ahead" in str(exc_info.value.detail)

    def test_plate_not_available_for_day_raises_400(self):
        """Target day not in plate's available_kitchen_days raises 400."""
        plate = self._make_plate()
        with pytest.raises(HTTPException) as exc_info:
            determine_target_kitchen_day(
                target_day="Monday",
                plate=plate,
                current_day="Tuesday",
                available_kitchen_days=["Tuesday", "Wednesday"],
                country_code="AR",
                db=None,
                timezone_str="America/Argentina/Buenos_Aires",
            )
        assert exc_info.value.status_code == 400
        assert "Plate is not available" in str(exc_info.value.detail)
