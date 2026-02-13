"""
Integration tests for address autocomplete routes (GET /suggest, POST /validate).
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from application import app
from app.auth.dependencies import get_current_user, oauth2_scheme


@pytest.fixture
def mock_current_user():
    return {
        "user_id": "11111111-1111-1111-1111-111111111111",
        "role_type": "Employee",
        "role_name": "Admin",
        "institution_id": "22222222-2222-2222-2222-222222222222",
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


class TestAddressSuggestRoute:
    @patch("app.routes.address.address_autocomplete_service")
    def test_suggest_returns_200_and_suggestions(self, mock_svc, client_with_auth):
        mock_svc.suggest.return_value = [
            {
                "street_name": "Corrientes",
                "street_type": "Ave",
                "building_number": "1234",
                "apartment_unit": None,
                "floor": None,
                "city": "Buenos Aires",
                "province": "CABA",
                "postal_code": "C1043AAZ",
                "country_code": "ARG",
                "country_name": None,
                "formatted_address": "Av. Corrientes 1234, CABA, Argentina",
            }
        ]
        resp = client_with_auth.get("/api/v1/addresses/suggest?q=Av.+Corrientes")
        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["country_code"] == "ARG"
        mock_svc.suggest.assert_called_once()

    def test_suggest_requires_auth(self):
        with TestClient(app) as client:
            resp = client.get("/api/v1/addresses/suggest?q=test")
            assert resp.status_code == 401


class TestAddressValidateRoute:
    @patch("app.routes.address.address_autocomplete_service")
    def test_validate_returns_200_and_result(self, mock_svc, client_with_auth):
        mock_svc.validate.return_value = {
            "is_valid": True,
            "normalized": {
                "street_name": "Corrientes",
                "street_type": "Ave",
                "building_number": "1234",
                "apartment_unit": None,
                "floor": None,
                "city": "Buenos Aires",
                "province": "CABA",
                "postal_code": "C1043AAZ",
                "country_code": "ARG",
            },
            "formatted_address": "Av. Corrientes 1234, CABA, Argentina",
            "confidence": "high",
            "message": None,
        }
        body = {
            "street_name": "Corrientes",
            "street_type": "Ave",
            "building_number": "1234",
            "city": "Buenos Aires",
            "province": "CABA",
            "postal_code": "C1043",
            "country_code": "ARG",
        }
        resp = client_with_auth.post("/api/v1/addresses/validate", json=body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True
        assert data["normalized"]["country_code"] == "ARG"
        assert "formatted_address" in data
        mock_svc.validate.assert_called_once()

    def test_validate_requires_auth(self):
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/addresses/validate",
                json={
                    "street_name": "Test",
                    "street_type": "St",
                    "building_number": "1",
                    "city": "City",
                    "province": "State",
                    "postal_code": "12345",
                    "country_code": "ARG",
                },
            )
            assert resp.status_code == 401
