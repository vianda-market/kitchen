"""
Tests for user routes: PUT /users/me/employer (assign employer with address).
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from application import app
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.dto.models import UserDTO, EmployerDTO, AddressDTO
from app.config import Status, RoleType, RoleName


@pytest.fixture
def customer_user():
    """Customer user for employer assignment."""
    uid = uuid4()
    return {
        "user_id": uid,
        "role_type": "Customer",
        "role_name": "Comensal",
        "institution_id": uuid4(),
    }


@pytest.fixture
def supplier_user():
    """Supplier user (cannot assign employer)."""
    return {
        "user_id": uuid4(),
        "role_type": "Supplier",
        "role_name": "Admin",
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
    """PUT /users/me/employer with valid employer_id and address_id returns 200."""
    employer_id = uuid4()
    address_id = uuid4()
    user_id = customer_user["user_id"]

    employer_dto = EmployerDTO(
        employer_id=employer_id,
        name="Test Employer",
        address_id=address_id,
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(timezone.utc),
        modified_by=user_id,
        modified_date=datetime.now(timezone.utc),
    )
    address_dto = AddressDTO(
        address_id=address_id,
        institution_id=uuid4(),
        user_id=user_id,
        employer_id=employer_id,
        address_type=["Customer Employer"],
        street_type="St",
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
        created_date=datetime.now(timezone.utc),
        modified_by=user_id,
        modified_date=datetime.now(timezone.utc),
    )
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
        employer_id=employer_id,
        employer_address_id=address_id,
        market_id=uuid4(),
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(timezone.utc),
        modified_by=user_id,
        modified_date=datetime.now(timezone.utc),
    )

    with patch("app.services.crud_service.employer_service") as mock_employer, \
         patch("app.services.crud_service.address_service") as mock_address, \
         patch("app.routes.user.user_service") as mock_user:
        mock_employer.get_by_id.return_value = employer_dto
        mock_address.get_by_id.return_value = address_dto
        mock_user.update.return_value = updated_user

        response = client_customer.put(
            "/api/v1/users/me/employer",
            json={"employer_id": str(employer_id), "address_id": str(address_id)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["employer_id"] == str(employer_id)
        assert data["employer_address_id"] == str(address_id)
        mock_user.update.assert_called_once()
        call_args = mock_user.update.call_args
        update_data = call_args[0][1]  # (user_id, update_data, db, ...)
        assert update_data["employer_id"] == employer_id
        assert update_data["employer_address_id"] == address_id


def test_assign_employer_address_not_belonging_to_employer(client_customer, customer_user, mock_db):
    """PUT /users/me/employer with address not belonging to employer returns 400."""
    employer_id = uuid4()
    other_employer_id = uuid4()
    address_id = uuid4()
    user_id = customer_user["user_id"]

    employer_dto = EmployerDTO(
        employer_id=employer_id,
        name="Test Employer",
        address_id=address_id,
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(timezone.utc),
        modified_by=user_id,
        modified_date=datetime.now(timezone.utc),
    )
    address_dto = AddressDTO(
        address_id=address_id,
        institution_id=uuid4(),
        user_id=user_id,
        employer_id=other_employer_id,
        address_type=["Customer Employer"],
        street_type="St",
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
        created_date=datetime.now(timezone.utc),
        modified_by=user_id,
        modified_date=datetime.now(timezone.utc),
    )

    with patch("app.services.crud_service.employer_service") as mock_employer, \
         patch("app.services.crud_service.address_service") as mock_address, \
         patch("app.routes.user.user_service") as mock_user:
        mock_employer.get_by_id.return_value = employer_dto
        mock_address.get_by_id.return_value = address_dto

        response = client_customer.put(
            "/api/v1/users/me/employer",
            json={"employer_id": str(employer_id), "address_id": str(address_id)},
        )

        assert response.status_code == 400
        assert "does not belong" in response.json().get("detail", "").lower()
        mock_user.update.assert_not_called()


def test_assign_employer_supplier_forbidden(client_supplier, mock_db):
    """PUT /users/me/employer as Supplier returns 403."""
    employer_id = uuid4()
    address_id = uuid4()

    response = client_supplier.put(
        "/api/v1/users/me/employer",
        json={"employer_id": str(employer_id), "address_id": str(address_id)},
    )

    assert response.status_code == 403
    assert "Supplier" in response.json().get("detail", "")


# ---------------------------------------------------------------------------
# Deprecation tests: self-read/self-update via deprecated /{user_id} endpoints
# ---------------------------------------------------------------------------

def test_deprecated_get_user_self_read_returns_x_deprecated_header(client_customer, customer_user, mock_db):
    """GET /users/{user_id} for self-read returns X-Deprecated-Endpoint header."""
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
        created_date=datetime.now(timezone.utc),
        modified_by=user_id,
        modified_date=datetime.now(timezone.utc),
    )
    with patch("app.routes.user.user_service") as mock_user:
        mock_user.get_by_id.return_value = user_dto
        response = client_customer.get(f"/api/v1/users/{user_id}")
    assert response.status_code == 200
    assert response.headers.get("X-Deprecated-Endpoint") == "true"
    assert "X-Use-Instead" in response.headers
    assert "users/me" in response.headers.get("X-Use-Instead", "")


def test_deprecated_put_user_self_update_returns_x_deprecated_header(client_customer, customer_user, mock_db):
    """PUT /users/{user_id} for self-update returns X-Deprecated-Endpoint header."""
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
        created_date=datetime.now(timezone.utc),
        modified_by=user_id,
        modified_date=datetime.now(timezone.utc),
    )
    with patch("app.routes.user.user_service") as mock_user:
        mock_user.get_by_id.return_value = user_dto
        mock_user.update.return_value = user_dto
        response = client_customer.put(
            f"/api/v1/users/{user_id}",
            json={"first_name": "Updated"},
        )
    assert response.status_code == 200
    assert response.headers.get("X-Deprecated-Endpoint") == "true"
    assert "X-Use-Instead" in response.headers
    assert "users/me" in response.headers.get("X-Use-Instead", "")


def test_deprecated_get_enriched_user_self_read_returns_x_deprecated_header(client_customer, customer_user, mock_db):
    """GET /users/enriched/{user_id} for self-read returns X-Deprecated-Endpoint header."""
    user_id = customer_user["user_id"]
    inst_id = customer_user["institution_id"]
    market_id = uuid4()
    now = datetime.now(timezone.utc)
    enriched = {
        "user_id": user_id,
        "institution_id": inst_id,
        "institution_name": "Vianda Customers",
        "role_name": "Comensal",
        "role_type": "Customer",
        "username": "customer",
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "full_name": "Test User",
        "employer_id": None,
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
    assert response.status_code == 200
    assert response.headers.get("X-Deprecated-Endpoint") == "true"
    assert "X-Use-Instead" in response.headers
