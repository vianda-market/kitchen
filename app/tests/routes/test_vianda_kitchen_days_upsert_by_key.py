"""
Tests for vianda kitchen day upsert by canonical key:
- PUT /vianda-kitchen-days/by-key: insert path
- PUT /vianda-kitchen-days/by-key: update path
- PUT /vianda-kitchen-days/by-key: idempotency (same payload twice)
- PUT /vianda-kitchen-days/by-key: supplier-role 403
- PUT /vianda-kitchen-days/by-key: immutable vianda_id and kitchen_day on update
"""

from datetime import UTC
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
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchone.return_value = {"vianda_kitchen_day_id": uuid4()}
    conn.cursor.return_value = cursor
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


def _make_pkd_dto(*, vianda_id=None, kitchen_day: str = "monday", canonical_key: str | None = None):
    """Build a minimal mock ViandaKitchenDaysDTO-like object."""
    from datetime import datetime

    from app.config.enums.status import Status
    from app.dto.models import ViandaKitchenDaysDTO

    return ViandaKitchenDaysDTO(
        vianda_kitchen_day_id=uuid4(),
        vianda_id=vianda_id or uuid4(),
        kitchen_day=kitchen_day,
        status=Status.ACTIVE,
        is_archived=False,
        canonical_key=canonical_key,
        created_date=datetime.now(UTC),
        created_by=None,
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


def _make_vianda_dto(vianda_id=None):
    """Build a minimal mock ViandaDTO-like object."""
    from datetime import datetime
    from decimal import Decimal

    from app.config.enums.status import Status
    from app.dto.models import ViandaDTO

    pid = vianda_id or uuid4()
    return ViandaDTO(
        vianda_id=pid,
        product_id=uuid4(),
        restaurant_id=uuid4(),
        price=Decimal("15000"),
        credit=Decimal("8"),
        expected_payout_local_currency=Decimal("0"),
        delivery_time_minutes=15,
        status=Status.ACTIVE,
        is_archived=False,
        created_date=datetime.now(UTC),
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


def _valid_upsert_payload(
    *,
    canonical_key: str = "E2E_PKD_CAMBALACHE_BONDIOLA_MONDAY",
    vianda_id=None,
    kitchen_day: str = "monday",
) -> dict:
    """Minimal valid upsert payload."""
    return {
        "canonical_key": canonical_key,
        "vianda_id": str(vianda_id or uuid4()),
        "kitchen_day": kitchen_day,
        "status": "active",
    }


class TestViandaKitchenDayUpsertByKey:
    """PUT /api/v1/vianda-kitchen-days/by-key: insert, update, idempotency, auth, immutability."""

    @patch("app.routes.vianda_kitchen_days.find_vianda_kitchen_day_by_canonical_key")
    @patch("app.routes.vianda_kitchen_days.vianda_kitchen_days_service")
    @patch("app.routes.vianda_kitchen_days.vianda_service")
    @patch("app.routes.vianda_kitchen_days._check_unique_constraint")
    def test_upsert_inserts_when_key_not_found(
        self,
        mock_unique_check,
        mock_vianda_service,
        mock_pkd_service,
        mock_find,
        client_with_employee,
    ):
        """PUT /vianda-kitchen-days/by-key with a new canonical_key inserts a new row and returns 200."""
        vianda_id = uuid4()
        mock_find.return_value = None  # key does not exist yet
        mock_unique_check.return_value = False  # slot is free
        mock_vianda_service.get_by_id.return_value = _make_vianda_dto(vianda_id=vianda_id)

        created_dto = _make_pkd_dto(
            vianda_id=vianda_id,
            kitchen_day="monday",
            canonical_key="E2E_PKD_CAMBALACHE_BONDIOLA_MONDAY",
        )
        mock_pkd_service.get_by_id.return_value = created_dto

        payload = _valid_upsert_payload(
            canonical_key="E2E_PKD_CAMBALACHE_BONDIOLA_MONDAY",
            vianda_id=vianda_id,
            kitchen_day="monday",
        )

        resp = client_with_employee.put("/api/v1/vianda-kitchen-days/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "vianda_kitchen_day_id" in data
        assert data["kitchen_day"] == "monday"

    @patch("app.routes.vianda_kitchen_days.find_vianda_kitchen_day_by_canonical_key")
    @patch("app.routes.vianda_kitchen_days.vianda_kitchen_days_service")
    def test_upsert_updates_when_key_exists(
        self,
        mock_pkd_service,
        mock_find,
        client_with_employee,
    ):
        """PUT /vianda-kitchen-days/by-key with an existing canonical_key updates the row and returns 200."""
        vianda_id = uuid4()
        existing_dto = _make_pkd_dto(
            vianda_id=vianda_id,
            kitchen_day="monday",
            canonical_key="E2E_PKD_CAMBALACHE_BONDIOLA_MONDAY",
        )
        mock_find.return_value = existing_dto

        updated_dto = _make_pkd_dto(
            vianda_id=vianda_id,
            kitchen_day="monday",
            canonical_key="E2E_PKD_CAMBALACHE_BONDIOLA_MONDAY",
        )
        mock_pkd_service.get_by_id.return_value = updated_dto

        payload = _valid_upsert_payload(
            canonical_key="E2E_PKD_CAMBALACHE_BONDIOLA_MONDAY",
            vianda_id=vianda_id,
            kitchen_day="monday",
        )

        resp = client_with_employee.put("/api/v1/vianda-kitchen-days/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "vianda_kitchen_day_id" in data

    @patch("app.routes.vianda_kitchen_days.find_vianda_kitchen_day_by_canonical_key")
    @patch("app.routes.vianda_kitchen_days.vianda_kitchen_days_service")
    @patch("app.routes.vianda_kitchen_days.vianda_service")
    @patch("app.routes.vianda_kitchen_days._check_unique_constraint")
    def test_upsert_idempotent_same_payload_twice(
        self,
        mock_unique_check,
        mock_vianda_service,
        mock_pkd_service,
        mock_find,
        client_with_employee,
    ):
        """Calling upsert twice with identical payload behaves consistently."""
        vianda_id = uuid4()
        mock_unique_check.return_value = False
        mock_vianda_service.get_by_id.return_value = _make_vianda_dto(vianda_id=vianda_id)

        dto = _make_pkd_dto(
            vianda_id=vianda_id,
            kitchen_day="tuesday",
            canonical_key="E2E_PKD_IDEMPOTENT_TUESDAY",
        )
        mock_pkd_service.get_by_id.return_value = dto

        payload = _valid_upsert_payload(
            canonical_key="E2E_PKD_IDEMPOTENT_TUESDAY",
            vianda_id=vianda_id,
            kitchen_day="tuesday",
        )

        # First call: insert
        mock_find.return_value = None
        resp1 = client_with_employee.put("/api/v1/vianda-kitchen-days/by-key", json=payload)
        assert resp1.status_code == 200

        # Second call: key exists — should update
        mock_find.return_value = dto
        mock_pkd_service.get_by_id.return_value = dto
        resp2 = client_with_employee.put("/api/v1/vianda-kitchen-days/by-key", json=payload)
        assert resp2.status_code == 200

    def test_upsert_rejects_supplier_role(self):
        """PUT /vianda-kitchen-days/by-key with a supplier (non-internal) token returns 403."""
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
                resp = c.put("/api/v1/vianda-kitchen-days/by-key", json=payload)
                assert resp.status_code == 403, (
                    f"Expected 403 for supplier role, got {resp.status_code}. "
                    "get_employee_user must reject non-internal users."
                )
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.routes.vianda_kitchen_days.find_vianda_kitchen_day_by_canonical_key")
    @patch("app.routes.vianda_kitchen_days.vianda_kitchen_days_service")
    def test_upsert_vianda_id_and_kitchen_day_immutable_on_update(
        self,
        mock_pkd_service,
        mock_find,
        client_with_employee,
    ):
        """UPDATE path must not change vianda_id or kitchen_day.

        The existing vianda_id and kitchen_day on the found row are preserved
        regardless of what the caller sends — the DB UPDATE only touches status
        and canonical_key.
        """
        original_vianda_id = uuid4()
        different_vianda_id = uuid4()
        existing_dto = _make_pkd_dto(
            vianda_id=original_vianda_id,
            kitchen_day="wednesday",
            canonical_key="E2E_PKD_IMMUTABLE_TEST",
        )
        mock_find.return_value = existing_dto

        updated_dto = _make_pkd_dto(
            vianda_id=original_vianda_id,  # unchanged
            kitchen_day="wednesday",  # unchanged
            canonical_key="E2E_PKD_IMMUTABLE_TEST",
        )
        mock_pkd_service.get_by_id.return_value = updated_dto

        payload = _valid_upsert_payload(
            canonical_key="E2E_PKD_IMMUTABLE_TEST",
            # Caller tries to supply a different vianda_id — must be ignored on UPDATE
            vianda_id=different_vianda_id,
            kitchen_day="friday",  # Also trying to change kitchen_day — must be ignored
        )

        resp = client_with_employee.put("/api/v1/vianda-kitchen-days/by-key", json=payload)

        # Response must still be 200 — the immutability is silent (not a 400)
        assert resp.status_code == 200
        data = resp.json()
        # The returned row retains the original vianda_id and kitchen_day
        assert str(data["vianda_id"]) == str(original_vianda_id)
        assert data["kitchen_day"] == "wednesday"
