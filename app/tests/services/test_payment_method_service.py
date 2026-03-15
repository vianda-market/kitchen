"""
Unit tests for PaymentMethodService

Tests the business logic for linking payment methods to their type-specific records
and activating them.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import HTTPException

from app.services.payment_method_service import link_payment_method_to_type
from app.dto.models import PaymentMethodDTO


class TestPaymentMethodService:
    """Test cases for payment method linking service"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database connection"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_conn.commit = Mock()
        mock_conn.rollback = Mock()
        return mock_conn
    
    @pytest.fixture
    def sample_payment_method_pending(self):
        """Sample payment method in Pending status with no method_type_id"""
        return PaymentMethodDTO(
            payment_method_id=uuid4(),
            user_id=uuid4(),
            method_type="Stripe",
            method_type_id=None,
            is_archived=False,
            status="Pending",
            is_default=False,
            created_date=datetime.now(timezone.utc),
            modified_by=uuid4(),
            modified_date=datetime.now(timezone.utc)
        )
    
    @pytest.fixture
    def sample_payment_method_active(self):
        """Sample payment method already Active and linked"""
        return PaymentMethodDTO(
            payment_method_id=uuid4(),
            user_id=uuid4(),
            method_type="Stripe",
            method_type_id=uuid4(),
            is_archived=False,
            status="Active",
            is_default=False,
            created_date=datetime.now(timezone.utc),
            modified_by=uuid4(),
            modified_date=datetime.now(timezone.utc)
        )
    
    @pytest.fixture
    def sample_payment_method_wrong_type(self):
        """Sample payment method with wrong method_type (Mercado Pago when we expect Stripe)"""
        return PaymentMethodDTO(
            payment_method_id=uuid4(),
            user_id=uuid4(),
            method_type="Mercado Pago",
            method_type_id=None,
            is_archived=False,
            status="Pending",
            is_default=False,
            created_date=datetime.now(timezone.utc),
            modified_by=uuid4(),
            modified_date=datetime.now(timezone.utc)
        )
    
    def test_link_payment_method_success(
        self, mock_db, sample_payment_method_pending
    ):
        """Test successful linking of payment method to type-specific record (e.g. credit card)"""
        type_id = uuid4()
        user_id = uuid4()
        
        with patch('app.services.payment_method_service.payment_method_service') as mock_service:
            mock_service.get_by_id.return_value = sample_payment_method_pending
            
            mock_cursor = mock_db.cursor.return_value.__enter__.return_value
            mock_cursor.execute.return_value = None
            mock_cursor.rowcount = 1
            
            result = link_payment_method_to_type(
                payment_method_id=sample_payment_method_pending.payment_method_id,
                method_type="Stripe",
                type_id=type_id,
                current_user_id=user_id,
                db=mock_db
            )
            
            assert result is True
            mock_cursor.execute.assert_called_once()
            mock_db.commit.assert_called_once()
            # Verify UPDATE query was called with correct parameters
            call_args = mock_cursor.execute.call_args
            # Handle potential leading whitespace/newlines in SQL query
            assert call_args[0][0].strip().startswith("UPDATE payment_method")
            assert str(type_id) in call_args[0][1]
            assert str(user_id) in call_args[0][1]
    
    def test_link_payment_method_idempotent_already_linked(
        self, mock_db, sample_payment_method_active
    ):
        """Test idempotent behavior when payment method is already linked"""
        type_id = uuid4()
        user_id = uuid4()
        
        with patch('app.services.payment_method_service.payment_method_service') as mock_service:
            mock_service.get_by_id.return_value = sample_payment_method_active
            
            result = link_payment_method_to_type(
                payment_method_id=sample_payment_method_active.payment_method_id,
                method_type="Stripe",
                type_id=type_id,
                current_user_id=user_id,
                db=mock_db
            )
            
            assert result is False
            mock_db.cursor.assert_not_called()
    
    def test_link_payment_method_idempotent_not_pending(
        self, mock_db, sample_payment_method_pending
    ):
        """Test idempotent behavior when payment method status is not 'Pending'"""
        type_id = uuid4()
        user_id = uuid4()
        
        # Create payment method with status != 'Pending'
        payment_method = PaymentMethodDTO(
            payment_method_id=sample_payment_method_pending.payment_method_id,
            user_id=sample_payment_method_pending.user_id,
            method_type=sample_payment_method_pending.method_type,
            method_type_id=sample_payment_method_pending.method_type_id,
            is_archived=sample_payment_method_pending.is_archived,
            status="Active",
            is_default=sample_payment_method_pending.is_default,
            created_date=sample_payment_method_pending.created_date,
            modified_by=sample_payment_method_pending.modified_by,
            modified_date=sample_payment_method_pending.modified_date
        )
        
        with patch('app.services.payment_method_service.payment_method_service') as mock_service:
            mock_service.get_by_id.return_value = payment_method
            
            result = link_payment_method_to_type(
                payment_method_id=payment_method.payment_method_id,
                method_type="Stripe",
                type_id=type_id,
                current_user_id=user_id,
                db=mock_db
            )
            
            assert result is False
            mock_db.cursor.assert_not_called()
    
    def test_link_payment_method_not_found(self, mock_db):
        """Test error when payment method not found"""
        payment_method_id = uuid4()
        type_id = uuid4()
        user_id = uuid4()
        
        with patch('app.services.payment_method_service.payment_method_service') as mock_service:
            mock_service.get_by_id.return_value = None
            
            with pytest.raises(ValueError, match="not found"):
                link_payment_method_to_type(
                    payment_method_id=payment_method_id,
                    method_type="Stripe",
                    type_id=type_id,
                    current_user_id=user_id,
                    db=mock_db
                )
    
    def test_link_payment_method_type_mismatch(
        self, mock_db, sample_payment_method_wrong_type
    ):
        """Test error when payment method type doesn't match"""
        type_id = uuid4()
        user_id = uuid4()
        
        with patch('app.services.payment_method_service.payment_method_service') as mock_service:
            mock_service.get_by_id.return_value = sample_payment_method_wrong_type
            
            with pytest.raises(ValueError, match="type mismatch"):
                link_payment_method_to_type(
                    payment_method_id=sample_payment_method_wrong_type.payment_method_id,
                    method_type="Stripe",
                    type_id=type_id,
                    current_user_id=user_id,
                    db=mock_db
                )
    
    def test_link_payment_method_database_error(self, mock_db, sample_payment_method_pending):
        """Test error handling when database update fails"""
        type_id = uuid4()
        user_id = uuid4()
        
        with patch('app.services.payment_method_service.payment_method_service') as mock_service:
            mock_service.get_by_id.return_value = sample_payment_method_pending
            
            mock_cursor = mock_db.cursor.return_value.__enter__.return_value
            mock_cursor.execute.side_effect = Exception("Database error")
            
            with pytest.raises(Exception):
                link_payment_method_to_type(
                    payment_method_id=sample_payment_method_pending.payment_method_id,
                    method_type="Stripe",
                    type_id=type_id,
                    current_user_id=user_id,
                    db=mock_db
                )
            
            mock_db.rollback.assert_called_once()
    
    def test_link_payment_method_zero_rows_updated(
        self, mock_db, sample_payment_method_pending
    ):
        """Test handling when UPDATE returns 0 rows (concurrent update)"""
        type_id = uuid4()
        user_id = uuid4()
        
        with patch('app.services.payment_method_service.payment_method_service') as mock_service:
            mock_service.get_by_id.return_value = sample_payment_method_pending
            
            mock_cursor = mock_db.cursor.return_value.__enter__.return_value
            mock_cursor.execute.return_value = None
            mock_cursor.rowcount = 0  # No rows updated
            
            result = link_payment_method_to_type(
                payment_method_id=sample_payment_method_pending.payment_method_id,
                method_type="Stripe",
                type_id=type_id,
                current_user_id=user_id,
                db=mock_db
            )
            
            assert result is False
            mock_db.commit.assert_called_once()
    
    def test_link_payment_method_different_types(
        self, mock_db, sample_payment_method_pending
    ):
        """Test linking works for different payment method types (Stripe, etc.)"""
        type_id = uuid4()
        user_id = uuid4()
        
        # Create payment method with Stripe type (aggregator)
        payment_method = PaymentMethodDTO(
            payment_method_id=sample_payment_method_pending.payment_method_id,
            user_id=sample_payment_method_pending.user_id,
            method_type="Stripe",
            method_type_id=sample_payment_method_pending.method_type_id,
            is_archived=sample_payment_method_pending.is_archived,
            status=sample_payment_method_pending.status,
            is_default=sample_payment_method_pending.is_default,
            created_date=sample_payment_method_pending.created_date,
            modified_by=sample_payment_method_pending.modified_by,
            modified_date=sample_payment_method_pending.modified_date
        )
        
        with patch('app.services.payment_method_service.payment_method_service') as mock_service:
            mock_service.get_by_id.return_value = payment_method
            
            mock_cursor = mock_db.cursor.return_value.__enter__.return_value
            mock_cursor.execute.return_value = None
            mock_cursor.rowcount = 1
            
            result = link_payment_method_to_type(
                payment_method_id=payment_method.payment_method_id,
                method_type="Stripe",
                type_id=type_id,
                current_user_id=user_id,
                db=mock_db
            )
            
            assert result is True
            # Verify method_type was checked in UPDATE query
            call_args = mock_cursor.execute.call_args
            assert "Stripe" in call_args[0][1]

