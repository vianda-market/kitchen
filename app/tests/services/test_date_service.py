"""
Unit tests for Date Service.

Tests the business logic for date and time calculations including
timezone handling, business day calculations, and dev overrides.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, time, timedelta
import pytz

from app.services.date_service import (
    get_effective_current_day, is_dev_mode, get_effective_current_date
)


class TestDateService:
    """Test suite for Date Service business logic."""

    @patch('app.services.kitchen_day_service.settings')
    def test_get_effective_current_day_uses_dev_override_when_set(self, mock_settings):
        """Test that dev override is used when DEV_OVERRIDE_DAY is set."""
        mock_settings.DEV_OVERRIDE_DAY = "Monday"
        result = get_effective_current_day()
        assert result == "monday"

    @patch('app.services.kitchen_day_service.settings')
    def test_get_effective_current_day_ignores_invalid_dev_override(self, mock_settings):
        """Test that invalid dev override is ignored."""
        # Arrange
        mock_settings.DEV_OVERRIDE_DAY = "InvalidDay"
        
        with patch('app.services.kitchen_day_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.time.return_value = time(14, 0)  # 2 PM
            mock_now.strftime.return_value = "Tuesday"
            mock_datetime.now.return_value = mock_now
            
            result = get_effective_current_day()
            assert result == "tuesday"

    @patch('app.services.kitchen_day_service.settings')
    def test_get_effective_current_day_handles_empty_dev_override(self, mock_settings):
        """Test that empty dev override is ignored."""
        # Arrange
        mock_settings.DEV_OVERRIDE_DAY = ""
        
        with patch('app.services.kitchen_day_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.time.return_value = time(14, 0)  # 2 PM
            mock_now.strftime.return_value = "Wednesday"
            mock_datetime.now.return_value = mock_now
            
            result = get_effective_current_day()
            assert result == "wednesday"

    @patch('app.services.kitchen_day_service.settings')
    def test_get_effective_current_day_uses_previous_day_before_1pm(self, mock_settings):
        """Test that before 1 PM uses previous day's service window."""
        # Arrange
        mock_settings.DEV_OVERRIDE_DAY = None
        
        with patch('app.services.kitchen_day_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.time.return_value = time(12, 0)  # 12 PM (before 1 PM)
            mock_now.strftime.return_value = "Thursday"
            
            mock_yesterday = Mock()
            mock_yesterday.strftime.return_value = "Wednesday"
            mock_now.__sub__ = Mock(return_value=mock_yesterday)
            mock_datetime.now.return_value = mock_now
            
            result = get_effective_current_day()
            assert result == "wednesday"

    @patch('app.services.kitchen_day_service.settings')
    def test_get_effective_current_day_uses_current_day_after_1pm(self, mock_settings):
        """Test that after 1 PM uses current day's service window."""
        # Arrange
        mock_settings.DEV_OVERRIDE_DAY = None
        
        with patch('app.services.kitchen_day_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.time.return_value = time(14, 0)  # 2 PM (after 1 PM)
            mock_now.strftime.return_value = "Friday"
            mock_datetime.now.return_value = mock_now
            
            result = get_effective_current_day()
            assert result == "friday"

    @patch('app.services.kitchen_day_service.settings')
    def test_get_effective_current_day_handles_invalid_timezone(self, mock_settings):
        """Test that invalid timezone falls back to default."""
        # Arrange
        mock_settings.DEV_OVERRIDE_DAY = None
        
        with patch('app.services.kitchen_day_service.datetime') as mock_datetime, \
             patch('app.services.kitchen_day_service.pytz.timezone') as mock_timezone:
            mock_timezone.side_effect = [
                pytz.exceptions.UnknownTimeZoneError("Invalid timezone"),
                pytz.timezone("America/Argentina/Buenos_Aires"),
            ]
            
            mock_now = Mock()
            mock_now.time.return_value = time(14, 0)
            mock_now.strftime.return_value = "Saturday"
            mock_datetime.now.return_value = mock_now
            
            result = get_effective_current_day("Invalid/Timezone")
            assert result == "saturday"
            assert mock_timezone.call_count >= 2

    @patch('app.services.date_service.settings')
    def test_is_dev_mode_returns_true_when_override_set(self, mock_settings):
        """Test that is_dev_mode returns True when DEV_OVERRIDE_DAY is set."""
        # Arrange
        mock_settings.DEV_OVERRIDE_DAY = "Monday"
        
        # Act
        result = is_dev_mode()
        
        # Assert
        assert result is True

    @patch('app.services.date_service.settings')
    def test_is_dev_mode_returns_false_when_override_not_set(self, mock_settings):
        """Test that is_dev_mode returns False when DEV_OVERRIDE_DAY is not set."""
        # Arrange
        mock_settings.DEV_OVERRIDE_DAY = None
        
        # Act
        result = is_dev_mode()
        
        # Assert
        assert result is False

    @patch('app.services.date_service.settings')
    def test_is_dev_mode_returns_false_when_override_empty(self, mock_settings):
        """Test that is_dev_mode returns False when DEV_OVERRIDE_DAY is empty."""
        # Arrange
        mock_settings.DEV_OVERRIDE_DAY = ""
        
        # Act
        result = is_dev_mode()
        
        # Assert
        assert result is False

    @patch('app.services.date_service.settings')
    def test_get_effective_current_date_uses_dev_override_when_set(self, mock_settings):
        """Test that get_effective_current_date uses dev override when set."""
        # Arrange
        mock_settings.DEV_OVERRIDE_DAY = "Monday"
        
        with patch('app.services.date_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.weekday.return_value = 2  # Wednesday (0=Monday)
            mock_datetime.now.return_value = mock_now
            
            # Mock timedelta addition
            mock_override_date = Mock()
            mock_override_date.replace.return_value = datetime(2023, 10, 9, 14, 0, 0, 0)
            mock_now.__add__ = Mock(return_value=mock_override_date)
            
            # Act
            result = get_effective_current_date()
            
            # Assert
            assert result == datetime(2023, 10, 9, 14, 0, 0, 0)

    @patch('app.services.date_service.settings')
    def test_get_effective_current_date_returns_current_when_no_override(self, mock_settings):
        """Test that get_effective_current_date returns current date when no override."""
        # Arrange
        mock_settings.DEV_OVERRIDE_DAY = None
        
        with patch('app.services.date_service.datetime') as mock_datetime:
            mock_now = datetime(2023, 10, 11, 15, 30, 45, 123456)
            mock_datetime.now.return_value = mock_now
            
            # Act
            result = get_effective_current_date()
            
            # Assert
            assert result == mock_now

    @patch('app.services.date_service.settings')
    def test_get_effective_current_date_handles_invalid_timezone(self, mock_settings):
        """Test that get_effective_current_date handles invalid timezone."""
        # Arrange
        mock_settings.DEV_OVERRIDE_DAY = None
        
        with patch('app.services.date_service.datetime') as mock_datetime, \
             patch('app.services.date_service.pytz.timezone') as mock_timezone:
            
            # Mock timezone to raise exception first time, then return valid timezone
            mock_timezone.side_effect = [
                pytz.exceptions.UnknownTimeZoneError("Invalid timezone"),
                Mock()  # Fallback timezone
            ]
            
            mock_now = datetime(2023, 10, 11, 15, 30, 45, 123456)
            mock_datetime.now.return_value = mock_now
            
            # Act
            result = get_effective_current_date("Invalid/Timezone")
            
            # Assert
            assert result == mock_now
            assert mock_timezone.call_count == 2

    @patch('app.services.date_service.settings')
    def test_get_effective_current_date_handles_future_target_day(self, mock_settings):
        """Test that get_effective_current_date handles future target day correctly."""
        # Arrange
        mock_settings.DEV_OVERRIDE_DAY = "Friday"
        
        with patch('app.services.date_service.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.weekday.return_value = 0  # Monday (0=Monday, 4=Friday)
            mock_datetime.now.return_value = mock_now
            
            # Mock timedelta addition (Friday is 4 days in future, so go to last week)
            mock_override_date = Mock()
            mock_override_date.replace.return_value = datetime(2023, 10, 6, 14, 0, 0, 0)
            mock_now.__add__ = Mock(return_value=mock_override_date)
            
            # Act
            result = get_effective_current_date()
            
            # Assert
            assert result == datetime(2023, 10, 6, 14, 0, 0, 0)
