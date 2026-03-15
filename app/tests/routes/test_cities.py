"""
Tests for supported cities endpoint: GET /api/v1/cities/
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
        "role_type": "Customer",
        "role_name": "Comensal",
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
    """GET /api/v1/cities/ returns supported cities from city_info."""

    def test_returns_200_and_list_with_city_fields(self, client_with_customer):
        """Customer can list cities; each item has city_id, name, country_code, province_code."""
        resp = client_with_customer.get("/api/v1/cities/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for item in data:
            assert "city_id" in item
            assert "name" in item
            assert "country_code" in item
            assert "province_code" in item
            assert isinstance(item["name"], str)
            assert isinstance(item["country_code"], str)
            assert len(item["country_code"]) == 2

    def test_filter_by_country_code_returns_matching_cities(self, client_with_customer):
        """Optional country_code filter returns only cities in that country."""
        resp = client_with_customer.get("/api/v1/cities/?country_code=AR")
        assert resp.status_code == 200
        data = resp.json()
        for item in data:
            assert item["country_code"] == "AR"
        # Seed has Argentina cities
        assert len(data) >= 1

    def test_filter_by_province_code_returns_matching_cities(self, client_with_customer):
        """Optional province_code with country_code returns only cities in that province.
        Requires migration 002_add_province_to_city.sql and seed with province_code."""
        resp = client_with_customer.get("/api/v1/cities/?country_code=US")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        all_us = resp.json()
        assert isinstance(all_us, list)
        has_province = any(item.get("province_code") for item in all_us)
        if not has_province:
            pytest.skip("province_code not populated; run migration 002_add_province_to_city.sql and re-seed")
        resp = client_with_customer.get("/api/v1/cities/?country_code=US&province_code=WA")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for item in data:
            assert item["country_code"] == "US"
            assert item.get("province_code") == "WA"
            assert item["name"] == "Seattle"

    def test_province_filter_excludes_wrong_province(self, client_with_customer):
        """Florida cities do not include Seattle (Seattle is in Washington).
        Requires migration 002_add_province_to_city.sql and seed with province_code."""
        resp = client_with_customer.get("/api/v1/cities/?country_code=US")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        all_us = resp.json()
        assert isinstance(all_us, list)
        has_province = any(item.get("province_code") for item in all_us)
        if not has_province:
            pytest.skip("province_code not populated; run migration 002_add_province_to_city.sql and re-seed")
        resp = client_with_customer.get("/api/v1/cities/?country_code=US&province_code=FL")
        assert resp.status_code == 200
        data = resp.json()
        city_names = [item["name"] for item in data]
        assert "Seattle" not in city_names
        assert "Miami" in city_names
