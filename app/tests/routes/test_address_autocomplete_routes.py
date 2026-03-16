"""
Integration tests for address autocomplete routes (GET /suggest).
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from application import app
from app.auth.dependencies import get_current_user, oauth2_scheme


@pytest.fixture
def mock_current_user():
    return {
        "user_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "role_type": "Internal",
        "role_name": "Super Admin",
        "institution_id": "11111111-1111-1111-1111-111111111111",
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
                "place_id": "ChIJB_KWWvXKvJURs8VJkFcGiNE",
                "display_text": "Av. Corrientes 1234, CABA, Argentina",
            }
        ]
        resp = client_with_auth.get("/api/v1/addresses/suggest?q=Av.+Corrientes")
        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["place_id"] == "ChIJB_KWWvXKvJURs8VJkFcGiNE"
        assert data["suggestions"][0]["display_text"] == "Av. Corrientes 1234, CABA, Argentina"
        mock_svc.suggest.assert_called_once()

    def test_suggest_requires_auth(self):
        with TestClient(app) as client:
            resp = client.get("/api/v1/addresses/suggest?q=test")
            assert resp.status_code == 401

    @patch("app.routes.address.address_autocomplete_service")
    def test_suggest_returns_429_when_rate_limited(self, mock_svc, client_with_auth):
        """After 60 requests per user, 61st returns 429."""
        mock_svc.suggest.return_value = []
        # Reset rate limit state for this test
        from app.routes.address import _suggest_rate_limit_timestamps
        user_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
        _suggest_rate_limit_timestamps[user_id] = []

        # Exhaust rate limit (60 requests)
        for _ in range(60):
            resp = client_with_auth.get("/api/v1/addresses/suggest?q=x")
            assert resp.status_code == 200, "Expected 200 before limit exceeded"

        # 61st request returns 429
        resp = client_with_auth.get("/api/v1/addresses/suggest?q=x")
        assert resp.status_code == 429
        assert "Too many" in resp.json().get("detail", "")
