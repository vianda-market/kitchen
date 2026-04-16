"""
Tests for supported cities endpoint: GET /api/v1/cities
"""

from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

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


class TestListCities:
    """GET /api/v1/cities returns supported cities from city_info."""

    def test_returns_200_and_list_with_city_fields(self, client_with_customer):
        """Customer can list cities; each item has city_metadata_id, name, country_code.
        province_code filter was removed in PR1 (two-tier city_metadata restructure)."""
        resp = client_with_customer.get("/api/v1/cities")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for item in data:
            assert "city_metadata_id" in item
            assert "name" in item
            assert "country_code" in item
            assert isinstance(item["name"], str)
            assert isinstance(item["country_code"], str)
            assert len(item["country_code"]) == 2

    def test_filter_by_country_code_returns_matching_cities(self, client_with_customer):
        """Optional country_code filter returns only cities in that country."""
        resp = client_with_customer.get("/api/v1/cities?country_code=AR")
        assert resp.status_code == 200
        data = resp.json()
        for item in data:
            assert item["country_code"] == "AR"
        # Seed has Argentina cities
        assert len(data) >= 1
