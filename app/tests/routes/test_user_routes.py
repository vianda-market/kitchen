"""
Tests for user routes: PUT /users/me/employer (assign employer with address).
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from application import app
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, oauth2_scheme
from app.config import RoleName, RoleType, Status
from app.dependencies.database import get_db
from app.dto.models import AddressDTO, UserDTO
from app.tests.conftest import SAMPLE_CITY_ID


@pytest.fixture
def customer_user():
    """Customer user for employer assignment."""
    uid = uuid4()
    return {
        "user_id": uid,
        "role_type": "customer",
        "role_name": "comensal",
        "institution_id": uuid4(),
    }


@pytest.fixture
def supplier_user():
    """Supplier user (cannot assign employer)."""
    return {
        "user_id": uuid4(),
        "role_type": "supplier",
        "role_name": "admin",
        "institution_id": uuid4(),
    }


@pytest.fixture
def mock_db():
    """Mock DB connection for route tests."""
    return MagicMock()


@pytest.fixture
def client_customer(customer_user, mock_db):
    """Test client with Customer user."""

    def _override_oauth2():
        return "test-token"

    def _override_get_current_user():
        return customer_user

    async def _override_get_db():
        yield mock_db

    app.dependency_overrides[oauth2_scheme] = _override_oauth2
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client_supplier(supplier_user, mock_db):
    """Test client with Supplier user."""

    def _override_oauth2():
        return "test-token"

    def _override_get_current_user():
        return supplier_user

    async def _override_get_db():
        yield mock_db

    app.dependency_overrides[oauth2_scheme] = _override_oauth2
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(oauth2_scheme, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_assign_employer_success(client_customer, customer_user, mock_db):
    """PUT /users/me/employer with valid employer_entity_id and address_id returns 200."""
    employer_entity_id = uuid4()
    address_id = uuid4()
    user_id = customer_user["user_id"]
    employer_institution_id = uuid4()

    # Mock entity — route validates entity exists and address belongs to same institution
    mock_entity = MagicMock()
    mock_entity.institution_entity_id = employer_entity_id
    mock_entity.institution_id = employer_institution_id

    address_dto = AddressDTO(
        city_metadata_id=uuid4(),
        address_id=address_id,
        institution_id=employer_institution_id,  # Must match entity's institution_id
        user_id=user_id,
        address_type=["customer_employer"],
        street_type="st",
        street_name="Main St",
        building_number="123",
        city="Buenos Aires",
        province="Buenos Aires",
        postal_code="1000",
        country_code="AR",
        country_name="Argentina",
        timezone="America/Argentina/Buenos_Aires",
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(UTC),
        modified_by=user_id,
        modified_date=datetime.now(UTC),
    )
    mid = uuid4()
    updated_user = UserDTO(
        user_id=user_id,
        institution_id=uuid4(),
        role_type=RoleType.CUSTOMER,
        role_name=RoleName.COMENSAL,
        username="customer",
        hashed_password="hash",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        mobile_number=None,
        mobile_number_verified=False,
        mobile_number_verified_at=None,
        employer_entity_id=employer_entity_id,
        employer_address_id=address_id,
        market_id=mid,
        city_metadata_id=SAMPLE_CITY_ID,
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(UTC),
        modified_by=user_id,
        modified_date=datetime.now(UTC),
    )

    with (
        patch("app.services.crud_service.institution_entity_service") as mock_entity_svc,
        patch("app.services.crud_service.address_service") as mock_address,
        patch("app.routes.user.user_service") as mock_user,
    ):
        mock_entity_svc.get_by_id.return_value = mock_entity
        mock_address.get_by_id.return_value = address_dto
        mock_user.update.return_value = updated_user

        response = client_customer.put(
            "/api/v1/users/me/employer",
            json={"employer_entity_id": str(employer_entity_id), "address_id": str(address_id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["employer_entity_id"] == str(employer_entity_id)
        assert data["employer_address_id"] == str(address_id)
        mock_user.update.assert_called_once()
        call_args = mock_user.update.call_args
        update_data = call_args[0][1]  # (user_id, update_data, db, ...)
        assert update_data["employer_entity_id"] == employer_entity_id
        assert update_data["employer_address_id"] == address_id


def test_assign_employer_address_not_belonging_to_employer(client_customer, customer_user, mock_db):
    """PUT /users/me/employer with address from different institution returns 400."""
    employer_entity_id = uuid4()
    address_id = uuid4()
    user_id = customer_user["user_id"]
    employer_institution_id = uuid4()
    other_institution_id = uuid4()  # Address belongs to a different institution

    # Mock entity
    mock_entity = MagicMock()
    mock_entity.institution_entity_id = employer_entity_id
    mock_entity.institution_id = employer_institution_id

    # Address with different institution_id → validation should fail
    address_dto = AddressDTO(
        city_metadata_id=uuid4(),
        address_id=address_id,
        institution_id=other_institution_id,  # Different from entity's institution
        user_id=user_id,
        address_type=["customer_employer"],
        street_type="st",
        street_name="Main St",
        building_number="123",
        city="Buenos Aires",
        province="Buenos Aires",
        postal_code="1000",
        country_code="AR",
        country_name="Argentina",
        timezone="America/Argentina/Buenos_Aires",
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(UTC),
        modified_by=user_id,
        modified_date=datetime.now(UTC),
    )

    with (
        patch("app.services.crud_service.institution_entity_service") as mock_entity_svc,
        patch("app.services.crud_service.address_service") as mock_address,
        patch("app.routes.user.user_service") as mock_user,
    ):
        mock_entity_svc.get_by_id.return_value = mock_entity
        mock_address.get_by_id.return_value = address_dto

        response = client_customer.put(
            "/api/v1/users/me/employer",
            json={"employer_entity_id": str(employer_entity_id), "address_id": str(address_id)},
        )

        assert response.status_code == 400
        # K3+: detail is now an envelope dict; extract message for string checks.
        raw = response.json().get("detail", "")
        detail_str = raw.get("message", "") if isinstance(raw, dict) else str(raw)
        assert "does not belong" in detail_str.lower()
        mock_user.update.assert_not_called()


def test_assign_employer_supplier_forbidden(client_supplier, mock_db):
    """PUT /users/me/employer as Supplier returns 403."""
    employer_entity_id = uuid4()
    address_id = uuid4()

    response = client_supplier.put(
        "/api/v1/users/me/employer",
        json={"employer_entity_id": str(employer_entity_id), "address_id": str(address_id)},
    )

    assert response.status_code == 403
    # K3+: detail is now an envelope dict; extract message for string checks.
    raw = response.json().get("detail", "")
    detail_str = raw.get("message", "") if isinstance(raw, dict) else str(raw)
    assert "Supplier" in detail_str


# ---------------------------------------------------------------------------
# Deprecation tests: self-read/self-update via deprecated /{user_id} endpoints
# ---------------------------------------------------------------------------


def test_deprecated_get_user_self_read_returns_410_gone(client_customer, customer_user, mock_db):
    """GET /users/{user_id} for Customer self-read returns 410 Gone with migration hint."""
    user_id = customer_user["user_id"]
    user_dto = UserDTO(
        user_id=user_id,
        institution_id=customer_user["institution_id"],
        role_type=RoleType.CUSTOMER,
        role_name=RoleName.COMENSAL,
        username="customer",
        hashed_password="hash",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        market_id=uuid4(),
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(UTC),
        modified_by=user_id,
        modified_date=datetime.now(UTC),
    )
    with patch("app.routes.user.user_service") as mock_user:
        mock_user.get_by_id.return_value = user_dto
        response = client_customer.get(f"/api/v1/users/{user_id}")
    assert response.status_code == 410
    # K3+: detail is now an envelope dict; extract message for string checks.
    raw = response.json().get("detail") or ""
    detail_str = raw.get("message", "") if isinstance(raw, dict) else str(raw)
    assert "users/me" in detail_str


def test_deprecated_put_user_self_update_returns_410_gone(client_customer, customer_user, mock_db):
    """PUT /users/{user_id} for Customer self-update returns 410 Gone with migration hint."""
    user_id = customer_user["user_id"]
    user_dto = UserDTO(
        user_id=user_id,
        institution_id=customer_user["institution_id"],
        role_type=RoleType.CUSTOMER,
        role_name=RoleName.COMENSAL,
        username="customer",
        hashed_password="hash",
        first_name="Updated",
        last_name="User",
        email="test@example.com",
        market_id=uuid4(),
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(UTC),
        modified_by=user_id,
        modified_date=datetime.now(UTC),
    )
    with patch("app.routes.user.user_service") as mock_user:
        mock_user.get_by_id.return_value = user_dto
        mock_user.update.return_value = user_dto
        response = client_customer.put(
            f"/api/v1/users/{user_id}",
            json={"first_name": "Updated"},
        )
    assert response.status_code == 410
    # K3+: detail is now an envelope dict; extract message for string checks.
    raw = response.json().get("detail") or ""
    detail_str = raw.get("message", "") if isinstance(raw, dict) else str(raw)
    assert "users/me" in detail_str


def test_deprecated_get_enriched_user_self_read_returns_410_gone(client_customer, customer_user, mock_db):
    """GET /users/enriched/{user_id} for Customer self-read returns 410 Gone with migration hint."""
    user_id = customer_user["user_id"]
    inst_id = customer_user["institution_id"]
    market_id = uuid4()
    now = datetime.now(UTC)
    enriched = {
        "user_id": user_id,
        "institution_id": inst_id,
        "institution_name": "Vianda Customers",
        "role_name": "comensal",
        "role_type": "customer",
        "username": "customer",
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "full_name": "Test User",
        "employer_entity_id": None,
        "market_id": market_id,
        "market_name": "Argentina",
        "is_archived": False,
        "status": Status.ACTIVE,
        "created_date": now,
        "modified_date": now,
    }
    with patch("app.routes.user.get_enriched_user_by_id") as mock_get:
        mock_get.return_value = enriched
        response = client_customer.get(f"/api/v1/users/enriched/{user_id}")
    assert response.status_code == 410
    # K3+: detail is now an envelope dict; extract message for string checks.
    raw = response.json().get("detail") or ""
    detail_str = raw.get("message", "") if isinstance(raw, dict) else str(raw)
    assert "users/me" in detail_str


def test_put_me_mobile_change_resets_verification_flags(client_customer, customer_user, mock_db):
    """PUT /users/me with a new mobile_number clears mobile_number_verified flags in update payload."""
    user_id = customer_user["user_id"]
    market_id = uuid4()
    inst_id = customer_user["institution_id"]
    verified_at = datetime.now(UTC)
    existing = UserDTO(
        user_id=user_id,
        institution_id=inst_id,
        role_type=RoleType.CUSTOMER,
        role_name=RoleName.COMENSAL,
        username="customer",
        hashed_password="hash",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        mobile_number="+14155552671",
        mobile_number_verified=True,
        mobile_number_verified_at=verified_at,
        employer_entity_id=None,
        market_id=market_id,
        city_metadata_id=SAMPLE_CITY_ID,
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(UTC),
        modified_by=user_id,
        modified_date=datetime.now(UTC),
    )
    updated = existing.model_copy(
        update={
            "mobile_number": "+15005550006",
            "mobile_number_verified": False,
            "mobile_number_verified_at": None,
        }
    )
    with (
        patch("app.routes.user.user_service") as mock_user,
        patch("app.routes.user.get_assigned_market_ids", return_value=[market_id]),
    ):
        mock_user.get_by_id.return_value = existing
        mock_user.update.return_value = updated
        response = client_customer.put(
            "/api/v1/users/me",
            json={"mobile_number": "+15005550006"},
        )
    assert response.status_code == 200
    update_data = mock_user.update.call_args[0][1]
    assert update_data["mobile_number_verified"] is False
    assert update_data["mobile_number_verified_at"] is None
    assert update_data["mobile_number"] == "+15005550006"


def test_put_me_new_email_triggers_verification_flow(client_customer, customer_user, mock_db):
    """PUT /users/me with new email calls email change service and clears email_verified; response includes message."""
    user_id = customer_user["user_id"]
    market_id = uuid4()
    inst_id = customer_user["institution_id"]
    existing = UserDTO(
        user_id=user_id,
        institution_id=inst_id,
        role_type=RoleType.CUSTOMER,
        role_name=RoleName.COMENSAL,
        username="customer",
        hashed_password="hash",
        first_name="Test",
        last_name="User",
        email="old@example.com",
        mobile_number=None,
        mobile_number_verified=False,
        mobile_number_verified_at=None,
        email_verified=True,
        email_verified_at=datetime.now(UTC),
        employer_entity_id=None,
        market_id=market_id,
        city_metadata_id=SAMPLE_CITY_ID,
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(UTC),
        modified_by=user_id,
        modified_date=datetime.now(UTC),
    )
    updated = existing.model_copy(
        update={
            "email_verified": False,
            "email_verified_at": None,
        }
    )
    with (
        patch("app.routes.user.user_service") as mock_user,
        patch("app.routes.user.email_change_service.request_email_change") as mock_req,
        patch("app.routes.user.get_assigned_market_ids", return_value=[market_id]),
    ):
        mock_user.get_by_id.return_value = existing
        mock_user.update.return_value = updated
        response = client_customer.put(
            "/api/v1/users/me",
            json={"email": "new@example.com"},
        )
    assert response.status_code == 200
    mock_req.assert_called_once()
    args = mock_req.call_args[0]
    assert args[0] == user_id
    assert args[1] == "new@example.com"
    data = response.json()
    assert "new@example.com" in (data.get("email_change_message") or "")
    assert data["email"] == "old@example.com"
    ud = mock_user.update.call_args[0][1]
    assert ud.get("email_verified") is False
    assert "email" not in ud


def test_post_me_verify_email_change_success(client_customer, customer_user, mock_db):
    """POST /users/me/verify-email-change returns success message."""
    with patch("app.routes.user.email_change_service.verify_email_change") as mock_verify:
        response = client_customer.post(
            "/api/v1/users/me/verify-email-change",
            json={"code": "123456"},
        )
    assert response.status_code == 200
    assert response.json().get("message")
    mock_verify.assert_called_once_with(customer_user["user_id"], "123456", mock_db)
