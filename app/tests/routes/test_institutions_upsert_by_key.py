"""
Tests for institution upsert:
- PUT /institutions/by-key: insert, update, idempotency.
- PUT /institutions/by-key: auth guard (supplier role rejected with 403).
- PUT /institutions/by-key: immutable institution_type on update.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_employee_user, oauth2_scheme
from app.dependencies.database import get_db
from app.services import entity_service as _entity_service_module  # noqa: F401 – ensures patch target is importable
from app.services.crud_service import institution_service

# Needs live Postgres (TestClient triggers DB pool init via unmocked code paths).
# Excluded from unit test job by -m "not database"; runs in acceptance (Newman).
pytestmark = pytest.mark.database


@pytest.fixture
def mock_employee_user():
    return {
        "user_id": str(uuid4()),
        "role_type": "internal",
        "role_name": "admin",
        "institution_id": str(uuid4()),
    }


@pytest.fixture
def mock_db():
    """A mock psycopg2 connection that silently accepts cursor/commit/rollback calls."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.fixture
def client_with_employee(mock_employee_user, mock_db):
    def _override_get_employee_user():
        return mock_employee_user

    def _override_oauth2_scheme():
        return "test-token"

    def _override_get_db():
        return mock_db

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_employee_user] = _override_get_employee_user
    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_employee_user, None)
        app.dependency_overrides.pop(get_db, None)


def _make_institution_dto(*, canonical_key=None):
    """Build a minimal mock institution DTO."""
    iid = uuid4()
    mbid = uuid4()

    m = MagicMock()
    m.institution_id = iid
    m.name = "E2E Supplier Institution"
    m.institution_type = "supplier"
    m.is_archived = False
    m.status = "active"
    m.canonical_key = canonical_key
    m.support_email_suppressed_until = None
    m.last_support_email_date = None
    m.created_date = "2026-01-01T00:00:00Z"
    m.modified_date = "2026-01-01T00:00:00Z"
    m.created_by = None
    m.modified_by = mbid
    return m


def _valid_upsert_payload(*, canonical_key="E2E_INSTITUTION_SUPPLIER"):
    """Minimal valid upsert payload."""
    return {
        "canonical_key": canonical_key,
        "name": "E2E Supplier Institution",
        "institution_type": "supplier",
        "market_ids": [str(uuid4())],
        "status": "active",
    }


def _mock_attach_market_ids(institution, db):
    """Minimal stand-in for attach_institution_market_ids."""
    market_id = uuid4()
    return {
        "institution_id": institution.institution_id,
        "name": institution.name,
        "institution_type": institution.institution_type,
        "market_ids": [market_id],
        "support_email_suppressed_until": None,
        "last_support_email_date": None,
        "is_archived": institution.is_archived,
        "status": institution.status,
        "canonical_key": institution.canonical_key,
        "created_date": institution.created_date,
        "created_by": institution.created_by,
        "modified_by": institution.modified_by,
        "modified_date": institution.modified_date,
    }


