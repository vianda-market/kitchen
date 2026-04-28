"""
Tests for product upsert:
- PUT /products/by-key: insert path
- PUT /products/by-key: update path
- PUT /products/by-key: idempotency (same payload twice)
- PUT /products/by-key: auth guard (supplier role rejected with 403)
- PUT /products/by-key: immutable institution_id on update
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_employee_user, oauth2_scheme
from app.dependencies.database import get_db
from app.services.crud_service import product_service

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


def _make_product_dto(*, canonical_key=None, institution_id=None):
    """Build a minimal mock product DTO whose model_dump returns a valid ProductResponseSchema-compatible dict."""
    product_id = uuid4()
    iid = institution_id or uuid4()
    data = {
        "product_id": product_id,
        "institution_id": iid,
        "name": "Big Burguer",
        "name_i18n": None,
        "ingredients": None,
        "ingredients_i18n": None,
        "description": None,
        "description_i18n": None,
        "dietary": None,
        "is_archived": False,
        "status": "active",
        "image_url": "http://localhost:8000/static/placeholders/product_default.png",
        "image_storage_path": "static/placeholders/product_default.png",
        "image_thumbnail_url": "http://localhost:8000/static/placeholders/product_default.png",
        "image_thumbnail_storage_path": "static/placeholders/product_default.png",
        "image_checksum": "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
        "canonical_key": canonical_key,
        "created_date": "2026-01-01T00:00:00",
        "modified_date": "2026-01-01T00:00:00",
        "modified_by": str(uuid4()),
    }
    m = MagicMock()
    m.product_id = product_id
    m.institution_id = iid
    m.name = data["name"]
    m.canonical_key = canonical_key
    # model_dump must return the plain dict so ProductResponseSchema(**dict) works
    m.model_dump = MagicMock(return_value=data)
    return m


def _valid_upsert_payload(*, canonical_key="E2E_PRODUCT_BIG_BURGUER", institution_id=None):
    """Minimal valid upsert payload."""
    return {
        "canonical_key": canonical_key,
        "institution_id": str(institution_id or uuid4()),
        "name": "Big Burguer",
    }


class TestProductUpsertByKey:
    """PUT /api/v1/products/by-key: insert, update, idempotency, auth, immutability."""

    @patch("app.services.crud_service.find_product_by_canonical_key")
    @patch.object(product_service, "create")
    def test_upsert_inserts_when_key_not_found(self, mock_create, mock_find, client_with_employee):
        """PUT /products/by-key with a new canonical_key inserts a new product and returns 200."""
        mock_find.return_value = None  # key does not exist yet
        created = _make_product_dto(canonical_key="E2E_PRODUCT_BIG_BURGUER")
        mock_create.return_value = created

        payload = _valid_upsert_payload(canonical_key="E2E_PRODUCT_BIG_BURGUER")
        resp = client_with_employee.put("/api/v1/products/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "product_id" in data
        mock_create.assert_called_once()

    @patch("app.services.crud_service.find_product_by_canonical_key")
    @patch.object(product_service, "update")
    def test_upsert_updates_when_key_exists(self, mock_update, mock_find, client_with_employee):
        """PUT /products/by-key with an existing canonical_key updates the product and returns 200."""
        existing = _make_product_dto(canonical_key="E2E_PRODUCT_BIG_BURGUER")
        mock_find.return_value = existing
        updated = _make_product_dto(canonical_key="E2E_PRODUCT_BIG_BURGUER")
        updated.name = "Big Burguer Updated"
        mock_update.return_value = updated

        payload = _valid_upsert_payload(canonical_key="E2E_PRODUCT_BIG_BURGUER")
        payload["name"] = "Big Burguer Updated"
        resp = client_with_employee.put("/api/v1/products/by-key", json=payload)

        assert resp.status_code == 200
        mock_update.assert_called_once()
        # canonical_key and institution_id must not be passed to product_service.update
        update_payload = mock_update.call_args[0][1]
        assert "canonical_key" not in update_payload
        assert "institution_id" not in update_payload

    @patch("app.services.crud_service.find_product_by_canonical_key")
    @patch.object(product_service, "create")
    def test_upsert_idempotent_same_payload_twice(self, mock_create, mock_find, client_with_employee):
        """Calling upsert twice with identical payload should behave consistently."""
        # First call: insert
        mock_find.return_value = None
        created = _make_product_dto(canonical_key="E2E_PRODUCT_IDEMPOTENT")
        mock_create.return_value = created

        payload = _valid_upsert_payload(canonical_key="E2E_PRODUCT_IDEMPOTENT")
        resp1 = client_with_employee.put("/api/v1/products/by-key", json=payload)
        assert resp1.status_code == 200

        # Second call: key now exists — should call update instead of create
        mock_find.return_value = created
        with patch.object(product_service, "update") as mock_update:
            mock_update.return_value = created
            resp2 = client_with_employee.put("/api/v1/products/by-key", json=payload)
            assert resp2.status_code == 200
            mock_update.assert_called_once()

    def test_upsert_requires_employee_auth(self):
        """PUT /products/by-key without employee auth returns 403."""

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
                resp = c.put("/api/v1/products/by-key", json=payload)
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_employee_user, None)

    def test_upsert_rejects_supplier_role(self):
        """PUT /products/by-key with a supplier (non-internal) token returns 403.

        The Postman E2E collection creates the product during the Supplier Menu
        Setup phase after a supplier login. get_employee_user must reject that token.
        This regression test ensures the auth guard is in place before Newman runs.
        """
        supplier_user = {
            "user_id": str(uuid4()),
            "role_type": "supplier",  # Not "internal" — must be rejected
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
                resp = c.put("/api/v1/products/by-key", json=payload)
                assert resp.status_code == 403, (
                    f"Expected 403 for supplier role, got {resp.status_code}. "
                    "get_employee_user must reject non-internal users."
                )
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.services.crud_service.find_product_by_canonical_key")
    @patch.object(product_service, "update")
    def test_upsert_institution_id_immutable_on_update(self, mock_update, mock_find, client_with_employee):
        """PUT /products/by-key update path must not pass institution_id to product_service.update.

        institution_id is immutable after creation.  Even if the caller sends a
        different institution_id in the payload, the existing value is preserved
        and the new value is silently ignored on the update path.
        """
        original_institution_id = uuid4()
        existing = _make_product_dto(
            canonical_key="E2E_PRODUCT_IMMUTABLE_TEST",
            institution_id=original_institution_id,
        )
        mock_find.return_value = existing
        updated = _make_product_dto(
            canonical_key="E2E_PRODUCT_IMMUTABLE_TEST",
            institution_id=original_institution_id,
        )
        mock_update.return_value = updated

        payload = _valid_upsert_payload(canonical_key="E2E_PRODUCT_IMMUTABLE_TEST")
        # Caller tries to change institution_id — must be ignored since it is immutable
        payload["institution_id"] = str(uuid4())

        resp = client_with_employee.put("/api/v1/products/by-key", json=payload)

        assert resp.status_code == 200
        update_payload = mock_update.call_args[0][1]
        assert "institution_id" not in update_payload, (
            "institution_id must not be passed to product_service.update — it is immutable after creation"
        )
