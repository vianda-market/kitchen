"""
Unit tests for DiscretionaryService

Tests the business logic for discretionary credit request management,
including creation, approval, rejection, and validation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from decimal import Decimal
from datetime import datetime
from fastapi import HTTPException

from app.services.discretionary_service import DiscretionaryService
from app.dto.models import (
    DiscretionaryDTO, DiscretionaryResolutionDTO,
    UserDTO, RestaurantDTO
)
from app.config import DiscretionaryReason
from app.config.enums import Status, DiscretionaryStatus


class TestDiscretionaryService:
    """Test cases for DiscretionaryService"""
    
    @pytest.fixture
    def discretionary_service(self):
        """Create DiscretionaryService instance"""
        return DiscretionaryService()
    
    @pytest.fixture
    def sample_admin_user(self):
        """Sample admin user for testing"""
        return {
            "user_id": uuid4(),
            "role_type": "Admin",
            "institution_id": uuid4()
        }
    
    @pytest.fixture
    def sample_super_admin(self):
        """Sample super-admin user for testing
        
        Super Admin users have role_type='Employee' and role_name='Super Admin'.
        This allows them to have global access (via Employee role_type) plus special 
        approval permissions (via role_name).
        """
        return {
            "user_id": uuid4(),
            "role_type": "Employee",
            "role_name": "Super Admin",
            "institution_id": uuid4()
        }
    
    @pytest.fixture
    def sample_request_data(self):
        """Sample discretionary request data"""
        return {
            "user_id": uuid4(),
            "restaurant_id": None,
            "category": DiscretionaryReason.MARKETING_CAMPAIGN,  # Category is now the enum
            "reason": "New customer onboarding incentive",  # Reason is now free-form text
            "amount": Decimal("10.0"),
            "comment": "Customer service issue resolved"
        }
    
    @pytest.fixture
    def sample_discretionary_dto(self):
        """Sample DiscretionaryDTO for testing"""
        return DiscretionaryDTO(
            discretionary_id=uuid4(),
            user_id=uuid4(),
            restaurant_id=None,
            approval_id=None,
            category=DiscretionaryReason.MARKETING_CAMPAIGN,  # Category is now the enum
            reason="New customer onboarding incentive",  # Reason is now free-form text
            amount=Decimal("10.0"),
            comment="Customer service issue resolved",
            is_archived=False,
            status=DiscretionaryStatus.PENDING,
            created_date=datetime.now(),
            modified_by=uuid4(),
            modified_date=datetime.now()
        )
    
    @pytest.fixture
    def sample_user_dto(self):
        """Sample UserDTO for testing"""
        from app.config import Status, RoleType, RoleName
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
            cellphone="1234567890",
            employer_id=None,
            market_id=uuid4(),
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(),
            modified_by=uuid4(),
            modified_date=datetime.now()
        )
    
    @pytest.fixture
    def sample_restaurant_dto(self):
        """Sample RestaurantDTO for testing"""
        from app.config import Status
        return RestaurantDTO(
            restaurant_id=uuid4(),
            institution_id=uuid4(),
            institution_entity_id=uuid4(),
            credit_currency_id=uuid4(),
            name="Test Restaurant",
            address_id=uuid4(),
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(),
            modified_by=uuid4(),
            modified_date=datetime.now()
        )
    
    @pytest.fixture
    def mock_db(self):
        """Mock database connection"""
        return Mock()
    
    # =============================================================================
    # CREATE DISCRETIONARY REQUEST TESTS
    # =============================================================================
    
    def test_create_discretionary_request_success(self, discretionary_service, sample_admin_user, sample_request_data, sample_user_dto, sample_discretionary_dto, mock_db):
        """Test successful discretionary request creation"""
        # Arrange
        mock_user = sample_user_dto
        mock_discretionary = sample_discretionary_dto
        
        with patch('app.services.discretionary_service.user_service') as mock_user_service, \
             patch('app.services.discretionary_service.discretionary_service') as mock_discretionary_service:
            
            mock_user_service.get_by_id.return_value = mock_user
            mock_discretionary_service.create.return_value = mock_discretionary
            
            # Act
            result = discretionary_service.create_discretionary_request(
                sample_request_data, sample_admin_user, mock_db
            )
            
            # Assert
            assert result == mock_discretionary
            mock_user_service.get_by_id.assert_called_once_with(sample_request_data["user_id"], mock_db)
            mock_discretionary_service.create.assert_called_once()
            
            # Verify request data was properly prepared
            from app.config import Status
            call_args = mock_discretionary_service.create.call_args[0][0]
            assert call_args["status"] == Status.PENDING
            assert call_args["modified_by"] == sample_admin_user["user_id"]
    
    def test_create_discretionary_request_with_restaurant_success(self, discretionary_service, sample_admin_user, sample_restaurant_dto, sample_discretionary_dto, mock_db):
        """Test successful discretionary request creation with restaurant"""
        # Arrange - Use restaurant-specific category
        request_data = {
            "restaurant_id": uuid4(),
            "category": DiscretionaryReason.FULL_ORDER_REFUND,  # Restaurant-specific category
            "reason": "Order was marked as not collected but customer confirmed pickup",  # Free-form explanation
            "amount": Decimal("15.0"),
            "comment": "Restaurant service issue"
        }
        
        mock_restaurant = sample_restaurant_dto
        mock_discretionary = sample_discretionary_dto
        
        with patch('app.services.discretionary_service.restaurant_service') as mock_restaurant_service, \
             patch('app.services.discretionary_service.discretionary_service') as mock_discretionary_service:
            
            mock_restaurant_service.get_by_id.return_value = mock_restaurant
            mock_discretionary_service.create.return_value = mock_discretionary
            
            # Act
            result = discretionary_service.create_discretionary_request(
                request_data, sample_admin_user, mock_db
            )
            
            # Assert
            assert result == mock_discretionary
            mock_restaurant_service.get_by_id.assert_called_once_with(request_data["restaurant_id"], mock_db)
            mock_discretionary_service.create.assert_called_once()
    
    def test_create_discretionary_request_missing_required_fields(self, discretionary_service, sample_admin_user, mock_db):
        """Test discretionary request creation with missing required fields"""
        # Arrange
        incomplete_request_data = {
            "user_id": uuid4()
            # Missing: category, amount (reason is optional)
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            discretionary_service.create_discretionary_request(
                incomplete_request_data, sample_admin_user, mock_db
            )
        
        assert exc_info.value.status_code == 400
        assert "Missing required fields" in exc_info.value.detail
    
    def test_create_discretionary_request_invalid_amount(self, discretionary_service, sample_admin_user, mock_db):
        """Test discretionary request creation with invalid amount"""
        # Arrange
        request_data = {
            "user_id": uuid4(),
            "category": DiscretionaryReason.CREDIT_REFUND,
            "reason": "Customer refund request",
            "amount": Decimal("0")  # Invalid: zero amount
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            discretionary_service.create_discretionary_request(
                request_data, sample_admin_user, mock_db
            )
        
        assert exc_info.value.status_code == 400
        assert "Amount must be greater than 0" in exc_info.value.detail
    
    def test_create_discretionary_request_invalid_category(self, discretionary_service, sample_admin_user, mock_db):
        """Test discretionary request creation with invalid category"""
        # Arrange
        request_data = {
            "user_id": uuid4(),
            "category": "invalid_category",  # Invalid enum value
            "reason": "Some explanation",
            "amount": Decimal("10.0")
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            discretionary_service.create_discretionary_request(
                request_data, sample_admin_user, mock_db
            )
        
        assert exc_info.value.status_code == 400
        assert "Invalid category" in exc_info.value.detail
    
    def test_create_discretionary_request_requires_restaurant(self, discretionary_service, sample_admin_user, mock_db):
        """Test discretionary request creation with restaurant-required category but user_id provided"""
        # Arrange - Use restaurant-specific category with user_id (should fail)
        request_data = {
            "user_id": uuid4(),  # Has user_id but no restaurant_id
            "category": DiscretionaryReason.FULL_ORDER_REFUND,  # Requires restaurant_id
            "reason": "Trying to refund order without restaurant context",
            "amount": Decimal("10.0")
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            discretionary_service.create_discretionary_request(
                request_data, sample_admin_user, mock_db
            )
        
        assert exc_info.value.status_code == 400
        assert "requires restaurant_id" in exc_info.value.detail
    
    def test_create_discretionary_request_user_not_found(self, discretionary_service, sample_admin_user, sample_request_data, mock_db):
        """Test discretionary request creation with non-existent user"""
        # Arrange - Category validation happens first, so we need valid category
        request_data = sample_request_data.copy()
        request_data["category"] = DiscretionaryReason.CREDIT_REFUND  # Ensure valid category enum
        
        with patch('app.services.discretionary_service.user_service') as mock_user_service:
            mock_user_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                discretionary_service.create_discretionary_request(
                    request_data, sample_admin_user, mock_db
                )
            
            # User validation happens after category validation, so 404 is correct
            assert exc_info.value.status_code == 404
            assert "User" in exc_info.value.detail
    
    def test_create_discretionary_request_restaurant_not_found(self, discretionary_service, sample_admin_user, sample_user_dto, mock_db):
        """Test discretionary request creation with non-existent restaurant"""
        # Arrange - Use restaurant-specific category
        request_data = {
            "restaurant_id": uuid4(),
            "category": DiscretionaryReason.FULL_ORDER_REFUND,  # Restaurant-specific category
            "reason": "Full refund for incorrectly processed order",
            "amount": Decimal("10.0")
        }
        
        with patch('app.services.discretionary_service.restaurant_service') as mock_restaurant_service:
            mock_restaurant_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                discretionary_service.create_discretionary_request(
                    request_data, sample_admin_user, mock_db
                )
            
            # Restaurant validation happens after category validation, so 404 is correct
            assert exc_info.value.status_code == 404
            assert "Restaurant" in exc_info.value.detail

    def test_create_discretionary_request_optional_institution_market_matching_success(
        self, discretionary_service, sample_admin_user, sample_request_data, sample_user_dto, sample_discretionary_dto, mock_db
    ):
        """Test create succeeds when optional institution_id and market_id match the selected user."""
        inst_id = uuid4()
        mkt_id = uuid4()
        sample_user_dto.institution_id = inst_id
        sample_user_dto.market_id = mkt_id
        request_data = {
            **sample_request_data,
            "institution_id": inst_id,
            "market_id": mkt_id,
        }
        with patch("app.services.discretionary_service.user_service") as mock_user_service, \
             patch("app.services.discretionary_service.discretionary_service") as mock_disc_service:
            mock_user_service.get_by_id.return_value = sample_user_dto
            mock_disc_service.create.return_value = sample_discretionary_dto
            result = discretionary_service.create_discretionary_request(
                request_data, sample_admin_user, mock_db
            )
            assert result == sample_discretionary_dto
            call_args = mock_disc_service.create.call_args[0][0]
            assert "institution_id" not in call_args
            assert "market_id" not in call_args

    def test_create_discretionary_request_institution_mismatch_returns_400(
        self, discretionary_service, sample_admin_user, sample_request_data, sample_user_dto, mock_db
    ):
        """Test create returns 400 when optional institution_id does not match selected user."""
        sample_user_dto.institution_id = uuid4()
        request_data = {
            **sample_request_data,
            "institution_id": uuid4(),  # different from user's institution
        }
        with patch("app.services.discretionary_service.user_service") as mock_user_service:
            mock_user_service.get_by_id.return_value = sample_user_dto
            with pytest.raises(HTTPException) as exc_info:
                discretionary_service.create_discretionary_request(
                    request_data, sample_admin_user, mock_db
                )
            assert exc_info.value.status_code == 400
            assert "not in the specified institution" in exc_info.value.detail

    def test_create_discretionary_request_market_mismatch_returns_400(
        self, discretionary_service, sample_admin_user, sample_request_data, sample_user_dto, mock_db
    ):
        """Test create returns 400 when optional market_id does not match selected user."""
        sample_user_dto.market_id = uuid4()
        request_data = {
            **sample_request_data,
            "market_id": uuid4(),  # different from user's market
        }
        with patch("app.services.discretionary_service.user_service") as mock_user_service:
            mock_user_service.get_by_id.return_value = sample_user_dto
            with pytest.raises(HTTPException) as exc_info:
                discretionary_service.create_discretionary_request(
                    request_data, sample_admin_user, mock_db
                )
            assert exc_info.value.status_code == 400
            assert "not in the specified market" in exc_info.value.detail

    def test_create_discretionary_request_restaurant_institution_mismatch_returns_400(
        self, discretionary_service, sample_admin_user, sample_restaurant_dto, sample_discretionary_dto, mock_db
    ):
        """Test create returns 400 when optional institution_id does not match selected restaurant."""
        request_data = {
            "restaurant_id": uuid4(),
            "category": DiscretionaryReason.FULL_ORDER_REFUND,
            "reason": "Refund",
            "amount": Decimal("10.0"),
            "institution_id": uuid4(),  # different from restaurant's
        }
        with patch("app.services.discretionary_service.restaurant_service") as mock_rest_service, \
             patch("app.services.discretionary_service.discretionary_service") as mock_disc_service:
            mock_rest_service.get_by_id.return_value = sample_restaurant_dto
            mock_disc_service.create.return_value = sample_discretionary_dto
            with pytest.raises(HTTPException) as exc_info:
                discretionary_service.create_discretionary_request(
                    request_data, sample_admin_user, mock_db
                )
            assert exc_info.value.status_code == 400
            assert "not in the specified institution" in exc_info.value.detail

    def test_create_discretionary_request_restaurant_market_mismatch_returns_400(
        self, discretionary_service, sample_admin_user, sample_restaurant_dto, mock_db
    ):
        """Test create returns 400 when optional market_id does not match selected restaurant (credit_currency)."""
        entity_cc_id = uuid4()
        request_data = {
            "restaurant_id": uuid4(),
            "category": DiscretionaryReason.FULL_ORDER_REFUND,
            "reason": "Refund",
            "amount": Decimal("10.0"),
            "market_id": uuid4(),
        }
        with patch("app.services.discretionary_service.restaurant_service") as mock_rest_service, \
             patch("app.services.entity_service.get_credit_currency_id_for_restaurant", return_value=entity_cc_id), \
             patch("app.services.discretionary_service.market_service") as mock_market_service:
            mock_rest_service.get_by_id.return_value = sample_restaurant_dto
            mock_market_service.get_by_id.return_value = {"credit_currency_id": uuid4()}  # different from entity
            with pytest.raises(HTTPException) as exc_info:
                discretionary_service.create_discretionary_request(
                    request_data, sample_admin_user, mock_db
                )
            assert exc_info.value.status_code == 400
            assert "not in the specified market" in exc_info.value.detail

    # =============================================================================
    # APPROVE DISCRETIONARY REQUEST TESTS
    # =============================================================================
    
    def test_approve_discretionary_request_success(self, discretionary_service, sample_super_admin, sample_discretionary_dto, mock_db):
        """Test successful discretionary request approval"""
        # Arrange
        discretionary_id = uuid4()
        mock_discretionary = sample_discretionary_dto
        mock_discretionary.status = DiscretionaryStatus.PENDING
        
        mock_resolution = DiscretionaryResolutionDTO(
            approval_id=uuid4(),
            discretionary_id=discretionary_id,
            resolution="Approved",
            is_archived=False,
            status=Status.ACTIVE,
            resolved_by=sample_super_admin["user_id"],
            resolved_date=datetime.now(),
            created_date=datetime.now(),
            resolution_comment=None
        )
        
        with patch('app.services.discretionary_service.discretionary_service') as mock_discretionary_service, \
             patch('app.services.discretionary_service.discretionary_resolution_service') as mock_resolution_service, \
             patch.object(discretionary_service, '_create_discretionary_transaction') as mock_create_transaction:
            
            mock_discretionary_service.get_by_id.return_value = mock_discretionary
            mock_resolution_service.create.return_value = mock_resolution
            
            # Act
            result = discretionary_service.approve_discretionary_request(
                discretionary_id, sample_super_admin, mock_db
            )
            
            # Assert
            assert result == mock_resolution
            mock_discretionary_service.get_by_id.assert_called_once_with(discretionary_id, mock_db)
            mock_resolution_service.create.assert_called_once()
            mock_create_transaction.assert_called_once_with(mock_discretionary, sample_super_admin, mock_db)
            
            # Verify discretionary request was updated
            mock_discretionary_service.update.assert_called_once_with(
                discretionary_id,
                {"status": DiscretionaryStatus.APPROVED, "approval_id": mock_resolution.approval_id},
                mock_db
            )
    
    def test_approve_discretionary_request_not_found(self, discretionary_service, sample_super_admin, mock_db):
        """Test approval of non-existent discretionary request"""
        # Arrange
        discretionary_id = uuid4()
        
        with patch('app.services.discretionary_service.discretionary_service') as mock_discretionary_service:
            mock_discretionary_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                discretionary_service.approve_discretionary_request(
                    discretionary_id, sample_super_admin, mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Discretionary request" in exc_info.value.detail
    
    def test_approve_discretionary_request_not_pending(self, discretionary_service, sample_super_admin, sample_discretionary_dto, mock_db):
        """Test approval of non-pending discretionary request"""
        # Arrange
        discretionary_id = uuid4()
        mock_discretionary = sample_discretionary_dto
        mock_discretionary.status = DiscretionaryStatus.APPROVED  # Already approved
        
        with patch('app.services.discretionary_service.discretionary_service') as mock_discretionary_service:
            mock_discretionary_service.get_by_id.return_value = mock_discretionary
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                discretionary_service.approve_discretionary_request(
                    discretionary_id, sample_super_admin, mock_db
                )
            
            assert exc_info.value.status_code == 400
            assert "Cannot approve request with status: Approved" in str(exc_info.value.detail)
    
    # =============================================================================
    # REJECT DISCRETIONARY REQUEST TESTS
    # =============================================================================
    
    def test_reject_discretionary_request_success(self, discretionary_service, sample_super_admin, sample_discretionary_dto, mock_db):
        """Test successful discretionary request rejection"""
        # Arrange
        discretionary_id = uuid4()
        rejection_reason = "Insufficient evidence provided"
        
        mock_discretionary = sample_discretionary_dto
        mock_discretionary.status = DiscretionaryStatus.PENDING
        
        mock_resolution = DiscretionaryResolutionDTO(
            approval_id=uuid4(),
            discretionary_id=discretionary_id,
            resolution="Rejected",
            is_archived=False,
            status=Status.ACTIVE,
            resolved_by=sample_super_admin["user_id"],
            resolved_date=datetime.now(),
            created_date=datetime.now(),
            resolution_comment=rejection_reason
        )
        
        with patch('app.services.discretionary_service.discretionary_service') as mock_discretionary_service, \
             patch('app.services.discretionary_service.discretionary_resolution_service') as mock_resolution_service:
            
            mock_discretionary_service.get_by_id.return_value = mock_discretionary
            mock_resolution_service.create.return_value = mock_resolution
            
            # Act
            result = discretionary_service.reject_discretionary_request(
                discretionary_id, sample_super_admin, rejection_reason, mock_db
            )
            
            # Assert
            assert result == mock_resolution
            mock_discretionary_service.get_by_id.assert_called_once_with(discretionary_id, mock_db)
            mock_resolution_service.create.assert_called_once()
            
            # Verify discretionary request was updated
            mock_discretionary_service.update.assert_called_once_with(
                discretionary_id,
                {"status": DiscretionaryStatus.REJECTED, "approval_id": mock_resolution.approval_id},
                mock_db
            )
    
    def test_reject_discretionary_request_not_found(self, discretionary_service, sample_super_admin, mock_db):
        """Test rejection of non-existent discretionary request"""
        # Arrange
        discretionary_id = uuid4()
        
        with patch('app.services.discretionary_service.discretionary_service') as mock_discretionary_service:
            mock_discretionary_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                discretionary_service.reject_discretionary_request(
                    discretionary_id, sample_super_admin, "Test reason", mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Discretionary request" in exc_info.value.detail
    
    def test_reject_discretionary_request_not_pending(self, discretionary_service, sample_super_admin, sample_discretionary_dto, mock_db):
        """Test rejection of non-pending discretionary request"""
        # Arrange
        discretionary_id = uuid4()
        mock_discretionary = sample_discretionary_dto
        mock_discretionary.status = DiscretionaryStatus.REJECTED  # Already rejected
        
        with patch('app.services.discretionary_service.discretionary_service') as mock_discretionary_service:
            mock_discretionary_service.get_by_id.return_value = mock_discretionary
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                discretionary_service.reject_discretionary_request(
                    discretionary_id, sample_super_admin, "Test reason", mock_db
                )
            
            assert exc_info.value.status_code == 400
            assert "Cannot reject request with status: Rejected" in str(exc_info.value.detail)
    
    # =============================================================================
    # GET PENDING REQUESTS TESTS
    # =============================================================================
    
    def test_get_pending_requests_success(self, discretionary_service, sample_discretionary_dto, mock_db):
        """Test successful retrieval of pending requests"""
        # Arrange
        # Create separate instances to avoid modifying the same object
        pending_request = DiscretionaryDTO(
            discretionary_id=uuid4(),
            user_id=uuid4(),
            restaurant_id=None,
            approval_id=None,
            category=DiscretionaryReason.MARKETING_CAMPAIGN,  # Category is now the enum
            reason="New customer promotional credit",  # Reason is now free-form text
            amount=Decimal("10.0"),
            comment="Test comment",
            is_archived=False,
            status=Status.PENDING,
            created_date=datetime.now(),
            modified_by=uuid4(),
            modified_date=datetime.now()
        )
        
        approved_request = DiscretionaryDTO(
            discretionary_id=uuid4(),
            user_id=uuid4(),
            restaurant_id=None,
            approval_id=None,
            category=DiscretionaryReason.MARKETING_CAMPAIGN,  # Category is now the enum
            reason="New customer promotional credit",  # Reason is now free-form text
            amount=Decimal("10.0"),
            comment="Test comment",
            is_archived=False,
            status=DiscretionaryStatus.APPROVED,
            created_date=datetime.now(),
            modified_by=uuid4(),
            modified_date=datetime.now()
        )
        
        all_requests = [approved_request, pending_request]
        
        with patch('app.services.discretionary_service.discretionary_service') as mock_discretionary_service:
            mock_discretionary_service.get_all.return_value = all_requests
            
            # Act
            result = discretionary_service.get_pending_requests(mock_db)
            
            # Assert
            assert len(result) == 1
            assert result[0] == pending_request
            assert result[0].status == DiscretionaryStatus.PENDING
    
    def test_get_pending_requests_empty(self, discretionary_service, sample_discretionary_dto, mock_db):
        """Test retrieval of pending requests when none exist"""
        # Arrange
        approved_request = sample_discretionary_dto
        approved_request.status = DiscretionaryStatus.APPROVED
        
        all_requests = [approved_request]
        
        with patch('app.services.discretionary_service.discretionary_service') as mock_discretionary_service:
            mock_discretionary_service.get_all.return_value = all_requests
            
            # Act
            result = discretionary_service.get_pending_requests(mock_db)
            
            # Assert
            assert len(result) == 0
    
    # =============================================================================
    # GET REQUESTS BY ADMIN TESTS
    # =============================================================================
    
    def test_get_requests_by_admin_success(self, discretionary_service, sample_discretionary_dto, mock_db):
        """Test successful retrieval of requests by admin"""
        # Arrange
        admin_user_id = uuid4()
        
        # Create separate instances to avoid modifying the same object
        admin_request = DiscretionaryDTO(
            discretionary_id=uuid4(),
            user_id=uuid4(),
            restaurant_id=None,
            approval_id=None,
            category=DiscretionaryReason.MARKETING_CAMPAIGN,  # Category is now the enum
            reason="New customer promotional credit",  # Reason is now free-form text
            amount=Decimal("10.0"),
            comment="Test comment",
            is_archived=False,
            status=Status.PENDING,
            created_date=datetime.now(),
            modified_by=admin_user_id,
            modified_date=datetime.now()
        )
        
        other_request = DiscretionaryDTO(
            discretionary_id=uuid4(),
            user_id=uuid4(),
            restaurant_id=None,
            approval_id=None,
            category=DiscretionaryReason.MARKETING_CAMPAIGN,  # Category is now the enum
            reason="New customer promotional credit",  # Reason is now free-form text
            amount=Decimal("10.0"),
            comment="Test comment",
            is_archived=False,
            status=Status.PENDING,
            created_date=datetime.now(),
            modified_by=uuid4(),  # Different admin
            modified_date=datetime.now()
        )
        
        all_requests = [other_request, admin_request]
        
        with patch('app.services.discretionary_service.discretionary_service') as mock_discretionary_service:
            mock_discretionary_service.get_all.return_value = all_requests
            
            # Act
            result = discretionary_service.get_requests_by_admin(admin_user_id, mock_db)
            
            # Assert
            assert len(result) == 1
            assert result[0] == admin_request
            assert result[0].modified_by == admin_user_id
    
    def test_get_requests_by_admin_empty(self, discretionary_service, sample_discretionary_dto, mock_db):
        """Test retrieval of requests by admin when none exist"""
        # Arrange
        admin_user_id = uuid4()
        
        other_request = sample_discretionary_dto
        other_request.modified_by = uuid4()  # Different admin
        
        all_requests = [other_request]
        
        with patch('app.services.discretionary_service.discretionary_service') as mock_discretionary_service:
            mock_discretionary_service.get_all.return_value = all_requests
            
            # Act
            result = discretionary_service.get_requests_by_admin(admin_user_id, mock_db)
            
            # Assert
            assert len(result) == 0
