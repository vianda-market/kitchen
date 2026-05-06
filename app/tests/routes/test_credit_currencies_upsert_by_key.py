"""
Tests for credit currency upsert:
- PUT /credit-currencies/by-key: insert path
- PUT /credit-currencies/by-key: update path (existing canonical_key)
- PUT /credit-currencies/by-key: idempotency (same payload twice)
- PUT /credit-currencies/by-key: supplier-role 403
- PUT /credit-currencies/by-key: currency_code immutable on update
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_employee_user, get_resolved_locale, oauth2_scheme
from app.config import Status
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

    def _override_get_resolved_locale():
        return "en"

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_employee_user] = _override_get_employee_user
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_resolved_locale] = _override_get_resolved_locale
    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_employee_user, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_resolved_locale, None)
        app.dependency_overrides.pop(get_db, None)


def _make_currency_dto(*, canonical_key: str | None = None, currency_metadata_id=None, currency_code: str = "ARS"):
    """Build a minimal mock CreditCurrencyDTO."""
    from datetime import UTC, datetime

    from app.dto.models import CreditCurrencyDTO

    mid = currency_metadata_id or uuid4()
    return CreditCurrencyDTO(
        currency_metadata_id=mid,
        currency_code=currency_code,
        credit_value_supplier_local=Decimal("1400"),
        currency_conversion_usd=Decimal("0.001"),
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime(2026, 1, 1, tzinfo=UTC),
        modified_by=uuid4(),
        modified_date=datetime(2026, 1, 1, tzinfo=UTC),
        canonical_key=canonical_key,
    )


def _make_currency_response_dict(
    *, canonical_key: str | None = None, currency_metadata_id=None, currency_code: str = "ARS"
) -> dict:
    """Build a minimal mock credit currency response dict (CRUDService.get_by_id shape)."""
    from datetime import UTC, datetime

    mid = currency_metadata_id or uuid4()

    return {
        "currency_metadata_id": mid,
        "currency_name": None,
        "currency_code": currency_code,
        "credit_value_supplier_local": 1400.0,
        "currency_conversion_usd": 0.001,
        "is_archived": False,
        "status": "active",
        "created_date": datetime(2026, 1, 1, tzinfo=UTC),
        "modified_date": datetime(2026, 1, 1, tzinfo=UTC),
        "canonical_key": canonical_key,
    }


def _valid_upsert_payload(*, canonical_key: str = "E2E_CURRENCY_ARS") -> dict:
    """Minimal valid upsert payload."""
    return {
        "canonical_key": canonical_key,
        "currency_name": "Argentine Peso",
        "credit_value_supplier_local": 1400,
    }


class TestCreditCurrencyUpsertByKey:
    """PUT /api/v1/credit-currencies/by-key: insert, update, idempotency, auth, immutability."""

    def test_upsert_inserts_when_key_not_found(self, client_with_employee):
        """PUT /credit-currencies/by-key with a new canonical_key inserts a new currency and returns 200."""
        from app.services.crud_service import credit_currency_service

        created_id = uuid4()
        response_dict = _make_currency_response_dict(canonical_key="E2E_CURRENCY_ARS", currency_metadata_id=created_id)

        with (
            patch("app.services.crud_service.find_credit_currency_by_canonical_key", return_value=None),
            patch("app.config.supported_currencies.get_currency_code_by_name", return_value="ARS"),
            patch("app.services.cron.currency_refresh.fetch_usd_rate_for_currency", return_value=(0.001, None)),
            patch("app.utils.db.db_read", return_value=None),
            patch.object(
                credit_currency_service,
                "create",
                return_value=_make_currency_dto(canonical_key="E2E_CURRENCY_ARS", currency_metadata_id=created_id),
            ) as mock_create,
            patch.object(credit_currency_service, "get_by_id", return_value=response_dict),
        ):
            payload = _valid_upsert_payload(canonical_key="E2E_CURRENCY_ARS")
            resp = client_with_employee.put("/api/v1/credit-currencies/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "currency_metadata_id" in data
        assert data["currency_code"] == "ARS"
        mock_create.assert_called_once()

    def test_upsert_updates_when_key_exists(self, client_with_employee):
        """PUT /credit-currencies/by-key with an existing canonical_key updates the currency and returns 200."""
        from app.services.crud_service import credit_currency_service

        existing_dto = _make_currency_dto(canonical_key="E2E_CURRENCY_ARS")
        updated_response = _make_currency_response_dict(
            canonical_key="E2E_CURRENCY_ARS",
            currency_metadata_id=existing_dto.currency_metadata_id,
        )

        with (
            patch("app.services.crud_service.find_credit_currency_by_canonical_key", return_value=existing_dto),
            patch("app.config.supported_currencies.get_currency_code_by_name", return_value="ARS"),
            patch.object(credit_currency_service, "create") as mock_create,
            patch.object(credit_currency_service, "get_by_id", return_value=updated_response),
        ):
            payload = _valid_upsert_payload(canonical_key="E2E_CURRENCY_ARS")
            payload["credit_value_supplier_local"] = 1600
            resp = client_with_employee.put("/api/v1/credit-currencies/by-key", json=payload)

        assert resp.status_code == 200
        mock_create.assert_not_called()

    def test_upsert_idempotent_same_payload_twice(self, client_with_employee):
        """Calling upsert twice with identical payload should behave consistently (HTTP 200 both times)."""
        from app.services.crud_service import credit_currency_service

        created_id = uuid4()
        response_dict = _make_currency_response_dict(
            canonical_key="E2E_CURRENCY_IDEMPOTENT", currency_metadata_id=created_id
        )
        payload = _valid_upsert_payload(canonical_key="E2E_CURRENCY_IDEMPOTENT")

        # First call: insert path
        with (
            patch("app.services.crud_service.find_credit_currency_by_canonical_key", return_value=None),
            patch("app.config.supported_currencies.get_currency_code_by_name", return_value="ARS"),
            patch("app.services.cron.currency_refresh.fetch_usd_rate_for_currency", return_value=(0.001, None)),
            patch("app.utils.db.db_read", return_value=None),
            patch.object(
                credit_currency_service,
                "create",
                return_value=_make_currency_dto(
                    canonical_key="E2E_CURRENCY_IDEMPOTENT", currency_metadata_id=created_id
                ),
            ),
            patch.object(credit_currency_service, "get_by_id", return_value=response_dict),
        ):
            resp1 = client_with_employee.put("/api/v1/credit-currencies/by-key", json=payload)
        assert resp1.status_code == 200

        # Second call: update path (key now exists)
        existing_dto = _make_currency_dto(canonical_key="E2E_CURRENCY_IDEMPOTENT", currency_metadata_id=created_id)
        with (
            patch("app.services.crud_service.find_credit_currency_by_canonical_key", return_value=existing_dto),
            patch("app.config.supported_currencies.get_currency_code_by_name", return_value="ARS"),
            patch.object(credit_currency_service, "create") as mock_create,
            patch.object(credit_currency_service, "get_by_id", return_value=response_dict),
        ):
            resp2 = client_with_employee.put("/api/v1/credit-currencies/by-key", json=payload)
        assert resp2.status_code == 200
        mock_create.assert_not_called()

    def test_upsert_rejects_supplier_role(self):
        """PUT /credit-currencies/by-key with a supplier (non-internal) token returns 403."""
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
                resp = c.put("/api/v1/credit-currencies/by-key", json=payload)
                assert resp.status_code == 403, (
                    f"Expected 403 for supplier role, got {resp.status_code}. "
                    "get_employee_user must reject non-internal users."
                )
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_current_user, None)

    def test_upsert_currency_code_immutable_on_update(self, client_with_employee, mock_db):
        """PUT /credit-currencies/by-key update path must NOT update currency_code.

        currency_code is the ISO 4217 natural unique key and is immutable after
        creation.  The update path only writes credit_value_supplier_local — it
        must not attempt to change currency_code.
        """
        from app.services.crud_service import credit_currency_service

        existing_dto = _make_currency_dto(canonical_key="E2E_CURRENCY_IMMUTABLE", currency_code="ARS")
        response_dict = _make_currency_response_dict(
            canonical_key="E2E_CURRENCY_IMMUTABLE",
            currency_metadata_id=existing_dto.currency_metadata_id,
            currency_code="ARS",
        )

        # Capture SQL executed via the cursor
        executed_sql: list[str] = []
        cursor_mock = mock_db.cursor.return_value

        def capture_execute(sql, params=None):
            executed_sql.append(sql)

        cursor_mock.execute.side_effect = capture_execute

        with (
            patch("app.services.crud_service.find_credit_currency_by_canonical_key", return_value=existing_dto),
            patch("app.config.supported_currencies.get_currency_code_by_name", return_value="ARS"),
            patch.object(credit_currency_service, "get_by_id", return_value=response_dict),
        ):
            payload = _valid_upsert_payload(canonical_key="E2E_CURRENCY_IMMUTABLE")
            resp = client_with_employee.put("/api/v1/credit-currencies/by-key", json=payload)

        assert resp.status_code == 200

        # Verify that the UPDATE statement on the update path does NOT include currency_code.
        for sql in executed_sql:
            if "UPDATE core.currency_metadata" in sql:
                assert "currency_code" not in sql.lower(), (
                    "currency_code must not appear in the UPDATE SQL on the update path — "
                    "it is immutable after creation"
                )
