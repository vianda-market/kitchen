"""
Tests for leads routes: GET /api/v1/leads/zipcode-metrics (no auth, rate-limited).
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from application import app
from app.routes import leads


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestZipcodeMetricsEndpoint:
    """GET /api/v1/leads/zipcode-metrics."""

    @patch("app.routes.leads.get_zipcode_metrics")
    def test_200_response_shape(self, mock_get_metrics, client):
        """Response has requested_zipcode, matched_zipcode, restaurant_count, has_coverage (no center for unauthenticated)."""
        mock_get_metrics.return_value = {
            "requested_zipcode": "12345",
            "matched_zipcode": "12345",
            "restaurant_count": 2,
            "has_coverage": True,
        }
        resp = client.get("/api/v1/leads/zipcode-metrics", params={"zip": "12345", "country_code": "US"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["requested_zipcode"] == "12345"
        assert data["matched_zipcode"] == "12345"
        assert data["restaurant_count"] == 2
        assert data["has_coverage"] is True
        assert "center" not in data

    @patch("app.routes.leads.get_zipcode_metrics")
    def test_200_zip_only_default_country(self, mock_get_metrics, client):
        """Omitting country_code uses default US."""
        mock_get_metrics.return_value = {
            "requested_zipcode": "90210",
            "matched_zipcode": "90210",
            "restaurant_count": 0,
            "has_coverage": False,
        }
        resp = client.get("/api/v1/leads/zipcode-metrics", params={"zip": "90210"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["restaurant_count"] == 0
        assert data["has_coverage"] is False
        mock_get_metrics.assert_called_once()
        call_kw = mock_get_metrics.call_args[1]
        assert call_kw["country_code"] == "US"

    @patch("app.routes.leads.get_zipcode_metrics")
    def test_route_normalizes_country_code_and_passes_to_service(self, mock_get_metrics, client):
        """Route normalizes country_code to uppercase and applies default US when omitted."""
        mock_get_metrics.return_value = {
            "requested_zipcode": "12345",
            "matched_zipcode": "12345",
            "restaurant_count": 0,
            "has_coverage": False,
        }
        resp = client.get("/api/v1/leads/zipcode-metrics", params={"zip": "12345", "country_code": "ar"})
        assert resp.status_code == 200
        mock_get_metrics.assert_called_once()
        call_kw = mock_get_metrics.call_args[1]
        assert call_kw["country_code"] == "AR"

    @patch("app.routes.leads.get_zipcode_metrics")
    def test_429_when_rate_limit_exceeded(self, mock_get_metrics, client):
        """When rate limit (20/minute) is exceeded, endpoint returns 429."""
        mock_get_metrics.return_value = {
            "requested_zipcode": "12345",
            "matched_zipcode": "12345",
            "restaurant_count": 0,
            "has_coverage": False,
        }
        # Exhaust rate limit: 21 requests, 21st returns 429
        for _ in range(20):
            resp = client.get("/api/v1/leads/zipcode-metrics", params={"zip": "12345"})
            assert resp.status_code == 200
        resp = client.get("/api/v1/leads/zipcode-metrics", params={"zip": "12345"})
        assert resp.status_code == 429
        assert "rate limit" in (resp.json().get("detail") or "").lower() or "too many" in (resp.json().get("detail") or "").lower()
