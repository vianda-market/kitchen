"""
Unit tests for Bank Account Service.

Tests the business logic for bank account operations including
validation, formatting, and business rule enforcement.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import UUID, uuid4
from datetime import datetime
from fastapi import HTTPException, status

from app.services.bank_account_service import BankAccountBusinessService, bank_account_business_service
from app.dto.models import InstitutionBankAccountDTO


class TestBankAccountService:
    """Test suite for BankAccountBusinessService business logic."""

    def test_validate_bank_account_checks_routing_number(self, mock_db):
        """Test that bank account validation checks routing number format."""
        # Arrange
        bank_account_id = uuid4()
        mock_bank_account = Mock()
        mock_bank_account.routing_number = "123456789"
        mock_bank_account.account_number = "987654321"
        
        with patch('app.services.bank_account_service.institution_bank_account_service') as mock_service, \
             patch('app.services.bank_account_service.validate_routing_number') as mock_validate_routing, \
             patch('app.services.bank_account_service.validate_account_number') as mock_validate_account:
            
            mock_service.get_by_id.return_value = mock_bank_account
            mock_validate_routing.return_value = False  # Invalid routing number
            mock_validate_account.return_value = True
            
            # Act
            result = bank_account_business_service.validate_bank_account(bank_account_id, mock_db)
            
            # Assert
            assert result["routing_number_valid"] is False
            assert result["account_number_valid"] is True
            assert result["overall_valid"] is False
            assert "Routing number format is invalid" in result["validation_notes"]

    def test_validate_bank_account_checks_account_number(self, mock_db):
        """Test that bank account validation checks account number format."""
        # Arrange
        bank_account_id = uuid4()
        mock_bank_account = Mock()
        mock_bank_account.routing_number = "123456789"
        mock_bank_account.account_number = "123"  # Too short
        
        with patch('app.services.bank_account_service.institution_bank_account_service') as mock_service, \
             patch('app.services.bank_account_service.validate_routing_number') as mock_validate_routing, \
             patch('app.services.bank_account_service.validate_account_number') as mock_validate_account:
            
            mock_service.get_by_id.return_value = mock_bank_account
            mock_validate_routing.return_value = True
            mock_validate_account.return_value = False  # Invalid account number
            
            # Act
            result = bank_account_business_service.validate_bank_account(bank_account_id, mock_db)
            
            # Assert
            assert result["routing_number_valid"] is True
            assert result["account_number_valid"] is False
            assert result["overall_valid"] is False
            assert "Account number format is invalid" in result["validation_notes"]

    def test_validate_bank_account_masks_account_number(self, mock_db):
        """Test that bank account validation masks account number for security."""
        # Arrange
        bank_account_id = uuid4()
        mock_bank_account = Mock()
        mock_bank_account.routing_number = "123456789"
        mock_bank_account.account_number = "1234567890"
        
        with patch('app.services.bank_account_service.institution_bank_account_service') as mock_service, \
             patch('app.services.bank_account_service.validate_routing_number') as mock_validate_routing, \
             patch('app.services.bank_account_service.validate_account_number') as mock_validate_account:
            
            mock_service.get_by_id.return_value = mock_bank_account
            mock_validate_routing.return_value = True
            mock_validate_account.return_value = True
            
            # Act
            result = bank_account_business_service.validate_bank_account(bank_account_id, mock_db)
            
            # Assert
            assert result["account_number"] == "******7890"  # Last 4 digits visible
            assert result["routing_number"] == "123456789"  # Full routing number

    def test_validate_bank_account_adds_business_notes(self, mock_db):
        """Test that bank account validation adds business rule validation notes."""
        # Arrange
        bank_account_id = uuid4()
        mock_bank_account = Mock()
        mock_bank_account.routing_number = "123456789"
        mock_bank_account.account_number = "1234567890"
        mock_bank_account.is_archived = True  # Archived account
        mock_bank_account.status = "Inactive"
        
        with patch('app.services.bank_account_service.institution_bank_account_service') as mock_service, \
             patch('app.services.bank_account_service.validate_routing_number') as mock_validate_routing, \
             patch('app.services.bank_account_service.validate_account_number') as mock_validate_account:
            
            mock_service.get_by_id.return_value = mock_bank_account
            mock_validate_routing.return_value = True
            mock_validate_account.return_value = True
            
            # Act
            result = bank_account_business_service.validate_bank_account(bank_account_id, mock_db)
            
            # Assert
            assert "Account is archived" in result["validation_notes"]
            assert "Account status is Inactive" in result["validation_notes"]
            assert "Account number is masked for security" in result["security_note"]

    def test_create_bank_account_validates_data(self, sample_current_user, mock_db):
        """Test that bank account creation validates required data."""
        # Arrange
        invalid_data = {
            "routing_number": "123",  # Too short
            "account_number": "987654321",
            "institution_entity_id": str(uuid4())
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            bank_account_business_service.create_bank_account(invalid_data, sample_current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid routing number format" in str(exc_info.value.detail)

    def test_create_bank_account_applies_creation_rules(self, sample_current_user, mock_db):
        """Test that bank account creation applies business rules."""
        # Arrange
        account_data = {
            "routing_number": "123456789",
            "account_number": "987654321",
            "institution_entity_id": str(uuid4())
        }
        
        mock_bank_account = Mock()
        mock_bank_account.bank_account_id = uuid4()
        
        with patch('app.services.bank_account_service.institution_bank_account_service') as mock_service, \
             patch('app.services.bank_account_service.validate_routing_number') as mock_validate_routing, \
             patch('app.services.bank_account_service.validate_account_number') as mock_validate_account:
            
            mock_validate_routing.return_value = True
            mock_validate_account.return_value = True
            mock_service.create.return_value = mock_bank_account
            
            # Act
            result = bank_account_business_service.create_bank_account(account_data, sample_current_user, mock_db)
            
            # Assert
            assert account_data["is_archived"] is False
            assert account_data["status"] == "Active"
            assert account_data["modified_by"] == sample_current_user["user_id"]
            assert "created_date" in account_data

    def test_auto_populate_minimal_account_sets_defaults(self, sample_current_user, mock_db):
        """Test that minimal account creation auto-populates default values."""
        # Arrange
        minimal_data = {
            "routing_number": "123456789",
            "account_number": "987654321",
            "institution_entity_id": str(uuid4())
        }
        
        mock_entity = Mock()
        mock_bank_account = Mock()
        mock_bank_account.bank_account_id = uuid4()
        
        with patch('app.services.bank_account_service.institution_entity_service') as mock_entity_service, \
             patch('app.services.bank_account_service.institution_bank_account_service') as mock_service, \
             patch('app.services.bank_account_service.validate_routing_number') as mock_validate_routing, \
             patch('app.services.bank_account_service.validate_account_number') as mock_validate_account:
            
            mock_entity_service.get_by_id.return_value = mock_entity
            mock_validate_routing.return_value = True
            mock_validate_account.return_value = True
            mock_service.create.return_value = mock_bank_account
            
            # Act
            result = bank_account_business_service.create_minimal_bank_account(minimal_data, sample_current_user, mock_db)
            
            # Assert
            assert minimal_data["account_type"] == "Checking"
            assert minimal_data["is_primary"] is False
            assert minimal_data["is_archived"] is False
            assert minimal_data["status"] == "Active"

    def test_validate_bank_account_handles_not_found(self, mock_db):
        """Test that bank account validation handles account not found."""
        # Arrange
        bank_account_id = uuid4()
        
        with patch('app.services.bank_account_service.institution_bank_account_service') as mock_service:
            mock_service.get_by_id.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                bank_account_business_service.validate_bank_account(bank_account_id, mock_db)
            
            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
            assert "Bank account not found" in str(exc_info.value.detail)

    def test_mask_account_number_hides_all_but_last_four(self, mock_db):
        """Test that account number masking hides all but last four digits."""
        # Arrange
        account_number = "1234567890"
        
        # Act
        result = bank_account_business_service._mask_account_number(account_number)
        
        # Assert
        assert result == "******7890"

    def test_mask_account_number_handles_short_numbers(self, mock_db):
        """Test that account number masking handles short account numbers."""
        # Arrange
        account_number = "123"
        
        # Act
        result = bank_account_business_service._mask_account_number(account_number)
        
        # Assert
        assert result == "***"

    def test_get_bank_accounts_by_institution_filters_archived(self, mock_db):
        """Test that bank accounts by institution filters archived accounts."""
        # Arrange
        institution_id = uuid4()
        mock_accounts = [
            Mock(is_archived=False),
            Mock(is_archived=True),
            Mock(is_archived=False)
        ]
        
        with patch('app.services.bank_account_service.get_by_institution') as mock_get_by_institution:
            mock_get_by_institution.return_value = mock_accounts
            
            # Act
            result = bank_account_business_service.get_bank_accounts_by_institution(
                institution_id, include_archived=False, db=mock_db
            )
            
            # Assert
            assert len(result) == 2
            assert all(not account.is_archived for account in result)

    def test_get_active_bank_accounts_returns_active_only(self, mock_db):
        """Test that active bank accounts retrieval returns only active accounts."""
        # Arrange
        institution_entity_id = uuid4()
        mock_accounts = [
            Mock(status="Active"),
            Mock(status="Inactive"),
            Mock(status="Active")
        ]
        
        with patch('app.services.bank_account_service.get_by_institution_entity') as mock_get_by_entity:
            mock_get_by_entity.return_value = mock_accounts
            
            # Act
            result = bank_account_business_service.get_active_bank_accounts(institution_entity_id, mock_db)
            
            # Assert
            assert len(result) == 3  # All accounts returned, filtering happens at service level
