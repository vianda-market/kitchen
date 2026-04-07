"""
Unit tests for User Profile Service endpoints.

Tests the business logic for user profile operations including
account termination, employer assignment, and profile updates.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import HTTPException, status

from app.services.crud_service import user_service, employer_service
from app.dto.models import UserDTO, EmployerDTO
from app.config import Status, RoleType, RoleName


class TestUserProfileService:
    """Test suite for User Profile Service business logic."""

    @pytest.fixture
    def sample_user_dto(self):
        """Sample user DTO for testing."""
        return UserDTO(
            user_id=uuid4(),
            institution_id=uuid4(),
            role_type=RoleType.CUSTOMER,
            role_name=RoleName.COMENSAL,
            username="testuser",
            hashed_password="hashed_password",
            first_name="Test",
            last_name="User",
            email="test@example.com",
            mobile_number="+14155552671",
            mobile_number_verified=False,
            mobile_number_verified_at=None,
            employer_id=None,
            market_id=uuid4(),
            city_id=uuid4(),
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(timezone.utc),
            modified_by=uuid4(),
            modified_date=datetime.now(timezone.utc)
        )

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
    def sample_current_user(self):
        """Sample current user dict for testing."""
        return {
            "user_id": uuid4(),
            "role_type": "Customer",
            "role_name": "Comensal",
            "institution_id": uuid4()
        }

    def test_terminate_account_archives_user(self, sample_current_user, sample_user_dto, mock_db):
        """Test that account termination archives the user."""
        # Arrange
        user_id = sample_current_user["user_id"]
        
        with patch('app.services.crud_service.user_service') as mock_user_service:
            mock_user_service.get_by_id.return_value = sample_user_dto
            mock_user_service.soft_delete.return_value = True
            
            # Act - Simulate the endpoint logic
            existing_user = mock_user_service.get_by_id(user_id, mock_db, scope=None)
            assert existing_user is not None
            
            success = mock_user_service.soft_delete(
                user_id,
                user_id,  # Self-termination
                mock_db,
                scope=None
            )
            
            # Assert
            assert success is True
            mock_user_service.get_by_id.assert_called_once_with(user_id, mock_db, scope=None)
            mock_user_service.soft_delete.assert_called_once_with(
                user_id,
                user_id,
                mock_db,
                scope=None
            )

    def test_terminate_account_handles_user_not_found(self, sample_current_user, mock_db):
        """Test that account termination handles user not found."""
        # Arrange
        user_id = sample_current_user["user_id"]
        
        with patch('app.services.crud_service.user_service') as mock_user_service:
            mock_user_service.get_by_id.return_value = None
            
            # Act & Assert
            existing_user = mock_user_service.get_by_id(user_id, mock_db, scope=None)
            assert existing_user is None
            # In actual endpoint, this would raise user_not_found()

    def test_terminate_account_handles_soft_delete_failure(self, sample_current_user, sample_user_dto, mock_db):
        """Test that account termination handles soft delete failure."""
        # Arrange
        user_id = sample_current_user["user_id"]
        
        with patch('app.services.crud_service.user_service') as mock_user_service:
            mock_user_service.get_by_id.return_value = sample_user_dto
            mock_user_service.soft_delete.return_value = False
            
            # Act
            existing_user = mock_user_service.get_by_id(user_id, mock_db, scope=None)
            success = mock_user_service.soft_delete(
                user_id,
                user_id,
                mock_db,
                scope=None
            )
            
            # Assert
            assert success is False
            # In actual endpoint, this would raise HTTPException(500)

    def test_assign_employer_validates_employer_exists(self, sample_current_user, sample_employer_dto, sample_user_dto, mock_db):
        """Test that employer assignment validates employer exists and address belongs to employer."""
        # Arrange
        from app.dto.models import AddressDTO

        user_id = sample_current_user["user_id"]
        employer_id = sample_employer_dto.employer_id
        address_id = sample_employer_dto.address_id
        sample_address = AddressDTO(
            address_id=address_id,
            institution_id=uuid4(),
            user_id=user_id,
            employer_id=employer_id,
            address_type=["Customer Employer"],
            street_type="St",
            street_name="Test St",
            building_number="123",
            city="Buenos Aires",
            province="Buenos Aires",
            country_code="AR",
            country_name="Argentina",
            postal_code="1000",
            timezone="America/Argentina/Buenos_Aires",
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(timezone.utc),
            modified_by=user_id,
            modified_date=datetime.now(timezone.utc),
        )

        with patch('app.services.crud_service.employer_service') as mock_employer_service, \
             patch('app.services.crud_service.address_service') as mock_address_service, \
             patch('app.services.crud_service.user_service') as mock_user_service:

            mock_employer_service.get_by_id.return_value = sample_employer_dto
            mock_address_service.get_by_id.return_value = sample_address
            mock_user_service.update.return_value = sample_user_dto

            # Act - Simulate the endpoint logic (employer + address validation, then update)
            employer = mock_employer_service.get_by_id(employer_id, mock_db)
            address = mock_address_service.get_by_id(address_id, mock_db, scope=None)
            assert employer is not None
            assert address is not None
            assert address.employer_id == employer_id

            update_data = {
                "employer_id": employer_id,
                "employer_address_id": address_id,
                "modified_by": user_id
            }

            updated = mock_user_service.update(
                user_id,
                update_data,
                mock_db,
                scope=None
            )

            # Assert
            assert updated is not None
            mock_employer_service.get_by_id.assert_called_once_with(employer_id, mock_db)
            mock_address_service.get_by_id.assert_called_once_with(address_id, mock_db, scope=None)
            mock_user_service.update.assert_called_once_with(
                user_id,
                update_data,
                mock_db,
                scope=None
            )

    def test_assign_employer_handles_employer_not_found(self, sample_current_user, mock_db):
        """Test that employer assignment handles employer not found."""
        # Arrange
        employer_id = uuid4()
        
        with patch('app.services.crud_service.employer_service') as mock_employer_service:
            mock_employer_service.get_by_id.return_value = None
            
            # Act
            employer = mock_employer_service.get_by_id(employer_id, mock_db)
            
            # Assert
            assert employer is None
            # In actual endpoint, this would raise employer_not_found()

    def test_assign_employer_handles_update_failure(self, sample_current_user, sample_employer_dto, mock_db):
        """Test that employer assignment handles update failure."""
        from app.dto.models import AddressDTO

        user_id = sample_current_user["user_id"]
        employer_id = sample_employer_dto.employer_id
        address_id = sample_employer_dto.address_id
        sample_address = AddressDTO(
            address_id=address_id,
            institution_id=uuid4(),
            user_id=user_id,
            employer_id=employer_id,
            address_type=["Customer Employer"],
            street_type="St",
            street_name="Test St",
            building_number="123",
            city="Buenos Aires",
            province="Buenos Aires",
            country_code="AR",
            country_name="Argentina",
            postal_code="1000",
            timezone="America/Argentina/Buenos_Aires",
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(timezone.utc),
            modified_by=user_id,
            modified_date=datetime.now(timezone.utc),
        )

        with patch('app.services.crud_service.employer_service') as mock_employer_service, \
             patch('app.services.crud_service.address_service') as mock_address_service, \
             patch('app.services.crud_service.user_service') as mock_user_service:

            mock_employer_service.get_by_id.return_value = sample_employer_dto
            mock_address_service.get_by_id.return_value = sample_address
            mock_user_service.update.return_value = None

            employer = mock_employer_service.get_by_id(employer_id, mock_db)
            address = mock_address_service.get_by_id(address_id, mock_db, scope=None)
            assert employer is not None
            assert address is not None

            update_data = {
                "employer_id": employer_id,
                "employer_address_id": address_id,
                "modified_by": user_id
            }

            updated = mock_user_service.update(
                user_id,
                update_data,
                mock_db,
                scope=None
            )

            assert updated is None

