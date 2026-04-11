"""
Unit tests for Entity Service.

Tests the business logic for entity-specific operations including
user lookups, product filtering, and business rule enforcement.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import HTTPException

from app.services.entity_service import (
    get_user_by_username, get_user_by_email, get_products_by_institution,
    get_plates_by_restaurant, get_bills_by_status,
    get_employers_by_name,
    get_enriched_discretionary_requests,
    get_enriched_discretionary_request_by_id,
    search_users,
    search_restaurants,
    get_enriched_plates,
    get_enriched_plate_by_id,
)
from app.dto.models import UserDTO, ProductDTO, PlateDTO, InstitutionBillDTO, EmployerDTO
from app.config import Status, RoleType, RoleName
from decimal import Decimal


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
            "market_id": uuid4(),
            "is_archived": False,
            "status": Status.ACTIVE,
            "created_date": datetime.now(timezone.utc),
            "modified_by": uuid4(),
            "modified_date": datetime.now(timezone.utc)
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

    def test_get_user_by_username_normalizes_to_lowercase(self, mock_db):
        """Test that get_user_by_username normalizes username to lowercase before lookup."""
        # Arrange: user stored with lowercase username
        mock_user_data = {
            "user_id": uuid4(),
            "username": "testuser",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "institution_id": uuid4(),
            "role_type": RoleType.CUSTOMER,
            "role_name": RoleName.COMENSAL,
            "hashed_password": "hashed_password",
            "market_id": uuid4(),
            "is_archived": False,
            "status": Status.ACTIVE,
            "created_date": datetime.now(timezone.utc),
            "modified_by": uuid4(),
            "modified_date": datetime.now(timezone.utc)
        }
        with patch('app.services.entity_service.user_service') as mock_user_service:
            mock_user_service.get_by_field.return_value = UserDTO(**mock_user_data)
            # Act: pass mixed-case username
            result = get_user_by_username("TestUser", mock_db)
            # Assert: lookup used lowercase
            assert result is not None
            assert result.username == "testuser"
            mock_user_service.get_by_field.assert_called_once_with("username", "testuser", mock_db, scope=None)

    def test_get_user_by_email_normalizes_to_lowercase(self, mock_db):
        """Test that get_user_by_email normalizes email to lowercase before lookup."""
        mock_user_data = {
            "user_id": uuid4(),
            "username": "testuser",
            "email": "user@example.com",
            "first_name": "Test",
            "last_name": "User",
            "institution_id": uuid4(),
            "role_type": RoleType.CUSTOMER,
            "role_name": RoleName.COMENSAL,
            "hashed_password": "hashed_password",
            "market_id": uuid4(),
            "is_archived": False,
            "status": Status.ACTIVE,
            "created_date": datetime.now(timezone.utc),
            "modified_by": uuid4(),
            "modified_date": datetime.now(timezone.utc)
        }
        with patch('app.services.entity_service.user_service') as mock_user_service:
            mock_user_service.get_by_field.return_value = UserDTO(**mock_user_data)
            result = get_user_by_email("User@Example.com", mock_db)
            assert result is not None
            assert result.email == "user@example.com"
            mock_user_service.get_by_field.assert_called_once_with("email", "user@example.com", mock_db, scope=None)

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
                status="active",
                modified_by=uuid4(),
                is_archived=False,
                image_url="http://localhost:8000/static/placeholders/product_default.png",
                image_storage_path="static/placeholders/product_default.png",
                image_thumbnail_url="http://localhost:8000/static/placeholders/product_default.png",
                image_thumbnail_storage_path="static/placeholders/product_default.png",
                image_checksum="7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
                created_date=datetime.now(timezone.utc),
                modified_date=datetime.now(timezone.utc)
            ),
            ProductDTO(
                product_id=uuid4(),
                institution_id=other_institution_id,  # Different institution
                name="Product 2",
                status="active",
                modified_by=uuid4(),
                is_archived=False,
                image_url="http://localhost:8000/static/placeholders/product_default.png",
                image_storage_path="static/placeholders/product_default.png",
                image_thumbnail_url="http://localhost:8000/static/placeholders/product_default.png",
                image_thumbnail_storage_path="static/placeholders/product_default.png",
                image_checksum="7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
                created_date=datetime.now(timezone.utc),
                modified_date=datetime.now(timezone.utc)
            ),
            ProductDTO(
                product_id=uuid4(),
                institution_id=institution_id,
                name="Product 3",
                status="active",
                modified_by=uuid4(),
                is_archived=False,
                image_url="http://localhost:8000/static/placeholders/product_default.png",
                image_storage_path="static/placeholders/product_default.png",
                image_thumbnail_url="http://localhost:8000/static/placeholders/product_default.png",
                image_thumbnail_storage_path="static/placeholders/product_default.png",
                image_checksum="7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
                created_date=datetime.now(timezone.utc),
                modified_date=datetime.now(timezone.utc)
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
                price=Decimal("10.0"),
                credit=Decimal("5"),
                expected_payout_local_currency=Decimal("0"),
                delivery_time_minutes=15,
                status="active",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.now(timezone.utc),
                modified_date=datetime.now(timezone.utc)
            ),
            PlateDTO(
                plate_id=uuid4(),
                restaurant_id=other_restaurant_id,  # Different restaurant
                product_id=uuid4(),
                price=Decimal("15.0"),
                credit=Decimal("7"),
                expected_payout_local_currency=Decimal("0"),
                delivery_time_minutes=20,
                status="active",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.now(timezone.utc),
                modified_date=datetime.now(timezone.utc)
            ),
            PlateDTO(
                plate_id=uuid4(),
                restaurant_id=restaurant_id,
                product_id=uuid4(),
                price=Decimal("8.0"),
                credit=Decimal("4"),
                expected_payout_local_currency=Decimal("0"),
                delivery_time_minutes=10,
                status="active",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.now(timezone.utc),
                modified_date=datetime.now(timezone.utc)
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
        status = "pending"
        
        # Create mock InstitutionBillDTOs
        mock_bills = [
            InstitutionBillDTO(
                institution_bill_id=uuid4(),
                institution_id=institution_id,
                institution_entity_id=institution_id,
                currency_metadata_id=uuid4(),
                status=status,
                period_start=datetime.now(timezone.utc),
                period_end=datetime.now(timezone.utc),
                resolution="Monthly",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.now(timezone.utc),
                modified_date=datetime.now(timezone.utc)
            ),
            InstitutionBillDTO(
                institution_bill_id=uuid4(),
                institution_id=institution_id,
                institution_entity_id=institution_id,
                currency_metadata_id=uuid4(),
                status=Status.PROCESSED,  # Different status
                period_start=datetime.now(timezone.utc),
                period_end=datetime.now(timezone.utc),
                resolution="Monthly",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.now(timezone.utc),
                modified_date=datetime.now(timezone.utc)
            ),
            InstitutionBillDTO(
                institution_bill_id=uuid4(),
                institution_id=institution_id,
                institution_entity_id=institution_id,
                currency_metadata_id=uuid4(),
                status=status,
                period_start=datetime.now(timezone.utc),
                period_end=datetime.now(timezone.utc),
                resolution="Monthly",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.now(timezone.utc),
                modified_date=datetime.now(timezone.utc)
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
        status = "pending"
        
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
                status="active",
                modified_by=uuid4(),
                is_archived=False,
                created_date=datetime.now(timezone.utc),
                modified_date=datetime.now(timezone.utc)
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
        status = "pending"
        
        with patch('app.services.entity_service.institution_bill_service') as mock_bill_service:
            mock_bill_service.get_all.side_effect = Exception("Service error")
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                get_bills_by_status(institution_id, status, mock_db)
            
            assert exc_info.value.status_code == 500
            assert "Failed to get bills for institution" in str(exc_info.value.detail)

    @patch("app.services.entity_service.db_read")
    def test_search_users_applies_institution_id_and_market_id_filters(self, mock_db_read, mock_db):
        """search_users adds WHERE conditions for institution_id and market_id when provided."""
        inst_id = uuid4()
        mkt_id = uuid4()
        mock_db_read.side_effect = [
            {"total": 1},  # count query (fetch_one=True returns dict)
            [{"user_id": uuid4(), "full_name": "A", "username": "a", "email": "a@x.com"}],  # data query
        ]
        rows, total = search_users(
            q="a",
            search_by="name",
            db=mock_db,
            institution_id=inst_id,
            market_id=mkt_id,
        )
        assert total == 1
        assert len(rows) == 1
        assert mock_db_read.call_count == 2
        count_call_args = mock_db_read.call_args_list[0]
        count_params = count_call_args[0][1]
        assert str(inst_id) in count_params
        assert str(mkt_id) in count_params

    @patch("app.services.entity_service.db_read")
    def test_search_restaurants_applies_institution_id_and_market_id_filters(self, mock_db_read, mock_db):
        """search_restaurants adds WHERE conditions for institution_id and market_id when provided."""
        inst_id = uuid4()
        mkt_id = uuid4()
        mock_db_read.side_effect = [
            {"total": 1},  # count query (fetch_one=True returns dict)
            [{"restaurant_id": uuid4(), "name": "R1"}],  # data query
        ]
        rows, total = search_restaurants(
            q="R",
            search_by="name",
            db=mock_db,
            institution_id=inst_id,
            market_id=mkt_id,
        )
        assert total == 1
        assert len(rows) == 1
        assert mock_db_read.call_count == 2
        count_params = mock_db_read.call_args_list[0][0][1]
        assert str(inst_id) in count_params
        assert str(mkt_id) in count_params


class TestEnrichedDiscretionary:
    """Tests for enriched discretionary requests (created_by / created_by_name)."""

    @patch('app.services.enriched_service.db_read')
    def test_get_enriched_discretionary_requests_includes_created_by_fields(self, mock_db_read, mock_db):
        """Enriched list response includes created_by and created_by_name."""
        did = uuid4()
        uid = uuid4()
        iid = uuid4()
        ccid = uuid4()
        mid = uuid4()
        creator_id = uuid4()
        now = datetime.now(timezone.utc)
        mock_db_read.return_value = [
            {
                "discretionary_id": str(did),
                "user_id": str(uid),
                "user_full_name": "Jane Doe",
                "user_username": "jane.doe",
                "restaurant_id": None,
                "restaurant_name": None,
                "institution_id": str(iid),
                "institution_name": "Test Inc",
                "currency_metadata_id": str(ccid),
                "currency_name": "Credits",
                "currency_code": "CR",
                "market_id": str(mid),
                "market_name": "Argentina",
                "country_code": "AR",
                "approval_id": None,
                "category": "marketing_campaign",
                "reason": "Test",
                "amount": Decimal("10.00"),
                "comment": None,
                "is_archived": False,
                "status": "pending",
                "created_date": now,
                "modified_date": now,
                "created_by": str(creator_id),
                "created_by_name": "Admin User",
            }
        ]
        result = get_enriched_discretionary_requests(mock_db)
        assert len(result) == 1
        assert result[0].created_by == creator_id
        assert result[0].created_by_name == "Admin User"

    @patch('app.services.enriched_service.db_read')
    def test_get_enriched_discretionary_request_by_id_includes_created_by_fields(self, mock_db_read, mock_db):
        """Enriched by-id response includes created_by and created_by_name."""
        did = uuid4()
        creator_id = uuid4()
        now = datetime.now(timezone.utc)
        mock_db_read.return_value = {
            "discretionary_id": str(did),
            "user_id": str(uuid4()),
            "user_full_name": "Jane Doe",
            "user_username": "jane.doe",
            "restaurant_id": None,
            "restaurant_name": None,
            "institution_id": str(uuid4()),
            "institution_name": "Test Inc",
            "currency_metadata_id": str(uuid4()),
            "currency_name": "Credits",
            "currency_code": "CR",
            "market_id": str(uuid4()),
            "market_name": "Argentina",
            "country_code": "AR",
            "approval_id": None,
            "category": "marketing_campaign",
            "reason": "Test",
            "amount": Decimal("10.00"),
            "comment": None,
            "is_archived": False,
            "status": "pending",
            "created_date": now,
            "modified_date": now,
            "created_by": str(creator_id),
            "created_by_name": "Admin User",
        }
        result = get_enriched_discretionary_request_by_id(did, mock_db)
        assert result is not None
        assert result.created_by == creator_id
        assert result.created_by_name == "Admin User"


class TestEnrichedPlatesPortionSize:
    """Tests for portion_size and minimum review threshold in enriched plates."""

    @patch("app.services.entity_service._plate_enriched_service")
    @patch.dict("sys.modules", {"google": Mock(), "google.cloud": Mock(), "google.cloud.storage": Mock()})
    def test_portion_size_insufficient_reviews_when_review_count_below_5(
        self, mock_plate_enriched, mock_db
    ):
        """When review_count < 5, portion_size is insufficient_reviews and averages are null."""
        from app.schemas.consolidated_schemas import PlateEnrichedResponseSchema

        plate = PlateEnrichedResponseSchema(
            plate_id=uuid4(),
            product_id=uuid4(),
            restaurant_id=uuid4(),
            institution_name="Test",
            restaurant_name="Test Restaurant",
            cuisine=None,
            pickup_instructions=None,
            country_name="Argentina",
            country_code="AR",
            province="BA",
            city="Buenos Aires",
            street_type="Av",
            street_name="Santa Fe",
            building_number="100",
            address_display="Av Santa Fe 100",
            latitude=None,
            longitude=None,
            average_stars=4.5,
            average_portion_size=2.0,
            review_count=3,
            product_name="Pasta",
            dietary=None,
            ingredients=None,
            product_image_url=None,
            product_image_storage_path="",
            has_image=False,
            price=Decimal("12.00"),
            credit=2,
            expected_payout_local_currency=Decimal("0"),
            no_show_discount=0,
            delivery_time_minutes=15,
            is_archived=False,
            status="active",
            created_date=datetime.now(timezone.utc),
            modified_date=datetime.now(timezone.utc),
        )
        mock_plate_enriched.get_enriched.return_value = [plate]

        result = get_enriched_plates(mock_db)

        assert len(result) == 1
        p = result[0]
        assert p.portion_size == "insufficient_reviews"
        assert p.average_stars is None
        assert p.average_portion_size is None

    @patch("app.services.entity_service._plate_enriched_service")
    @patch.dict("sys.modules", {"google": Mock(), "google.cloud": Mock(), "google.cloud.storage": Mock()})
    def test_portion_size_bucketed_when_review_count_ge_5(
        self, mock_plate_enriched, mock_db
    ):
        """When review_count >= 5, portion_size is bucketed from average_portion_size."""
        from app.schemas.consolidated_schemas import PlateEnrichedResponseSchema

        plate = PlateEnrichedResponseSchema(
            plate_id=uuid4(),
            product_id=uuid4(),
            restaurant_id=uuid4(),
            institution_name="Test",
            restaurant_name="Test Restaurant",
            cuisine=None,
            pickup_instructions=None,
            country_name="Argentina",
            country_code="AR",
            province="BA",
            city="Buenos Aires",
            street_type=None,
            street_name=None,
            building_number=None,
            address_display="Av Santa Fe 100",
            latitude=None,
            longitude=None,
            average_stars=4.2,
            average_portion_size=2.1,
            review_count=15,
            product_name="Grilled Chicken",
            dietary=None,
            ingredients=None,
            product_image_url=None,
            product_image_storage_path="",
            has_image=False,
            price=Decimal("12.00"),
            credit=2,
            expected_payout_local_currency=Decimal("0"),
            no_show_discount=0,
            delivery_time_minutes=15,
            is_archived=False,
            status="active",
            created_date=datetime.now(timezone.utc),
            modified_date=datetime.now(timezone.utc),
        )
        mock_plate_enriched.get_enriched.return_value = [plate]

        result = get_enriched_plates(mock_db)

        assert len(result) == 1
        p = result[0]
        assert p.portion_size == "standard"  # 2.1 -> standard
        assert p.average_stars == 4.2
        assert p.average_portion_size == 2.1

    @patch("app.services.entity_service._plate_enriched_service")
    @patch.dict("sys.modules", {"google": Mock(), "google.cloud": Mock(), "google.cloud.storage": Mock()})
    def test_get_enriched_plate_by_id_portion_size(
        self, mock_plate_enriched, mock_db
    ):
        """get_enriched_plate_by_id applies portion_size logic."""
        from app.schemas.consolidated_schemas import PlateEnrichedResponseSchema

        plate_id = uuid4()
        plate = PlateEnrichedResponseSchema(
            plate_id=plate_id,
            product_id=uuid4(),
            restaurant_id=uuid4(),
            institution_name="Test",
            restaurant_name="Test Restaurant",
            cuisine=None,
            pickup_instructions=None,
            country_name="Argentina",
            country_code="AR",
            province="BA",
            city="Buenos Aires",
            street_type=None,
            street_name=None,
            building_number=None,
            address_display="Av Santa Fe 100",
            latitude=None,
            longitude=None,
            average_stars=4.0,
            average_portion_size=1.2,  # -> light
            review_count=10,
            product_name="Small Plate",
            dietary=None,
            ingredients=None,
            product_image_url=None,
            product_image_storage_path="",
            has_image=False,
            price=Decimal("8.00"),
            credit=1,
            expected_payout_local_currency=Decimal("0"),
            no_show_discount=0,
            delivery_time_minutes=15,
            is_archived=False,
            status="active",
            created_date=datetime.now(timezone.utc),
            modified_date=datetime.now(timezone.utc),
        )
        mock_plate_enriched.get_enriched_by_id.return_value = plate

        result = get_enriched_plate_by_id(plate_id, mock_db)

        assert result is not None
        assert result.portion_size == "light"
