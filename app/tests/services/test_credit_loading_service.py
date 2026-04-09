"""
Unit tests for CreditLoadingService

Tests the business logic for creating discretionary credit transactions
that feed into the existing balance management system.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from decimal import Decimal
from datetime import datetime
from fastapi import HTTPException

from app.services.credit_loading_service import CreditLoadingService
from app.dto.models import (
    ClientTransactionDTO, RestaurantTransactionDTO,
    RestaurantDTO, CreditCurrencyDTO
)
from app.config import Status, TransactionType


class TestCreditLoadingService:
    """Test cases for CreditLoadingService"""
    
    @pytest.fixture
    def credit_loading_service(self):
        """Create CreditLoadingService instance"""
        return CreditLoadingService()
    
    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing"""
        return uuid4()
    
    @pytest.fixture
    def sample_restaurant_id(self):
        """Sample restaurant ID for testing"""
        return uuid4()
    
    @pytest.fixture
    def sample_discretionary_id(self):
        """Sample discretionary ID for testing"""
        return uuid4()
    
    @pytest.fixture
    def sample_modified_by(self):
        """Sample modified_by user ID for testing"""
        return uuid4()
    
    @pytest.fixture
    def sample_amount(self):
        """Sample credit amount for testing"""
        return Decimal("10.0")
    
    @pytest.fixture
    def sample_restaurant_dto(self):
        """Sample RestaurantDTO for testing (credit_currency from institution_entity)"""
        return RestaurantDTO(
            restaurant_id=uuid4(),
            institution_id=uuid4(),
            institution_entity_id=uuid4(),
            address_id=uuid4(),
            name="Test Restaurant",
            cuisine=None,
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(),
            modified_by=uuid4(),
            modified_date=datetime.now()
        )
    
    @pytest.fixture
    def sample_client_transaction_dto(self):
        """Sample ClientTransactionDTO for testing"""
        return ClientTransactionDTO(
            transaction_id=uuid4(),
            user_id=uuid4(),
            source="discretionary",
            plate_selection_id=None,
            discretionary_id=uuid4(),
            credit=Decimal("10.0"),
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(),
            modified_by=uuid4(),
            modified_date=datetime.now()
        )
    
    @pytest.fixture
    def sample_restaurant_transaction_dto(self):
        """Sample RestaurantTransactionDTO for testing"""
        return RestaurantTransactionDTO(
            transaction_id=uuid4(),
            restaurant_id=uuid4(),
            plate_selection_id=None,
            discretionary_id=uuid4(),
            credit_currency_id=uuid4(),
            was_collected=False,
            ordered_timestamp=datetime.now(),
            collected_timestamp=None,
            arrival_time=None,
            completion_time=None,
            expected_completion_time=None,
            transaction_type=TransactionType.DISCRETIONARY,
            credit=Decimal("10.0"),
            no_show_discount=None,
            currency_code="USD",
            final_amount=Decimal("10.0"),
            is_archived=False,
            status=Status.ACTIVE,
            created_date=datetime.now(),
            modified_by=uuid4(),
            modified_date=datetime.now()
        )
    
    @pytest.fixture
    def sample_credit_currency_dto(self):
        """Sample CreditCurrencyDTO for testing"""
        return CreditCurrencyDTO(
            credit_currency_id=uuid4(),
            currency_name="Test Credits",
            currency_code="USD",
            credit_value_local_currency=Decimal("1.0"),
            currency_conversion_usd=Decimal("1.0"),
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
    # CREATE CLIENT CREDIT TRANSACTION TESTS
    # =============================================================================
    
    def test_create_client_credit_transaction_success(
        self, 
        credit_loading_service, 
        sample_user_id, 
        sample_amount, 
        sample_discretionary_id, 
        sample_modified_by, 
        sample_client_transaction_dto,
        mock_db
    ):
        """Test successful client credit transaction creation"""
        # Arrange
        mock_transaction = sample_client_transaction_dto
        
        with patch('app.services.credit_loading_service.client_transaction_service') as mock_service, \
             patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user, \
             patch('app.services.crud_service.update_balance') as mock_update_balance:
            
            mock_service.create.return_value = mock_transaction
            # Mock subscription for balance update
            from app.dto.models import SubscriptionDTO
            mock_subscription = SubscriptionDTO(
                subscription_id=uuid4(),
                user_id=sample_user_id,
                plan_id=uuid4(),
                market_id=uuid4(),
                balance=Decimal("10.0"),
                renewal_date=datetime.now(),
                is_archived=False,
                status=Status.ACTIVE,
                created_date=datetime.now(),
                modified_by=uuid4(),
                modified_date=datetime.now()
            )
            mock_get_by_user.return_value = mock_subscription
            mock_update_balance.return_value = True
            
            # Act
            result = credit_loading_service.create_client_credit_transaction(
                sample_user_id, sample_amount, sample_discretionary_id, sample_modified_by, mock_db
            )
            
            # Assert
            assert result == mock_transaction
            mock_service.create.assert_called_once()
            
            # Verify transaction data
            call_args = mock_service.create.call_args[0][0]
            assert call_args["user_id"] == sample_user_id
            assert call_args["source"] == "discretionary"
            assert call_args["discretionary_id"] == sample_discretionary_id
            assert call_args["credit"] == sample_amount
            assert call_args["status"] == Status.ACTIVE
            assert call_args["modified_by"] == sample_modified_by
    
    def test_create_client_credit_transaction_zero_amount(
        self, 
        credit_loading_service, 
        sample_user_id, 
        sample_discretionary_id, 
        sample_modified_by, 
        mock_db
    ):
        """Test client credit transaction creation with zero amount"""
        # Arrange
        zero_amount = Decimal("0")
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            credit_loading_service.create_client_credit_transaction(
                sample_user_id, zero_amount, sample_discretionary_id, sample_modified_by, mock_db
            )
        
        assert exc_info.value.status_code == 400
        assert "Credit amount must be positive" in exc_info.value.detail
    
    def test_create_client_credit_transaction_negative_amount(
        self, 
        credit_loading_service, 
        sample_user_id, 
        sample_discretionary_id, 
        sample_modified_by, 
        mock_db
    ):
        """Test client credit transaction creation with negative amount"""
        # Arrange
        negative_amount = Decimal("-5.0")
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            credit_loading_service.create_client_credit_transaction(
                sample_user_id, negative_amount, sample_discretionary_id, sample_modified_by, mock_db
            )
        
        assert exc_info.value.status_code == 400
        assert "Credit amount must be positive" in exc_info.value.detail
    
    def test_create_client_credit_transaction_service_error(
        self, 
        credit_loading_service, 
        sample_user_id, 
        sample_amount, 
        sample_discretionary_id, 
        sample_modified_by, 
        mock_db
    ):
        """Test client credit transaction creation with service error"""
        # Arrange
        with patch('app.services.credit_loading_service.client_transaction_service') as mock_service:
            mock_service.create.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                credit_loading_service.create_client_credit_transaction(
                    sample_user_id, sample_amount, sample_discretionary_id, sample_modified_by, mock_db
                )
            
            assert exc_info.value.status_code == 500
            assert "Failed to create client credit transaction" in exc_info.value.detail
    
    # =============================================================================
    # CREATE RESTAURANT CREDIT TRANSACTION TESTS
    # =============================================================================
    
    def test_create_restaurant_credit_transaction_success(
        self, 
        credit_loading_service, 
        sample_restaurant_id, 
        sample_amount, 
        sample_discretionary_id, 
        sample_modified_by, 
        sample_restaurant_dto,
        sample_restaurant_transaction_dto,
        sample_credit_currency_dto,
        mock_db
    ):
        """Test successful restaurant credit transaction creation"""
        # Arrange
        mock_restaurant = sample_restaurant_dto
        mock_restaurant.restaurant_id = sample_restaurant_id
        mock_transaction = sample_restaurant_transaction_dto
        
        expected_cc_id = sample_credit_currency_dto.credit_currency_id
        
        with patch('app.services.credit_loading_service.restaurant_service') as mock_restaurant_service, \
             patch('app.services.entity_service.get_credit_currency_id_for_restaurant', return_value=expected_cc_id), \
             patch('app.services.credit_loading_service.credit_currency_service') as mock_currency_service, \
             patch('app.services.credit_loading_service.create_with_conservative_balance_update') as mock_create_with_balance:
            mock_restaurant_service.get_by_id.return_value = mock_restaurant
            mock_currency_service.get_by_id.return_value = sample_credit_currency_dto
            mock_create_with_balance.return_value = mock_transaction
            
            # Act
            result = credit_loading_service.create_restaurant_credit_transaction(
                sample_restaurant_id, sample_amount, sample_discretionary_id, sample_modified_by, mock_db
            )
            
            # Assert
            assert result == mock_transaction
            mock_restaurant_service.get_by_id.assert_called_once_with(sample_restaurant_id, mock_db)
            mock_currency_service.get_by_id.assert_called_once_with(expected_cc_id, mock_db)
            mock_create_with_balance.assert_called_once()
            
            # Verify transaction data
            call_args = mock_create_with_balance.call_args[0][0]
            assert call_args["restaurant_id"] == sample_restaurant_id
            assert call_args["plate_selection_id"] is None
            assert call_args["credit"] == sample_amount
            assert call_args["final_amount"] == sample_amount
            assert call_args["status"] == "pending"
            assert call_args["modified_by"] == sample_modified_by
    
    def test_create_restaurant_credit_transaction_zero_amount(
        self, 
        credit_loading_service, 
        sample_restaurant_id, 
        sample_discretionary_id, 
        sample_modified_by, 
        mock_db
    ):
        """Test restaurant credit transaction creation with zero amount"""
        # Arrange
        zero_amount = Decimal("0")
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            credit_loading_service.create_restaurant_credit_transaction(
                sample_restaurant_id, zero_amount, sample_discretionary_id, sample_modified_by, mock_db
            )
        
        assert exc_info.value.status_code == 400
        assert "Credit amount must be positive" in exc_info.value.detail
    
    def test_create_restaurant_credit_transaction_negative_amount(
        self, 
        credit_loading_service, 
        sample_restaurant_id, 
        sample_discretionary_id, 
        sample_modified_by, 
        mock_db
    ):
        """Test restaurant credit transaction creation with negative amount"""
        # Arrange
        negative_amount = Decimal("-5.0")
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            credit_loading_service.create_restaurant_credit_transaction(
                sample_restaurant_id, negative_amount, sample_discretionary_id, sample_modified_by, mock_db
            )
        
        assert exc_info.value.status_code == 400
        assert "Credit amount must be positive" in exc_info.value.detail
    
    def test_create_restaurant_credit_transaction_restaurant_not_found(
        self, 
        credit_loading_service, 
        sample_restaurant_id, 
        sample_amount, 
        sample_discretionary_id, 
        sample_modified_by, 
        sample_restaurant_dto,
        sample_credit_currency_dto,
        mock_db
    ):
        """Test restaurant credit transaction creation with non-existent restaurant"""
        # Arrange
        with patch('app.services.credit_loading_service.restaurant_service') as mock_restaurant_service:
            mock_restaurant_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                credit_loading_service.create_restaurant_credit_transaction(
                    sample_restaurant_id, sample_amount, sample_discretionary_id, sample_modified_by, mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Restaurant" in exc_info.value.detail
    
    def test_create_restaurant_credit_transaction_service_error(
        self, 
        credit_loading_service, 
        sample_restaurant_id, 
        sample_amount, 
        sample_discretionary_id, 
        sample_modified_by, 
        sample_restaurant_dto,
        sample_credit_currency_dto,
        mock_db
    ):
        """Test restaurant credit transaction creation with service error"""
        # Arrange
        mock_restaurant = sample_restaurant_dto
        
        with patch('app.services.credit_loading_service.restaurant_service') as mock_restaurant_service, \
             patch('app.services.entity_service.get_credit_currency_id_for_restaurant', return_value=sample_credit_currency_dto.credit_currency_id), \
             patch('app.services.credit_loading_service.credit_currency_service') as mock_currency_service, \
             patch('app.services.credit_loading_service.create_with_conservative_balance_update') as mock_create_with_balance:
            
            mock_restaurant_service.get_by_id.return_value = mock_restaurant
            mock_currency_service.get_by_id.return_value = sample_credit_currency_dto
            mock_create_with_balance.side_effect = Exception("Database error")
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                credit_loading_service.create_restaurant_credit_transaction(
                    sample_restaurant_id, sample_amount, sample_discretionary_id, sample_modified_by, mock_db
                )
            
            assert exc_info.value.status_code == 500
            assert "Failed to create restaurant credit transaction" in exc_info.value.detail
    
    # =============================================================================
    # DECIMAL PRECISION TESTS
    # =============================================================================
    
    def test_create_client_credit_transaction_decimal_precision(
        self, 
        credit_loading_service, 
        sample_user_id, 
        sample_discretionary_id, 
        sample_modified_by, 
        sample_client_transaction_dto,
        mock_db
    ):
        """Test client credit transaction creation with decimal precision"""
        # Arrange
        precise_amount = Decimal("10.99")
        mock_transaction = sample_client_transaction_dto
        
        with patch('app.services.credit_loading_service.client_transaction_service') as mock_service, \
             patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user, \
             patch('app.services.crud_service.update_balance') as mock_update_balance:
            
            mock_service.create.return_value = mock_transaction
            # Mock subscription for balance update
            from app.dto.models import SubscriptionDTO
            mock_subscription = SubscriptionDTO(
                subscription_id=uuid4(),
                user_id=sample_user_id,
                plan_id=uuid4(),
                market_id=uuid4(),
                balance=Decimal("10.0"),
                renewal_date=datetime.now(),
                is_archived=False,
                status=Status.ACTIVE,
                created_date=datetime.now(),
                modified_by=uuid4(),
                modified_date=datetime.now()
            )
            mock_get_by_user.return_value = mock_subscription
            mock_update_balance.return_value = True
            
            # Act
            result = credit_loading_service.create_client_credit_transaction(
                sample_user_id, precise_amount, sample_discretionary_id, sample_modified_by, mock_db
            )
            
            # Assert
            assert result == mock_transaction
            
            # Verify decimal precision is maintained
            call_args = mock_service.create.call_args[0][0]
            assert call_args["credit"] == precise_amount
    
    def test_create_restaurant_credit_transaction_decimal_precision(
        self, 
        credit_loading_service, 
        sample_restaurant_id, 
        sample_discretionary_id, 
        sample_modified_by, 
        sample_restaurant_dto,
        sample_restaurant_transaction_dto,
        sample_credit_currency_dto,
        mock_db
    ):
        """Test restaurant credit transaction creation with decimal precision"""
        # Arrange
        precise_amount = Decimal("15.99")
        mock_restaurant = sample_restaurant_dto
        mock_transaction = sample_restaurant_transaction_dto
        
        with patch('app.services.credit_loading_service.restaurant_service') as mock_restaurant_service, \
             patch('app.services.entity_service.get_credit_currency_id_for_restaurant', return_value=sample_credit_currency_dto.credit_currency_id), \
             patch('app.services.credit_loading_service.credit_currency_service') as mock_currency_service, \
             patch('app.services.credit_loading_service.create_with_conservative_balance_update') as mock_create_with_balance:
            mock_restaurant_service.get_by_id.return_value = mock_restaurant
            mock_currency_service.get_by_id.return_value = sample_credit_currency_dto
            mock_create_with_balance.return_value = mock_transaction
            
            # Act
            result = credit_loading_service.create_restaurant_credit_transaction(
                sample_restaurant_id, precise_amount, sample_discretionary_id, sample_modified_by, mock_db
            )
            
            # Assert
            assert result == mock_transaction
            
            # Verify decimal precision is maintained
            call_args = mock_create_with_balance.call_args[0][0]
            assert call_args["credit"] == precise_amount  # Decimal maintains precision
            assert call_args["final_amount"] == precise_amount  # Decimal maintains precision