class TestInstitutionUpsertByKey:
    """PUT /api/v1/institutions/by-key: insert, update, idempotency, auth, immutability."""

    @patch("app.services.crud_service.find_institution_by_canonical_key")
    @patch.object(institution_service, "create")
    @patch("app.services.entity_service.attach_institution_market_ids")
    def test_upsert_inserts_when_key_not_found(
        self,
        mock_attach,
        mock_create,
        mock_find,
        client_with_employee,
    ):
        """PUT /institutions/by-key with a new canonical_key inserts a new institution and returns 200."""
        mock_find.return_value = None  # key does not exist yet

        created = _make_institution_dto(canonical_key="E2E_INSTITUTION_SUPPLIER")
        mock_create.return_value = created
        mock_attach.side_effect = _mock_attach_market_ids

        payload = _valid_upsert_payload(canonical_key="E2E_INSTITUTION_SUPPLIER")

        resp = client_with_employee.put("/api/v1/institutions/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "institution_id" in data
        mock_create.assert_called_once()

    @patch("app.services.crud_service.find_institution_by_canonical_key")
    @patch.object(institution_service, "update")
    @patch("app.services.entity_service.attach_institution_market_ids")
    def test_upsert_updates_when_key_exists(self, mock_attach, mock_update, mock_find, client_with_employee):
        """PUT /institutions/by-key with an existing canonical_key updates the institution and returns 200."""
        existing = _make_institution_dto(canonical_key="E2E_INSTITUTION_SUPPLIER")
        mock_find.return_value = existing

        updated = _make_institution_dto(canonical_key="E2E_INSTITUTION_SUPPLIER")
        updated.name = "E2E Supplier Updated"
        mock_update.return_value = updated
        mock_attach.side_effect = _mock_attach_market_ids

        payload = _valid_upsert_payload(canonical_key="E2E_INSTITUTION_SUPPLIER")
        payload["name"] = "E2E Supplier Updated"

        resp = client_with_employee.put("/api/v1/institutions/by-key", json=payload)

        assert resp.status_code == 200
        mock_update.assert_called_once()
        # institution_type and canonical_key must not be passed to update
        update_payload = mock_update.call_args[0][1]
        assert "canonical_key" not in update_payload
        assert "institution_type" not in update_payload

    @patch("app.services.crud_service.find_institution_by_canonical_key")
    @patch.object(institution_service, "create")
    @patch("app.services.entity_service.attach_institution_market_ids")
    def test_upsert_idempotent_same_payload_twice(
        self,
        mock_attach,
        mock_create,
        mock_find,
        client_with_employee,
    ):
        """Calling upsert twice with identical payload should behave consistently."""
        mock_find.return_value = None  # First call: insert
        created = _make_institution_dto(canonical_key="E2E_INSTITUTION_IDEMPOTENT")
        mock_create.return_value = created
        mock_attach.side_effect = _mock_attach_market_ids

        payload = _valid_upsert_payload(canonical_key="E2E_INSTITUTION_IDEMPOTENT")

        resp1 = client_with_employee.put("/api/v1/institutions/by-key", json=payload)
        assert resp1.status_code == 200

        # Second call: key now exists — should call update instead of create
        mock_find.return_value = created
        with patch.object(institution_service, "update") as mock_update:
            mock_update.return_value = created
            resp2 = client_with_employee.put("/api/v1/institutions/by-key", json=payload)
            assert resp2.status_code == 200
            mock_update.assert_called_once()

    def test_upsert_requires_employee_auth(self):
        """PUT /institutions/by-key without employee auth returns 403."""

        def _override_get_employee_user():
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="Forbidden")

        def _override_oauth2_scheme():
            return "test-token"

        app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
        app.dependency_overrides[get_employee_user] = _override_get_employee_user
        try:
            with TestClient(app) as c:
                payload = _valid_upsert_payload()
                resp = c.put("/api/v1/institutions/by-key", json=payload)
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_employee_user, None)

    def test_upsert_rejects_supplier_role(self):
        """PUT /institutions/by-key with a supplier (non-internal) token returns 403."""
        supplier_user = {
            "user_id": str(uuid4()),
            "role_type": "supplier",
            "role_name": "admin",
            "institution_id": str(uuid4()),
        }

        def _override_get_current_user():
            return supplier_user

        def _override_oauth2_scheme():
            return "supplier-test-token"

        app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
        app.dependency_overrides[get_current_user] = _override_get_current_user
        try:
            with TestClient(app) as c:
                payload = _valid_upsert_payload()
                resp = c.put("/api/v1/institutions/by-key", json=payload)
                assert resp.status_code == 403, (
                    f"Expected 403 for supplier role, got {resp.status_code}. "
                    "get_employee_user must reject non-internal users."
                )
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.services.crud_service.find_institution_by_canonical_key")
    @patch.object(institution_service, "update")
    @patch("app.services.entity_service.attach_institution_market_ids")
    def test_upsert_institution_type_immutable_on_update(
        self, mock_attach, mock_update, mock_find, client_with_employee
    ):
        """PUT /institutions/by-key update path must not pass institution_type to institution_service.update.

        institution_type is immutable after creation.  Even if the caller sends a
        different institution_type in the payload, it must be silently stripped and
        the existing type preserved.
        """
        existing = _make_institution_dto(canonical_key="E2E_INSTITUTION_IMMUTABLE_TEST")
        existing.institution_type = "supplier"
        mock_find.return_value = existing

        updated = _make_institution_dto(canonical_key="E2E_INSTITUTION_IMMUTABLE_TEST")
        mock_update.return_value = updated
        mock_attach.side_effect = _mock_attach_market_ids

        payload = _valid_upsert_payload(canonical_key="E2E_INSTITUTION_IMMUTABLE_TEST")
        # Caller sends employer — must be ignored since institution_type is immutable
        payload["institution_type"] = "employer"

        resp = client_with_employee.put("/api/v1/institutions/by-key", json=payload)

        assert resp.status_code == 200
        update_payload = mock_update.call_args[0][1]
        assert "institution_type" not in update_payload, (
            "institution_type must be stripped from the update payload — it is immutable after creation"
        )
