"""
Tests for supported provinces endpoint: GET /api/v1/provinces
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from application import app
from app.auth.dependencies import get_client_employee_or_supplier_user, oauth2_scheme


@pytest.fixture
def mock_customer_user():
    return {
        "user_id": str(uuid4()),
        "role_type": "customer",
        "role_name": "comensal",
        "institution_id": str(uuid4()),
    }


@pytest.fixture
def client_with_customer(mock_customer_user):
    def _override_get_client_employee_or_supplier_user():
        return mock_customer_user

    def _override_oauth2_scheme():
        return "test-token"

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_client_employee_or_supplier_user] = _override_get_client_employee_or_supplier_user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_client_employee_or_supplier_user, None)


class TestListProvinces:
    """GET /api/v1/provinces returns supported provinces from config."""

    def test_returns_200_and_list_with_province_fields(self, client_with_customer):
        """Customer can list provinces; each item has province_code, province_name, country_code."""
        resp = client_with_customer.get("/api/v1/provinces")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for item in data:
            assert "province_code" in item
            assert "province_name" in item
            assert "country_code" in item
            assert isinstance(item["province_code"], str)
            assert isinstance(item["province_name"], str)
            assert len(item["country_code"]) == 2

    def test_filter_by_country_code_returns_matching_provinces(self, client_with_customer):
        """Optional country_code filter returns only provinces for that country."""
        resp = client_with_customer.get("/api/v1/provinces?country_code=US")
        assert resp.status_code == 200
        data = resp.json()
        for item in data:
            assert item["country_code"] == "US"
        assert len(data) >= 1
        codes = [item["province_code"] for item in data]
        assert "WA" in codes
        assert "FL" in codes

    def test_us_includes_washington_and_florida(self, client_with_customer):
        """US provinces include Washington (Seattle) and Florida (Miami)."""
        resp = client_with_customer.get("/api/v1/provinces?country_code=US")
        assert resp.status_code == 200
        data = resp.json()
        codes = [item["province_code"] for item in data]
        assert "WA" in codes
        assert "FL" in codes
