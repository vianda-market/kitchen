"""
Tests for market upsert:
- PUT /markets/by-key: insert path
- PUT /markets/by-key: update path
- PUT /markets/by-key: idempotency (same payload twice)
- PUT /markets/by-key: auth guard (supplier role rejected with 403)
- PUT /markets/by-key: immutable country_code on update
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_employee_user, oauth2_scheme
from app.dependencies.database import get_db

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

    def _override_get_current_user():
        return mock_employee_user

    def _override_oauth2_scheme():
        return "test-token"

    def _override_get_db():
        return mock_db

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_employee_user] = _override_get_employee_user
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_employee_user, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def _make_market_dict(*, canonical_key: str | None = None, market_id=None, country_code: str = "AR") -> dict:
    """Build a minimal mock market dict matching market_service return shape."""
    mid = market_id or uuid4()
    currency_id = uuid4()
    return {
        "market_id": mid,
        "country_name": "Argentina",
        "country_code": country_code,
        "currency_metadata_id": currency_id,
        "currency_code": "ARS",
        "currency_name": "Argentine Peso",
        "credit_value_supplier_local": None,
        "currency_conversion_usd": None,
        "timezone": None,
        "language": "es",
        "phone_dial_code": "+54",
        "phone_local_digits": 10,
        "tax_id_label": None,
        "tax_id_mask": None,
        "tax_id_regex": None,
        "tax_id_example": None,
        "is_archived": False,
        "status": "active",
        "canonical_key": canonical_key,
        "created_date": "2026-01-01T00:00:00Z",
        "modified_date": "2026-01-01T00:00:00Z",
    }


def _valid_upsert_payload(*, canonical_key: str = "E2E_MARKET_AR") -> dict:
    """Minimal valid upsert payload."""
    return {
        "canonical_key": canonical_key,
        "country_code": "AR",
        "currency_metadata_id": str(uuid4()),
        "language": "es",
        "phone_dial_code": "+54",
        "phone_local_digits": 10,
        "status": "active",
    }


class TestMarketUpsertByKey:
    """PUT /api/v1/markets/by-key: insert, update, idempotency, auth, immutability."""

    @patch("app.services.crud_service.find_market_by_canonical_key")
    @patch("app.routes.admin.markets.market_service")
    def test_upsert_inserts_when_key_not_found(
        self,
        mock_market_service,
        mock_find,
        client_with_employee,
        mock_db,
    ):
        """PUT /markets/by-key with a new canonical_key inserts a new market and returns 200."""
        mock_find.return_value = None  # key does not exist yet
        mock_market_service.get_by_country_code.return_value = None  # no existing market for country

        created = _make_market_dict(canonical_key="E2E_MARKET_AR")
        mock_market_service.create.return_value = created
        mock_market_service.get_by_id.return_value = created

        payload = _valid_upsert_payload(canonical_key="E2E_MARKET_AR")

        resp = client_with_employee.put("/api/v1/markets/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "market_id" in data
        mock_market_service.create.assert_called_once()

    @patch("app.services.crud_service.find_market_by_canonical_key")
    @patch("app.routes.admin.markets.market_service")
    def test_upsert_updates_when_key_exists(
        self,
        mock_market_service,
        mock_find,
        client_with_employee,
    ):
        """PUT /markets/by-key with an existing canonical_key updates the market and returns 200."""
        existing = _make_market_dict(canonical_key="E2E_MARKET_AR")
        mock_find.return_value = existing

        updated = _make_market_dict(canonical_key="E2E_MARKET_AR")
        updated["language"] = "en"
        mock_market_service.update.return_value = updated
        mock_market_service.get_by_id.return_value = updated

        payload = _valid_upsert_payload(canonical_key="E2E_MARKET_AR")
        payload["language"] = "en"

        resp = client_with_employee.put("/api/v1/markets/by-key", json=payload)

        assert resp.status_code == 200
        mock_market_service.update.assert_called_once()
        # country_code must not be passed to market_service.update (it is immutable)
        update_call_kwargs = mock_market_service.update.call_args[1]
        assert "country_code" not in update_call_kwargs

    @patch("app.services.crud_service.find_market_by_canonical_key")
    @patch("app.routes.admin.markets.market_service")
    def test_upsert_idempotent_same_payload_twice(
        self,
        mock_market_service,
        mock_find,
        client_with_employee,
    ):
        """Calling upsert twice with identical payload should behave consistently."""
        mock_find.return_value = None  # First call: insert
        mock_market_service.get_by_country_code.return_value = None  # no existing market for country
        created = _make_market_dict(canonical_key="E2E_MARKET_IDEMPOTENT")
        mock_market_service.create.return_value = created
        mock_market_service.get_by_id.return_value = created

        payload = _valid_upsert_payload(canonical_key="E2E_MARKET_IDEMPOTENT")

        resp1 = client_with_employee.put("/api/v1/markets/by-key", json=payload)
        assert resp1.status_code == 200

        # Second call: key now exists — should call update instead of create
        mock_find.return_value = created
        mock_market_service.update.return_value = created
        resp2 = client_with_employee.put("/api/v1/markets/by-key", json=payload)
        assert resp2.status_code == 200
        mock_market_service.update.assert_called_once()

    def test_upsert_requires_employee_auth(self):
        """PUT /markets/by-key without employee auth returns 403."""

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
                resp = c.put("/api/v1/markets/by-key", json=payload)
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_employee_user, None)

    def test_upsert_rejects_supplier_role(self):
        """PUT /markets/by-key with a supplier (non-internal) token returns 403."""
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
                resp = c.put("/api/v1/markets/by-key", json=payload)
                assert resp.status_code == 403, (
                    f"Expected 403 for supplier role, got {resp.status_code}. "
                    "get_employee_user must reject non-internal users."
                )
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.services.crud_service.find_market_by_canonical_key")
    @patch("app.routes.admin.markets.market_service")
    def test_upsert_country_code_immutable_on_update(
        self,
        mock_market_service,
        mock_find,
        client_with_employee,
    ):
        """PUT /markets/by-key update path must not pass country_code to market_service.update.

        country_code is immutable after creation.  Even if the caller sends a
        different country_code in the payload, the existing country_code is preserved
        and the new value is silently ignored on the update path.
        """
        existing = _make_market_dict(canonical_key="E2E_MARKET_IMMUTABLE_TEST", country_code="AR")
        mock_find.return_value = existing

        updated = _make_market_dict(canonical_key="E2E_MARKET_IMMUTABLE_TEST", country_code="AR")
        mock_market_service.update.return_value = updated
        mock_market_service.get_by_id.return_value = updated

        payload = _valid_upsert_payload(canonical_key="E2E_MARKET_IMMUTABLE_TEST")
        # Caller tries to change country_code — must be ignored since it is immutable
        payload["country_code"] = "US"

        resp = client_with_employee.put("/api/v1/markets/by-key", json=payload)

        assert resp.status_code == 200
        update_call_kwargs = mock_market_service.update.call_args[1]
        assert "country_code" not in update_call_kwargs, (
            "country_code must not be passed to market_service.update — it is immutable after creation"
        )
