"""
Tests for institution no_show_discount scoping.

Only Supplier institutions carry no_show_discount. Internal, Customer, and Employer
institutions must not persist this value - backend strips it on create and clears it on update.
"""

import pytest
from typing import Optional
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from application import app
from app.auth.dependencies import get_admin_user, get_current_user, oauth2_scheme
from app.services.crud_service import institution_service


GLOBAL_MARKET_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def admin_user():
    """Internal Admin user with global access for institution operations."""
    return {
        "user_id": str(uuid4()),
        "role_type": "Internal",
        "role_name": "Admin",
        "institution_id": str(uuid4()),
    }


@pytest.fixture
def super_admin_user():
    """Internal Super Admin user - can create Internal-type institutions."""
    return {
        "user_id": str(uuid4()),
        "role_type": "Internal",
        "role_name": "Super Admin",
        "institution_id": str(uuid4()),
    }


@pytest.fixture
def client_with_admin(admin_user):
    """TestClient with Admin user overrides for auth."""

    def _override_get_current_user():
        return admin_user

    def _override_get_admin_user():
        return admin_user

    def _override_oauth2_scheme():
        return "test-token"

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_admin_user] = _override_get_admin_user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_admin_user, None)


@pytest.fixture
def client_with_super_admin(super_admin_user):
    """TestClient with Super Admin user overrides for auth."""
    app.dependency_overrides[oauth2_scheme] = lambda: "test-token"
    app.dependency_overrides[get_current_user] = lambda: super_admin_user
    app.dependency_overrides[get_admin_user] = lambda: super_admin_user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_admin_user, None)


def _institution_create_payload(institution_type: str, no_show_discount: Optional[int] = None):
    """Minimal valid institution create payload."""
    payload = {
        "name": "Test Institution",
        "institution_type": institution_type,
        "market_id": GLOBAL_MARKET_ID,
    }
    if no_show_discount is not None:
        payload["no_show_discount"] = no_show_discount
    return payload


class TestInstitutionCreateNoShowDiscountScoping:
    """Create: no_show_discount must be stripped for non-Supplier institutions."""

    @patch.object(institution_service, "create")
    def test_create_employee_institution_with_no_show_discount_strips_value(
        self, mock_create, client_with_super_admin
    ):
        """POST /api/v1/institutions/ with Internal + no_show_discount: 20 does not persist it."""
        created = MagicMock()
        created.institution_id = uuid4()
        created.name = "Test Institution"
        created.institution_type = "Internal"
        created.market_id = uuid4()
        created.no_show_discount = None
        created.is_archived = False
        created.status = "Active"
        created.created_date = "2026-01-01T00:00:00Z"
        created.modified_date = "2026-01-01T00:00:00Z"
        created.created_by = None
        created.modified_by = uuid4()
        mock_create.return_value = created

        payload = _institution_create_payload("Internal", no_show_discount=20)
        resp = client_with_super_admin.post("/api/v1/institutions/", json=payload)

        assert resp.status_code == 201
        call_args = mock_create.call_args
        assert call_args is not None
        passed_payload = call_args[0][0]
        assert "no_show_discount" not in passed_payload or passed_payload.get("no_show_discount") is None

    @patch.object(institution_service, "create")
    def test_create_customer_institution_with_no_show_discount_strips_value(
        self, mock_create, client_with_super_admin
    ):
        """POST /api/v1/institutions/ with Customer + no_show_discount: 20 does not persist it."""
        created = MagicMock()
        created.institution_id = uuid4()
        created.name = "Test Institution"
        created.institution_type = "Customer"
        created.market_id = uuid4()
        created.no_show_discount = None
        created.is_archived = False
        created.status = "Active"
        created.created_date = "2026-01-01T00:00:00Z"
        created.modified_date = "2026-01-01T00:00:00Z"
        created.created_by = None
        created.modified_by = uuid4()
        mock_create.return_value = created

        payload = _institution_create_payload("Customer", no_show_discount=20)
        resp = client_with_super_admin.post("/api/v1/institutions/", json=payload)

        assert resp.status_code == 201
        call_args = mock_create.call_args
        assert call_args is not None
        passed_payload = call_args[0][0]
        assert "no_show_discount" not in passed_payload or passed_payload.get("no_show_discount") is None

    @patch.object(institution_service, "create")
    def test_create_employer_institution_with_no_show_discount_strips_value(
        self, mock_create, client_with_admin
    ):
        """POST /api/v1/institutions/ with Employer + no_show_discount: 20 does not persist it."""
        created = MagicMock()
        created.institution_id = uuid4()
        created.name = "Test Institution"
        created.institution_type = "Employer"
        created.market_id = uuid4()
        created.no_show_discount = None
        created.is_archived = False
        created.status = "Active"
        created.created_date = "2026-01-01T00:00:00Z"
        created.modified_date = "2026-01-01T00:00:00Z"
        created.created_by = None
        created.modified_by = uuid4()
        mock_create.return_value = created

        payload = _institution_create_payload("Employer", no_show_discount=20)
        resp = client_with_admin.post("/api/v1/institutions/", json=payload)

        assert resp.status_code == 201
        call_args = mock_create.call_args
        assert call_args is not None
        passed_payload = call_args[0][0]
        assert "no_show_discount" not in passed_payload or passed_payload.get("no_show_discount") is None

    @patch.object(institution_service, "create")
    def test_create_employee_institution_as_admin_returns_403(
        self, mock_create, client_with_admin
    ):
        """POST /api/v1/institutions/ with institution_type=Internal as Admin returns 403."""
        payload = _institution_create_payload("Internal", no_show_discount=None)
        payload["name"] = "Test Internal Inc"
        resp = client_with_admin.post("/api/v1/institutions/", json=payload)
        assert resp.status_code == 403
        assert "Super Admin" in resp.json().get("detail", "")
        mock_create.assert_not_called()

    @patch.object(institution_service, "create")
    def test_create_customer_institution_as_admin_returns_403(
        self, mock_create, client_with_admin
    ):
        """POST /api/v1/institutions/ with institution_type=Customer as Admin returns 403."""
        payload = _institution_create_payload("Customer", no_show_discount=None)
        payload["name"] = "Test Customer Inc"
        resp = client_with_admin.post("/api/v1/institutions/", json=payload)
        assert resp.status_code == 403
        assert "Super Admin" in resp.json().get("detail", "")
        mock_create.assert_not_called()

    @patch.object(institution_service, "create")
    def test_create_supplier_institution_with_no_show_discount_persists_value(
        self, mock_create, client_with_admin
    ):
        """POST /api/v1/institutions/ with Supplier + no_show_discount: 15 persists it."""
        created = MagicMock()
        created.institution_id = uuid4()
        created.name = "Test Supplier"
        created.institution_type = "Supplier"
        created.market_id = uuid4()
        created.no_show_discount = 15
        created.is_archived = False
        created.status = "Active"
        created.created_date = "2026-01-01T00:00:00Z"
        created.modified_date = "2026-01-01T00:00:00Z"
        created.created_by = None
        created.modified_by = uuid4()
        mock_create.return_value = created

        payload = _institution_create_payload("Supplier", no_show_discount=15)
        resp = client_with_admin.post("/api/v1/institutions/", json=payload)

        assert resp.status_code == 201
        call_args = mock_create.call_args
        assert call_args is not None
        passed_payload = call_args[0][0]
        assert passed_payload.get("no_show_discount") == 15


