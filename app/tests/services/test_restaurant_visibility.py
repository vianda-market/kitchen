"""
Unit tests for restaurant_visibility helpers: restaurant_has_active_vianda_kitchen_days,
restaurant_has_active_qr_code, restaurant_entity_has_payouts_enabled.
"""

from unittest.mock import patch
from uuid import uuid4

from app.services.restaurant_visibility import (
    restaurant_entity_has_payouts_enabled,
    restaurant_has_active_qr_code,
    restaurant_has_active_vianda_kitchen_days,
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


class TestRestaurantHasActiveViandaKitchenDays:
    """restaurant_has_active_vianda_kitchen_days returns True/False based on DB state."""

    @patch("app.services.restaurant_visibility.db_read")
    def test_returns_true_when_active_vianda_kitchen_days_exists(self, mock_db_read):
        mock_db_read.return_value = {"1": 1}  # fetch_one returns dict or None
        restaurant_id = uuid4()
        mock_db = object()
        assert restaurant_has_active_vianda_kitchen_days(restaurant_id, mock_db) is True

    @patch("app.services.restaurant_visibility.db_read")
    def test_returns_false_when_none(self, mock_db_read):
        mock_db_read.return_value = None
        restaurant_id = uuid4()
        mock_db = object()
        assert restaurant_has_active_vianda_kitchen_days(restaurant_id, mock_db) is False


class TestRestaurantEntityHasPayoutsEnabled:
    """restaurant_entity_has_payouts_enabled returns True when entity payout_onboarding_status='complete'."""

    @patch("app.services.restaurant_visibility.db_read")
    def test_returns_true_when_entity_payouts_complete(self, mock_db_read):
        mock_db_read.return_value = {"1": 1}
        restaurant_id = uuid4()
        mock_db = object()
        result = restaurant_entity_has_payouts_enabled(restaurant_id, mock_db)
        assert result is True
        mock_db_read.assert_called_once()
        call_kw = mock_db_read.call_args[1]
        assert call_kw.get("fetch_one") is True
        # Query should join restaurant_info to institution_entity_info on payout status
        query_str = mock_db_read.call_args[0][0]
        assert "payout_onboarding_status" in query_str
        assert "complete" in query_str

    @patch("app.services.restaurant_visibility.db_read")
    def test_returns_false_when_entity_payouts_not_complete(self, mock_db_read):
        mock_db_read.return_value = None
        restaurant_id = uuid4()
        mock_db = object()
        assert restaurant_entity_has_payouts_enabled(restaurant_id, mock_db) is False

    @patch("app.services.restaurant_visibility.db_read")
    def test_passes_restaurant_id_as_string(self, mock_db_read):
        """Verifies UUID is stringified before psycopg2 binding (kitchen NEVER rule)."""
        mock_db_read.return_value = None
        restaurant_id = uuid4()
        mock_db = object()
        restaurant_entity_has_payouts_enabled(restaurant_id, mock_db)
        call_args = mock_db_read.call_args[0]
        params = call_args[1]
        assert isinstance(params[0], str), "UUID must be cast to str before DB binding"
        assert params[0] == str(restaurant_id)
