"""
Tests for user upsert by canonical key:
- PUT /users/by-key: insert path (new canonical_key creates user)
- PUT /users/by-key: update path (same canonical_key updates fields)
- PUT /users/by-key: idempotency (same payload twice is a no-op after first call)
- PUT /users/by-key: password handling on update without password (existing hash preserved)
- PUT /users/by-key: auth guard (supplier role rejected with 403)
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_employee_user, oauth2_scheme
from app.config import RoleName, RoleType, Status
from app.schemas.consolidated_schemas import UserResponseSchema
from app.services.crud_service import user_service

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


def _make_user_dto(*, canonical_key=None, institution_id=None, market_id=None):
    """Build a minimal mock user DTO (MagicMock for service-layer mocking)."""
    m = MagicMock()
    m.user_id = uuid4()
    m.institution_id = institution_id or uuid4()
    m.role_type = RoleType.SUPPLIER
    m.role_name = RoleName.ADMIN
    m.username = "test_supplier"
    m.email = "test_supplier@example.com"
    m.hashed_password = "$2b$12$hashedpassword"
    m.first_name = "Test"
    m.last_name = "Supplier"
    m.mobile_number = None
    m.mobile_number_verified = False
    m.mobile_number_verified_at = None
    m.email_verified = False
    m.email_verified_at = None
    m.employer_entity_id = None
    m.employer_address_id = None
    m.workplace_group_id = None
    m.support_email_suppressed_until = None
    m.last_support_email_date = None
    m.market_id = market_id or uuid4()
    m.city_metadata_id = None
    m.locale = "en"
    m.referral_code = None
    m.referred_by_code = None
    m.is_archived = False
    m.status = Status.ACTIVE
    m.canonical_key = canonical_key
    m.created_date = datetime(2026, 1, 1, tzinfo=UTC)
    m.created_by = None
    m.modified_by = uuid4()
    m.modified_date = datetime(2026, 1, 1, tzinfo=UTC)
    return m


def _make_user_response(*, user_id=None, institution_id=None, market_id=None, canonical_key=None):
    """Build a minimal UserResponseSchema for response mocking."""
    uid = user_id or uuid4()
    iid = institution_id or uuid4()
    mid = market_id or uuid4()
    return UserResponseSchema(
        user_id=uid,
        institution_id=iid,
        role_type=RoleType.SUPPLIER,
        role_name=RoleName.ADMIN,
        username="test_supplier",
        email="test_supplier@example.com",
        first_name="Test",
        last_name="Supplier",
        market_id=mid,
        market_ids=[mid],
        locale="en",
        is_archived=False,
        status=Status.ACTIVE,
        canonical_key=canonical_key,
        email_change_message=None,
        created_date=datetime(2026, 1, 1, tzinfo=UTC),
        modified_date=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _valid_upsert_payload(*, canonical_key="E2E_USER_SUPPLIER_ADMIN"):
    """Minimal valid upsert payload for a supplier user."""
    return {
        "canonical_key": canonical_key,
        "institution_id": str(uuid4()),
        "role_type": "supplier",
        "role_name": "admin",
        "username": "test_supplier_admin",
        "email": "test_supplier_admin@example.com",
        "password": "Supplier123!",
        "first_name": "Test",
        "last_name": "Supplier",
        "market_id": str(uuid4()),
        "status": "active",
    }


class TestUserUpsertByKey:
    """PUT /api/v1/users/by-key: insert, update, idempotency, password, auth."""

    @patch("app.routes.user.find_user_by_canonical_key")
    @patch("app.routes.user._user_dto_to_response")
    @patch.object(user_service, "create")
    def test_upsert_inserts_when_key_not_found(self, mock_create, mock_response, mock_find, client_with_employee):
        """PUT /users/by-key with a new canonical_key inserts a new user and returns 200."""
        mock_find.return_value = None  # key does not exist yet
        created_dto = _make_user_dto(canonical_key="E2E_USER_SUPPLIER_ADMIN")
        mock_create.return_value = created_dto
        mock_response.return_value = _make_user_response(
            user_id=created_dto.user_id,
            institution_id=created_dto.institution_id,
            market_id=created_dto.market_id,
            canonical_key="E2E_USER_SUPPLIER_ADMIN",
        )

        payload = _valid_upsert_payload(canonical_key="E2E_USER_SUPPLIER_ADMIN")
        resp = client_with_employee.put("/api/v1/users/by-key", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data
        mock_create.assert_called_once()
        # canonical_key must reach the create call
        create_payload = mock_create.call_args[0][0]
        assert create_payload.get("canonical_key") == "E2E_USER_SUPPLIER_ADMIN"
        # password must be hashed, not stored as plain text
        assert "hashed_password" in create_payload
        assert "password" not in create_payload

    @patch("app.routes.user.find_user_by_canonical_key")
    @patch("app.routes.user._user_dto_to_response")
    @patch.object(user_service, "update")
    def test_upsert_updates_when_key_exists(self, mock_update, mock_response, mock_find, client_with_employee):
        """PUT /users/by-key with an existing canonical_key updates the user and returns 200."""
        existing = _make_user_dto(canonical_key="E2E_USER_SUPPLIER_ADMIN")
        mock_find.return_value = existing
        updated_dto = _make_user_dto(canonical_key="E2E_USER_SUPPLIER_ADMIN")
        updated_dto.first_name = "Updated"
        mock_update.return_value = updated_dto
        mock_response.return_value = _make_user_response(
            user_id=updated_dto.user_id,
            canonical_key="E2E_USER_SUPPLIER_ADMIN",
        )

        payload = _valid_upsert_payload(canonical_key="E2E_USER_SUPPLIER_ADMIN")
        payload["first_name"] = "Updated"
        resp = client_with_employee.put("/api/v1/users/by-key", json=payload)

        assert resp.status_code == 200
        mock_update.assert_called_once()
        update_payload = mock_update.call_args[0][1]
        # canonical_key must NOT be passed to user_service.update (it's the lookup key)
        assert "canonical_key" not in update_payload
        # Immutable fields must not be in the update payload
        assert "institution_id" not in update_payload
        assert "username" not in update_payload
        assert "role_type" not in update_payload

    @patch("app.routes.user.find_user_by_canonical_key")
    @patch("app.routes.user._user_dto_to_response")
    @patch.object(user_service, "create")
    def test_upsert_idempotent_same_payload_twice(self, mock_create, mock_response, mock_find, client_with_employee):
        """Calling upsert twice with identical payload behaves consistently."""
        # First call: insert
        mock_find.return_value = None
        created_dto = _make_user_dto(canonical_key="E2E_USER_IDEMPOTENT")
        mock_create.return_value = created_dto
        mock_response.return_value = _make_user_response(canonical_key="E2E_USER_IDEMPOTENT")

        payload = _valid_upsert_payload(canonical_key="E2E_USER_IDEMPOTENT")
        resp1 = client_with_employee.put("/api/v1/users/by-key", json=payload)
        assert resp1.status_code == 200

        # Second call: key now exists — should call update instead of create
        mock_find.return_value = created_dto
        with patch.object(user_service, "update") as mock_update:
            mock_update.return_value = created_dto
            mock_response.return_value = _make_user_response(canonical_key="E2E_USER_IDEMPOTENT")
            resp2 = client_with_employee.put("/api/v1/users/by-key", json=payload)
            assert resp2.status_code == 200
            mock_update.assert_called_once()

    @patch("app.routes.user.find_user_by_canonical_key")
    @patch("app.routes.user._user_dto_to_response")
    @patch.object(user_service, "update")
    def test_update_without_password_preserves_existing_hash(
        self, mock_update, mock_response, mock_find, client_with_employee
    ):
        """On UPDATE, omitting password leaves the existing hash untouched.

        The update payload must NOT include 'hashed_password' when password
        was not provided in the upsert request.  If hashed_password were
        accidentally set to None or empty, the user would be locked out.
        """
        existing = _make_user_dto(canonical_key="E2E_USER_NO_PWD_UPDATE")
        existing.hashed_password = "$2b$12$existinghash"
        mock_find.return_value = existing
        updated_dto = _make_user_dto(canonical_key="E2E_USER_NO_PWD_UPDATE")
        mock_update.return_value = updated_dto
        mock_response.return_value = _make_user_response(canonical_key="E2E_USER_NO_PWD_UPDATE")

        # No password in the update request
        payload = _valid_upsert_payload(canonical_key="E2E_USER_NO_PWD_UPDATE")
        del payload["password"]
        payload["first_name"] = "NoPasswordUpdate"

        resp = client_with_employee.put("/api/v1/users/by-key", json=payload)
        assert resp.status_code == 200
        mock_update.assert_called_once()
        update_payload = mock_update.call_args[0][1]
        # hashed_password must NOT appear in the update payload when password was omitted
        assert "hashed_password" not in update_payload, (
            "Existing password hash must not be overwritten when 'password' is absent from upsert"
        )
        assert "password" not in update_payload

    def test_upsert_rejects_supplier_role(self):
        """PUT /users/by-key with a supplier (non-internal) token returns 403.

        The endpoint is Internal-only (get_employee_user dependency).
        A supplier JWT must be rejected to prevent suppliers from creating
        arbitrary canonical accounts via this seed endpoint.
        """
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
                resp = c.put("/api/v1/users/by-key", json=payload)
                assert resp.status_code == 403, (
                    f"Expected 403 for supplier role, got {resp.status_code}. "
                    "get_employee_user must reject non-internal users."
                )
        finally:
            app.dependency_overrides.pop(oauth2_scheme, None)
            app.dependency_overrides.pop(get_current_user, None)
