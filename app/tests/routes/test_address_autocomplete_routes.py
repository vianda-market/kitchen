"""
Integration tests for address autocomplete routes (GET /suggest).
"""

from unittest.mock import patch

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, oauth2_scheme


@pytest.fixture
def mock_current_user():
    return {
        "user_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "role_type": "internal",
        "role_name": "super_admin",
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
                "place_id": "dXJuOm1ieHBsYzo0NTk2Mjg",
                "display_text": "Avenida Corrientes 1234, Buenos Aires, Argentina",
            }
        ]
        resp = client_with_auth.get("/api/v1/addresses/suggest?q=Av.+Corrientes")
        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["place_id"] == "dXJuOm1ieHBsYzo0NTk2Mjg"
        assert data["suggestions"][0]["display_text"] == "Avenida Corrientes 1234, Buenos Aires, Argentina"
        mock_svc.suggest.assert_called_once()

    @patch("app.routes.address.address_autocomplete_service")
    def test_suggest_forwards_session_token(self, mock_svc, client_with_auth):
        mock_svc.suggest.return_value = []
        resp = client_with_auth.get("/api/v1/addresses/suggest?q=test&session_token=my-token")
        assert resp.status_code == 200
        call_kw = mock_svc.suggest.call_args[1]
        assert call_kw["session_token"] == "my-token"

    def test_suggest_requires_auth(self):
        with TestClient(app) as client:
            resp = client.get("/api/v1/addresses/suggest?q=test")
            assert resp.status_code == 401

    @patch("app.routes.address.address_autocomplete_service")
    def test_suggest_returns_429_when_rate_limited(self, mock_svc, client_with_auth):
        """When RATE_LIMIT_ENABLED=True and the user is Free tier, 31st suggest request returns 429."""
        mock_svc.suggest.return_value = []

        from app.auth.middleware.rate_limit_middleware import _buckets

        _buckets.clear()

        free_claims = {
            "sub": "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "role_type": "customer",
            "onboarding_status": "in_progress",
            "institution_id": "11111111-1111-1111-1111-111111111111",
        }

        with (
            patch("app.auth.middleware.rate_limit_middleware.settings") as mock_settings,
            patch("app.auth.middleware.rate_limit_middleware._extract_bearer_token", return_value="fake-token"),
            patch("app.auth.middleware.rate_limit_middleware._decode_claims", return_value=free_claims),
        ):
            mock_settings.RATE_LIMIT_ENABLED = True
            mock_settings.RATE_LIMIT_MAX_TRACKED_USERS = 10_000
            mock_settings.RATE_LIMIT_EVICTION_AGE_SECONDS = 120

            # Exhaust endpoint rate limit (30 requests for Free tier /addresses/suggest)
            for _ in range(30):
                resp = client_with_auth.get("/api/v1/addresses/suggest?q=x")
                assert resp.status_code == 200, "Expected 200 before limit exceeded"

            # 31st request returns 429
            resp = client_with_auth.get("/api/v1/addresses/suggest?q=x")
            assert resp.status_code == 429
            assert "Retry-After" in resp.headers

        _buckets.clear()
