"""
Unit tests for restaurant_visibility helpers: restaurant_has_active_plate_kitchen_days,
restaurant_has_active_qr_code.
"""

import pytest
from uuid import uuid4
from unittest.mock import patch

from app.services.restaurant_visibility import (
    restaurant_has_active_plate_kitchen_days,
    restaurant_has_active_qr_code,
)


class TestRestaurantHasActiveQRCode:
    """restaurant_has_active_qr_code returns True/False based on DB state."""

    @patch("app.services.restaurant_visibility.db_read")
    def test_returns_true_when_active_qr_code_exists(self, mock_db_read):
        mock_db_read.return_value = {"1": 1}  # fetch_one returns dict or None
        restaurant_id = uuid4()
        mock_db = object()
        assert restaurant_has_active_qr_code(restaurant_id, mock_db) is True
        mock_db_read.assert_called_once()
        call_kw = mock_db_read.call_args[1]
        assert call_kw.get("fetch_one") is True
        assert "qr_code" in mock_db_read.call_args[0][0]
        assert "active" in mock_db_read.call_args[0][0].lower()

    @patch("app.services.restaurant_visibility.db_read")
    def test_returns_false_when_no_active_qr_code(self, mock_db_read):
        mock_db_read.return_value = None  # fetch_one returns None when no row
        restaurant_id = uuid4()
        mock_db = object()
        assert restaurant_has_active_qr_code(restaurant_id, mock_db) is False


class TestRestaurantHasActivePlateKitchenDays:
    """restaurant_has_active_plate_kitchen_days returns True/False based on DB state."""

    @patch("app.services.restaurant_visibility.db_read")
    def test_returns_true_when_active_plate_kitchen_days_exists(self, mock_db_read):
        mock_db_read.return_value = {"1": 1}  # fetch_one returns dict or None
        restaurant_id = uuid4()
        mock_db = object()
        assert restaurant_has_active_plate_kitchen_days(restaurant_id, mock_db) is True

    @patch("app.services.restaurant_visibility.db_read")
    def test_returns_false_when_none(self, mock_db_read):
        mock_db_read.return_value = None
        restaurant_id = uuid4()
        mock_db = object()
        assert restaurant_has_active_plate_kitchen_days(restaurant_id, mock_db) is False
