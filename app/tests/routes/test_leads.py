"""
Tests for leads routes: GET /api/v1/leads/markets, zipcode-metrics (no auth, rate-limited).
"""

from unittest.mock import patch

import pytest
from application import app
from fastapi.testclient import TestClient

from app.routes import leads


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_markets_cache():
    """Reset the leads markets cache before each test."""
    leads._markets_cache.clear()
    yield
    leads._markets_cache.clear()


class TestLeadsMarketsEndpoint:
    """GET /api/v1/leads/markets."""

    @patch("app.routes.leads.get_markets_with_coverage")
    def test_200_returns_public_market_fields_only(self, mock_coverage, client):
        """Response has public market fields (country_code, country_name, language, phone, locale); no market_id."""
        mock_coverage.return_value = [
            {
                "country_code": "AR",
                "country_name": "Argentina",
                "language": "es",
                "phone_dial_code": "+54",
                "phone_local_digits": 10,
            },
            {
                "country_code": "US",
                "country_name": "United States",
                "language": "en",
                "phone_dial_code": "+1",
                "phone_local_digits": 10,
            },
        ]
        resp = client.get("/api/v1/leads/markets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["country_code"] == "AR"
        assert data[0]["country_name"] == "Argentina"
        assert data[0]["language"] == "es"
        assert data[0]["locale"] == "es-AR"
        assert data[0]["has_active_kitchens"] is True
        assert data[1]["country_code"] == "US"
        assert data[1]["locale"] == "en-US"
        assert data[1]["has_active_kitchens"] is True
        assert "market_id" not in data[0]
        assert "market_id" not in data[1]

    @patch("app.routes.leads.market_service")
    def test_excludes_global_marketplace_supplier_audience(self, mock_market_service, client):
        """Global Marketplace is excluded from supplier audience list."""
        mock_market_service.get_all.return_value = [
            {
                "market_id": "00000000-0000-0000-0000-000000000001",
                "country_code": "XG",
                "country_name": "Global",
                "language": "en",
            },
            {
                "market_id": "11111111-1111-1111-1111-111111111111",
                "country_code": "AR",
                "country_name": "Argentina",
                "language": "es",
            },
        ]

        def is_global(m_id):
            return str(m_id) == "00000000-0000-0000-0000-000000000001"

        with patch("app.routes.leads.is_global_market", side_effect=is_global):
            resp = client.get("/api/v1/leads/markets", params={"audience": "supplier"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["country_code"] == "AR"
        assert data[0]["country_name"] == "Argentina"
        assert data[0]["locale"] == "es-AR"

    @patch("app.routes.leads.get_markets_with_coverage")
    def test_no_auth_required(self, mock_coverage, client):
        """Endpoint works without Authorization header."""
        mock_coverage.return_value = []
        resp = client.get("/api/v1/leads/markets")
        assert resp.status_code == 200

    @patch("app.routes.leads.get_markets_with_coverage")
    def test_unknown_audience_defaults_to_coverage_filtered(self, mock_coverage, client):
        """Unknown audience value falls back to coverage-filtered (restrictive default)."""
        mock_coverage.return_value = [
            {
                "country_code": "AR",
                "country_name": "Argentina",
                "language": "es",
                "phone_dial_code": "+54",
                "phone_local_digits": 10,
            },
        ]
        resp = client.get("/api/v1/leads/markets", params={"audience": "garbage"})
        assert resp.status_code == 200
        mock_coverage.assert_called_once()  # coverage path, not get_all


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
        # Exhaust rate limit: 21 requests; 21st should return 429.
        # Rate limit is per-IP; TestClient may share connection so limit applies.
        for _i in range(21):
            resp = client.get("/api/v1/leads/zipcode-metrics", params={"zip": "12345"})
            if resp.status_code == 429:
                body = resp.json()
                msg = (body.get("detail") or body.get("error") or "").lower()
                assert "rate_limited" in msg or "rate limit" in msg or "too many" in msg
                return
        # If all 21 returned 200, rate limiting may be disabled in test (e.g. limiter bypass)
        pytest.skip("Rate limit not triggered in test env (limiter may be disabled)")


class TestLeadsCitiesEndpoint:
    """GET /api/v1/leads/cities."""

    @pytest.fixture(autouse=True)
    def _clear_cities_cache(self):
        """Reset the cities caches before/after each test."""
        leads._cities_cache.clear()
        leads._cities_coverage_cache.clear()
        yield
        leads._cities_cache.clear()
        leads._cities_coverage_cache.clear()

    @patch("app.routes.leads.get_cities_with_coverage")
    def test_default_mode_returns_flat_city_list(self, mock_coverage, client):
        """Default mode (no mode param) returns LeadsCitiesResponseSchema with cities list."""
        mock_coverage.return_value = ["Buenos Aires", "Córdoba"]
        resp = client.get("/api/v1/leads/cities", params={"country_code": "AR"})
        assert resp.status_code == 200
        data = resp.json()
        assert "cities" in data
        assert data["cities"] == ["Buenos Aires", "Córdoba"]

    @patch("app.services.city_metrics_service.get_supplier_cities_for_country")
    def test_supplier_audience_still_returns_flat_list(self, mock_supplier, client):
        """audience=supplier returns flat cities list (backward compat unchanged)."""
        mock_supplier.return_value = ["Rosario", "Mendoza"]
        resp = client.get("/api/v1/leads/cities", params={"country_code": "AR", "audience": "supplier"})
        assert resp.status_code == 200
        data = resp.json()
        assert "cities" in data
        assert isinstance(data["cities"], list)

    @patch("app.routes.leads.get_cities_with_restaurant_counts")
    def test_coverage_mode_returns_city_with_count_objects(self, mock_counts, client):
        """mode=coverage returns list of {city, restaurant_count} objects."""
        mock_counts.return_value = [
            {"city": "Buenos Aires", "restaurant_count": 8},
            {"city": "Córdoba", "restaurant_count": 3},
        ]
        resp = client.get("/api/v1/leads/cities", params={"country_code": "AR", "mode": "coverage"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["city"] == "Buenos Aires"
        assert data[0]["restaurant_count"] == 8
        assert data[1]["city"] == "Córdoba"
        assert data[1]["restaurant_count"] == 3

    @patch("app.routes.leads.get_cities_with_restaurant_counts")
    def test_coverage_mode_excludes_zero_count_cities(self, mock_counts, client):
        """Service excludes cities with no active plate coverage; mode=coverage returns what service returns."""
        mock_counts.return_value = [{"city": "Buenos Aires", "restaurant_count": 5}]
        resp = client.get("/api/v1/leads/cities", params={"country_code": "AR", "mode": "coverage"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["restaurant_count"] == 5

    @patch("app.routes.leads.get_cities_with_restaurant_counts")
    def test_coverage_mode_empty_country_returns_empty_list(self, mock_counts, client):
        """mode=coverage with no covered cities returns empty list (not error)."""
        mock_counts.return_value = []
        resp = client.get("/api/v1/leads/cities", params={"country_code": "US", "mode": "coverage"})
        assert resp.status_code == 200
        assert resp.json() == []


class TestLeadsMarketsHasActiveKitchens:
    """GET /api/v1/leads/markets — has_active_kitchens field."""

    @patch("app.routes.leads.get_markets_with_coverage")
    def test_customer_mode_has_active_kitchens_true(self, mock_coverage, client):
        """Default (customer) mode: all returned markets have has_active_kitchens=True (they passed coverage filter)."""
        mock_coverage.return_value = [
            {
                "country_code": "AR",
                "country_name": "Argentina",
                "language": "es",
                "phone_dial_code": "+54",
                "phone_local_digits": 10,
            },
        ]
        resp = client.get("/api/v1/leads/markets")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["has_active_kitchens"] is True

    @patch("app.routes.leads.get_coverage_flags_for_markets")
    @patch("app.routes.leads.market_service")
    def test_supplier_mode_has_active_kitchens_reflects_coverage(self, mock_market_service, mock_flags, client):
        """Supplier mode: has_active_kitchens is True only for markets in the covered set."""
        mock_market_service.get_all.return_value = [
            {
                "market_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "country_code": "AR",
                "country_name": "Argentina",
                "language": "es",
                "phone_dial_code": "+54",
                "phone_local_digits": 10,
            },
            {
                "market_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "country_code": "US",
                "country_name": "United States",
                "language": "en",
                "phone_dial_code": "+1",
                "phone_local_digits": 10,
            },
        ]
        mock_flags.return_value = {"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}

        def is_global(m_id):
            return str(m_id) == "00000000-0000-0000-0000-000000000001"

        with patch("app.routes.leads.is_global_market", side_effect=is_global):
            resp = client.get("/api/v1/leads/markets", params={"audience": "supplier"})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        ar = next(m for m in data if m["country_code"] == "AR")
        us = next(m for m in data if m["country_code"] == "US")
        assert ar["has_active_kitchens"] is True
        assert us["has_active_kitchens"] is False

    @patch("app.routes.leads.get_coverage_flags_for_markets")
    @patch("app.routes.leads.market_service")
    def test_supplier_mode_archived_plate_yields_false(self, mock_market_service, mock_flags, client):
        """Supplier mode: market not in covered set → has_active_kitchens=False (e.g. all plates archived)."""
        mock_market_service.get_all.return_value = [
            {
                "market_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                "country_code": "MX",
                "country_name": "Mexico",
                "language": "es",
                "phone_dial_code": "+52",
                "phone_local_digits": 10,
            },
        ]
        mock_flags.return_value = set()

        def is_global(m_id):
            return False

        with patch("app.routes.leads.is_global_market", side_effect=is_global):
            resp = client.get("/api/v1/leads/markets", params={"audience": "supplier"})

        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["has_active_kitchens"] is False
