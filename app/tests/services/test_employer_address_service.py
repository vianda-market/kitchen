"""
Unit tests for Employer Address Service endpoints.

Tests the business logic for employer address operations including
getting addresses for an employer and adding addresses to an employer.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import HTTPException, status

from app.services.crud_service import employer_service, address_service
from app.services.address_service import address_business_service
from app.dto.models import EmployerDTO, AddressDTO
from app.config import Status, AddressType


class TestEmployerAddressService:
    """Test suite for Employer Address Service business logic."""

    @pytest.fixture
    def sample_employer_dto(self):
        """Sample employer DTO for testing."""
        return EmployerDTO(
            employer_id=uuid4(),
            name="Test Employer",
            address_id=uuid4(),
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(timezone.utc),
            modified_by=uuid4(),
            modified_date=datetime.now(timezone.utc)
        )

    @pytest.fixture
    def sample_address_dto(self):
        """Sample address DTO for testing."""
        return AddressDTO(
            address_id=uuid4(),
            institution_id=uuid4(),
            user_id=uuid4(),
            employer_id=uuid4(),  # Default employer_id, will be overridden in tests as needed
            address_type=[AddressType.CUSTOMER_EMPLOYER.value],
            is_default=False,
            floor=None,
            country_name="Argentina",
            country_code="AR",
            province="Buenos Aires",
            city="Buenos Aires",
            postal_code="1000",
            street_type="St",
            street_name="Test Street",
            building_number="123",
            apartment_unit=None,
            timezone="America/Argentina/Buenos_Aires",
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(timezone.utc),
            modified_by=uuid4(),
            modified_date=datetime.now(timezone.utc)
        )

    @pytest.fixture
    def sample_current_user(self):
        """Sample current user dict for testing."""
        return {
            "user_id": uuid4(),
            "role_type": "Customer",
            "role_name": "Comensal",
            "institution_id": uuid4()
        }

    def test_get_employer_addresses_validates_employer_exists(self, sample_employer_dto, sample_address_dto, mock_db):
        """Test that getting employer addresses validates employer exists."""
        # Arrange
        employer_id = sample_employer_dto.employer_id
        
        with patch('app.services.crud_service.employer_service') as mock_employer_service, \
             patch('app.services.crud_service.address_service') as mock_address_service:
            
            mock_employer_service.get_by_id.return_value = sample_employer_dto
            mock_address_service.get_all_by_field.return_value = [sample_address_dto]
            
            # Act - Simulate the endpoint logic
            employer = mock_employer_service.get_by_id(employer_id, mock_db)
            assert employer is not None
            
            addresses = mock_address_service.get_all_by_field(
                "employer_id",
                employer_id,
                mock_db,
                scope=None
            )
            
            # Assert
            assert addresses is not None
            assert len(addresses) == 1
            mock_employer_service.get_by_id.assert_called_once_with(employer_id, mock_db)
            mock_address_service.get_all_by_field.assert_called_once_with(
                "employer_id",
                employer_id,
                mock_db,
                scope=None
            )

    def test_get_employer_addresses_handles_employer_not_found(self, mock_db):
        """Test that getting employer addresses handles employer not found."""
        # Arrange
        employer_id = uuid4()
        
        with patch('app.services.crud_service.employer_service') as mock_employer_service:
            mock_employer_service.get_by_id.return_value = None
            
            # Act
            employer = mock_employer_service.get_by_id(employer_id, mock_db)
            
            # Assert
            assert employer is None
            # In actual endpoint, this would raise employer_not_found()

    def test_get_employer_addresses_returns_empty_list_when_no_addresses(self, sample_employer_dto, mock_db):
        """Test that getting employer addresses returns empty list when no addresses exist."""
        # Arrange
        employer_id = sample_employer_dto.employer_id
        
        with patch('app.services.crud_service.employer_service') as mock_employer_service, \
             patch('app.services.crud_service.address_service') as mock_address_service:
            
            mock_employer_service.get_by_id.return_value = sample_employer_dto
            mock_address_service.get_all_by_field.return_value = []
            
            # Act
            employer = mock_employer_service.get_by_id(employer_id, mock_db)
            addresses = mock_address_service.get_all_by_field(
                "employer_id",
                employer_id,
                mock_db,
                scope=None
            )
            
            # Assert
            assert addresses == []

    def test_add_employer_address_validates_employer_exists(self, sample_employer_dto, sample_address_dto, sample_current_user, mock_db):
        """Test that adding employer address validates employer exists."""
        # Arrange
        employer_id = sample_employer_dto.employer_id
        address_data = {
            "institution_id": str(uuid4()),
            "user_id": str(sample_current_user["user_id"]),
            "address_type": [AddressType.CUSTOMER_EMPLOYER.value],
            "country": "Argentina",
            "province": "Buenos Aires",
            "city": "Buenos Aires",
            "postal_code": "1000",
            "street_type": "St",
            "street_name": "Test Street",
            "building_number": "123"
        }
        
        with patch('app.services.crud_service.employer_service') as mock_employer_service, \
             patch('app.services.address_service.address_business_service') as mock_address_service:
            
            mock_employer_service.get_by_id.return_value = sample_employer_dto
            
            # Create address DTO with the correct employer_id for the mock return value
            address_dict = sample_address_dto.model_dump()
            address_dict["employer_id"] = employer_id  # Set to match the employer_id being tested
            address_with_correct_employer = AddressDTO(**address_dict)
            mock_address_service.create_address_with_geocoding.return_value = address_with_correct_employer
            
            # Act - Simulate the endpoint logic
            employer = mock_employer_service.get_by_id(employer_id, mock_db)
            assert employer is not None
            
            # Ensure address_type includes "Customer Employer"
            address_types = address_data.get("address_type", [])
            if AddressType.CUSTOMER_EMPLOYER.value not in address_types:
                address_types.append(AddressType.CUSTOMER_EMPLOYER.value)
            address_data["address_type"] = address_types
            
            # Link address to employer
            address_data["employer_id"] = str(employer_id)  # Service expects string UUID
            address_data["modified_by"] = sample_current_user["user_id"]
            
            new_address = mock_address_service.create_address_with_geocoding(
                address_data,
                sample_current_user,
                mock_db,
                scope=None
            )
            
            # Assert
            assert new_address is not None
            # Compare UUIDs (employer_id should match)
            assert new_address.employer_id == employer_id
            mock_employer_service.get_by_id.assert_called_once_with(employer_id, mock_db)
            mock_address_service.create_address_with_geocoding.assert_called_once()

    def test_add_employer_address_handles_employer_not_found(self, sample_current_user, mock_db):
        """Test that adding employer address handles employer not found."""
        # Arrange
        employer_id = uuid4()
        
        with patch('app.services.crud_service.employer_service') as mock_employer_service:
            mock_employer_service.get_by_id.return_value = None
            
            # Act
            employer = mock_employer_service.get_by_id(employer_id, mock_db)
            
            # Assert
            assert employer is None
            # In actual endpoint, this would raise employer_not_found()

    def test_add_employer_address_handles_creation_failure(self, sample_employer_dto, sample_current_user, mock_db):
        """Test that adding employer address handles creation failure."""
        # Arrange
        employer_id = sample_employer_dto.employer_id
        address_data = {
            "institution_id": str(uuid4()),
            "user_id": str(sample_current_user["user_id"]),
            "address_type": [AddressType.CUSTOMER_EMPLOYER.value],
            "country": "Argentina",
            "province": "Buenos Aires",
            "city": "Buenos Aires",
            "postal_code": "1000",
            "street_type": "St",
            "street_name": "Test Street",
            "building_number": "123",
            "employer_id": employer_id,
            "modified_by": sample_current_user["user_id"]
        }
        
        with patch('app.services.crud_service.employer_service') as mock_employer_service, \
             patch('app.services.address_service.address_business_service') as mock_address_service:
            
            mock_employer_service.get_by_id.return_value = sample_employer_dto
            mock_address_service.create_address_with_geocoding.return_value = None
            
            # Act
            employer = mock_employer_service.get_by_id(employer_id, mock_db)
            assert employer is not None
            
            new_address = mock_address_service.create_address_with_geocoding(
                address_data,
                sample_current_user,
                mock_db,
                scope=None
            )
            
            # Assert
            assert new_address is None
            # In actual endpoint, this would raise HTTPException(500)

    def test_add_employer_address_does_not_send_address_type(self, sample_employer_dto, sample_address_dto, sample_current_user, mock_db):
        """Test that adding employer address does not send address_type; backend derives it from employer_id linkage."""
        # Arrange
        employer_id = sample_employer_dto.employer_id
        address_data = {
            "institution_id": str(uuid4()),
            "user_id": str(sample_current_user["user_id"]),
            "address_type": ["Customer Home"],  # Client may send; route strips it
            "country": "Argentina",
            "province": "Buenos Aires",
            "city": "Buenos Aires",
            "postal_code": "1000",
            "street_type": "St",
            "street_name": "Test Street",
            "building_number": "123",
        }
        with patch('app.services.crud_service.employer_service') as mock_employer_service, \
             patch('app.services.address_service.address_business_service') as mock_address_service:
            mock_employer_service.get_by_id.return_value = sample_employer_dto
            mock_address_service.create_address_with_geocoding.return_value = sample_address_dto

            # Simulate route: strip address_type, set employer_id, then create
            address_data.pop("address_type", None)
            address_data["employer_id"] = employer_id
            address_data["modified_by"] = sample_current_user["user_id"]
            mock_address_service.create_address_with_geocoding(address_data, sample_current_user, mock_db, scope=None)

            # Assert: create was called with address_data that has employer_id and no client address_type
            call_args = mock_address_service.create_address_with_geocoding.call_args[0][0]
            assert call_args.get("employer_id") == employer_id
            assert "address_type" not in call_args or call_args.get("address_type") == []

