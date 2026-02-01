"""
Unit tests for Credit Validation Service.

Tests the business logic for credit validation including sufficient credits,
insufficient credits, and edge cases like exact credit matches.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import UUID, uuid4
from decimal import Decimal
from fastapi import HTTPException

from app.services.credit_validation_service import (
    validate_sufficient_credits,
    handle_insufficient_credits,
    get_user_balance
)
from app.dto.models import SubscriptionDTO


class TestCreditValidationService:
    """Test suite for Credit Validation Service business logic."""

    def test_validate_sufficient_credits_allows_when_balance_greater_than_required(self, mock_db):
        """Test that validation passes when user has more credits than required."""
        # Arrange
        user_id = uuid4()
        required_credits = 5.0
        current_balance = 10.0
        
        mock_subscription = SubscriptionDTO(
            subscription_id=uuid4(),
            user_id=user_id,
            plan_id=uuid4(),
            balance=Decimal(str(current_balance)),
            renewal_date="2023-12-31T23:59:59",
            is_archived=False,
            status="Active",
            created_date="2023-01-01T00:00:00",
            modified_by=uuid4(),
            modified_date="2023-01-01T00:00:00"
        )
        
        with patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user:
            mock_get_by_user.return_value = mock_subscription
            
            # Act
            result = validate_sufficient_credits(user_id, required_credits, mock_db)
            
            # Assert
            assert result.has_sufficient_credits is True
            assert result.current_balance == 10.0
            assert result.required_credits == 5.0
            assert result.remaining_balance_after_purchase == 5.0
            assert result.shortfall == 0.0
            assert result.can_proceed is True
            assert "Sufficient credits available" in result.message

    def test_validate_sufficient_credits_allows_when_balance_equals_required(self, mock_db):
        """Test that validation passes when user has exactly enough credits (resulting in 0 balance)."""
        # Arrange
        user_id = uuid4()
        required_credits = 5.0
        current_balance = 5.0  # Exactly enough
        
        mock_subscription = SubscriptionDTO(
            subscription_id=uuid4(),
            user_id=user_id,
            plan_id=uuid4(),
            balance=Decimal(str(current_balance)),
            renewal_date="2023-12-31T23:59:59",
            is_archived=False,
            status="Active",
            created_date="2023-01-01T00:00:00",
            modified_by=uuid4(),
            modified_date="2023-01-01T00:00:00"
        )
        
        with patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user:
            mock_get_by_user.return_value = mock_subscription
            
            # Act
            result = validate_sufficient_credits(user_id, required_credits, mock_db)
            
            # Assert
            assert result.has_sufficient_credits is True
            assert result.current_balance == 5.0
            assert result.required_credits == 5.0
            assert result.remaining_balance_after_purchase == 0.0  # Key: allows 0 balance
            assert result.shortfall == 0.0
            assert result.can_proceed is True
            assert "Sufficient credits available" in result.message

    def test_validate_sufficient_credits_blocks_when_balance_less_than_required(self, mock_db):
        """Test that validation fails when user has insufficient credits."""
        # Arrange
        user_id = uuid4()
        required_credits = 5.0
        current_balance = 3.0  # Insufficient
        
        mock_subscription = SubscriptionDTO(
            subscription_id=uuid4(),
            user_id=user_id,
            plan_id=uuid4(),
            balance=Decimal(str(current_balance)),
            renewal_date="2023-12-31T23:59:59",
            is_archived=False,
            status="Active",
            created_date="2023-01-01T00:00:00",
            modified_by=uuid4(),
            modified_date="2023-01-01T00:00:00"
        )
        
        with patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user:
            mock_get_by_user.return_value = mock_subscription
            
            # Act
            result = validate_sufficient_credits(user_id, required_credits, mock_db)
            
            # Assert
            assert result.has_sufficient_credits is False
            assert result.current_balance == 3.0
            assert result.required_credits == 5.0
            assert result.remaining_balance_after_purchase == -2.0  # Would be negative
            assert result.shortfall == 2.0
            assert result.can_proceed is False
            assert "Insufficient credits" in result.message

    def test_validate_sufficient_credits_blocks_when_balance_is_zero(self, mock_db):
        """Test that validation fails when user has zero credits."""
        # Arrange
        user_id = uuid4()
        required_credits = 5.0
        current_balance = 0.0  # Zero balance
        
        mock_subscription = SubscriptionDTO(
            subscription_id=uuid4(),
            user_id=user_id,
            plan_id=uuid4(),
            balance=Decimal(str(current_balance)),
            renewal_date="2023-12-31T23:59:59",
            is_archived=False,
            status="Active",
            created_date="2023-01-01T00:00:00",
            modified_by=uuid4(),
            modified_date="2023-01-01T00:00:00"
        )
        
        with patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user:
            mock_get_by_user.return_value = mock_subscription
            
            # Act
            result = validate_sufficient_credits(user_id, required_credits, mock_db)
            
            # Assert
            assert result.has_sufficient_credits is False
            assert result.current_balance == 0.0
            assert result.required_credits == 5.0
            assert result.remaining_balance_after_purchase == -5.0  # Would be negative
            assert result.shortfall == 5.0
            assert result.can_proceed is False
            assert "Insufficient credits" in result.message

    def test_validate_sufficient_credits_raises_exception_when_subscription_not_found(self, mock_db):
        """Test that validation raises exception when user subscription is not found."""
        # Arrange
        user_id = uuid4()
        required_credits = 5.0
        
        with patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user:
            mock_get_by_user.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                validate_sufficient_credits(user_id, required_credits, mock_db)
            
            assert exc_info.value.status_code == 404
            assert "User subscription not found" in str(exc_info.value.detail)

    def test_validate_sufficient_credits_handles_database_error(self, mock_db):
        """Test that validation handles database errors gracefully."""
        # Arrange
        user_id = uuid4()
        required_credits = 5.0
        
        with patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user:
            mock_get_by_user.side_effect = Exception("Database connection error")
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                validate_sufficient_credits(user_id, required_credits, mock_db)
            
            assert exc_info.value.status_code == 500
            assert "Error validating user credits" in str(exc_info.value.detail)

    def test_handle_insufficient_credits_with_zero_balance(self):
        """Test insufficient credits handling when user has zero balance."""
        # Arrange
        user_id = uuid4()
        required_credits = 5.0
        current_balance = 0.0
        
        # Act
        result = handle_insufficient_credits(user_id, required_credits, current_balance)
        
        # Assert
        assert result.error_type == "insufficient_credits"
        assert "no credits remaining" in result.message
        assert result.current_balance == 0.0
        assert result.required_credits == 5.0
        assert result.shortfall == 5.0
        assert result.retry_after_payment is True
        assert "payment page" in result.payment_instructions

    def test_handle_insufficient_credits_with_partial_balance(self):
        """Test insufficient credits handling when user has partial balance."""
        # Arrange
        user_id = uuid4()
        required_credits = 5.0
        current_balance = 2.0
        
        # Act
        result = handle_insufficient_credits(user_id, required_credits, current_balance)
        
        # Assert
        assert result.error_type == "insufficient_credits"
        assert "You have 2.0 credits, but this plate costs 5.0 credits" in result.message
        assert result.current_balance == 2.0
        assert result.required_credits == 5.0
        assert result.shortfall == 3.0
        assert result.retry_after_payment is True
        assert "3.0 credits" in result.payment_instructions

    def test_get_user_balance_returns_balance_when_found(self, mock_db):
        """Test that get_user_balance returns balance when subscription is found."""
        # Arrange
        user_id = uuid4()
        current_balance = 10.0
        
        mock_subscription = SubscriptionDTO(
            subscription_id=uuid4(),
            user_id=user_id,
            plan_id=uuid4(),
            balance=Decimal(str(current_balance)),
            renewal_date="2023-12-31T23:59:59",
            is_archived=False,
            status="Active",
            created_date="2023-01-01T00:00:00",
            modified_by=uuid4(),
            modified_date="2023-01-01T00:00:00"
        )
        
        with patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user:
            mock_get_by_user.return_value = mock_subscription
            
            # Act
            result = get_user_balance(user_id, mock_db)
            
            # Assert
            assert result == 10.0

    def test_get_user_balance_returns_none_when_not_found(self, mock_db):
        """Test that get_user_balance returns None when subscription is not found."""
        # Arrange
        user_id = uuid4()
        
        with patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user:
            mock_get_by_user.return_value = None
            
            # Act
            result = get_user_balance(user_id, mock_db)
            
            # Assert
            assert result is None

    def test_get_user_balance_handles_exception(self, mock_db):
        """Test that get_user_balance handles exceptions gracefully."""
        # Arrange
        user_id = uuid4()
        
        with patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user:
            mock_get_by_user.side_effect = Exception("Database error")
            
            # Act
            result = get_user_balance(user_id, mock_db)
            
            # Assert
            assert result is None

    def test_credit_validation_edge_case_decimal_precision(self, mock_db):
        """Test credit validation with decimal precision edge cases."""
        # Arrange
        user_id = uuid4()
        required_credits = 2.5
        current_balance = 2.5  # Exactly enough with decimals
        
        mock_subscription = SubscriptionDTO(
            subscription_id=uuid4(),
            user_id=user_id,
            plan_id=uuid4(),
            balance=Decimal(str(current_balance)),
            renewal_date="2023-12-31T23:59:59",
            is_archived=False,
            status="Active",
            created_date="2023-01-01T00:00:00",
            modified_by=uuid4(),
            modified_date="2023-01-01T00:00:00"
        )
        
        with patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user:
            mock_get_by_user.return_value = mock_subscription
            
            # Act
            result = validate_sufficient_credits(user_id, required_credits, mock_db)
            
            # Assert
            assert result.has_sufficient_credits is True
            assert result.remaining_balance_after_purchase == 0.0
            assert result.can_proceed is True

    def test_credit_validation_very_small_shortfall(self, mock_db):
        """Test credit validation with very small shortfall."""
        # Arrange
        user_id = uuid4()
        required_credits = 5.0
        current_balance = 4.99  # Very small shortfall
        
        mock_subscription = SubscriptionDTO(
            subscription_id=uuid4(),
            user_id=user_id,
            plan_id=uuid4(),
            balance=Decimal(str(current_balance)),
            renewal_date="2023-12-31T23:59:59",
            is_archived=False,
            status="Active",
            created_date="2023-01-01T00:00:00",
            modified_by=uuid4(),
            modified_date="2023-01-01T00:00:00"
        )
        
        with patch('app.services.crud_service.subscription_service.get_by_user') as mock_get_by_user:
            mock_get_by_user.return_value = mock_subscription
            
            # Act
            result = validate_sufficient_credits(user_id, required_credits, mock_db)
            
            # Assert
            assert result.has_sufficient_credits is False
            assert abs(result.shortfall - 0.01) < 0.001  # Allow for floating point precision
            assert result.can_proceed is False
