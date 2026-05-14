"""
Unit tests for vianda selection validation (validate_pickup_time_range, 1-week-ahead order window, etc.).
"""

from datetime import date
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from freezegun import freeze_time

from app.dto.models import ViandaDTO
from app.services.vianda_selection_validation import (
    _find_next_available_kitchen_day_in_week,
    determine_target_kitchen_day,
    validate_pickup_time_range,
)


class TestValidatePickupTimeRange:
    """validate_pickup_time_range rejects values outside market's allowed pickup windows."""

    def test_valid_window_ar_monday_passes(self):
        """AR market Monday: 12:00-12:15 is within 11:30-13:30."""
        validate_pickup_time_range("AR", "monday", date(2026, 3, 9), "12:00-12:15")

    def test_valid_window_us_friday_passes(self):
        """US market Friday: 11:30-11:45 is valid."""
        validate_pickup_time_range("US", "friday", date(2026, 3, 13), "11:30-11:45")

    def test_invalid_window_raises_400(self):
        """Window outside allowed range raises 400 with allowed windows in detail."""
        with pytest.raises(HTTPException) as exc_info:
            validate_pickup_time_range("AR", "monday", date(2026, 3, 9), "08:00-08:15")
        assert exc_info.value.status_code == 400
        assert "08:00-08:15" in str(exc_info.value.detail)
        assert "11:30" in str(exc_info.value.detail) or "Allowed" in str(exc_info.value.detail)

    def test_empty_pickup_time_range_raises_422(self):
        """Empty or missing pickup_time_range raises 422."""
        with pytest.raises(HTTPException) as exc_info:
            validate_pickup_time_range("AR", "monday", date(2026, 3, 9), "")
        assert exc_info.value.status_code == 422

    def test_unknown_country_raises_400(self):
        """Unknown country returns no windows -> 400."""
        with pytest.raises(HTTPException) as exc_info:
            validate_pickup_time_range("XX", "monday", date(2026, 3, 9), "12:00-12:15")
        assert exc_info.value.status_code == 400
        assert "No pickup windows" in str(exc_info.value.detail)


class TestOneWeekAheadOrderWindow:
    """1-week-ahead order window: orders allowed from today through today+7 days."""

    def _make_vianda(self):
        vianda = Mock(spec=ViandaDTO)
        vianda.vianda_id = "00000000-0000-0000-0000-000000000001"
        vianda.restaurant_id = "00000000-0000-0000-0000-000000000002"
        return vianda

    @freeze_time("2026-03-07 12:00:00")  # Saturday March 7
    def test_saturday_to_monday_allowed(self):
        """From Saturday, ordering for Monday (2 days ahead) is allowed."""
        vianda = self._make_vianda()
        result = determine_target_kitchen_day(
            target_day="monday",
            vianda=vianda,
            current_day="saturday",
            available_kitchen_days=["monday", "tuesday", "wednesday", "thursday", "friday"],
            country_code="AR",
            db=None,
            timezone_str="America/Argentina/Buenos_Aires",
        )
        assert result == "monday"

    @freeze_time("2026-03-03 12:00:00")  # Tuesday March 3
    def test_tuesday_to_next_monday_allowed(self):
        """From Tuesday, ordering for next Monday (6 days ahead) is allowed."""
        vianda = self._make_vianda()
        result = determine_target_kitchen_day(
            target_day="monday",
            vianda=vianda,
            current_day="tuesday",
            available_kitchen_days=["monday", "wednesday", "friday"],
            country_code="AR",
            db=None,
            timezone_str="America/Argentina/Buenos_Aires",
        )
        assert result == "monday"

    @freeze_time("2026-03-03 15:00:00")  # Tuesday March 3, 3pm
    def test_tuesday_to_next_tuesday_allowed(self):
        """From Tuesday 3pm, ordering for next Tuesday (7 days ahead) is allowed."""
        vianda = self._make_vianda()
        result = determine_target_kitchen_day(
            target_day="tuesday",
            vianda=vianda,
            current_day="tuesday",
            available_kitchen_days=["tuesday"],
            country_code="AR",
            db=None,
            timezone_str="America/Argentina/Buenos_Aires",
        )
        assert result == "tuesday"

    @freeze_time("2026-03-07 12:00:00")  # Saturday March 7
    def test_saturday_without_timezone_rejects(self):
        """When timezone_str is None, target day is rejected with 1-week-ahead message."""
        vianda = self._make_vianda()
        with pytest.raises(HTTPException) as exc_info:
            determine_target_kitchen_day(
                target_day="monday",
                vianda=vianda,
                current_day="saturday",
                available_kitchen_days=["monday"],
                country_code="AR",
                db=None,
                timezone_str=None,
            )
        assert exc_info.value.status_code == 400
        assert "1 week ahead" in str(exc_info.value.detail)

    def test_vianda_not_available_for_day_raises_400(self):
        """Target day not in vianda's available_kitchen_days raises 400."""
        vianda = self._make_vianda()
        with pytest.raises(HTTPException) as exc_info:
            determine_target_kitchen_day(
                target_day="monday",
                vianda=vianda,
                current_day="tuesday",
                available_kitchen_days=["tuesday", "wednesday"],
                country_code="AR",
                db=None,
                timezone_str="America/Argentina/Buenos_Aires",
            )
        assert exc_info.value.status_code == 400
        assert "Vianda is not available" in str(exc_info.value.detail)


