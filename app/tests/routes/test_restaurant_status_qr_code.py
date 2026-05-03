"""
Tests for restaurant status validation:
- Cannot activate without entity Stripe Connect payouts (422)
- Cannot activate without active plate_kitchen_days (400)
- Cannot activate without active QR code (400)
- Succeeds when entity payouts + plate_kitchen_days + QR code are all present (200)
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, oauth2_scheme

# Needs live Postgres (TestClient triggers DB pool init via unmocked code paths).
# Excluded from unit test job by -m "not database"; runs in acceptance (Newman).
pytestmark = pytest.mark.database


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


class TestRestaurantActivationPayoutsGate:
    """PUT /api/v1/restaurants/{id} status=Active — payouts gate runs before setup checks."""

    @patch("app.routes.restaurant.restaurant_service")
    @patch("app.routes.restaurant.restaurant_entity_has_payouts_enabled")
    def test_returns_422_when_entity_payouts_not_complete(
        self, mock_payouts, mock_restaurant_service, client_with_auth
    ):
        """Activation fails 422 with entity_payouts_required error code when Stripe Connect is incomplete."""
        restaurant_id = uuid4()
        mock_restaurant_service.get_by_id.return_value = MagicMock(restaurant_id=restaurant_id, institution_id=uuid4())
        mock_payouts.return_value = False

        resp = client_with_auth.put(
            f"/api/v1/restaurants/{restaurant_id}",
            json={"status": "active"},
        )
        assert resp.status_code == 422
        raw = resp.json().get("detail", {})
        assert isinstance(raw, dict), f"Expected envelope dict, got: {raw!r}"
        assert raw.get("code") == "restaurant.active_requires_entity_payouts"
        assert "Stripe Connect" in raw.get("message", "")
        mock_payouts.assert_called_once()

    @patch("app.routes.restaurant.restaurant_service")
    @patch("app.routes.restaurant.restaurant_entity_has_payouts_enabled")
    @patch("app.routes.restaurant.restaurant_has_active_qr_code")
    @patch("app.routes.restaurant.restaurant_has_active_plate_kitchen_days")
    def test_payouts_check_runs_before_setup_checks(
        self, mock_has_pkd, mock_has_qr, mock_payouts, mock_restaurant_service, client_with_auth
    ):
        """Payouts gate short-circuits before plate/QR checks when payouts are missing."""
        restaurant_id = uuid4()
        mock_restaurant_service.get_by_id.return_value = MagicMock(restaurant_id=restaurant_id, institution_id=uuid4())
        mock_payouts.return_value = False
        mock_has_pkd.return_value = True
        mock_has_qr.return_value = True

        resp = client_with_auth.put(
            f"/api/v1/restaurants/{restaurant_id}",
            json={"status": "active"},
        )
        assert resp.status_code == 422
        raw = resp.json().get("detail", {})
        assert raw.get("code") == "restaurant.active_requires_entity_payouts"
        # plate/QR checks must not have been called — payouts gate fires first
        mock_has_pkd.assert_not_called()
        mock_has_qr.assert_not_called()

    @patch("app.routes.restaurant.get_currency_metadata_id_for_restaurant")
    @patch("app.routes.restaurant.restaurant_service")
    @patch("app.routes.restaurant.restaurant_entity_has_payouts_enabled")
    @patch("app.routes.restaurant.restaurant_has_active_qr_code")
    @patch("app.routes.restaurant.restaurant_has_active_plate_kitchen_days")
    def test_succeeds_when_payouts_and_setup_complete(  # noqa: PLR0913
        self,
        mock_has_pkd,
        mock_has_qr,
        mock_payouts,
        mock_restaurant_service,
        mock_get_credit_currency,
        client_with_auth,
    ):
        """Activation succeeds when entity has payouts, plate_kitchen_days, and QR code."""
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
        mock_payouts.return_value = True
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


class TestRestaurantStatusRequiresActiveQRCode:
    """PUT /api/v1/restaurants/{id} with status=Active requires active QR code (payouts gated separately)."""

    @patch("app.routes.restaurant.restaurant_service")
    @patch("app.routes.restaurant.restaurant_entity_has_payouts_enabled")
    @patch("app.routes.restaurant.restaurant_has_active_qr_code")
    @patch("app.routes.restaurant.restaurant_has_active_plate_kitchen_days")
    def test_returns_400_when_no_active_qr_code(
        self, mock_has_pkd, mock_has_qr, mock_payouts, mock_restaurant_service, client_with_auth
    ):
        """When entity has payouts, restaurant has plate_kitchen_days but no active QR code, return 400."""
        restaurant_id = uuid4()
        mock_restaurant_service.get_by_id.return_value = MagicMock(restaurant_id=restaurant_id, institution_id=uuid4())
        mock_payouts.return_value = True
        mock_has_pkd.return_value = True
        mock_has_qr.return_value = False

        resp = client_with_auth.put(
            f"/api/v1/restaurants/{restaurant_id}",
            json={"status": "active"},
        )
        assert resp.status_code == 400
        # K3+: detail is now an envelope dict; extract message for string checks.
        raw = resp.json().get("detail", "")
        detail_str = raw.get("message", "") if isinstance(raw, dict) else str(raw)
        assert "QR code" in detail_str
        mock_has_qr.assert_called_once()

    @patch("app.routes.restaurant.restaurant_service")
    @patch("app.routes.restaurant.restaurant_entity_has_payouts_enabled")
    @patch("app.routes.restaurant.restaurant_has_active_qr_code")
    @patch("app.routes.restaurant.restaurant_has_active_plate_kitchen_days")
    def test_returns_400_when_no_plate_kitchen_days(
        self, mock_has_pkd, mock_has_qr, mock_payouts, mock_restaurant_service, client_with_auth
    ):
        """When entity has payouts, restaurant has QR code but no plate_kitchen_days, return 400."""
        restaurant_id = uuid4()
        mock_restaurant_service.get_by_id.return_value = MagicMock(restaurant_id=restaurant_id, institution_id=uuid4())
        mock_payouts.return_value = True
        mock_has_pkd.return_value = False
        mock_has_qr.return_value = True

        resp = client_with_auth.put(
            f"/api/v1/restaurants/{restaurant_id}",
            json={"status": "active"},
        )
        assert resp.status_code == 400
        # K3+: detail is now an envelope dict; extract message for string checks.
        raw = resp.json().get("detail", "")
        detail_str = raw.get("message", "") if isinstance(raw, dict) else str(raw)
        assert "plate_kitchen_days" in detail_str
        mock_has_pkd.assert_called_once()

    @patch("app.routes.restaurant.restaurant_service")
    @patch("app.routes.restaurant.restaurant_entity_has_payouts_enabled")
    @patch("app.routes.restaurant.restaurant_has_active_qr_code")
    @patch("app.routes.restaurant.restaurant_has_active_plate_kitchen_days")
    def test_returns_400_when_both_missing(
        self, mock_has_pkd, mock_has_qr, mock_payouts, mock_restaurant_service, client_with_auth
    ):
        """When entity has payouts but restaurant has neither plate_kitchen_days nor QR code, return 400."""
        restaurant_id = uuid4()
        mock_restaurant_service.get_by_id.return_value = MagicMock(restaurant_id=restaurant_id, institution_id=uuid4())
        mock_payouts.return_value = True
        mock_has_pkd.return_value = False
        mock_has_qr.return_value = False

        resp = client_with_auth.put(
            f"/api/v1/restaurants/{restaurant_id}",
            json={"status": "active"},
        )
        assert resp.status_code == 400
        # K3+: detail is now an envelope dict; extract message for string checks.
        raw = resp.json().get("detail", "")
        detail_str = raw.get("message", "") if isinstance(raw, dict) else str(raw)
        assert "plate_kitchen_days" in detail_str or "QR code" in detail_str

    @patch("app.routes.restaurant.get_currency_metadata_id_for_restaurant")
    @patch("app.routes.restaurant.restaurant_service")
    @patch("app.routes.restaurant.restaurant_entity_has_payouts_enabled")
    @patch("app.routes.restaurant.restaurant_has_active_qr_code")
    @patch("app.routes.restaurant.restaurant_has_active_plate_kitchen_days")
    def test_succeeds_when_both_present(  # noqa: PLR0913
        self,
        mock_has_pkd,
        mock_has_qr,
        mock_payouts,
        mock_restaurant_service,
        mock_get_credit_currency,
        client_with_auth,
    ):
        """When entity has payouts, plate_kitchen_days, and QR code, status update succeeds."""
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
        mock_payouts.return_value = True
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
