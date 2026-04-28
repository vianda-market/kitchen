"""
Tests for restaurant holiday upsert:
- PUT /restaurant-holidays/by-key: insert path
- PUT /restaurant-holidays/by-key: update path
- PUT /restaurant-holidays/by-key: idempotency (same payload twice)
- PUT /restaurant-holidays/by-key: supplier-role 403
- PUT /restaurant-holidays/by-key: immutable restaurant_id + holiday_date on update
"""

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_employee_user, oauth2_scheme
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


def _make_holiday_dto(*, canonical_key: str | None = None, holiday_id=None, restaurant_id=None):
    """Build a minimal mock RestaurantHolidaysDTO-like object."""
    from app.dto.models import RestaurantHolidaysDTO

    hid = holiday_id or uuid4()
    rid = restaurant_id or uuid4()
    now_dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    return RestaurantHolidaysDTO(
        holiday_id=hid,
        restaurant_id=rid,
        country_code="AR",
        holiday_date=date(2026, 7, 9),
        holiday_name="Restaurant Maintenance Day",
        is_recurring=False,
        recurring_month=None,
        recurring_day=None,
        status=Status.ACTIVE,
        is_archived=False,
        source="manual",
        canonical_key=canonical_key,
        created_date=now_dt,
        created_by=None,
        modified_by=uuid4(),
        modified_date=now_dt,
    )


def _valid_upsert_payload(*, canonical_key: str = "E2E_HOLIDAY_CAMBALACHE_MAINTENANCE") -> dict:
    """Minimal valid upsert payload."""
    return {
        "canonical_key": canonical_key,
        "restaurant_id": str(uuid4()),
        "holiday_date": "2026-07-09",
        "holiday_name": "Restaurant Maintenance Day",
        "is_recurring": False,
        "status": "active",
    }


