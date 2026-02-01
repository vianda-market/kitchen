"""
Unit tests for Entity Service.

Tests the business logic for entity-specific operations including
user lookups, product filtering, and business rule enforcement.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import UUID, uuid4
from datetime import datetime
from fastapi import HTTPException

from app.services.entity_service import (
    get_user_by_username, get_products_by_institution, 
    get_plates_by_restaurant, get_bills_by_status,
    get_employers_by_name
)
from app.dto.models import UserDTO, ProductDTO, PlateDTO, InstitutionBillDTO, EmployerDTO
from app.config import Status, RoleType, RoleName


class TestEntityService:
    """Test suite for Entity Service business logic."""

    def test_get_user_by_username_returns_user_when_found(self, mock_db):
        """Test that get_user_by_username returns user when found."""
        # Arrange
        username = "testuser"
        mock_user_data = {
            "user_id": uuid4(),
            "username": username,
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "institution_id": uuid4(),
            "role_type": RoleType.CUSTOMER,
            "role_name": RoleName.COMENSAL,
            "hashed_password": "hashed_password",
            "is_archived": False,
            "status": Status.ACTIVE,
            "created_date": datetime.utcnow(),
            "modified_by": uuid4(),
            "modified_date": datetime.utcnow()
        }
        
        with patch('app.services.entity_service.user_service') as mock_user_service:
            mock_user_service.get_by_field.return_value = UserDTO(**mock_user_data)
            
            # Act
            result = get_user_by_username(username, mock_db)
            
            # Assert
            assert result is not None
            assert result.username == username
            assert result.email == "test@example.com"
            mock_user_service.get_by_field.assert_called_once_with("username", username, mock_db, scope=None)

    def test_get_user_by_username_returns_none_when_not_found(self, mock_db):
        """Test that get_user_by_username returns None when user not found."""
        # Arrange
        username = "nonexistent"
        
        with patch('app.services.entity_service.user_service') as mock_user_service:
            mock_user_service.get_by_field.return_value = None
            
            # Act
            result = get_user_by_username(username, mock_db)
            
            # Assert
            assert result is None
            mock_user_service.get_by_field.assert_called_once_with("username", username, mock_db, scope=None)

    def test_get_user_by_username_handles_database_error(self, mock_db):
        """Test that get_user_by_username handles database errors gracefully."""
        # Arrange
        username = "testuser"
        
        with patch('app.services.entity_service.user_service') as mock_user_service:
            mock_user_service.get_by_field.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                get_user_by_username(username, mock_db)
            
            assert exc_info.value.status_code == 500
            assert "Failed to get user by username" in str(exc_info.value.detail)

    def test_get_products_by_institution_filters_correctly(self, mock_db):
        """Test that get_products_by_institution filters products by institution."""
        # Arrange
        institution_id = uuid4()
        other_institution_id = uuid4()
        
        # Create mock ProductDTOs
        mock_products = [
            ProductDTO(
                product_id=uuid4(),
                institution_id=institution_id,
                name="Product 1",
                status="Active",
                modified_by=uuid4(),
                is_archived=False,
                image_url="http://localhost:8000/static/placeholders/product_default.png",
                image_storage_path="static/placeholders/product_default.png",
                image_checksum="7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
                created_date=datetime.utcnow(),
                modified_date=datetime.utcnow()
            ),
            ProductDTO(
                product_id=uuid4(),
                institution_id=other_institution_id,  # Different institution
                name="Product 2",
                status="Active",
                modified_by=uuid4(),
                is_archived=False,
                image_url="http://localhost:8000/static/placeholders/product_default.png",
                image_storage_path="static/placeholders/product_default.png",
                image_checksum="7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
                created_date=datetime.utcnow(),
                modified_date=datetime.utcnow()
            ),
            ProductDTO(
                product_id=uuid4(),
                institution_id=institution_id,
                name="Product 3",
                status="Active",
                modified_by=uuid4(),
                is_archived=False,
                image_url="http://localhost:8000/static/placeholders/product_default.png",
                image_storage_path="static/placeholders/product_default.png",
                image_checksum="7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
                created_date=datetime.utcnow(),
                modified_date=datetime.utcnow()
            )
        ]
        
        with patch('app.services.entity_service.product_service') as mock_product_service:
            mock_product_service.get_all.return_value = mock_products
            
            # Act
            result = get_products_by_institution(institution_id, mock_db)
            
            # Assert
            assert len(result) == 2
            assert all(product.institution_id == institution_id for product in result)
            assert result[0].name == "Product 1"  # Sorted by name
            assert result[1].name == "Product 3"

    def test_get_products_by_institution_handles_no_products(self, mock_db):
        """Test that get_products_by_institution handles no products found."""
        # Arrange
        institution_id = uuid4()
        
        with patch('app.services.entity_service.product_service') as mock_product_service:
            mock_product_service.get_all.return_value = []
            
            # Act
            result = get_products_by_institution(institution_id, mock_db)
            
            # Assert
            assert result == []

    def test_get_plates_by_restaurant_filters_correctly(self, mock_db):
        """Test that get_plates_by_restaurant filters plates by restaurant."""
        # Arrange
        restaurant_id = uuid4()
        other_restaurant_id = uuid4()
        
        # Create mock PlateDTOs
        mock_plates = [
            PlateDTO(
                plate_id=uuid4(),
                restaurant_id=restaurant_id,
                product_id=uuid4(),
                price=10.0,
                credit=5,
                savings=2,
                no_show_discount=10,
                delivery_time_minutes=15,
                status="Active",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.utcnow(),
                modified_date=datetime.utcnow()
            ),
            PlateDTO(
                plate_id=uuid4(),
                restaurant_id=other_restaurant_id,  # Different restaurant
                product_id=uuid4(),
                price=15.0,
                credit=7,
                savings=3,
                no_show_discount=15,
                delivery_time_minutes=20,
                status="Active",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.utcnow(),
                modified_date=datetime.utcnow()
            ),
            PlateDTO(
                plate_id=uuid4(),
                restaurant_id=restaurant_id,
                product_id=uuid4(),
                price=8.0,
                credit=4,
                savings=1,
                no_show_discount=5,
                delivery_time_minutes=10,
                status="Active",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.utcnow(),
                modified_date=datetime.utcnow()
            )
        ]
        
        with patch('app.services.entity_service.plate_service') as mock_plate_service:
            mock_plate_service.get_all.return_value = mock_plates
            
            # Act
            result = get_plates_by_restaurant(restaurant_id, mock_db)
            
            # Assert
            assert len(result) == 2
            assert all(plate.restaurant_id == restaurant_id for plate in result)
            assert result[0].price == 8.0  # Sorted by price (8.0)
            assert result[1].price == 10.0  # Sorted by price (10.0)

    def test_get_plates_by_restaurant_handles_no_plates(self, mock_db):
        """Test that get_plates_by_restaurant handles no plates found."""
        # Arrange
        restaurant_id = uuid4()
        
        with patch('app.services.entity_service.plate_service') as mock_plate_service:
            mock_plate_service.get_all.return_value = []
            
            # Act
            result = get_plates_by_restaurant(restaurant_id, mock_db)
            
            # Assert
            assert result == []

    def test_get_bills_by_status_filters_correctly(self, mock_db):
        """Test that get_bills_by_status filters bills by status."""
        # Arrange
        institution_id = uuid4()
        status = "Pending"
        
        # Create mock InstitutionBillDTOs
        mock_bills = [
            InstitutionBillDTO(
                institution_bill_id=uuid4(),
                institution_id=institution_id,
                institution_entity_id=institution_id,
                restaurant_id=uuid4(),
                credit_currency_id=uuid4(),
                status=status,
                period_start=datetime.utcnow(),
                period_end=datetime.utcnow(),
                resolution="Monthly",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.utcnow(),
                modified_date=datetime.utcnow()
            ),
            InstitutionBillDTO(
                institution_bill_id=uuid4(),
                institution_id=institution_id,
                institution_entity_id=institution_id,
                restaurant_id=uuid4(),
                credit_currency_id=uuid4(),
                status=Status.PROCESSED,  # Different status
                period_start=datetime.utcnow(),
                period_end=datetime.utcnow(),
                resolution="Monthly",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.utcnow(),
                modified_date=datetime.utcnow()
            ),
            InstitutionBillDTO(
                institution_bill_id=uuid4(),
                institution_id=institution_id,
                institution_entity_id=institution_id,
                restaurant_id=uuid4(),
                credit_currency_id=uuid4(),
                status=status,
                period_start=datetime.utcnow(),
                period_end=datetime.utcnow(),
                resolution="Monthly",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.utcnow(),
                modified_date=datetime.utcnow()
            )
        ]
        
        with patch('app.services.entity_service.institution_bill_service') as mock_bill_service:
            mock_bill_service.get_all.return_value = mock_bills
            
            # Act
            result = get_bills_by_status(institution_id, status, mock_db)
            
            # Assert
            assert len(result) == 2
            assert all(bill.institution_entity_id == institution_id for bill in result)
            assert all(bill.status == status for bill in result)

    def test_get_bills_by_status_handles_no_bills(self, mock_db):
        """Test that get_bills_by_status handles no bills found."""
        # Arrange
        institution_id = uuid4()
        status = "Pending"
        
        with patch('app.services.entity_service.institution_bill_service') as mock_bill_service:
            mock_bill_service.get_all.return_value = []
            
            # Act
            result = get_bills_by_status(institution_id, status, mock_db)
            
            # Assert
            assert result == []

    def test_get_employers_by_name_returns_employers_when_found(self, mock_db):
        """Test that get_employers_by_name returns employers when found."""
        # Arrange
        employer_name = "Test Company"
        mock_employers = [
            EmployerDTO(
                employer_id=uuid4(),
                name=employer_name,
                address_id=uuid4(),
                status="Active",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.utcnow(),
                modified_date=datetime.utcnow()
            )
        ]
        
        with patch('app.services.entity_service.employer_service') as mock_employer_service:
            mock_employer_service.get_all.return_value = mock_employers
            
            # Act
            result = get_employers_by_name(employer_name, mock_db)
            
            # Assert
            assert len(result) == 1
            assert result[0].name == employer_name

    def test_get_employers_by_name_returns_empty_when_not_found(self, mock_db):
        """Test that get_employers_by_name returns empty list when employer not found."""
        # Arrange
        employer_name = "Nonexistent Company"
        
        with patch('app.services.entity_service.employer_service') as mock_employer_service:
            mock_employer_service.get_all.return_value = []
            
            # Act
            result = get_employers_by_name(employer_name, mock_db)
            
            # Assert
            assert result == []

    def test_get_employers_by_name_handles_database_error(self, mock_db):
        """Test that get_employers_by_name handles database errors gracefully."""
        # Arrange
        employer_name = "Test Company"
        
        with patch('app.services.entity_service.employer_service') as mock_employer_service:
            mock_employer_service.get_all.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                get_employers_by_name(employer_name, mock_db)
            
            assert exc_info.value.status_code == 500
            assert "Failed to search employers" in str(exc_info.value.detail)

    def test_get_products_by_institution_handles_service_error(self, mock_db):
        """Test that get_products_by_institution handles service errors gracefully."""
        # Arrange
        institution_id = uuid4()
        
        with patch('app.services.entity_service.product_service') as mock_product_service:
            mock_product_service.get_all.side_effect = Exception("Service error")
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                get_products_by_institution(institution_id, mock_db)
            
            assert exc_info.value.status_code == 500
            assert "Failed to get products for institution" in str(exc_info.value.detail)

    def test_get_plates_by_restaurant_handles_service_error(self, mock_db):
        """Test that get_plates_by_restaurant handles service errors gracefully."""
        # Arrange
        restaurant_id = uuid4()
        
        with patch('app.services.entity_service.plate_service') as mock_plate_service:
            mock_plate_service.get_all.side_effect = Exception("Service error")
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                get_plates_by_restaurant(restaurant_id, mock_db)
            
            assert exc_info.value.status_code == 500
            assert "Failed to get plates for restaurant" in str(exc_info.value.detail)

    def test_get_bills_by_status_handles_service_error(self, mock_db):
        """Test that get_bills_by_status handles service errors gracefully."""
        # Arrange
        institution_id = uuid4()
        status = "Pending"
        
        with patch('app.services.entity_service.institution_bill_service') as mock_bill_service:
            mock_bill_service.get_all.side_effect = Exception("Service error")
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                get_bills_by_status(institution_id, status, mock_db)
            
            assert exc_info.value.status_code == 500
            assert "Failed to get bills for institution" in str(exc_info.value.detail)
