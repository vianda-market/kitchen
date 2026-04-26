"""
Unit tests for Client Bill Service.

Tests the business logic for client bill operations including
currency resolution, validation, and bill processing.
"""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.schemas.billing.client_bill import ClientBillUpdateSchema
from app.services.client_bill_service import client_bill_business_service


class TestClientBillUpdateSchema:
    """Schema accepts partial payloads (all fields optional with None defaults)."""

    def test_empty_payload_is_valid(self):
        schema = ClientBillUpdateSchema()
        assert schema.amount is None
        assert schema.currency_code is None

    def test_partial_payload_only_currency(self):
        schema = ClientBillUpdateSchema(currency_code="ARS")
        assert schema.currency_code == "ARS"
        assert schema.amount is None


class TestClientBillService:
    """Test suite for ClientBillBusinessService business logic."""

    def test_resolve_currency_code_looks_up_currency(self, sample_bill_data, mock_db):
        """Test that currency code resolution looks up currency correctly."""
        # Arrange
        mock_currency = Mock()
        mock_currency.currency_code = "EUR"

        with patch("app.services.client_bill_service.resolve_currency_code") as mock_resolve_currency:
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
        with patch("app.services.client_bill_service.credit_currency_service") as mock_currency_service:
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
        result = client_bill_business_service.calculate_bill_total(base_amount, tax_rate, discount_amount)

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
            # Missing currency_metadata_id
        }

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            client_bill_business_service._validate_bill_data(incomplete_data)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") == "validation.field_required"
        else:
            assert "Missing required fields" in str(detail)
            assert "currency_metadata_id" in str(detail)

    def test_validate_bill_data_validates_amount(self, mock_db):
        """Test that bill data validation validates amount is positive."""
        # Arrange
        invalid_amount_data = {
            "currency_metadata_id": str(uuid4()),
            "amount": -10.0,  # Invalid - negative amount
        }

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            client_bill_business_service._validate_bill_data(invalid_amount_data)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") == "credit.amount_must_be_positive"
        else:
            assert "Amount must be a positive number" in str(detail)

    def test_validate_bill_data_validates_currency_id_format(self, mock_db):
        """Test that bill data validation validates currency ID format."""
        # Arrange
        invalid_currency_data = {
            "currency_metadata_id": "invalid-uuid",  # Invalid UUID format
            "amount": 25.50,
        }

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            client_bill_business_service._validate_bill_data(invalid_currency_data)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") == "validation.invalid_format"
        else:
            assert "Invalid currency_metadata_id format" in str(detail)

    def test_validate_bill_amount_validates_positive_amount(self, mock_db):
        """Test that bill amount validation checks for positive amounts."""
        # Arrange
        mock_currency = Mock()

        with patch("app.services.client_bill_service.credit_currency_service") as mock_currency_service:
            mock_currency_service.get_by_id.return_value = mock_currency

            # Act
            result = client_bill_business_service.validate_bill_amount(0, uuid4(), mock_db)

            # Assert
            assert result is False

    def test_validate_bill_amount_handles_missing_currency(self, mock_db):
        """Test that bill amount validation handles missing currency."""
        # Arrange
        with patch("app.services.client_bill_service.credit_currency_service") as mock_currency_service:
            mock_currency_service.get_by_id.return_value = None

            # Act
            result = client_bill_business_service.validate_bill_amount(25.50, uuid4(), mock_db)

            # Assert
            assert result is False

    def test_get_bills_by_status_filters_correctly(self, mock_db):
        """Test that bills by status filtering works correctly."""
        # Arrange
        mock_bills = [Mock(status="pending"), Mock(status="paid"), Mock(status="pending")]

        with patch("app.services.client_bill_service.client_bill_service") as mock_bill_service:
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
            Mock(currency_metadata_id=currency_id),
            Mock(currency_metadata_id=uuid4()),
            Mock(currency_metadata_id=currency_id),
        ]

        with patch("app.services.client_bill_service.client_bill_service") as mock_bill_service:
            mock_bill_service.get_all.return_value = mock_bills

            # Act
            result = client_bill_business_service.get_bills_by_currency(currency_id, mock_db)

            # Assert
            assert len(result) == 2
            assert all(bill.currency_metadata_id == currency_id for bill in result)