class TestRestaurantHolidayUpsertByKey:
    """PUT /api/v1/restaurant-holidays/by-key: insert, update, idempotency, auth, immutability."""

    @patch("app.routes.restaurant_holidays.find_restaurant_holiday_by_canonical_key")
    @patch("app.routes.restaurant_holidays.restaurant_service")
    @patch("app.routes.restaurant_holidays.restaurant_holidays_service")
    @patch("app.routes.restaurant_holidays._derive_restaurant_country_code")
    def test_upsert_inserts_when_key_not_found(
        self,
        mock_derive_cc,
        mock_holidays_service,
        mock_restaurant_service,
        mock_find,
        client_with_employee,
    ):
        """PUT /restaurant-holidays/by-key with a new canonical_key inserts a holiday and returns 200."""
        mock_find.return_value = None  # key does not exist yet
        mock_derive_cc.return_value = "AR"

        restaurant_id = uuid4()
        mock_restaurant_service.get_by_id.return_value = MagicMock()

        created = _make_holiday_dto(canonical_key="E2E_HOLIDAY_CAMBALACHE_MAINTENANCE", restaurant_id=restaurant_id)
        mock_holidays_service.create.return_value = created

        payload = _valid_upsert_payload(canonical_key="E2E_HOLIDAY_CAMBALACHE_MAINTENANCE")
        payload["restaurant_id"] = str(restaurant_id)

        resp = client_with_employee.put("/api/v1/restaurant-holidays/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "holiday_id" in data
        mock_holidays_service.create.assert_called_once()

    @patch("app.routes.restaurant_holidays.find_restaurant_holiday_by_canonical_key")
    @patch("app.routes.restaurant_holidays.restaurant_holidays_service")
    def test_upsert_updates_when_key_exists(
        self,
        mock_holidays_service,
        mock_find,
        client_with_employee,
        mock_db,
    ):
        """PUT /restaurant-holidays/by-key with an existing canonical_key updates and returns 200."""
        existing = _make_holiday_dto(canonical_key="E2E_HOLIDAY_CAMBALACHE_MAINTENANCE")
        mock_find.return_value = existing

        updated = _make_holiday_dto(
            canonical_key="E2E_HOLIDAY_CAMBALACHE_MAINTENANCE",
            holiday_id=existing.holiday_id,
            restaurant_id=existing.restaurant_id,
        )
        mock_holidays_service.update.return_value = updated
        mock_holidays_service.get_by_id.return_value = updated

        payload = _valid_upsert_payload(canonical_key="E2E_HOLIDAY_CAMBALACHE_MAINTENANCE")
        payload["restaurant_id"] = str(existing.restaurant_id)

        resp = client_with_employee.put("/api/v1/restaurant-holidays/by-key", json=payload)

        assert resp.status_code == 200
        mock_holidays_service.update.assert_called_once()

    @patch("app.routes.restaurant_holidays.find_restaurant_holiday_by_canonical_key")
    @patch("app.routes.restaurant_holidays.restaurant_service")
    @patch("app.routes.restaurant_holidays.restaurant_holidays_service")
    @patch("app.routes.restaurant_holidays._derive_restaurant_country_code")
    def test_upsert_idempotent_same_payload_twice(
        self,
        mock_derive_cc,
        mock_holidays_service,
        mock_restaurant_service,
        mock_find,
        client_with_employee,
    ):
        """Calling upsert twice with identical payload should behave consistently."""
        mock_find.return_value = None  # First call: insert
        mock_derive_cc.return_value = "AR"
        mock_restaurant_service.get_by_id.return_value = MagicMock()

        restaurant_id = uuid4()
        created = _make_holiday_dto(canonical_key="E2E_HOLIDAY_IDEMPOTENT", restaurant_id=restaurant_id)
        mock_holidays_service.create.return_value = created

        payload = _valid_upsert_payload(canonical_key="E2E_HOLIDAY_IDEMPOTENT")
        payload["restaurant_id"] = str(restaurant_id)

        resp1 = client_with_employee.put("/api/v1/restaurant-holidays/by-key", json=payload)
        assert resp1.status_code == 200

        # Second call: key now exists — should call update instead of create
        mock_find.return_value = created
        mock_holidays_service.update.return_value = created
        mock_holidays_service.get_by_id.return_value = created
        resp2 = client_with_employee.put("/api/v1/restaurant-holidays/by-key", json=payload)
        assert resp2.status_code == 200
        mock_holidays_service.update.assert_called_once()

    def test_upsert_rejects_supplier_role(self):
        """PUT /restaurant-holidays/by-key with a supplier (non-internal) token returns 403."""
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
                resp = c.put("/api/v1/restaurant-holidays/by-key", json=payload)
                assert resp.status_code == 403, (
                    f"Expected 403 for supplier role, got {resp.status_code}. "
                    "get_employee_user must reject non-internal users."
                )
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_current_user, None)

    @patch("app.routes.restaurant_holidays.find_restaurant_holiday_by_canonical_key")
    @patch("app.routes.restaurant_holidays.restaurant_holidays_service")
    def test_upsert_restaurant_id_and_holiday_date_immutable_on_update(
        self,
        mock_holidays_service,
        mock_find,
        client_with_employee,
        mock_db,
    ):
        """PUT /restaurant-holidays/by-key update path must not change restaurant_id or holiday_date.

        restaurant_id and holiday_date are immutable after creation.  Even if the
        caller sends different values, the existing restaurant_id and holiday_date
        are preserved and the new values are silently ignored on the update path.
        """
        original_restaurant_id = uuid4()
        existing = _make_holiday_dto(
            canonical_key="E2E_HOLIDAY_IMMUTABLE_TEST",
            restaurant_id=original_restaurant_id,
        )
        mock_find.return_value = existing

        updated = _make_holiday_dto(
            canonical_key="E2E_HOLIDAY_IMMUTABLE_TEST",
            holiday_id=existing.holiday_id,
            restaurant_id=original_restaurant_id,
        )
        mock_holidays_service.update.return_value = updated
        mock_holidays_service.get_by_id.return_value = updated

        payload = _valid_upsert_payload(canonical_key="E2E_HOLIDAY_IMMUTABLE_TEST")
        # Caller tries to change restaurant_id — must be ignored since it is immutable
        payload["restaurant_id"] = str(uuid4())  # different restaurant_id
        payload["holiday_date"] = "2099-12-25"  # different holiday_date

        resp = client_with_employee.put("/api/v1/restaurant-holidays/by-key", json=payload)

        assert resp.status_code == 200
        # Verify update was called with the data from the request (update fields only)
        # and that restaurant_id + holiday_date from the existing record were used
        mock_holidays_service.update.assert_called_once()
        update_call_kwargs = mock_holidays_service.update.call_args
        # The update data dict (second positional arg) should NOT contain restaurant_id or holiday_date
        update_data = update_call_kwargs[0][1]  # positional: (holiday_id, update_data, db)
        assert "restaurant_id" not in update_data, (
            "restaurant_id must not be passed to update — it is immutable after creation"
        )
        assert "holiday_date" not in update_data, (
            "holiday_date must not be passed to update — it is immutable after creation"
        )
