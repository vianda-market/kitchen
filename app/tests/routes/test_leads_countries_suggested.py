"""
Tests for the LeadsCountriesResponseSchema envelope and suggested_country_code
resolution on GET /leads/countries and GET /leads/supplier-countries (kitchen #217).

Covers:
- Unit tests for _resolve_suggested_country helper.
- Unit tests for LeadsCountriesResponseSchema shape.
- Endpoint tests (TestClient, no live DB):
    (a) cf-ipcountry=AR and AR is a launched market  → suggested_country_code = "AR"
    (b) cf-ipcountry=JP and JP is NOT in the list    → suggested_country_code = null
    (c) header absent                                → suggested_country_code = null
    (d) countries array still matches the old shape (same country items)
- Same four cases applied to /leads/supplier-countries.
- Cache-Control is private, no-store on both endpoints.
"""

from unittest.mock import patch

import psycopg2.extensions
import pytest
from application import app
from fastapi.testclient import TestClient

from app.dependencies.database import get_db
from app.routes.leads_country import _resolve_suggested_country
from app.schemas.consolidated_schemas import LeadsCountriesResponseSchema, LeadsCountrySchema

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_SAMPLE_COUNTRY_ROWS = [
    {
        "code": "AR",
        "name": "Argentina",
        "currency": "ARS",
        "phone_prefix": "+54",
        "default_locale": "es",
    },
    {
        "code": "US",
        "name": "United States",
        "currency": "USD",
        "phone_prefix": "+1",
        "default_locale": "en",
    },
]

_SAMPLE_COUNTRIES = [LeadsCountrySchema(**r) for r in _SAMPLE_COUNTRY_ROWS]

_LAUNCHED_CODES = {"AR", "US"}


# ---------------------------------------------------------------------------
# Unit tests — _resolve_suggested_country helper
# ---------------------------------------------------------------------------


class TestResolveSuggestedCountry:
    """Unit tests for the geo-resolution helper."""

    def test_launched_country_returns_code(self):
        assert _resolve_suggested_country("AR", _LAUNCHED_CODES) == "AR"

    def test_code_normalised_to_upper(self):
        assert _resolve_suggested_country("ar", _LAUNCHED_CODES) == "AR"

    def test_unlaunched_country_returns_none(self):
        assert _resolve_suggested_country("JP", _LAUNCHED_CODES) is None

    def test_header_absent_returns_none(self):
        assert _resolve_suggested_country(None, _LAUNCHED_CODES) is None

    def test_empty_string_returns_none(self):
        assert _resolve_suggested_country("", _LAUNCHED_CODES) is None

    def test_cloudflare_unknown_sentinel_returns_none(self):
        """CF uses 'XX' for unresolvable IPs."""
        assert _resolve_suggested_country("XX", _LAUNCHED_CODES) is None

    def test_invalid_non_alpha2_returns_none(self):
        assert _resolve_suggested_country("ARG", _LAUNCHED_CODES) is None

    def test_empty_country_set_returns_none(self):
        assert _resolve_suggested_country("AR", set()) is None


# ---------------------------------------------------------------------------
# Unit tests — LeadsCountriesResponseSchema
# ---------------------------------------------------------------------------


class TestLeadsCountriesResponseSchema:
    """Unit tests for the response envelope schema."""

    def test_schema_with_suggested_code(self):
        schema = LeadsCountriesResponseSchema(
            countries=_SAMPLE_COUNTRIES, suggested_country_code="AR"
        )
        assert schema.suggested_country_code == "AR"
        assert len(schema.countries) == 2

    def test_schema_with_null_suggested_code(self):
        schema = LeadsCountriesResponseSchema(
            countries=_SAMPLE_COUNTRIES, suggested_country_code=None
        )
        assert schema.suggested_country_code is None

    def test_schema_countries_preserve_all_fields(self):
        schema = LeadsCountriesResponseSchema(
            countries=_SAMPLE_COUNTRIES, suggested_country_code=None
        )
        first = schema.countries[0]
        assert first.code == "AR"
        assert first.currency == "ARS"
        assert first.phone_prefix == "+54"
        assert first.default_locale == "es"

    def test_schema_empty_countries(self):
        schema = LeadsCountriesResponseSchema(countries=[], suggested_country_code=None)
        assert schema.countries == []
        assert schema.suggested_country_code is None


# ---------------------------------------------------------------------------
# Shared test infrastructure
# ---------------------------------------------------------------------------


def _mock_db():
    from unittest.mock import MagicMock

    return MagicMock(spec=psycopg2.extensions.connection)


@pytest.fixture
def leads_country_client():
    """TestClient with DB overridden (no real DB). No reCAPTCHA override needed —
    /leads/countries and /leads/supplier-countries are on public_router (no reCAPTCHA dep)."""
    app.dependency_overrides[get_db] = _mock_db
    try:
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


# Raw DB rows returned by the service (include modified_date fields for ETag computation).
_RAW_DB_ROWS = [
    {
        "code": "AR",
        "currency": "ARS",
        "phone_prefix": "+54",
        "default_locale": "es",
        "market_modified_date": "2024-01-01",
        "currency_modified_date": "2024-01-01",
    },
    {
        "code": "US",
        "currency": "USD",
        "phone_prefix": "+1",
        "default_locale": "en",
        "market_modified_date": "2024-01-01",
        "currency_modified_date": "2024-01-01",
    },
]


