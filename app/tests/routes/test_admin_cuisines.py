"""Tests for admin cuisine endpoints: CRUD + suggestion review"""

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_admin_user, get_current_user, oauth2_scheme


@pytest.fixture
def mock_admin_user():
    return {
        "user_id": str(uuid4()),
        "role_type": "internal",
        "role_name": "super_admin",
        "institution_id": str(uuid4()),
    }


@pytest.fixture
def client_with_admin(mock_admin_user):
    def _override_get_admin_user():
        return mock_admin_user

    def _override_get_current_user():
        return mock_admin_user

    def _override_oauth2_scheme():
        return "test-token"

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_admin_user] = _override_get_admin_user
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_admin_user, None)
        app.dependency_overrides.pop(get_current_user, None)


# ---- Helpers ----


def _cuisine_dict(**overrides):
    """Build a cuisine dict with sensible defaults."""
    now = datetime.now(UTC).isoformat()
    base = {
        "cuisine_id": str(uuid4()),
        "cuisine_name": "Italian",
        "cuisine_name_i18n": {"es": "Italiana"},
        "slug": "italian",
        "parent_cuisine_id": None,
        "description": "Classic Italian cuisine",
        "origin_source": "seed",
        "display_order": 1,
        "is_archived": False,
        "status": "active",
        "created_date": now,
        "modified_date": now,
    }
    base.update(overrides)
    return base


def _suggestion_dict(**overrides):
    """Build a suggestion dict with sensible defaults."""
    now = datetime.now(UTC).isoformat()
    base = {
        "suggestion_id": str(uuid4()),
        "suggested_name": "Peruvian Fusion",
        "suggested_by": str(uuid4()),
        "restaurant_id": None,
        "suggestion_status": "pending",
        "reviewed_by": None,
        "reviewed_date": None,
        "review_notes": None,
        "resolved_cuisine_id": None,
        "created_date": now,
    }
    base.update(overrides)
    return base


# ---- Cuisine CRUD Tests ----