class TestInstitutionUpdateNoShowDiscountScoping:
    """Update: no_show_discount must be cleared for non-Supplier institutions."""

    @patch.object(institution_service, "get_by_id")
    @patch.object(institution_service, "update")
    def test_update_employee_institution_with_no_show_discount_clears_value(
        self, mock_update, mock_get_by_id, client_with_super_admin
    ):
        """PUT /api/v1/institutions/{id} with no_show_discount: 25 on Employee institution clears it."""
        inst_id = uuid4()
        mod_by = uuid4()
        existing = MagicMock()
        existing.institution_id = inst_id
        existing.institution_type = "Internal"
        existing.name = "Test Internal Inc"
        existing.market_id = uuid4()
        existing.no_show_discount = None
        existing.is_archived = False
        existing.status = "Active"
        mock_get_by_id.return_value = existing

        updated = MagicMock()
        updated.institution_id = inst_id
        updated.institution_type = "Internal"
        updated.name = "Test Internal Inc"
        updated.market_id = existing.market_id
        updated.no_show_discount = None
        updated.is_archived = False
        updated.status = "Active"
        updated.created_date = "2026-01-01T00:00:00Z"
        updated.modified_date = "2026-01-01T00:00:00Z"
        updated.created_by = None
        updated.modified_by = mod_by
        mock_update.return_value = updated

        resp = client_with_super_admin.put(
            f"/api/v1/institutions/{inst_id}",
            json={"no_show_discount": 25},
        )

        assert resp.status_code == 200
        call_args = mock_update.call_args
        assert call_args is not None
        passed_payload = call_args[0][1]
        assert passed_payload.get("no_show_discount") is None

    @patch.object(institution_service, "get_by_id")
    @patch.object(institution_service, "update")
    def test_update_supplier_to_employee_clears_no_show_discount(
        self, mock_update, mock_get_by_id, client_with_super_admin
    ):
        """PUT changing institution_type from Supplier to Internal clears no_show_discount."""
        inst_id = uuid4()
        existing = MagicMock()
        existing.institution_id = inst_id
        existing.institution_type = "Supplier"
        existing.name = "Test Supplier Inc"
        existing.market_id = uuid4()
        existing.no_show_discount = 20
        existing.is_archived = False
        existing.status = "Active"
        mock_get_by_id.return_value = existing

        updated = MagicMock()
        updated.institution_id = inst_id
        updated.institution_type = "Internal"
        updated.name = "Test Supplier Inc"
        updated.market_id = existing.market_id
        updated.no_show_discount = None
        updated.is_archived = False
        updated.status = "Active"
        updated.created_date = "2026-01-01T00:00:00Z"
        updated.modified_date = "2026-01-01T00:00:00Z"
        updated.created_by = None
        updated.modified_by = uuid4()
        mock_update.return_value = updated

        resp = client_with_super_admin.put(
            f"/api/v1/institutions/{inst_id}",
            json={"institution_type": "Internal"},
        )

        assert resp.status_code == 200
        call_args = mock_update.call_args
        assert call_args is not None
        passed_payload = call_args[0][1]
        assert passed_payload.get("no_show_discount") is None
