"""
Tests for Cache-Control header semantics on /leads/* endpoints (kitchen #125).

Verifies:
- /leads/markets: max-age=60 when populated; no-store when empty.
- /leads/cities: max-age=60 when populated; no-store when empty (default + coverage modes).
- /leads/email-registered: always no-store.

Service calls are patched so these tests do not require a live DB.
The recaptcha and DB dependencies are overridden for the test client.
"""

from unittest.mock import patch

import psycopg2.extensions
import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.recaptcha import verify_recaptcha
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import MarketPublicMinimalSchema

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _noop_recaptcha():
    """Override for verify_recaptcha — returns None (no-op)."""
    return


def _mock_db():
    """Override for get_db — returns a real-looking mock."""
    from unittest.mock import MagicMock

    return MagicMock(spec=psycopg2.extensions.connection)


@pytest.fixture
def leads_client():
    """TestClient with recaptcha and DB overridden (no real network/DB)."""
    app.dependency_overrides[verify_recaptcha] = _noop_recaptcha
    app.dependency_overrides[get_db] = _mock_db
    try:
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        app.dependency_overrides.pop(verify_recaptcha, None)
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# /leads/markets
# ---------------------------------------------------------------------------

_SAMPLE_MARKET = MarketPublicMinimalSchema(
    country_code="US",
    country_name="United States",
    language="en",
    phone_dial_code="+1",
    phone_local_digits=10,
    has_active_kitchens=True,
)


class TestLeadsMarketsCache:
    """GET /api/v1/leads/markets Cache-Control semantics."""

    def test_populated_response_carries_max_age_60(self, leads_client):
        """When markets are returned, Cache-Control is public, max-age=60."""
        with patch("app.routes.leads._get_cached_markets", return_value=[_SAMPLE_MARKET]):
            resp = leads_client.get("/api/v1/leads/markets", params={"language": "en"})
        assert resp.status_code == 200
        assert resp.json()  # non-empty
        assert resp.headers.get("cache-control") == "public, max-age=60"

    def test_empty_response_carries_no_store(self, leads_client):
        """When no markets are returned (pre-activation), Cache-Control is no-store."""
        with patch("app.routes.leads._get_cached_markets", return_value=[]):
            resp = leads_client.get("/api/v1/leads/markets", params={"language": "en"})
        assert resp.status_code == 200
        assert resp.json() == []
        assert resp.headers.get("cache-control") == "no-store"


# ---------------------------------------------------------------------------
# /leads/cities
# ---------------------------------------------------------------------------


class TestLeadsCitiesCache:
    """GET /api/v1/leads/cities Cache-Control semantics."""

    def test_populated_cities_response_carries_max_age_60(self, leads_client):
        """Populated city list → Cache-Control: public, max-age=60."""
        with patch("app.routes.leads._get_cached_cities", return_value=["Buenos Aires", "Córdoba"]):
            resp = leads_client.get("/api/v1/leads/cities", params={"country_code": "AR"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("cities")
        assert resp.headers.get("cache-control") == "public, max-age=60"

    def test_empty_cities_response_carries_no_store(self, leads_client):
        """Empty city list (pre-activation country) → Cache-Control: no-store."""
        with patch("app.routes.leads._get_cached_cities", return_value=[]):
            resp = leads_client.get("/api/v1/leads/cities", params={"country_code": "AR"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("cities") == []
        assert resp.headers.get("cache-control") == "no-store"

    def test_coverage_mode_populated_carries_max_age_60(self, leads_client):
        """Coverage mode with results → Cache-Control: public, max-age=60."""
        coverage_data = [{"city": "Buenos Aires", "restaurant_count": 5}]
        with patch("app.routes.leads.get_cities_with_restaurant_counts", return_value=coverage_data):
            resp = leads_client.get("/api/v1/leads/cities", params={"country_code": "AR", "mode": "coverage"})
        assert resp.status_code == 200
        assert resp.json()
        assert resp.headers.get("cache-control") == "public, max-age=60"

    def test_coverage_mode_empty_carries_no_store(self, leads_client):
        """Coverage mode with no results → Cache-Control: no-store."""
        import app.routes.leads as leads_module

        # Clear the server-side coverage cache so a previous populated run doesn't interfere.
        leads_module._cities_coverage_cache.clear()
        with patch("app.routes.leads.get_cities_with_restaurant_counts", return_value=[]):
            resp = leads_client.get("/api/v1/leads/cities", params={"country_code": "AR", "mode": "coverage"})
        assert resp.status_code == 200
        assert resp.json() == []
        assert resp.headers.get("cache-control") == "no-store"


# ---------------------------------------------------------------------------
# /leads/email-registered
# ---------------------------------------------------------------------------


class TestLeadsEmailRegisteredCache:
    """GET /api/v1/leads/email-registered Cache-Control semantics."""

    def test_registered_true_carries_no_store(self, leads_client):
        """Known email → registered=true, always no-store."""
        with patch("app.routes.leads.get_user_by_email", return_value={"user_id": "abc"}):
            resp = leads_client.get("/api/v1/leads/email-registered", params={"email": "user@example.com"})
        assert resp.status_code == 200
        assert resp.json()["registered"] is True
        assert resp.headers.get("cache-control") == "no-store"

    def test_unregistered_carries_no_store(self, leads_client):
        """Unknown email → registered=false, always no-store."""
        with patch("app.routes.leads.get_user_by_email", return_value=None):
            resp = leads_client.get("/api/v1/leads/email-registered", params={"email": "new@example.com"})
        assert resp.status_code == 200
        assert resp.json()["registered"] is False
        assert resp.headers.get("cache-control") == "no-store"
