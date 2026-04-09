"""
Tests for address create route: institution_id/user_id optional for B2C, required for B2B (safeguard).
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from application import app
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.dto.models import AddressDTO
from app.config import Status


@pytest.fixture
def customer_user_with_institution():
    """Customer user with institution_id (B2C allowed to omit institution_id in body)."""
    uid = uuid4()
    iid = uuid4()
    return {
        "user_id": uid,
        "role_type": "customer",
        "role_name": "comensal",
        "institution_id": iid,
    }


@pytest.fixture
def customer_user_without_institution():
    """Customer user without institution_id (should get 400)."""
    return {
        "user_id": uuid4(),
        "role_type": "customer",
        "role_name": "comensal",
        "institution_id": None,
    }


@pytest.fixture
def b2b_employee_user():
    """B2B user (Internal); must send institution_id and user_id in body."""
    return {
        "user_id": uuid4(),
        "role_type": "Employee",
        "role_name": "admin",
        "institution_id": uuid4(),
    }


@pytest.fixture
def mock_db():
    """Mock DB connection for route tests."""
    return MagicMock()


def _minimal_address_body(include_institution_and_user=False, institution_id=None, user_id=None):
    body = {
        "province": "CABA",
        "city": "Buenos Aires",
        "postal_code": "C1043AAZ",
        "street_type": "ave",
        "street_name": "Corrientes",
        "building_number": "1234",
        "country_code": "AR",
    }
    if include_institution_and_user:
        body["institution_id"] = str(institution_id or uuid4())
        body["user_id"] = str(user_id or uuid4())
    return body


@pytest.fixture
def client_customer_with_institution(customer_user_with_institution, mock_db):
    """Test client with Customer user that has institution_id."""
    def _override_oauth2():
        return "test-token"

    def _override_get_current_user():
        return customer_user_with_institution

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
def client_customer_without_institution(customer_user_without_institution, mock_db):
    """Test client with Customer user that has no institution_id."""
    def _override_oauth2():
        return "test-token"

    def _override_get_current_user():
        return customer_user_without_institution

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
def client_b2b_employee(b2b_employee_user, mock_db):
    """Test client with B2B Internal user."""
    def _override_oauth2():
        return "test-token"

    def _override_get_current_user():
        return b2b_employee_user

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


class TestAddressCreateInstitutionSafeguard:
    """Safeguard: B2C may omit institution_id/user_id; B2B must send them."""

    @patch("app.routes.address.address_business_service")
    def test_customer_can_omit_institution_id_and_user_id(
        self, mock_business_service, client_customer_with_institution, customer_user_with_institution
    ):
        """Customer (B2C) can omit institution_id and user_id; backend sets from JWT; expect 201."""
        uid = customer_user_with_institution["user_id"]
        iid = customer_user_with_institution["institution_id"]
        mock_dto = AddressDTO(
            address_id=uuid4(),
            institution_id=iid,
            user_id=uid,
            employer_id=None,
            address_type=[],
            is_default=False,
            floor=None,
            country_name="Argentina",
            country_code="AR",
            province="CABA",
            city="Buenos Aires",
            postal_code="C1043AAZ",
            street_type="ave",
            street_name="Corrientes",
            building_number="1234",
            apartment_unit=None,
            timezone="America/Argentina/Buenos_Aires",
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(timezone.utc),
            modified_by=uid,
            modified_date=datetime.now(timezone.utc),
        )
        mock_business_service.create_address_with_geocoding.return_value = mock_dto

        resp = client_customer_with_institution.post(
            "/api/v1/addresses",
            json=_minimal_address_body(include_institution_and_user=False),
        )

        assert resp.status_code == 201
        data = resp.json()
        assert str(data["institution_id"]) == str(iid)
        assert str(data["user_id"]) == str(uid)
        call_args = mock_business_service.create_address_with_geocoding.call_args
        addr_data = call_args[0][0]
        assert addr_data["institution_id"] == iid
        assert addr_data["user_id"] == uid

    def test_customer_without_institution_id_in_jwt_gets_400(
        self, client_customer_without_institution
    ):
        """Customer with no institution_id in JWT gets 400 when creating address."""
        resp = client_customer_without_institution.post(
            "/api/v1/addresses",
            json=_minimal_address_body(include_institution_and_user=False),
        )
        assert resp.status_code == 400
        assert "institution" in resp.json().get("detail", "").lower()

    def test_b2b_omitting_institution_id_gets_400(self, client_b2b_employee):
        """B2B (Internal) omitting institution_id or user_id gets 400."""
        resp = client_b2b_employee.post(
            "/api/v1/addresses",
            json=_minimal_address_body(include_institution_and_user=False),
        )
        assert resp.status_code == 400
        detail = resp.json().get("detail", "")
        assert "institution_id" in detail or "B2B" in detail or "required" in detail
