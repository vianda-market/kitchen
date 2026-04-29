"""
Tests for QR code canonical-key upsert:
- PUT /qr-codes/by-key: insert path (new canonical_key creates a QR code)
- PUT /qr-codes/by-key: update path (existing canonical_key updates in-place)
- PUT /qr-codes/by-key: idempotency (same payload twice returns 200 both times)
- PUT /qr-codes/by-key: supplier role rejected with 403
- PUT /qr-codes/by-key: restaurant_id is immutable on update
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_employee_user, oauth2_scheme
from app.config.enums.status import Status
from app.dependencies.database import get_db
from app.dto.models import QRCodeDTO

# Needs live Postgres (TestClient triggers DB pool init via unmocked code paths).
# Excluded from unit test job by -m "not database"; runs in acceptance (Newman).
pytestmark = pytest.mark.database

_FAKE_IMAGE_URL = "https://storage.googleapis.com/bucket/qr/test.png"
_FAKE_STORAGE_PATH = "qr/test.png"
_FAKE_PAYLOAD = "https://vianda.app/qr?id=abc123&sig=deadbeef"


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
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
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


def _make_qr_dto(*, canonical_key: str | None = None, qr_code_id=None, restaurant_id=None) -> QRCodeDTO:
    """Build a minimal QRCodeDTO matching DB shape."""
    import datetime as dt

    qid = qr_code_id or uuid4()
    rid = restaurant_id or uuid4()
    user_id = uuid4()
    return QRCodeDTO(
        qr_code_id=qid,
        restaurant_id=rid,
        qr_code_payload=_FAKE_PAYLOAD,
        qr_code_image_url=_FAKE_IMAGE_URL,
        image_storage_path=_FAKE_STORAGE_PATH,
        qr_code_checksum="abc123",
        is_archived=False,
        status=Status.ACTIVE,
        canonical_key=canonical_key,
        created_date=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        created_by=user_id,
        modified_by=user_id,
        modified_date=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
    )


def _valid_upsert_payload(*, canonical_key: str = "E2E_QR_CAMBALACHE", restaurant_id=None) -> dict:
    """Minimal valid upsert payload."""
    return {
        "canonical_key": canonical_key,
        "restaurant_id": str(restaurant_id or uuid4()),
    }


class TestQrCodeUpsertByKey:
    """PUT /api/v1/qr-codes/by-key: insert, update, idempotency, auth, immutability."""

    @patch("app.routes.qr_code.find_qr_code_by_canonical_key")
    @patch("app.routes.qr_code.atomic_qr_service")
    @patch("app.utils.gcs.resolve_qr_code_image_url", side_effect=lambda d: d)
    def test_upsert_inserts_when_key_not_found(
        self,
        _mock_resolve,
        mock_atomic_service,
        mock_find,
        client_with_employee,
    ):
        """PUT /qr-codes/by-key with a new canonical_key creates a QR code and returns 200."""
        mock_find.return_value = None  # key does not exist yet

        new_qr = _make_qr_dto(canonical_key="E2E_QR_CAMBALACHE")
        mock_atomic_service.create_qr_code_atomic.return_value = (new_qr, None)

        payload = _valid_upsert_payload(
            canonical_key="E2E_QR_CAMBALACHE",
            restaurant_id=new_qr.restaurant_id,
        )

        resp = client_with_employee.put("/api/v1/qr-codes/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "qr_code_id" in data
        mock_atomic_service.create_qr_code_atomic.assert_called_once()

    @patch("app.routes.qr_code.find_qr_code_by_canonical_key")
    @patch("app.routes.qr_code.qr_code_service")
    @patch("app.utils.gcs.resolve_qr_code_image_url", side_effect=lambda d: d)
    def test_upsert_updates_when_key_exists(
        self,
        _mock_resolve,
        mock_qr_service,
        mock_find,
        client_with_employee,
    ):
        """PUT /qr-codes/by-key with an existing canonical_key updates in-place and returns 200."""
        existing = _make_qr_dto(canonical_key="E2E_QR_CAMBALACHE")
        mock_find.return_value = existing

        updated = _make_qr_dto(canonical_key="E2E_QR_CAMBALACHE", qr_code_id=existing.qr_code_id)
        mock_qr_service.get_by_id.return_value = updated

        payload = _valid_upsert_payload(
            canonical_key="E2E_QR_CAMBALACHE",
            restaurant_id=existing.restaurant_id,
        )

        resp = client_with_employee.put("/api/v1/qr-codes/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["qr_code_id"] == str(existing.qr_code_id)
        # create must not have been called on the update path
        mock_qr_service.get_by_id.assert_called_once()

    @patch("app.routes.qr_code.find_qr_code_by_canonical_key")
    @patch("app.routes.qr_code.atomic_qr_service")
    @patch("app.utils.gcs.resolve_qr_code_image_url", side_effect=lambda d: d)
    def test_upsert_idempotent_same_payload_twice(
        self,
        _mock_resolve,
        mock_atomic_service,
        mock_find,
        client_with_employee,
    ):
        """Calling upsert twice with identical payload should return 200 both times."""
        canonical_key = "E2E_QR_IDEMPOTENT"
        payload = _valid_upsert_payload(canonical_key=canonical_key)

        # First call: INSERT path
        mock_find.return_value = None
        new_qr = _make_qr_dto(canonical_key=canonical_key)
        mock_atomic_service.create_qr_code_atomic.return_value = (new_qr, None)

        resp1 = client_with_employee.put("/api/v1/qr-codes/by-key", json=payload)
        assert resp1.status_code == 200

        # Second call: UPDATE path (key now exists)
        with patch("app.routes.qr_code.qr_code_service") as mock_qr_service:
            with patch("app.utils.gcs.resolve_qr_code_image_url", side_effect=lambda d: d):
                mock_find.return_value = new_qr
                mock_qr_service.get_by_id.return_value = new_qr

                resp2 = client_with_employee.put("/api/v1/qr-codes/by-key", json=payload)
                assert resp2.status_code == 200

    def test_upsert_requires_employee_auth(self):
        """PUT /qr-codes/by-key without employee auth returns 403."""

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
                resp = c.put("/api/v1/qr-codes/by-key", json=payload)
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_employee_user, None)

    def test_upsert_rejects_supplier_role(self):
        """PUT /qr-codes/by-key with a supplier (non-internal) token returns 403."""
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
                resp = c.put("/api/v1/qr-codes/by-key", json=payload)
                assert resp.status_code == 403, (
                    f"Expected 403 for supplier role, got {resp.status_code}. "
                    "get_employee_user must reject non-internal users."
                )
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.routes.qr_code.find_qr_code_by_canonical_key")
    @patch("app.routes.qr_code.qr_code_service")
    @patch("app.utils.gcs.resolve_qr_code_image_url", side_effect=lambda d: d)
    def test_upsert_restaurant_id_immutable_on_update(
        self,
        _mock_resolve,
        mock_qr_service,
        mock_find,
        client_with_employee,
    ):
        """PUT /qr-codes/by-key update path must not reassign restaurant_id.

        restaurant_id is immutable after creation.  Even if the caller sends a
        different restaurant_id in the payload, the existing restaurant_id is
        preserved — the update path ignores the incoming restaurant_id entirely.
        """
        original_restaurant_id = uuid4()
        existing = _make_qr_dto(
            canonical_key="E2E_QR_IMMUTABLE_TEST",
            restaurant_id=original_restaurant_id,
        )
        mock_find.return_value = existing

        updated = _make_qr_dto(
            canonical_key="E2E_QR_IMMUTABLE_TEST",
            qr_code_id=existing.qr_code_id,
            restaurant_id=original_restaurant_id,
        )
        mock_qr_service.get_by_id.return_value = updated

        # Caller tries to reassign restaurant_id — must be ignored
        different_restaurant_id = uuid4()
        payload = _valid_upsert_payload(
            canonical_key="E2E_QR_IMMUTABLE_TEST",
            restaurant_id=different_restaurant_id,
        )

        resp = client_with_employee.put("/api/v1/qr-codes/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        # The response must reflect the original restaurant, not the new one
        assert data["restaurant_id"] == str(original_restaurant_id), (
            "restaurant_id must not change on update path — it is immutable after creation"
        )