class TestAdminCuisineCRUD:
    """Admin CRUD on /api/v1/admin/cuisines."""

    @patch("app.routes.admin.cuisines.cuisine_service")
    @patch("app.routes.admin.cuisines.cuisine_crud_service")
    def test_create_cuisine_returns_201(self, mock_crud, mock_service, client_with_admin):
        """POST /admin/cuisines with valid body returns 201."""
        mock_service._generate_slug.return_value = "thai"
        mock_crud.create.return_value = _cuisine_dict(cuisine_name="Thai", slug="thai")
        payload = {"cuisine_name": "Thai"}
        resp = client_with_admin.post("/api/v1/admin/cuisines", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["cuisine_name"] == "Thai"
        assert data["slug"] == "thai"
        mock_crud.create.assert_called_once()

    @patch("app.routes.admin.cuisines.cuisine_service")
    def test_list_all_cuisines_returns_200(self, mock_service, client_with_admin):
        """GET /admin/cuisines returns 200 with list."""
        mock_service.search_cuisines.return_value = [
            _cuisine_dict(cuisine_name="Italian"),
            _cuisine_dict(cuisine_name="French", slug="french"),
        ]
        resp = client_with_admin.get("/api/v1/admin/cuisines")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    @patch("app.routes.admin.cuisines.cuisine_crud_service")
    def test_get_cuisine_returns_200(self, mock_crud, client_with_admin):
        """GET /admin/cuisines/{id} returns 200 when found."""
        cuisine_id = str(uuid4())
        mock_crud.get_by_id.return_value = _cuisine_dict(cuisine_id=cuisine_id)
        resp = client_with_admin.get(f"/api/v1/admin/cuisines/{cuisine_id}")
        assert resp.status_code == 200
        assert resp.json()["cuisine_id"] == cuisine_id

    @patch("app.routes.admin.cuisines.cuisine_crud_service")
    def test_get_cuisine_not_found_returns_404(self, mock_crud, client_with_admin):
        """GET /admin/cuisines/{id} returns 404 when not found."""
        mock_crud.get_by_id.return_value = None
        resp = client_with_admin.get(f"/api/v1/admin/cuisines/{uuid4()}")
        assert resp.status_code == 404

    @patch("app.routes.admin.cuisines.cuisine_crud_service")
    def test_update_cuisine_returns_200(self, mock_crud, client_with_admin):
        """PUT /admin/cuisines/{id} returns 200 with updated data."""
        cuisine_id = str(uuid4())
        mock_crud.update.return_value = _cuisine_dict(cuisine_id=cuisine_id, cuisine_name="Updated Italian")
        payload = {"cuisine_name": "Updated Italian"}
        resp = client_with_admin.put(f"/api/v1/admin/cuisines/{cuisine_id}", json=payload)
        assert resp.status_code == 200
        assert resp.json()["cuisine_name"] == "Updated Italian"

    @patch("app.routes.admin.cuisines.cuisine_crud_service")
    def test_delete_cuisine_soft_delete(self, mock_crud, client_with_admin):
        """DELETE /admin/cuisines/{id} soft-deletes via get_by_id + soft_delete and returns the
        pre-archive DTO with is_archived flipped. Direct CRUDService.update with is_archived=True
        is the wrong path because CRUDService.update re-fetches via get_by_id (filters archived)
        and returns None for the just-archived row."""
        cuisine_id = str(uuid4())
        # get_by_id returns the CuisineDTO-shaped dict (route wraps it in the response model)
        from app.config import Status
        from app.dto.models import CuisineDTO

        mock_crud.get_by_id.return_value = CuisineDTO(
            cuisine_id=UUID(cuisine_id),
            cuisine_name="Italian",
            cuisine_name_i18n=None,
            slug="italian",
            parent_cuisine_id=None,
            description=None,
            origin_source="seed",
            display_order=None,
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(UTC),
            modified_by=UUID(str(uuid4())),
            modified_date=datetime.now(UTC),
        )
        mock_crud.soft_delete.return_value = True
        resp = client_with_admin.delete(f"/api/v1/admin/cuisines/{cuisine_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_archived"] is True


# ---- Suggestion Review Tests ----


class TestAdminSuggestionReview:
    """Admin review of cuisine suggestions."""

    @patch("app.routes.admin.cuisines.cuisine_service")
    def test_list_pending_suggestions_returns_200(self, mock_service, client_with_admin):
        """GET /admin/cuisines/suggestions returns 200 with pending list."""
        mock_service.get_pending_suggestions.return_value = [
            _suggestion_dict(),
            _suggestion_dict(suggested_name="Nordic Brunch"),
        ]
        resp = client_with_admin.get("/api/v1/admin/cuisines/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    @patch("app.routes.admin.cuisines.cuisine_service")
    def test_approve_suggestion_returns_200(self, mock_service, client_with_admin):
        """PUT /admin/cuisines/suggestions/{id}/approve returns 200."""
        suggestion_id = str(uuid4())
        resolved_cuisine_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        mock_service.approve_suggestion.return_value = _suggestion_dict(
            suggestion_id=suggestion_id,
            suggestion_status="approved",
            resolved_cuisine_id=resolved_cuisine_id,
            reviewed_by=str(uuid4()),
            reviewed_date=now,
        )
        payload = {
            "resolved_cuisine_id": resolved_cuisine_id,
            "review_notes": "Looks good",
        }
        resp = client_with_admin.put(
            f"/api/v1/admin/cuisines/suggestions/{suggestion_id}/approve",
            json=payload,
        )
        assert resp.status_code == 200
        assert resp.json()["suggestion_status"] == "approved"

    @patch("app.routes.admin.cuisines.cuisine_service")
    def test_approve_not_found_returns_404(self, mock_service, client_with_admin):
        """PUT /admin/cuisines/suggestions/{id}/approve returns 404 when not found."""
        mock_service.approve_suggestion.return_value = None
        payload = {"review_notes": "n/a"}
        resp = client_with_admin.put(
            f"/api/v1/admin/cuisines/suggestions/{uuid4()}/approve",
            json=payload,
        )
        assert resp.status_code == 404

    @patch("app.routes.admin.cuisines.cuisine_service")
    def test_reject_suggestion_returns_200(self, mock_service, client_with_admin):
        """PUT /admin/cuisines/suggestions/{id}/reject returns 200."""
        suggestion_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        mock_service.reject_suggestion.return_value = _suggestion_dict(
            suggestion_id=suggestion_id,
            suggestion_status="rejected",
            reviewed_by=str(uuid4()),
            reviewed_date=now,
            review_notes="Not a distinct cuisine",
        )
        payload = {"review_notes": "Not a distinct cuisine"}
        resp = client_with_admin.put(
            f"/api/v1/admin/cuisines/suggestions/{suggestion_id}/reject",
            json=payload,
        )
        assert resp.status_code == 200
        assert resp.json()["suggestion_status"] == "rejected"
