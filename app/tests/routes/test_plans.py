"""
Tests for plan create/update/upsert:
- Global Marketplace cannot be assigned to plans (400).
- plan create enforces rollover=true, rollover_cap=null.
- PUT /plans/by-key: insert, update, and idempotency.
- PUT /plans/by-key: auth guard (non-employee returns 403).
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_employee_user, oauth2_scheme
from app.services.crud_service import plan_service
from app.services.market_service import GLOBAL_MARKET_ID

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

    def _override_get_current_user():
        return mock_employee_user

    def _override_oauth2_scheme():
        return "test-token"

    app.dependency_overrides[oauth2_scheme] = _override_oauth2_scheme
    app.dependency_overrides[get_employee_user] = _override_get_employee_user
    app.dependency_overrides[get_current_user] = _override_get_current_user
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_employee_user, None)
        app.dependency_overrides.pop(get_current_user, None)


def _valid_plan_payload(market_id=None):
    """Minimal valid plan create payload; use market_id or a random UUID.

    price/credit = 100.0/10 = 10.0/credit, well above the 20% spread floor
    (seeded supplier_value=1.0, floor=20% → threshold=1.2/credit).
    """
    mid = market_id or uuid4()
    return {
        "market_id": str(mid),
        "name": "Test Plan",
        "credit": 10,
        "price": 100.0,
    }


class TestPlanGlobalMarketRejection:
    """POST and PUT /api/v1/plans reject Global Marketplace market_id with 400."""

    def test_create_plan_with_global_market_returns_400(self, client_with_employee):
        """POST /api/v1/plans with market_id=Global returns 400 and does not create."""
        payload = _valid_plan_payload(market_id=GLOBAL_MARKET_ID)
        resp = client_with_employee.post("/api/v1/plans", json=payload)
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data
        # K3+: detail is now an envelope dict; extract message for string checks.
        raw = data["detail"]
        detail_str = raw.get("message", "") if isinstance(raw, dict) else str(raw)
        assert "Global Marketplace" in detail_str
        assert "plan" in detail_str.lower()

    def test_update_plan_with_global_market_returns_400(self, client_with_employee):
        """PUT /api/v1/plans{plan_id} with market_id=Global returns 400."""
        plan_id = uuid4()
        payload = {"market_id": str(GLOBAL_MARKET_ID)}
        resp = client_with_employee.put(f"/api/v1/plans/{plan_id}", json=payload)
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data
        # K3+: detail is now an envelope dict; extract message for string checks.
        raw = data["detail"]
        detail_str = raw.get("message", "") if isinstance(raw, dict) else str(raw)
        assert "Global Marketplace" in detail_str
        assert "plan" in detail_str.lower()


# Argentina market (from seed); plans cannot use Global
ARGENTINA_MARKET_ID = "00000000-0000-0000-0000-000000000002"


def _make_plan_dto(*, market_id=None, canonical_key=None):
    """Build a minimal mock plan DTO."""
    m = MagicMock()
    m.plan_id = uuid4()
    m.market_id = market_id or uuid4()
    m.name = "Test"
    m.name_i18n = None
    m.marketing_description = None
    m.marketing_description_i18n = None
    m.features = None
    m.features_i18n = None
    m.cta_label = None
    m.cta_label_i18n = None
    m.credit = 10
    m.price = 9.99
    m.credit_cost_local_currency = 1.0
    m.credit_cost_usd = 1.0
    m.rollover = True
    m.rollover_cap = None
    m.canonical_key = canonical_key
    m.is_archived = False
    m.status = "active"
    m.created_date = "2026-01-01T00:00:00Z"
    m.modified_date = "2026-01-01T00:00:00Z"
    m.modified_by = uuid4()
    return m


def _valid_upsert_payload(*, canonical_key="TEST_KEY_AR_001", market_id=None):
    """Minimal valid upsert payload."""
    mid = market_id or ARGENTINA_MARKET_ID
    return {
        "canonical_key": canonical_key,
        "market_id": str(mid),
        "name": "Test Plan",
        "credit": 20,
        "price": 50000.0,
    }


class TestPlanCreateRolloverDefaults:
    """Plan create enforces rollover=true and rollover_cap=null regardless of client payload."""

    @patch.object(plan_service, "create")
    def test_create_plan_enforces_rollover_true_and_cap_null(self, mock_create, client_with_employee):
        """POST /api/v1/plans ignores client rollover/rollover_cap; service receives rollover=True, rollover_cap=None."""
        created = _make_plan_dto(market_id=uuid4())
        mock_create.return_value = created

        payload = _valid_plan_payload(market_id=ARGENTINA_MARKET_ID)
        payload["rollover"] = False
        payload["rollover_cap"] = 5

        resp = client_with_employee.post("/api/v1/plans", json=payload)

        assert resp.status_code == 201
        call_args = mock_create.call_args
        assert call_args is not None
        passed_payload = call_args[0][0]
        assert passed_payload["rollover"] is True
        assert passed_payload["rollover_cap"] is None


class TestPlanUpsertByKey:
    """PUT /api/v1/plans/by-key: insert, update, idempotency, auth."""

    @patch("app.services.crud_service.find_plan_by_canonical_key")
    @patch.object(plan_service, "create")
    def test_upsert_inserts_when_key_not_found(self, mock_create, mock_find, client_with_employee):
        """PUT /plans/by-key with a new canonical_key inserts a new plan and returns 200."""
        mock_find.return_value = None  # key does not exist yet
        created = _make_plan_dto(canonical_key="TEST_KEY_AR_001")
        mock_create.return_value = created

        payload = _valid_upsert_payload(canonical_key="TEST_KEY_AR_001")
        resp = client_with_employee.put("/api/v1/plans/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "plan_id" in data
        mock_create.assert_called_once()
        # Verify rollover is forced to True in the service call
        service_payload = mock_create.call_args[0][0]
        assert service_payload["rollover"] is True
        assert service_payload["rollover_cap"] is None

    @patch("app.services.crud_service.find_plan_by_canonical_key")
    @patch.object(plan_service, "update")
    def test_upsert_updates_when_key_exists(self, mock_update, mock_find, client_with_employee):
        """PUT /plans/by-key with an existing canonical_key updates the plan and returns 200."""
        existing = _make_plan_dto(canonical_key="TEST_KEY_AR_001")
        mock_find.return_value = existing
        updated = _make_plan_dto(canonical_key="TEST_KEY_AR_001")
        updated.price = 60000.0
        mock_update.return_value = updated

        payload = _valid_upsert_payload(canonical_key="TEST_KEY_AR_001")
        payload["price"] = 60000.0
        resp = client_with_employee.put("/api/v1/plans/by-key", json=payload)

        assert resp.status_code == 200
        mock_update.assert_called_once()
        # canonical_key must not be passed to plan_service.update (update strips it)
        update_payload = mock_update.call_args[0][1]
        assert "canonical_key" not in update_payload

    @patch("app.services.crud_service.find_plan_by_canonical_key")
    @patch.object(plan_service, "create")
    def test_upsert_idempotent_same_payload_twice(self, mock_create, mock_find, client_with_employee):
        """Calling upsert twice with identical payload should behave consistently."""
        # First call: insert
        mock_find.return_value = None
        created = _make_plan_dto(canonical_key="TEST_KEY_AR_IDEMPOTENT")
        mock_create.return_value = created

        payload = _valid_upsert_payload(canonical_key="TEST_KEY_AR_IDEMPOTENT")
        resp1 = client_with_employee.put("/api/v1/plans/by-key", json=payload)
        assert resp1.status_code == 200

        # Second call: key now exists — should call update instead of create
        mock_find.return_value = created  # simulate the plan now existing
        with patch.object(plan_service, "update") as mock_update:
            mock_update.return_value = created
            resp2 = client_with_employee.put("/api/v1/plans/by-key", json=payload)
            assert resp2.status_code == 200
            mock_update.assert_called_once()

    def test_upsert_rejects_global_market(self, client_with_employee):
        """PUT /plans/by-key with market_id=Global returns 400."""
        payload = _valid_upsert_payload(canonical_key="TEST_KEY_GLOBAL")
        payload["market_id"] = str(GLOBAL_MARKET_ID)
        resp = client_with_employee.put("/api/v1/plans/by-key", json=payload)
        assert resp.status_code == 400
        data = resp.json()
        raw = data["detail"]
        detail_str = raw.get("message", "") if isinstance(raw, dict) else str(raw)
        assert "Global Marketplace" in detail_str

    def test_upsert_requires_employee_auth(self):
        """PUT /plans/by-key without employee auth returns 403."""

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
                resp = c.put("/api/v1/plans/by-key", json=payload)
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_employee_user, None)
