"""
Tests for supported currencies endpoint: GET /api/v1/currencies/
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from application import app
from app.auth.dependencies import get_employee_user, oauth2_scheme


@pytest.fixture
def mock_employee_user():
    return {
        "user_id": str(uuid4()),
        "role_type": "Employee",
        "role_name": "Admin",
        "institution_id": str(uuid4()),
    }


@pytest.fixture
def client_with_employee(mock_employee_user):
    def _override_get_employee_user():
        return mock_employee_user

    def _override_oauth2_scheme():
        return "test-token"

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_employee_user] = _override_get_employee_user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_employee_user, None)


class TestListSupportedCurrencies:
    """GET /api/v1/currencies/ returns supported currencies for dropdown."""

    def test_returns_200_and_list_with_currency_name_and_code(self, client_with_employee):
        """Employee can list supported currencies; each item has currency_name and currency_code."""
        resp = client_with_employee.get("/api/v1/currencies/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for item in data:
            assert "currency_name" in item
            assert "currency_code" in item
            assert isinstance(item["currency_name"], str)
            assert isinstance(item["currency_code"], str)

    def test_sorted_by_currency_name(self, client_with_employee):
        """List is sorted by currency_name (case-insensitive)."""
        resp = client_with_employee.get("/api/v1/currencies/")
        assert resp.status_code == 200
        data = resp.json()
        names = [x["currency_name"].lower() for x in data]
        assert names == sorted(names)

    def test_contains_us_dollar_and_argentine_peso(self, client_with_employee):
        """Response contains expected entries."""
        resp = client_with_employee.get("/api/v1/currencies/")
        assert resp.status_code == 200
        data = resp.json()
        names = [x["currency_name"] for x in data]
        codes = [x["currency_code"] for x in data]
        assert "US Dollar" in names
        assert "Argentine Peso" in names
        assert "USD" in codes
        assert "ARS" in codes
