"""
Shared test fixtures and configuration.

This file contains common fixtures, mocks, and test utilities
that are shared across all test modules.
"""

import pytest
from unittest.mock import Mock, MagicMock
from uuid import UUID, uuid4
from datetime import datetime
from decimal import Decimal
import psycopg2.extensions


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

@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "plaintext123",
        "first_name": "John",
        "last_name": "Doe",
        "username": "johndoe"
    }


@pytest.fixture
def sample_current_user():
    """Sample current user for testing."""
    return {
        "user_id": str(uuid4()),
        "username": "admin",
        "email": "admin@example.com"
    }


@pytest.fixture
def sample_user_dto():
    """Sample UserDTO for testing."""
    from app.dto.models import UserDTO
    from app.config import Status, RoleType, RoleName
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
        is_archived=False,
        status=Status.ACTIVE,
        created_date=datetime.utcnow(),
        modified_by=uuid4(),
        modified_date=datetime.utcnow()
    )


# =============================================================================
# Permission & Role-Based Access Control Fixtures
# =============================================================================

@pytest.fixture
def sample_employee_user():
    """Employee user (role_type='Employee', role_name='Admin') for testing.
    
    Employees have global access and can manage system configuration.
    """
    return {
        "user_id": uuid4(),
        "role_type": "Employee",
        "role_name": "Admin",
        "institution_id": uuid4()
    }


@pytest.fixture
def sample_super_admin_user():
    """Super Admin user (role_type='Employee', role_name='Super Admin') for testing.
    
    Super Admins have global access (via Employee role_type) plus special
    approval permissions (via role_name='Super Admin').
    """
    return {
        "user_id": uuid4(),
        "role_type": "Employee",
        "role_name": "Super Admin",
        "institution_id": uuid4()
    }


@pytest.fixture
def sample_supplier_user():
    """Supplier user (role_type='Supplier', role_name='Admin') for testing.
    
    Suppliers are scoped to their institution_id and cannot access
    system configuration APIs.
    """
    return {
        "user_id": uuid4(),
        "role_type": "Supplier",
        "role_name": "Admin",
        "institution_id": uuid4()
    }


@pytest.fixture
def sample_customer_user():
    """Customer user (role_type='Customer', role_name='Comensal') for testing.
    
    Customers access iOS/Android apps only and have limited backoffice access
    (e.g., viewing plans and fintech links).
    """
    return {
        "user_id": uuid4(),
        "role_type": "Customer",
        "role_name": "Comensal",
        "institution_id": uuid4()
    }


# =============================================================================
# Plate Pickup Fixtures
# =============================================================================

@pytest.fixture
def sample_pickup_record():
    """Sample PlatePickupLiveDTO for testing."""
    from app.dto.models import PlatePickupLiveDTO
    return PlatePickupLiveDTO(
        plate_pickup_id=uuid4(),
        plate_selection_id=uuid4(),
        user_id=uuid4(),
        restaurant_id=uuid4(),
        product_id=uuid4(),
        qr_code_id=uuid4(),
        qr_code_payload="QR123456",
        is_archived=False,
        status="Pending",
        created_date=datetime.utcnow(),
        modified_by=uuid4(),
        modified_date=datetime.utcnow()
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
        status="Active",
        created_date=datetime.utcnow(),
        modified_by=uuid4(),
        modified_date=datetime.utcnow()
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
        status="Active",
        created_date=datetime.utcnow(),
        modified_date=datetime.utcnow()
    )


@pytest.fixture
def sample_plate_selection():
    """Sample PlateSelectionDTO for testing."""
    from app.dto.models import PlateSelectionDTO
    return PlateSelectionDTO(
        plate_selection_id=uuid4(),
        user_id=uuid4(),
        plate_id=uuid4(),
        restaurant_id=uuid4(),
        is_archived=False,
        created_date=datetime.utcnow(),
        modified_date=datetime.utcnow()
    )


@pytest.fixture
def sample_plate():
    """Sample PlateDTO for testing."""
    from app.dto.models import PlateDTO
    return PlateDTO(
        plate_id=uuid4(),
        name="Test Plate",
        credit=5.0,
        delivery_time_minutes=15,
        no_show_discount=10.0,
        is_archived=False,
        created_date=datetime.utcnow(),
        modified_date=datetime.utcnow()
    )


@pytest.fixture
def sample_restaurant_transaction():
    """Sample RestaurantTransactionDTO for testing."""
    from app.dto.models import RestaurantTransactionDTO
    return RestaurantTransactionDTO(
        transaction_id=uuid4(),
        restaurant_id=uuid4(),
        plate_selection_id=None,
        discretionary_id=None,
        credit_currency_id=uuid4(),
        was_collected=False,
        ordered_timestamp=datetime.utcnow(),
        collected_timestamp=None,
        arrival_time=None,
        completion_time=None,
        expected_completion_time=None,
        transaction_type="Order",
        credit=Decimal("5.0"),
        no_show_discount=Decimal("10.0"),
        currency_code="USD",
        final_amount=Decimal("5.0"),
        is_archived=False,
        status="Pending",
        created_date=datetime.utcnow(),
        modified_by=uuid4(),
        modified_date=datetime.utcnow()
    )


# =============================================================================
# Business Logic Fixtures
# =============================================================================

@pytest.fixture
def sample_bill_data():
    """Sample client bill data for testing."""
    return {
        "credit_currency_id": str(uuid4()),
        "amount": 25.50,
        "status": "Pending"
    }


@pytest.fixture
def sample_credit_currency_dto():
    """Sample CreditCurrencyDTO for testing."""
    from app.dto.models import CreditCurrencyDTO
    return CreditCurrencyDTO(
        credit_currency_id=uuid4(),
        currency_name="Test Credits",
        currency_code="USD",
        credit_value=Decimal("1.0"),
        is_archived=False,
        status="Active",
        created_date=datetime.utcnow(),
        modified_by=uuid4(),
        modified_date=datetime.utcnow()
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
        "address_type": "restaurant"
    }


@pytest.fixture
def sample_bank_account_data():
    """Sample bank account data for testing."""
    return {
        "routing_number": "123456789",
        "account_number": "987654321",
        "institution_entity_id": str(uuid4()),
        "account_type": "Checking"
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
    return {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "status": "success"
    }


@pytest.fixture
def mock_failed_geocoding_api():
    """Mock failed geocoding API response."""
    return {
        "status": "error",
        "message": "Address not found"
    }


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
def mock_plate_pickup_live_service():
    """Mock plate pickup live service for testing."""
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
    defaults = {
        "is_archived": False,
        "created_date": datetime.utcnow(),
        "modified_date": datetime.utcnow()
    }
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
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers."""
    for item in items:
        # Add unit marker to all tests by default
        if "unit" not in item.keywords and "integration" not in item.keywords:
            item.add_marker(pytest.mark.unit)
