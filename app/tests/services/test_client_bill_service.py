"""
Unit tests for Client Bill Service.

Tests the business logic for client bill operations including
currency resolution, validation, and bill processing.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import UUID, uuid4
from datetime import datetime
from fastapi import HTTPException, status

from app.services.client_bill_service import ClientBillBusinessService, client_bill_business_service
from app.dto.models import ClientBillDTO, CreditCurrencyDTO
from app.config import Status


class TestClientBillService:
    """Test suite for ClientBillBusinessService business logic."""

    def test_resolve_currency_code_looks_up_currency(self, sample_bill_data, mock_db):
        """Test that currency code resolution looks up currency correctly."""
        # Arrange
        mock_currency = Mock()
        mock_currency.currency_code = "EUR"
        
        with patch('app.services.client_bill_service.resolve_currency_code') as mock_resolve_currency:
            # Mock resolve_currency_code to set currency_code directly
            def mock_resolve(data, db):
                data["currency_code"] = "EUR"
            mock_resolve_currency.side_effect = mock_resolve
            
            # Act
            client_bill_business_service._resolve_currency_code(sample_bill_data, mock_db)
            
            # Assert
            mock_resolve_currency.assert_called_once_with(sample_bill_data, mock_db)
            assert sample_bill_data["currency_code"] == "EUR"

    def test_resolve_currency_code_handles_missing_currency(self, sample_bill_data, mock_db):
        """Test that currency code resolution handles missing currency."""
        # Arrange
        with patch('app.services.client_bill_service.credit_currency_service') as mock_currency_service:
            mock_currency_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                client_bill_business_service._resolve_currency_code(sample_bill_data, mock_db)
            
            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "Credit currency not found" in str(exc_info.value.detail)

    def test_calculate_bill_total_applies_tax_and_discount(self, mock_db):
        """Test that bill total calculation applies tax and discount correctly."""
        # Arrange
        base_amount = 100.0
        tax_rate = 0.08  # 8%
        discount_amount = 10.0
        
        # Act
        result = client_bill_business_service.calculate_bill_total(
            base_amount, tax_rate, discount_amount
        )
        
        # Assert
        assert result["base_amount"] == 100.0
        assert result["discount_amount"] == 10.0
        assert result["subtotal"] == 90.0  # 100 - 10
        assert result["tax_rate"] == 0.08
        assert result["tax_amount"] == 7.2  # 90 * 0.08
        assert result["total"] == 97.2  # 90 + 7.2

    def test_calculate_bill_total_handles_no_tax_or_discount(self, mock_db):
        """Test that bill total calculation handles no tax or discount."""
        # Arrange
        base_amount = 50.0
        
        # Act
        result = client_bill_business_service.calculate_bill_total(base_amount)
        
        # Assert
        assert result["base_amount"] == 50.0
        assert result["discount_amount"] == 0.0
        assert result["subtotal"] == 50.0
        assert result["tax_rate"] == 0.0
        assert result["tax_amount"] == 0.0
        assert result["total"] == 50.0

    def test_validate_bill_data_checks_required_fields(self, mock_db):
        """Test that bill data validation checks required fields."""
        # Arrange
        incomplete_data = {
            "amount": 25.50
            # Missing credit_currency_id
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            client_bill_business_service._validate_bill_data(incomplete_data)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Missing required fields" in str(exc_info.value.detail)
        assert "credit_currency_id" in str(exc_info.value.detail)

    def test_validate_bill_data_validates_amount(self, mock_db):
        """Test that bill data validation validates amount is positive."""
        # Arrange
        invalid_amount_data = {
            "credit_currency_id": str(uuid4()),
            "amount": -10.0  # Invalid - negative amount
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            client_bill_business_service._validate_bill_data(invalid_amount_data)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Amount must be a positive number" in str(exc_info.value.detail)

    def test_validate_bill_data_validates_currency_id_format(self, mock_db):
        """Test that bill data validation validates currency ID format."""
        # Arrange
        invalid_currency_data = {
            "credit_currency_id": "invalid-uuid",  # Invalid UUID format
            "amount": 25.50
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            client_bill_business_service._validate_bill_data(invalid_currency_data)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid credit_currency_id format" in str(exc_info.value.detail)

    def test_validate_bill_amount_validates_positive_amount(self, mock_db):
        """Test that bill amount validation checks for positive amounts."""
        # Arrange
        mock_currency = Mock()
        
        with patch('app.services.client_bill_service.credit_currency_service') as mock_currency_service:
            mock_currency_service.get_by_id.return_value = mock_currency
            
            # Act
            result = client_bill_business_service.validate_bill_amount(0, uuid4(), mock_db)
            
            # Assert
            assert result is False

    def test_validate_bill_amount_handles_missing_currency(self, mock_db):
        """Test that bill amount validation handles missing currency."""
        # Arrange
        with patch('app.services.client_bill_service.credit_currency_service') as mock_currency_service:
            mock_currency_service.get_by_id.return_value = None
            
            # Act
            result = client_bill_business_service.validate_bill_amount(25.50, uuid4(), mock_db)
            
            # Assert
            assert result is False

    def test_get_bills_by_status_filters_correctly(self, mock_db):
        """Test that bills by status filtering works correctly."""
        # Arrange
        mock_bills = [
            Mock(status="pending"),
            Mock(status="paid"),
            Mock(status="pending")
        ]

        with patch('app.services.client_bill_service.client_bill_service') as mock_bill_service:
            mock_bill_service.get_all.return_value = mock_bills

            # Act
            result = client_bill_business_service.get_bills_by_status("pending", mock_db)

            # Assert
            assert len(result) == 2
            assert all(bill.status == "pending" for bill in result)

    def test_get_bills_by_currency_filters_correctly(self, mock_db):
        """Test that bills by currency filtering works correctly."""
        # Arrange
        currency_id = uuid4()
        mock_bills = [
            Mock(credit_currency_id=currency_id),
            Mock(credit_currency_id=uuid4()),
            Mock(credit_currency_id=currency_id)
        ]
        
        with patch('app.services.client_bill_service.client_bill_service') as mock_bill_service:
            mock_bill_service.get_all.return_value = mock_bills
            
            # Act
            result = client_bill_business_service.get_bills_by_currency(currency_id, mock_db)
            
            # Assert
            assert len(result) == 2
            assert all(bill.credit_currency_id == currency_id for bill in result)
