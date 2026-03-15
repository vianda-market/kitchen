"""
Tests for supported cuisines endpoint: GET /api/v1/cuisines/
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


class TestListCuisines:
    """GET /api/v1/cuisines/ returns supported cuisines from config."""

    def test_returns_200_and_list_with_cuisine_name(self, client_with_customer):
        """Customer can list cuisines; each item has cuisine_name."""
        resp = client_with_customer.get("/api/v1/cuisines/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for item in data:
            assert "cuisine_name" in item
            assert isinstance(item["cuisine_name"], str)

    def test_sorted_alphabetically(self, client_with_customer):
        """List is sorted by cuisine_name (case-insensitive)."""
        resp = client_with_customer.get("/api/v1/cuisines/")
        assert resp.status_code == 200
        data = resp.json()
        names = [x["cuisine_name"].lower() for x in data]
        assert names == sorted(names)

    def test_contains_italian_french_american(self, client_with_customer):
        """Response contains American, French, Italian per plan."""
        resp = client_with_customer.get("/api/v1/cuisines/")
        assert resp.status_code == 200
        data = resp.json()
        names = [x["cuisine_name"] for x in data]
        assert "American" in names
        assert "French" in names
        assert "Italian" in names


class TestRestaurantCuisineValidation:
    """RestaurantCreateSchema and RestaurantUpdateSchema validate cuisine against supported list."""

    def test_create_accepts_supported_cuisine(self):
        """RestaurantCreateSchema accepts Italian (case-insensitive)."""
        from app.schemas.consolidated_schemas import RestaurantCreateSchema
        from uuid import UUID
        schema = RestaurantCreateSchema(
            institution_id=UUID("11111111-1111-1111-1111-111111111111"),
            institution_entity_id=UUID("33333333-3333-3333-3333-333333333333"),
            address_id=UUID("44444444-4444-4444-4444-444444444444"),
            name="Test Restaurant",
            cuisine="Italian",
        )
        assert schema.cuisine == "Italian"

    def test_create_rejects_unsupported_cuisine(self):
        """RestaurantCreateSchema rejects unknown cuisine."""
        from app.schemas.consolidated_schemas import RestaurantCreateSchema
        from uuid import UUID
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            RestaurantCreateSchema(
                institution_id=UUID("11111111-1111-1111-1111-111111111111"),
                institution_entity_id=UUID("33333333-3333-3333-3333-333333333333"),
                address_id=UUID("44444444-4444-4444-4444-444444444444"),
                name="Test Restaurant",
                cuisine="Fusion",
            )
        assert "not supported" in str(exc_info.value).lower()

    def test_create_accepts_null_cuisine(self):
        """RestaurantCreateSchema accepts null cuisine."""
        from app.schemas.consolidated_schemas import RestaurantCreateSchema
        from uuid import UUID
        schema = RestaurantCreateSchema(
            institution_id=UUID("11111111-1111-1111-1111-111111111111"),
            institution_entity_id=UUID("33333333-3333-3333-3333-333333333333"),
            address_id=UUID("44444444-4444-4444-4444-444444444444"),
            name="Test Restaurant",
            cuisine=None,
        )
        assert schema.cuisine is None

    def test_update_accepts_supported_cuisine(self):
        """RestaurantUpdateSchema accepts French."""
        from app.schemas.consolidated_schemas import RestaurantUpdateSchema
        schema = RestaurantUpdateSchema(cuisine="French")
        assert schema.cuisine == "French"

    def test_update_rejects_unsupported_cuisine(self):
        """RestaurantUpdateSchema rejects unknown cuisine."""
        from app.schemas.consolidated_schemas import RestaurantUpdateSchema
        from pydantic import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            RestaurantUpdateSchema(cuisine="UnknownCuisine")
        assert "not supported" in str(exc_info.value).lower()
