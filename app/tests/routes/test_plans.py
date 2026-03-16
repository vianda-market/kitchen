"""
Tests for plan create/update: Global Marketplace cannot be assigned to plans (400);
plan create enforces rollover=true, rollover_cap=null.
"""

import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from application import app
from app.auth.dependencies import get_employee_user, oauth2_scheme
from app.services.market_service import GLOBAL_MARKET_ID
from app.services.crud_service import plan_service


@pytest.fixture
def mock_employee_user():
    return {
        "user_id": str(uuid4()),
        "role_type": "Internal",
        "role_name": "Admin",
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


def _valid_plan_payload(market_id=None):
    """Minimal valid plan create payload; use market_id or a random UUID."""
    mid = market_id or uuid4()
    return {
        "market_id": str(mid),
        "name": "Test Plan",
        "credit": 10,
        "price": 9.99,
    }


class TestPlanGlobalMarketRejection:
    """POST and PUT /api/v1/plans/ reject Global Marketplace market_id with 400."""

    def test_create_plan_with_global_market_returns_400(self, client_with_employee):
        """POST /api/v1/plans/ with market_id=Global returns 400 and does not create."""
        payload = _valid_plan_payload(market_id=GLOBAL_MARKET_ID)
        resp = client_with_employee.post("/api/v1/plans/", json=payload)
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data
        assert "Global Marketplace" in data["detail"]
        assert "plan" in data["detail"].lower()

    def test_update_plan_with_global_market_returns_400(self, client_with_employee):
        """PUT /api/v1/plans/{plan_id} with market_id=Global returns 400."""
        plan_id = uuid4()
        payload = {"market_id": str(GLOBAL_MARKET_ID)}
        resp = client_with_employee.put(f"/api/v1/plans/{plan_id}", json=payload)
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data
        assert "Global Marketplace" in data["detail"]
        assert "plan" in data["detail"].lower()


# Argentina market (from seed); plans cannot use Global
ARGENTINA_MARKET_ID = "00000000-0000-0000-0000-000000000002"


class TestPlanCreateRolloverDefaults:
    """Plan create enforces rollover=true and rollover_cap=null regardless of client payload."""

    @patch.object(plan_service, "create")
    def test_create_plan_enforces_rollover_true_and_cap_null(
        self, mock_create, client_with_employee
    ):
        """POST /api/v1/plans/ ignores client rollover/rollover_cap; service receives rollover=True, rollover_cap=None."""
        created = MagicMock()
        created.plan_id = uuid4()
        created.market_id = uuid4()
        created.name = "Test"
        created.credit = 10
        created.price = 9.99
        created.credit_worth = 1.0
        created.rollover = True
        created.rollover_cap = None
        created.is_archived = False
        created.status = "Active"
        created.created_date = "2026-01-01T00:00:00Z"
        created.modified_date = "2026-01-01T00:00:00Z"
        created.modified_by = uuid4()
        mock_create.return_value = created

        payload = _valid_plan_payload(market_id=ARGENTINA_MARKET_ID)
        payload["rollover"] = False
        payload["rollover_cap"] = 5

        resp = client_with_employee.post("/api/v1/plans/", json=payload)

        assert resp.status_code == 201
        call_args = mock_create.call_args
        assert call_args is not None
        passed_payload = call_args[0][0]
        assert passed_payload["rollover"] is True
        assert passed_payload["rollover_cap"] is None
