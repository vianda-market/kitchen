"""
Tests for market create/update: country_code only, country_name derived by backend.
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import patch

from application import app
from app.auth.dependencies import get_employee_user, oauth2_scheme


@pytest.fixture
def mock_employee_user():
    return {
        "user_id": str(uuid4()),
        "role_type": "internal",
        "role_name": "admin",
        "institution_id": str(uuid4()),
    }


@pytest.fixture
def client_with_employee(mock_employee_user):
    def _override_get_employee_user():
        return mock_employee_user

    def _override_oauth2_scheme():
        return "test-token"

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_employee_user] = _override_get_employee_user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_employee_user, None)


class TestCreateMarketCountryCodeOnly:
    """POST /api/v1/markets accepts country_code only; country_name is derived."""

    @patch("app.routes.admin.markets.market_service")
    def test_create_market_with_country_code_only_derives_country_name(
        self, mock_market_service, client_with_employee
    ):
        """Request body has only country_code; backend resolves country_name and passes both to service."""
        mock_market_service.create.return_value = {
            "market_id": str(uuid4()),
            "country_name": "Argentina",
            "country_code": "AR",
            "currency_metadata_id": str(uuid4()),
            "currency_code": "ARS",
            "currency_name": "Argentine Peso",
            "timezone": "America/Argentina/Buenos_Aires",
            "kitchen_close_time": "13:30",
            "is_archived": False,
            "status": "active",
            "created_date": "2026-02-10T12:00:00Z",
            "modified_date": "2026-02-10T12:00:00Z",
        }
        payload = {
            "country_code": "AR",
            "currency_metadata_id": str(uuid4()),
            "timezone": "America/Argentina/Buenos_Aires",
            "status": "active",
        }
        resp = client_with_employee.post("/api/v1/markets", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["country_code"] == "AR"
        assert data["country_name"] == "Argentina"
        mock_market_service.create.assert_called_once()
        call_kw = mock_market_service.create.call_args[1]
        assert call_kw["country_name"] == "Argentina"
        assert call_kw["country_code"] == "AR"

    def test_create_market_invalid_country_code_returns_400(self, client_with_employee):
        """Invalid country_code returns 400; service create is not called."""
        payload = {
            "country_code": "XX",
            "currency_metadata_id": str(uuid4()),
            "timezone": "America/Argentina/Buenos_Aires",
        }
        with patch("app.routes.admin.markets.market_service") as mock_market_service:
            resp = client_with_employee.post("/api/v1/markets", json=payload)
        assert resp.status_code == 400
        detail = resp.json().get("detail") or resp.json().get("error") or resp.text or ""
        assert "country" in detail.lower() or "invalid" in detail.lower()
        mock_market_service.create.assert_not_called()

    @patch("app.routes.admin.markets.market_service")
    def test_create_market_lowercase_country_code_normalized_to_uppercase(self, mock_market_service, client_with_employee):
        """Request with lowercase country_code (e.g. ar) is normalized to uppercase; service receives AR."""
        mock_market_service.create.return_value = {
            "market_id": str(uuid4()),
            "country_name": "Argentina",
            "country_code": "AR",
            "currency_metadata_id": str(uuid4()),
            "currency_code": "ARS",
            "currency_name": "Argentine Peso",
            "timezone": "America/Argentina/Buenos_Aires",
            "kitchen_close_time": "13:30",
            "is_archived": False,
            "status": "active",
            "created_date": "2026-02-10T12:00:00Z",
            "modified_date": "2026-02-10T12:00:00Z",
        }
        payload = {
            "country_code": "ar",
            "currency_metadata_id": str(uuid4()),
            "timezone": "America/Argentina/Buenos_Aires",
            "status": "active",
        }
        resp = client_with_employee.post("/api/v1/markets", json=payload)
        assert resp.status_code == 201
        assert resp.json()["country_code"] == "AR"
        call_kw = mock_market_service.create.call_args[1]
        assert call_kw["country_code"] == "AR"

    def test_create_market_request_must_not_include_country_name(self, client_with_employee):
        """Schema does not accept country_name; request with only country_code is valid."""
        payload = {
            "country_code": "AR",
            "currency_metadata_id": str(uuid4()),
            "timezone": "America/Argentina/Buenos_Aires",
        }
        with patch("app.routes.admin.markets.market_service") as mock_market_service:
            mock_market_service.create.return_value = {
                "market_id": str(uuid4()),
                "country_name": "Argentina",
                "country_code": "AR",
                "currency_metadata_id": payload["currency_metadata_id"],
                "currency_code": "ARS",
                "currency_name": "Argentine Peso",
                "timezone": payload["timezone"],
                "kitchen_close_time": "13:30",
                "is_archived": False,
                "status": "active",
                "created_date": "2026-02-10T12:00:00Z",
                "modified_date": "2026-02-10T12:00:00Z",
            }
            resp = client_with_employee.post("/api/v1/markets", json=payload)
        assert resp.status_code == 201
        assert resp.json()["country_name"] == "Argentina"
        assert resp.json()["country_code"] == "AR"
