"""
Shared test fixtures and configuration.

This file contains common fixtures, mocks, and test utilities
that are shared across all test modules.
"""

import os

os.environ.setdefault("MAPBOX_CACHE_MODE", "bypass")

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import Mock
from uuid import UUID, uuid4

import psycopg2.extensions
import pytest

# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
def mock_db():
    """Mock database connection for testing."""
    mock_conn = Mock(spec=psycopg2.extensions.connection)
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


@pytest.fixture
def mock_db_with_transaction():
    """Mock database connection with transaction support."""
    mock_conn = Mock(spec=psycopg2.extensions.connection)
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.begin = Mock()
    mock_conn.commit = Mock()
    mock_conn.rollback = Mock()
    return mock_conn


# =============================================================================
# User Fixtures
# =============================================================================

# US market UUID (must match seed / GET /leads/markets or /markets/enriched/)
SAMPLE_MARKET_ID = UUID("66666666-6666-6666-6666-666666666666")
# Sample city UUID (non-Global; must match market country for customer signup)
SAMPLE_CITY_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture
def sample_user_data():
    """Sample user data for testing. Uses country_code (resolved to market_id by signup service)."""
    return {
        "email": "test@example.com",
        "password": "plaintext123",
        "first_name": "John",
        "last_name": "Doe",
        "username": "johndoe",
        "country_code": "US",
        "city_metadata_id": SAMPLE_CITY_ID,
    }


@pytest.fixture
def sample_current_user():
    """Sample current user for testing."""
    return {"user_id": str(uuid4()), "username": "admin", "email": "admin@example.com"}


