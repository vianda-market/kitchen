"""Tests for cuisine endpoints: GET /api/v1/cuisines and POST /api/v1/cuisines/suggestions"""

import pytest
from uuid import UUID, uuid4
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from application import app
from app.auth.dependencies import (
    get_client_employee_or_supplier_user,
    get_employee_or_supplier_user,
    oauth2_scheme,
)


@pytest.fixture
def mock_customer_user():
    return {
        "user_id": str(uuid4()),
        "role_type": "Customer",
        "role_name": "Comensal",
        "institution_id": str(uuid4()),
    }


@pytest.fixture
def mock_supplier_user():
    return {
        "user_id": str(uuid4()),
        "role_type": "Supplier",
        "role_name": "Admin",
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


@pytest.fixture
def client_with_supplier(mock_supplier_user):
    def _override_get_employee_or_supplier_user():
        return mock_supplier_user

    def _override_oauth2_scheme():
        return "test-token"

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_employee_or_supplier_user] = _override_get_employee_or_supplier_user
    # Also override the broader dep so list endpoint works for supplier
    app.dependency_overrides[get_client_employee_or_supplier_user] = _override_get_employee_or_supplier_user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_employee_or_supplier_user, None)
        app.dependency_overrides.pop(get_client_employee_or_supplier_user, None)


class TestListCuisines:
    """GET /api/v1/cuisines returns cuisines from DB."""

    @patch("app.routes.cuisines.cuisine_service")
    def test_returns_200_and_list(self, mock_cuisine_service, client_with_customer):
        """Customer can list cuisines; each item has cuisine_id, cuisine_name, slug."""
        mock_cuisine_service.search_cuisines.return_value = [
            {
                "cuisine_id": str(uuid4()),
                "cuisine_name": "Italian",
                "slug": "italian",
                "parent_cuisine_id": None,
                "description": "Italian cuisine",
                "display_order": 1,
            },
            {
                "cuisine_id": str(uuid4()),
                "cuisine_name": "French",
                "slug": "french",
                "parent_cuisine_id": None,
                "description": None,
                "display_order": 2,
            },
        ]
        resp = client_with_customer.get("/api/v1/cuisines")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        for item in data:
            assert "cuisine_id" in item
            assert "cuisine_name" in item
            assert "slug" in item

    @patch("app.routes.cuisines.cuisine_service")
    def test_search_param_passed(self, mock_cuisine_service, client_with_customer):
        """Query param search=ita is forwarded to search_cuisines."""
        mock_cuisine_service.search_cuisines.return_value = [
            {
                "cuisine_id": str(uuid4()),
                "cuisine_name": "Italian",
                "slug": "italian",
                "parent_cuisine_id": None,
                "description": None,
                "display_order": 1,
            },
        ]
        resp = client_with_customer.get("/api/v1/cuisines?search=ita")
        assert resp.status_code == 200
        mock_cuisine_service.search_cuisines.assert_called_once()
        call_kwargs = mock_cuisine_service.search_cuisines.call_args
        # search keyword should be "ita"
        assert call_kwargs[1].get("search") == "ita" or call_kwargs[0][1] == "ita"

    def test_unauthenticated_returns_401(self):
        """No auth override results in 401."""
        # Ensure no overrides leak
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_client_employee_or_supplier_user, None)
        try:
            with TestClient(app) as c:
                resp = c.get("/api/v1/cuisines")
            assert resp.status_code == 401
        finally:
            pass


    @patch("app.routes.cuisines.cuisine_service")
    def test_language_param_localizes_cuisine_name(self, mock_cuisine_service, client_with_customer):
        """?language=es resolves cuisine_name from cuisine_name_i18n."""
        mock_cuisine_service.search_cuisines.return_value = [
            {
                "cuisine_id": str(uuid4()),
                "cuisine_name": "Japanese",
                "cuisine_name_i18n": {"en": "Japanese", "es": "Japonesa", "pt": "Japonesa"},
                "slug": "japanese",
                "parent_cuisine_id": None,
                "description": None,
                "display_order": 1,
            },
        ]
        resp = client_with_customer.get("/api/v1/cuisines?language=es")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["cuisine_name"] == "Japonesa"

    @patch("app.routes.cuisines.cuisine_service")
    def test_invalid_language_returns_422(self, mock_cuisine_service, client_with_customer):
        """?language=fr returns 422."""
        resp = client_with_customer.get("/api/v1/cuisines?language=fr")
        assert resp.status_code == 422

    @patch("app.routes.cuisines.cuisine_service")
    def test_accept_language_header_fallback(self, mock_cuisine_service, client_with_customer):
        """Accept-Language header is used when ?language= is not provided."""
        mock_cuisine_service.search_cuisines.return_value = [
            {
                "cuisine_id": str(uuid4()),
                "cuisine_name": "Italian",
                "cuisine_name_i18n": {"en": "Italian", "es": "Italiana", "pt": "Italiana"},
                "slug": "italian",
                "parent_cuisine_id": None,
                "description": None,
                "display_order": 1,
            },
        ]
        resp = client_with_customer.get("/api/v1/cuisines", headers={"Accept-Language": "es"})
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["cuisine_name"] == "Italiana"


class TestCreateSuggestion:
    """POST /api/v1/cuisines/suggestions — supplier suggestion workflow."""

    @patch("app.routes.cuisines.cuisine_service")
    def test_returns_201_with_suggestion(self, mock_cuisine_service, client_with_supplier):
        """Valid suggestion body returns 201 with suggestion_id and Pending status."""
        suggestion_id = str(uuid4())
        user_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        mock_cuisine_service.create_suggestion.return_value = {
            "suggestion_id": suggestion_id,
            "suggested_name": "Peruvian Fusion",
            "suggested_by": user_id,
            "restaurant_id": None,
            "suggestion_status": "Pending",
            "reviewed_by": None,
            "reviewed_date": None,
            "review_notes": None,
            "resolved_cuisine_id": None,
            "created_date": now,
        }
        payload = {"suggested_name": "Peruvian Fusion"}
        resp = client_with_supplier.post("/api/v1/cuisines/suggestions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["suggestion_id"] == suggestion_id
        assert data["suggestion_status"] == "Pending"

    def test_missing_suggested_name_returns_422(self, client_with_supplier):
        """POST with empty body returns 422 (suggested_name is required)."""
        resp = client_with_supplier.post("/api/v1/cuisines/suggestions", json={})
        assert resp.status_code == 422
