"""
Tests for plate upsert:
- PUT /plates/by-key: insert, update, and idempotency.
- PUT /plates/by-key: auth guard (non-employee returns 403).
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_employee_user, oauth2_scheme
from app.services.crud_service import plate_service

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


def _make_plate_dto(*, canonical_key=None):
    """Build a minimal mock plate DTO."""
    m = MagicMock()
    m.plate_id = uuid4()
    m.product_id = uuid4()
    m.restaurant_id = uuid4()
    m.price = Decimal("20000.00")
    m.credit = 8
    m.expected_payout_local_currency = Decimal("15000.00")
    m.delivery_time_minutes = 15
    m.is_archived = False
    m.status = "active"
    m.canonical_key = canonical_key
    m.created_date = "2026-01-01T00:00:00Z"
    m.modified_date = "2026-01-01T00:00:00Z"
    m.modified_by = uuid4()
    return m


def _valid_upsert_payload(*, canonical_key="TEST_RESTAURANT_PLATE_BONDIOLA"):
    """Minimal valid upsert payload."""
    return {
        "canonical_key": canonical_key,
        "product_id": str(uuid4()),
        "restaurant_id": str(uuid4()),
        "price": "20000.00",
        "credit": 8,
        "delivery_time_minutes": 15,
    }


class TestPlateUpsertByKey:
    """PUT /api/v1/plates/by-key: insert, update, idempotency, auth."""

    @patch("app.services.crud_service.find_plate_by_canonical_key")
    @patch.object(plate_service, "create")
    def test_upsert_inserts_when_key_not_found(self, mock_create, mock_find, client_with_employee):
        """PUT /plates/by-key with a new canonical_key inserts a new plate and returns 200."""
        mock_find.return_value = None  # key does not exist yet
        created = _make_plate_dto(canonical_key="TEST_RESTAURANT_PLATE_BONDIOLA")
        mock_create.return_value = created

        payload = _valid_upsert_payload(canonical_key="TEST_RESTAURANT_PLATE_BONDIOLA")
        resp = client_with_employee.put("/api/v1/plates/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "plate_id" in data
        mock_create.assert_called_once()

    @patch("app.services.crud_service.find_plate_by_canonical_key")
    @patch.object(plate_service, "update")
    def test_upsert_updates_when_key_exists(self, mock_update, mock_find, client_with_employee):
        """PUT /plates/by-key with an existing canonical_key updates the plate and returns 200."""
        existing = _make_plate_dto(canonical_key="TEST_RESTAURANT_PLATE_BONDIOLA")
        mock_find.return_value = existing
        updated = _make_plate_dto(canonical_key="TEST_RESTAURANT_PLATE_BONDIOLA")
        updated.price = Decimal("25000.00")
        mock_update.return_value = updated

        payload = _valid_upsert_payload(canonical_key="TEST_RESTAURANT_PLATE_BONDIOLA")
        payload["price"] = "25000.00"
        resp = client_with_employee.put("/api/v1/plates/by-key", json=payload)

        assert resp.status_code == 200
        mock_update.assert_called_once()
        # canonical_key must not be passed to plate_service.update (update strips it)
        update_payload = mock_update.call_args[0][1]
        assert "canonical_key" not in update_payload

    @patch("app.services.crud_service.find_plate_by_canonical_key")
    @patch.object(plate_service, "create")
    def test_upsert_idempotent_same_payload_twice(self, mock_create, mock_find, client_with_employee):
        """Calling upsert twice with identical payload should behave consistently."""
        # First call: insert
        mock_find.return_value = None
        created = _make_plate_dto(canonical_key="TEST_RESTAURANT_PLATE_IDEMPOTENT")
        mock_create.return_value = created

        payload = _valid_upsert_payload(canonical_key="TEST_RESTAURANT_PLATE_IDEMPOTENT")
        resp1 = client_with_employee.put("/api/v1/plates/by-key", json=payload)
        assert resp1.status_code == 200

        # Second call: key now exists — should call update instead of create
        mock_find.return_value = created  # simulate the plate now existing
        with patch.object(plate_service, "update") as mock_update:
            mock_update.return_value = created
            resp2 = client_with_employee.put("/api/v1/plates/by-key", json=payload)
            assert resp2.status_code == 200
            mock_update.assert_called_once()

    def test_upsert_requires_employee_auth(self):
        """PUT /plates/by-key without employee auth returns 403."""

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
                resp = c.put("/api/v1/plates/by-key", json=payload)
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_employee_user, None)