def _patch_countries(module_path: str):
    """Patch the given service function to return _RAW_DB_ROWS and clear the in-process cache.

    Both customer and supplier caches are cleared so test runs don't bleed into each other
    regardless of execution order.
    """
    import app.routes.leads_country as lc_module

    lc_module._countries_cache.clear()
    lc_module._supplier_countries_cache.clear()
    return patch(module_path, return_value=_RAW_DB_ROWS)


# ---------------------------------------------------------------------------
# Endpoint tests — /leads/countries
# ---------------------------------------------------------------------------


class TestLeadsCountriesEndpoint:
    """GET /api/v1/leads/countries endpoint tests."""

    def test_ar_launched_returns_suggested_ar(self, leads_country_client):
        """cf-ipcountry=AR + AR is in the countries list → suggested_country_code='AR'."""
        with _patch_countries("app.routes.leads_country.get_public_countries"):
            resp = leads_country_client.get(
                "/api/v1/leads/countries",
                params={"language": "en"},
                headers={"cf-ipcountry": "AR"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["suggested_country_code"] == "AR"

    def test_jp_not_launched_returns_null(self, leads_country_client):
        """cf-ipcountry=JP + JP not in countries list → suggested_country_code=null."""
        with _patch_countries("app.routes.leads_country.get_public_countries"):
            resp = leads_country_client.get(
                "/api/v1/leads/countries",
                params={"language": "en"},
                headers={"cf-ipcountry": "JP"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["suggested_country_code"] is None

    def test_header_absent_returns_null(self, leads_country_client):
        """No cf-ipcountry header → suggested_country_code=null."""
        with _patch_countries("app.routes.leads_country.get_public_countries"):
            resp = leads_country_client.get(
                "/api/v1/leads/countries",
                params={"language": "en"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["suggested_country_code"] is None

    def test_countries_array_contains_same_data(self, leads_country_client):
        """The countries array preserves the same items as the former list response."""
        with _patch_countries("app.routes.leads_country.get_public_countries"):
            resp = leads_country_client.get(
                "/api/v1/leads/countries",
                params={"language": "en"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "countries" in body
        codes = {c["code"] for c in body["countries"]}
        assert codes == {"AR", "US"}
        first_ar = next(c for c in body["countries"] if c["code"] == "AR")
        assert first_ar["currency"] == "ARS"
        assert first_ar["phone_prefix"] == "+54"
        assert first_ar["default_locale"] == "es"

    def test_cache_control_is_private_no_store(self, leads_country_client):
        """Cache-Control must be private, no-store to prevent shared caches poisoning."""
        with _patch_countries("app.routes.leads_country.get_public_countries"):
            resp = leads_country_client.get(
                "/api/v1/leads/countries",
                params={"language": "en"},
            )
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "private, no-store"


# ---------------------------------------------------------------------------
# Endpoint tests — /leads/supplier-countries
# ---------------------------------------------------------------------------


class TestLeadsSupplierCountriesEndpoint:
    """GET /api/v1/leads/supplier-countries endpoint tests."""

    def test_ar_launched_returns_suggested_ar(self, leads_country_client):
        """cf-ipcountry=AR + AR is in the supplier-countries list → suggested_country_code='AR'."""
        with _patch_countries("app.routes.leads_country.get_public_supplier_countries"):
            resp = leads_country_client.get(
                "/api/v1/leads/supplier-countries",
                params={"language": "en"},
                headers={"cf-ipcountry": "AR"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["suggested_country_code"] == "AR"

    def test_jp_not_launched_returns_null(self, leads_country_client):
        """cf-ipcountry=JP + JP not in supplier-countries list → suggested_country_code=null."""
        with _patch_countries("app.routes.leads_country.get_public_supplier_countries"):
            resp = leads_country_client.get(
                "/api/v1/leads/supplier-countries",
                params={"language": "en"},
                headers={"cf-ipcountry": "JP"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["suggested_country_code"] is None

    def test_header_absent_returns_null(self, leads_country_client):
        """No cf-ipcountry header → suggested_country_code=null."""
        with _patch_countries("app.routes.leads_country.get_public_supplier_countries"):
            resp = leads_country_client.get(
                "/api/v1/leads/supplier-countries",
                params={"language": "en"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["suggested_country_code"] is None

    def test_countries_array_contains_same_data(self, leads_country_client):
        """The countries array preserves the same items as the former list response."""
        with _patch_countries("app.routes.leads_country.get_public_supplier_countries"):
            resp = leads_country_client.get(
                "/api/v1/leads/supplier-countries",
                params={"language": "en"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "countries" in body
        codes = {c["code"] for c in body["countries"]}
        assert codes == {"AR", "US"}

    def test_cache_control_is_private_no_store(self, leads_country_client):
        """Cache-Control must be private, no-store to prevent shared caches poisoning."""
        with _patch_countries("app.routes.leads_country.get_public_supplier_countries"):
            resp = leads_country_client.get(
                "/api/v1/leads/supplier-countries",
                params={"language": "en"},
            )
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "private, no-store"
