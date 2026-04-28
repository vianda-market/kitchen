"""
Tests for institution entity upsert:
- PUT /institution-entities/by-key: insert, update, idempotency.
- PUT /institution-entities/by-key: auth guard (supplier role rejected with 403).
- PUT /institution-entities/by-key: immutable institution_id on update.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_employee_user, oauth2_scheme
from app.dependencies.database import get_db
from app.services.crud_service import institution_entity_service

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


def _make_entity_dto(*, canonical_key=None):
    """Build a minimal mock institution entity DTO."""
    entity_id = uuid4()
    institution_id = uuid4()
    address_id = uuid4()
    currency_metadata_id = uuid4()
    modified_by = uuid4()

    m = MagicMock()
    m.institution_entity_id = entity_id
    m.institution_id = institution_id
    m.address_id = address_id
    m.currency_metadata_id = currency_metadata_id
    m.tax_id = "30123456789"
    m.name = "E2E Supplier Entity"
    m.payout_provider_account_id = None
    m.payout_aggregator = None
    m.payout_onboarding_status = None
    m.email_domain = None
    m.canonical_key = canonical_key
    m.is_archived = False
    m.status = "active"
    m.created_date = "2026-01-01T00:00:00Z"
    m.modified_date = "2026-01-01T00:00:00Z"
    m.created_by = None
    m.modified_by = modified_by
    return m


def _valid_upsert_payload(*, canonical_key="E2E_INSTITUTION_ENTITY_SUPPLIER"):
    """Minimal valid upsert payload."""
    return {
        "canonical_key": canonical_key,
        "institution_id": str(uuid4()),
        "address_id": str(uuid4()),
        "tax_id": "30123456789",
        "name": "E2E Supplier Entity",
        "status": "active",
    }


class TestInstitutionEntityUpsertByKey:
    """PUT /api/v1/institution-entities/by-key: insert, update, idempotency, auth, immutability."""

    @patch("app.routes.institution_entity.find_institution_entity_by_canonical_key")
    @patch("app.services.entity_service.derive_currency_metadata_id_for_address")
    @patch("app.utils.db.db_read")
    @patch.object(institution_entity_service, "create")
    def test_upsert_inserts_when_key_not_found(
        self,
        mock_create,
        mock_db_read,
        mock_derive_currency,
        mock_find,
        client_with_employee,
    ):
        """PUT /institution-entities/by-key with a new canonical_key inserts a new entity and returns 200."""
        mock_find.return_value = None  # key does not exist yet

        created = _make_entity_dto(canonical_key="E2E_INSTITUTION_ENTITY_SUPPLIER")
        mock_create.return_value = created
        mock_derive_currency.return_value = uuid4()
        # Mock market_check: simulate address country maps to institution market
        mock_db_read.return_value = {"country_code": "AR"}

        payload = _valid_upsert_payload(canonical_key="E2E_INSTITUTION_ENTITY_SUPPLIER")

        resp = client_with_employee.put("/api/v1/institution-entities/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "institution_entity_id" in data
        mock_create.assert_called_once()

    @patch("app.routes.institution_entity.find_institution_entity_by_canonical_key")
    @patch("app.services.entity_service.derive_currency_metadata_id_for_address")
    @patch.object(institution_entity_service, "update")
    def test_upsert_updates_when_key_exists(
        self,
        mock_update,
        mock_derive_currency,
        mock_find,
        client_with_employee,
    ):
        """PUT /institution-entities/by-key with an existing canonical_key updates the entity and returns 200."""
        existing = _make_entity_dto(canonical_key="E2E_INSTITUTION_ENTITY_SUPPLIER")
        mock_find.return_value = existing

        updated = _make_entity_dto(canonical_key="E2E_INSTITUTION_ENTITY_SUPPLIER")
        updated.name = "E2E Supplier Entity Updated"
        mock_update.return_value = updated
        mock_derive_currency.return_value = uuid4()

        payload = _valid_upsert_payload(canonical_key="E2E_INSTITUTION_ENTITY_SUPPLIER")
        payload["name"] = "E2E Supplier Entity Updated"

        resp = client_with_employee.put("/api/v1/institution-entities/by-key", json=payload)

        assert resp.status_code == 200
        mock_update.assert_called_once()
        # institution_id and canonical_key must not be passed to update
        update_payload = mock_update.call_args[0][1]
        assert "canonical_key" not in update_payload
        assert "institution_id" not in update_payload

    @patch("app.routes.institution_entity.find_institution_entity_by_canonical_key")
    @patch("app.services.entity_service.derive_currency_metadata_id_for_address")
    @patch("app.utils.db.db_read")
    @patch.object(institution_entity_service, "create")
    def test_upsert_idempotent_same_payload_twice(
        self,
        mock_create,
        mock_db_read,
        mock_derive_currency,
        mock_find,
        client_with_employee,
    ):
        """Calling upsert twice with identical payload should behave consistently."""
        mock_find.return_value = None  # First call: insert
        created = _make_entity_dto(canonical_key="E2E_INSTITUTION_ENTITY_IDEMPOTENT")
        mock_create.return_value = created
        mock_derive_currency.return_value = uuid4()
        mock_db_read.return_value = {"country_code": "AR"}

        payload = _valid_upsert_payload(canonical_key="E2E_INSTITUTION_ENTITY_IDEMPOTENT")

        resp1 = client_with_employee.put("/api/v1/institution-entities/by-key", json=payload)
        assert resp1.status_code == 200

        # Second call: key now exists — should call update instead of create
        mock_find.return_value = created
        with patch.object(institution_entity_service, "update") as mock_update:
            mock_update.return_value = created
            resp2 = client_with_employee.put("/api/v1/institution-entities/by-key", json=payload)
            assert resp2.status_code == 200
            mock_update.assert_called_once()

    def test_upsert_requires_employee_auth(self):
        """PUT /institution-entities/by-key without employee auth returns 403."""

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
                resp = c.put("/api/v1/institution-entities/by-key", json=payload)
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_employee_user, None)

    def test_upsert_rejects_supplier_role(self):
        """PUT /institution-entities/by-key with a supplier (non-internal) token returns 403."""
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
                resp = c.put("/api/v1/institution-entities/by-key", json=payload)
                assert resp.status_code == 403, (
                    f"Expected 403 for supplier role, got {resp.status_code}. "
                    "get_employee_user must reject non-internal users."
                )
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.routes.institution_entity.find_institution_entity_by_canonical_key")
    @patch("app.services.entity_service.derive_currency_metadata_id_for_address")
    @patch.object(institution_entity_service, "update")
    def test_upsert_institution_id_immutable_on_update(
        self,
        mock_update,
        mock_derive_currency,
        mock_find,
        client_with_employee,
    ):
        """PUT /institution-entities/by-key update path must not pass institution_id to institution_entity_service.update.

        institution_id is immutable after creation.  Even if the caller sends a
        different institution_id in the payload, it must be silently stripped and
        the existing institution_id preserved.
        """
        existing = _make_entity_dto(canonical_key="E2E_INSTITUTION_ENTITY_IMMUTABLE_TEST")
        mock_find.return_value = existing

        updated = _make_entity_dto(canonical_key="E2E_INSTITUTION_ENTITY_IMMUTABLE_TEST")
        mock_update.return_value = updated
        mock_derive_currency.return_value = uuid4()

        payload = _valid_upsert_payload(canonical_key="E2E_INSTITUTION_ENTITY_IMMUTABLE_TEST")
        # Caller sends a different institution_id — must be ignored since it is immutable
        payload["institution_id"] = str(uuid4())

        resp = client_with_employee.put("/api/v1/institution-entities/by-key", json=payload)

        assert resp.status_code == 200
        update_payload = mock_update.call_args[0][1]
        assert "institution_id" not in update_payload, (
            "institution_id must be stripped from the update payload — it is immutable after creation"
        )
