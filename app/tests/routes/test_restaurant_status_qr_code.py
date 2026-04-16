"""
Tests for restaurant status validation: cannot set Active without active QR code.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, oauth2_scheme


@pytest.fixture
def mock_current_user():
    return {
        "user_id": str(uuid4()),
        "role_type": "internal",
        "role_name": "admin",
        "institution_id": str(uuid4()),
    }


@pytest.fixture
def client_with_auth(mock_current_user):
    def _override_get_current_user():
        return mock_current_user

    def _override_oauth2_scheme():
        return "test-token"

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_current_user, None)


class TestRestaurantStatusRequiresActiveQRCode:
    """PUT /api/v1/restaurants/{id} with status=Active requires active QR code."""

    @patch("app.routes.restaurant.restaurant_service")
    @patch("app.routes.restaurant.restaurant_has_active_qr_code")
    @patch("app.routes.restaurant.restaurant_has_active_plate_kitchen_days")
    def test_returns_400_when_no_active_qr_code(
        self, mock_has_pkd, mock_has_qr, mock_restaurant_service, client_with_auth
    ):
        """When restaurant has plate_kitchen_days but no active QR code, return 400."""
        restaurant_id = uuid4()
        mock_restaurant_service.get_by_id.return_value = MagicMock(restaurant_id=restaurant_id, institution_id=uuid4())
        mock_has_pkd.return_value = True
        mock_has_qr.return_value = False

        resp = client_with_auth.put(
            f"/api/v1/restaurants/{restaurant_id}",
            json={"status": "active"},
        )
        assert resp.status_code == 400
        assert "QR code" in resp.json().get("detail", "")
        mock_has_qr.assert_called_once()

    @patch("app.routes.restaurant.restaurant_service")
    @patch("app.routes.restaurant.restaurant_has_active_qr_code")
    @patch("app.routes.restaurant.restaurant_has_active_plate_kitchen_days")
    def test_returns_400_when_no_plate_kitchen_days(
        self, mock_has_pkd, mock_has_qr, mock_restaurant_service, client_with_auth
    ):
        """When restaurant has QR code but no plate_kitchen_days, return 400."""
        restaurant_id = uuid4()
        mock_restaurant_service.get_by_id.return_value = MagicMock(restaurant_id=restaurant_id, institution_id=uuid4())
        mock_has_pkd.return_value = False
        mock_has_qr.return_value = True

        resp = client_with_auth.put(
            f"/api/v1/restaurants/{restaurant_id}",
            json={"status": "active"},
        )
        assert resp.status_code == 400
        assert "plate_kitchen_days" in resp.json().get("detail", "")
        mock_has_pkd.assert_called_once()

    @patch("app.routes.restaurant.restaurant_service")
    @patch("app.routes.restaurant.restaurant_has_active_qr_code")
    @patch("app.routes.restaurant.restaurant_has_active_plate_kitchen_days")
    def test_returns_400_when_both_missing(self, mock_has_pkd, mock_has_qr, mock_restaurant_service, client_with_auth):
        """When restaurant has neither plate_kitchen_days nor QR code, return 400."""
        restaurant_id = uuid4()
        mock_restaurant_service.get_by_id.return_value = MagicMock(restaurant_id=restaurant_id, institution_id=uuid4())
        mock_has_pkd.return_value = False
        mock_has_qr.return_value = False

        resp = client_with_auth.put(
            f"/api/v1/restaurants/{restaurant_id}",
            json={"status": "active"},
        )
        assert resp.status_code == 400
        detail = resp.json().get("detail", "")
        assert "plate_kitchen_days" in detail or "QR code" in detail

    @patch("app.routes.restaurant.get_currency_metadata_id_for_restaurant")
    @patch("app.routes.restaurant.restaurant_service")
    @patch("app.routes.restaurant.restaurant_has_active_qr_code")
    @patch("app.routes.restaurant.restaurant_has_active_plate_kitchen_days")
    def test_succeeds_when_both_present(
        self, mock_has_pkd, mock_has_qr, mock_restaurant_service, mock_get_credit_currency, client_with_auth
    ):
        """When restaurant has both plate_kitchen_days and QR code, status update succeeds."""
        restaurant_id = uuid4()
        inst_entity_id = uuid4()
        inst_id = uuid4()
        addr_id = uuid4()
        currency_metadata_id = uuid4()
        mock_restaurant_service.get_by_id.return_value = MagicMock(
            restaurant_id=restaurant_id,
            institution_id=inst_id,
            institution_entity_id=inst_entity_id,
            status="pending",
            name="Test",
        )
        mock_has_pkd.return_value = True
        mock_has_qr.return_value = True
        mock_get_credit_currency.return_value = currency_metadata_id
        now = datetime.now(UTC)
        updated = MagicMock(
            restaurant_id=restaurant_id,
            institution_id=inst_id,
            institution_entity_id=inst_entity_id,
            status="active",
            name="Test",
            address_id=addr_id,
            cuisine=None,
            pickup_instructions=None,
            is_archived=False,
            model_dump=lambda: {
                "restaurant_id": restaurant_id,
                "institution_id": str(inst_id),
                "institution_entity_id": str(inst_entity_id),
                "status": "active",
                "name": "Test",
                "address_id": str(addr_id),
                "cuisine": None,
                "pickup_instructions": None,
                "is_archived": False,
                "created_date": now,
                "modified_date": now,
                "currency_metadata_id": str(currency_metadata_id),
            },
        )
        mock_restaurant_service.update.return_value = updated

        resp = client_with_auth.put(
            f"/api/v1/restaurants/{restaurant_id}",
            json={"status": "active"},
        )
        assert resp.status_code == 200
        mock_restaurant_service.update.assert_called_once()
