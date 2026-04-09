"""
Unit tests for Kitchen Day Service.

Tests centralized kitchen day logic: get_effective_current_day,
is_today_kitchen_closed, date_to_kitchen_day, get_kitchen_day_for_date.
"""

import pytest
from unittest.mock import patch
from datetime import date
from freezegun import freeze_time

from app.services.kitchen_day_service import (
    get_effective_current_day,
    is_today_kitchen_closed,
    date_to_kitchen_day,
    get_kitchen_day_for_date,
    VALID_KITCHEN_DAYS,
    WEEKDAY_NUM_TO_NAME,
)


class TestKitchenDayService:
    """Test suite for Kitchen Day Service."""

    @patch('app.services.kitchen_day_service.settings')
    def test_get_effective_current_day_dev_override(self, mock_settings):
        """DEV_OVERRIDE_DAY returns override when set."""
        mock_settings.DEV_OVERRIDE_DAY = "Wednesday"
        assert get_effective_current_day() == "Wednesday"

    @patch('app.services.kitchen_day_service.settings')
    @freeze_time("2025-03-05 12:00:00")  # Wednesday 12:00 - before 13:30 cutoff
    def test_get_effective_current_day_before_cutoff(self, mock_settings):
        """Before 13:30 uses previous day."""
        mock_settings.DEV_OVERRIDE_DAY = None
        result = get_effective_current_day("America/Argentina/Buenos_Aires")
        assert result == "Tuesday"

    @patch('app.services.kitchen_day_service.settings')
    @freeze_time("2025-03-05 17:00:00")  # 17:00 UTC = 14:00 Argentina - after 13:30 cutoff
    def test_get_effective_current_day_after_cutoff(self, mock_settings):
        """After 13:30 uses current day."""
        mock_settings.DEV_OVERRIDE_DAY = None
        result = get_effective_current_day("America/Argentina/Buenos_Aires")
        assert result == "Wednesday"

    @patch('app.services.kitchen_day_service.settings')
    def test_date_to_kitchen_day_dev_override(self, mock_settings):
        """date_to_kitchen_day respects DEV_OVERRIDE_DAY."""
        mock_settings.DEV_OVERRIDE_DAY = "Friday"
        assert date_to_kitchen_day(date(2025, 3, 5)) == "Friday"

    @patch('app.services.kitchen_day_service.settings')
    def test_date_to_kitchen_day_weekday_mapping(self, mock_settings):
        """date_to_kitchen_day maps weekdays correctly."""
        mock_settings.DEV_OVERRIDE_DAY = None
        assert date_to_kitchen_day(date(2025, 3, 3)) == "Monday"
        assert date_to_kitchen_day(date(2025, 3, 7)) == "Friday"

    @patch('app.services.kitchen_day_service.settings')
    @freeze_time("2025-03-05 17:00:00")  # 14:00 Argentina
    def test_get_kitchen_day_for_date_today_uses_effective(self, mock_settings):
        """For today, get_kitchen_day_for_date uses get_effective_current_day."""
        mock_settings.DEV_OVERRIDE_DAY = None
        result = get_kitchen_day_for_date(date(2025, 3, 5), "America/Argentina/Buenos_Aires")
        assert result == "Wednesday"

    @patch('app.services.kitchen_day_service.settings')
    @freeze_time("2025-03-05 17:00:00")  # 14:00 Argentina
    def test_get_kitchen_day_for_date_past_uses_date_to_kitchen_day(self, mock_settings):
        """For non-today, get_kitchen_day_for_date uses date_to_kitchen_day."""
        mock_settings.DEV_OVERRIDE_DAY = None
        result = get_kitchen_day_for_date(date(2025, 3, 3), "America/Argentina/Buenos_Aires")
        assert result == "Monday"

    def test_valid_kitchen_days_tuple(self):
        """VALID_KITCHEN_DAYS is a tuple of weekdays."""
        assert VALID_KITCHEN_DAYS == ("monday", "tuesday", "wednesday", "thursday", "friday")

    def test_weekday_num_to_name(self):
        """WEEKDAY_NUM_TO_NAME maps indices to day names."""
        assert WEEKDAY_NUM_TO_NAME[0] == "Monday"
        assert WEEKDAY_NUM_TO_NAME[4] == "Friday"