class TestFindNextAvailableKitchenDayHolidayAwareRemap:
    """
    Holiday-aware weekend→Friday remap in DEV_MODE.

    When today is Saturday or Sunday and DEV_MODE=True, the function maps the
    day to Friday. Before this fix the holiday check used the weekend date itself
    (never a holiday), so a Friday national holiday was silently skipped and the
    caller received a day that _validate_restaurant_for_day would then reject
    with 403 RESTAURANT_NATIONAL_HOLIDAY.

    After the fix the holiday check uses the preceding Friday's date, so a
    Friday holiday causes the function to skip that weekend entirely and
    continue iterating (the following Sunday maps to the next Friday, which is
    not a holiday, so "friday" is returned).
    """

    # today = Saturday 2026-05-09; preceding Friday = 2026-05-08 (Truman Day, US holiday)
    @freeze_time("2026-05-09 12:00:00")
    def test_saturday_friday_is_holiday_returns_prior_working_day(self):
        """
        Core acceptance-criteria test: weekend input + remapped Friday is a holiday
        → both weekend days (Saturday and Sunday) map to the same preceding Friday
        (2026-05-08), which is a holiday, so both are skipped. The next iteration
        lands on Monday 2026-05-11 (the prior working day in the forward scan).

        This exercises the exact bug from issue #257 (2026-05-08 Truman Day, US).

        Bug before fix: holiday check used the weekend date (e.g. 2026-05-09),
        which is never a holiday, so the Friday holiday was invisible and the caller
        received "friday" — then _validate_restaurant_for_day raised 403.

        After fix: holiday check uses the preceding Friday's date (2026-05-08), the
        holiday is detected, both weekend days are skipped, and "monday" is returned.
        """
        mock_db = Mock()

        def holiday_side_effect(date_str: str, country_code: str, db) -> bool:
            # 2026-05-08 is the holiday (Truman Day); all other dates are not
            return date_str == "2026-05-08"

        available_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]

        with (
            patch(
                "app.services.vianda_selection_validation._is_date_national_holiday", side_effect=holiday_side_effect
            ),
            patch("app.config.settings.settings") as mock_settings,
        ):
            mock_settings.DEV_MODE = True
            result = _find_next_available_kitchen_day_in_week(
                current_day="saturday",
                available_kitchen_days=available_days,
                country_code="US",
                db=mock_db,
            )

        # days_ahead=0: Saturday 2026-05-09 → holiday_check_date=Friday 2026-05-08 → holiday → skip
        # days_ahead=1: Sunday 2026-05-10  → holiday_check_date=Friday 2026-05-08 → holiday → skip
        # days_ahead=2: Monday 2026-05-11  → holiday_check_date=Monday 2026-05-11 → not holiday → "monday"
        assert result == "monday"

    @freeze_time("2026-05-09 12:00:00")  # Saturday
    def test_saturday_dev_mode_friday_not_holiday_returns_friday_immediately(self):
        """
        Saturday in DEV_MODE, preceding Friday is NOT a holiday.
        Expects the function to return 'friday' on the first iteration (no fallback).
        """
        mock_db = Mock()

        with (
            patch("app.services.vianda_selection_validation._is_date_national_holiday", return_value=False),
            patch("app.config.settings.settings") as mock_settings,
        ):
            mock_settings.DEV_MODE = True
            result = _find_next_available_kitchen_day_in_week(
                current_day="saturday",
                available_kitchen_days=["monday", "tuesday", "wednesday", "thursday", "friday"],
                country_code="US",
                db=mock_db,
            )

        # days_ahead=0: Saturday → holiday_check_date=Friday 2026-05-08 → not holiday → "friday"
        assert result == "friday"

    @freeze_time("2026-05-09 12:00:00")  # Saturday
    def test_production_mode_skips_weekend_and_returns_monday(self):
        """
        Production mode (DEV_MODE=False): weekend days are skipped entirely;
        next weekday in range is Monday.
        """
        mock_db = Mock()

        with (
            patch("app.services.vianda_selection_validation._is_date_national_holiday", return_value=False),
            patch("app.config.settings.settings") as mock_settings,
        ):
            mock_settings.DEV_MODE = False
            result = _find_next_available_kitchen_day_in_week(
                current_day="saturday",
                available_kitchen_days=["monday", "tuesday", "wednesday", "thursday", "friday"],
                country_code="US",
                db=mock_db,
            )

        # days_ahead=0: Saturday, DEV_MODE=False → skip
        # days_ahead=1: Sunday, DEV_MODE=False → skip
        # days_ahead=2: Monday (2026-05-11) → "monday", not a holiday → return
        assert result == "monday"