@pytest.fixture
def sample_user_dto():
    """Sample UserDTO for testing."""
    from app.config import RoleName, RoleType, Status
    from app.dto.models import UserDTO

    return UserDTO(
        user_id=uuid4(),
        institution_id=uuid4(),
        role_type=RoleType.CUSTOMER,
        role_name=RoleName.COMENSAL,
        username="johndoe",
        hashed_password="hashed_password_123",
        first_name="John",
        last_name="Doe",
        email="test@example.com",
        mobile_number=None,
        mobile_number_verified=False,
        mobile_number_verified_at=None,
        email_verified=False,
        email_verified_at=None,
        market_id=uuid4(),
        city_metadata_id=SAMPLE_CITY_ID,
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(UTC),
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


# =============================================================================
# Permission & Role-Based Access Control Fixtures
# =============================================================================


@pytest.fixture
def sample_employee_user():
    """Internal user (role_type='Internal', role_name='Admin') for testing.

    Internal users have global access and can manage system configuration.
    """
    return {"user_id": uuid4(), "role_type": "internal", "role_name": "admin", "institution_id": uuid4()}


@pytest.fixture
def sample_super_admin_user():
    """Super Admin user (role_type='internal', role_name='super_admin') for testing.

    Super Admins have global access (via Internal role_type) plus special
    approval permissions (via role_name='super_admin').
    """
    return {"user_id": uuid4(), "role_type": "internal", "role_name": "super_admin", "institution_id": uuid4()}


@pytest.fixture
def sample_supplier_user():
    """Supplier user (role_type='supplier', role_name='admin') for testing.

    Suppliers are scoped to their institution_id and cannot access
    system configuration APIs.
    """
    return {"user_id": uuid4(), "role_type": "supplier", "role_name": "admin", "institution_id": uuid4()}


@pytest.fixture
def sample_customer_user():
    """Customer user (role_type='customer', role_name='comensal') for testing.

    Customers access iOS/Android apps only and have limited backoffice access
    (e.g., viewing plans).
    """
    return {"user_id": uuid4(), "role_type": "customer", "role_name": "comensal", "institution_id": uuid4()}


# =============================================================================
# Vianda Pickup Fixtures
# =============================================================================


@pytest.fixture
def sample_pickup_record():
    """Sample ViandaPickupLiveDTO for testing."""
    from app.dto.models import ViandaPickupLiveDTO

    return ViandaPickupLiveDTO(
        vianda_pickup_id=uuid4(),
        vianda_selection_id=uuid4(),
        user_id=uuid4(),
        restaurant_id=uuid4(),
        product_id=uuid4(),
        qr_code_id=uuid4(),
        qr_code_payload="QR123456",
        is_archived=False,
        status="pending",
        created_date=datetime.now(UTC),
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


@pytest.fixture
def sample_qr_code():
    """Sample QRCodeDTO for testing."""
    from app.dto.models import QRCodeDTO

    return QRCodeDTO(
        qr_code_id=uuid4(),
        restaurant_id=uuid4(),
        qr_code_payload="restaurant_id:12345678-1234-1234-1234-1234567890ab",
        qr_code_image_url="http://localhost:8000/static/qr_codes/sample.png",
        image_storage_path="static/qr_codes/sample.png",
        qr_code_checksum="19f3c0f4f064b2fb601b53f1f4a6a3a053217a81d8427a7201da7dda4dd5c6d2",
        is_archived=False,
        status="active",
        created_date=datetime.now(UTC),
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


@pytest.fixture
def sample_restaurant():
    """Sample RestaurantDTO for testing."""
    from app.dto.models import RestaurantDTO

    return RestaurantDTO(
        restaurant_id=uuid4(),
        name="Test Restaurant",
        institution_id=uuid4(),
        is_archived=False,
        status="active",
        created_date=datetime.now(UTC),
        modified_date=datetime.now(UTC),
    )


@pytest.fixture
def sample_vianda_selection():
    """Sample ViandaSelectionDTO for testing."""
    from app.config import Status
    from app.dto.models import ViandaSelectionDTO

    return ViandaSelectionDTO(
        vianda_selection_id=uuid4(),
        user_id=uuid4(),
        vianda_id=uuid4(),
        restaurant_id=uuid4(),
        product_id=uuid4(),
        qr_code_id=uuid4(),
        credit=1,
        kitchen_day="monday",
        pickup_date=date.today(),
        pickup_time_range="12:00-12:15",
        pickup_intent="self",
        is_archived=False,
        status=Status.PENDING,
        created_date=datetime.now(UTC),
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


@pytest.fixture
def sample_vianda():
    """Sample ViandaDTO for testing."""
    from app.config import Status
    from app.dto.models import ViandaDTO

    return ViandaDTO(
        vianda_id=uuid4(),
        product_id=uuid4(),
        restaurant_id=uuid4(),
        price=Decimal("10.0"),
        credit=Decimal("5"),
        expected_payout_local_currency=Decimal("0"),
        delivery_time_minutes=15,
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.now(UTC),
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


@pytest.fixture
def sample_restaurant_transaction():
    """Sample RestaurantTransactionDTO for testing."""
    from app.dto.models import RestaurantTransactionDTO

    return RestaurantTransactionDTO(
        transaction_id=uuid4(),
        restaurant_id=uuid4(),
        vianda_selection_id=None,
        discretionary_id=None,
        currency_metadata_id=uuid4(),
        was_collected=False,
        ordered_timestamp=datetime.now(UTC),
        collected_timestamp=None,
        arrival_time=None,
        completion_time=None,
        expected_completion_time=None,
        transaction_type="order",
        credit=Decimal("5.0"),
        no_show_discount=Decimal("10.0"),
        currency_code="USD",
        final_amount=Decimal("5.0"),
        is_archived=False,
        status="pending",
        created_date=datetime.now(UTC),
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


# =============================================================================
# Business Logic Fixtures
# =============================================================================


@pytest.fixture
def sample_bill_data():
    """Sample client bill data for testing."""
    return {"currency_metadata_id": str(uuid4()), "amount": 25.50, "status": "pending"}


@pytest.fixture
def sample_credit_currency_dto():
    """Sample CreditCurrencyDTO for testing."""
    from app.dto.models import CreditCurrencyDTO

    return CreditCurrencyDTO(
        currency_metadata_id=uuid4(),
        currency_code="USD",
        credit_value_supplier_local=Decimal("1.0"),
        currency_conversion_usd=Decimal("1.0"),
        is_archived=False,
        status="active",
        created_date=datetime.now(UTC),
        modified_by=uuid4(),
        modified_date=datetime.now(UTC),
    )


@pytest.fixture
def sample_address_data():
    """Sample address data for testing."""
    return {
        "building_number": "123",
        "street_name": "Main St",
        "city": "New York",
        "province": "NY",
        "country": "US",
        "address_type": "restaurant",
    }


# =============================================================================
# Mock Utilities
# =============================================================================


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    mock_log = Mock()
    mock_log.info = Mock()
    mock_log.warning = Mock()
    mock_log.error = Mock()
    return mock_log


@pytest.fixture
def mock_geocoding_api():
    """Mock geocoding API response."""
    return {"latitude": 40.7128, "longitude": -74.0060, "status": "success"}


@pytest.fixture
def mock_failed_geocoding_api():
    """Mock failed geocoding API response."""
    return {"status": "error", "message": "Address not found"}


# =============================================================================
# Service Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_user_service():
    """Mock user service for testing."""
    return Mock()


@pytest.fixture
def mock_credit_currency_service():
    """Mock credit currency service for testing."""
    return Mock()


@pytest.fixture
def mock_address_service():
    """Mock address service for testing."""
    return Mock()


@pytest.fixture
def mock_geolocation_service():
    """Mock geolocation service for testing."""
    return Mock()


@pytest.fixture
def mock_vianda_pickup_live_service():
    """Mock vianda pickup live service for testing."""
    return Mock()


@pytest.fixture
def mock_qr_code_service():
    """Mock QR code service for testing."""
    return Mock()


@pytest.fixture
def mock_restaurant_service():
    """Mock restaurant service for testing."""
    return Mock()


# =============================================================================
# Test Utilities
# =============================================================================


def create_mock_dto(dto_class, **kwargs):
    """Create a mock DTO with default values."""
    defaults = {"is_archived": False, "created_date": datetime.now(UTC), "modified_date": datetime.now(UTC)}
    defaults.update(kwargs)
    return dto_class(**defaults)


def assert_http_exception(exc_info, expected_status_code, expected_detail_contains=None):
    """Assert HTTPException properties."""
    from fastapi import HTTPException

    assert isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == expected_status_code

    if expected_detail_contains:
        assert expected_detail_contains in str(exc_info.value.detail)


def mock_service_method(service, method_name, return_value=None, side_effect=None):
    """Helper to mock service methods."""
    if side_effect:
        setattr(service, method_name, Mock(side_effect=side_effect))
    else:
        setattr(service, method_name, Mock(return_value=return_value))


# =============================================================================
# Pytest Configuration
# =============================================================================


def pytest_configure(config):
    """Configure pytest settings."""
    # Add custom markers
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers."""
    for item in items:
        # Add unit marker to all tests by default
        if "unit" not in item.keywords and "integration" not in item.keywords:
            item.add_marker(pytest.mark.unit)
