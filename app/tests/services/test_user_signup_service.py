"""
Unit tests for User Signup Service.

Tests the business logic for user signup operations including
password hashing, role assignment, institution assignment, and validation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import UUID
from fastapi import HTTPException, status

from app.services.user_signup_service import UserSignupService, user_signup_service
from app.dto.models import UserDTO
from app.config import RoleType, RoleName


class TestUserSignupService:
    """Test suite for UserSignupService business logic."""

    def test_process_customer_signup_validates_required_fields(self, sample_user_data, mock_db):
        """Test that customer signup validates required fields."""
        # Arrange
        incomplete_data = {"email": "test@example.com"}  # Missing required fields
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.process_customer_signup(incomplete_data, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Missing required fields" in str(exc_info.value.detail)

    def test_process_customer_signup_validates_email_format(self, mock_db):
        """Test that customer signup validates email format."""
        # Arrange
        invalid_email_data = {
            "email": "invalid-email",
            "password": "plaintext123",
            "first_name": "John",
            "last_name": "Doe"
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.process_customer_signup(invalid_email_data, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid email format" in str(exc_info.value.detail)

    def test_process_customer_signup_validates_password_strength(self, mock_db):
        """Test that customer signup validates password strength."""
        # Arrange
        weak_password_data = {
            "email": "test@example.com",
            "password": "123",  # Too short
            "first_name": "John",
            "last_name": "Doe"
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.process_customer_signup(weak_password_data, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Password must be at least 8 characters long" in str(exc_info.value.detail)

    @patch('app.services.user_signup_service.create_user_with_validation')
    def test_process_customer_signup_hashes_password(self, mock_create_user, sample_user_data, mock_db, sample_user_dto):
        """Test that password is hashed during customer signup process."""
        # Arrange
        original_password = sample_user_data["password"]
        mock_create_user.return_value = sample_user_dto
        
        # Act
        result = user_signup_service.process_customer_signup(sample_user_data, mock_db)
        
        # Assert
        # Verify password was hashed and plain password removed
        call_args = mock_create_user.call_args[0][0]  # First positional argument (user_data)
        assert "hashed_password" in call_args
        assert "password" not in call_args
        assert call_args["hashed_password"] != original_password

    @patch('app.services.user_signup_service.create_user_with_validation')
    def test_process_customer_signup_applies_customer_rules(self, mock_create_user, sample_user_data, mock_db, sample_user_dto):
        """Test that customer signup applies correct business rules."""
        # Arrange
        mock_create_user.return_value = sample_user_dto
        
        # Act
        result = user_signup_service.process_customer_signup(sample_user_data, mock_db)
        
        # Assert
        call_args = mock_create_user.call_args[0][0]  # First positional argument (user_data)
        assert call_args["institution_id"] == UserSignupService.CUSTOMER_INSTITUTION
        assert call_args["role_type"] == UserSignupService.CUSTOMER_ROLE_TYPE
        assert call_args["role_name"] == UserSignupService.CUSTOMER_ROLE_NAME
        assert call_args["modified_by"] == UserSignupService.BOT_USER_ID
        assert call_args["email"] == sample_user_data["email"].lower()  # Should be lowercase

    def test_process_customer_signup_handles_missing_password(self, mock_db):
        """Test that customer signup handles missing password gracefully."""
        # Arrange
        user_data_without_password = {
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe"
        }
        
        # Act & Assert - Should raise validation error for missing password
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.process_customer_signup(user_data_without_password, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Missing required fields" in str(exc_info.value.detail)
        assert "password" in str(exc_info.value.detail)

    def test_process_admin_user_creation_validates_data(self, mock_db):
        """Test that admin user creation validates required data."""
        # Arrange
        incomplete_data = {"email": "test@example.com"}  # Missing required fields
        current_user = {"user_id": str(UUID("12345678-1234-1234-1234-123456789012"))}
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.process_admin_user_creation(incomplete_data, current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        # Error message changed - now checks institution_id first
        assert "Institution ID is required" in str(exc_info.value.detail)

    def test_process_admin_user_creation_validates_institution_required(self, mock_db):
        """Test that admin user creation requires institution_id."""
        # Arrange
        data_without_institution = {
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "role_type": "Customer",
            "role_name": "Comensal"
        }
        current_user = {"user_id": str(UUID("12345678-1234-1234-1234-123456789012"))}
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.process_admin_user_creation(data_without_institution, current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Institution ID is required" in str(exc_info.value.detail)

    def test_process_admin_user_creation_validates_role_required(self, mock_db):
        """Test that admin user creation requires role_type and role_name."""
        # Arrange
        data_without_role = {
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "institution_id": str(UUID("12345678-1234-1234-1234-123456789012"))
        }
        current_user = {"user_id": str(UUID("12345678-1234-1234-1234-123456789012"))}
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.process_admin_user_creation(data_without_role, current_user, mock_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        # Error message should mention role_type or role_name
        assert "role" in str(exc_info.value.detail).lower()

    @patch('app.services.user_signup_service.create_user_with_validation')
    def test_process_admin_user_creation_sets_modified_by(self, mock_create_user, sample_current_user, mock_db, sample_user_dto):
        """Test that admin user creation sets modified_by to current user."""
        # Arrange
        user_data = {
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "institution_id": str(UUID("12345678-1234-1234-1234-123456789012")),
            "role_type": "Customer",
            "role_name": "Comensal"
        }
        mock_create_user.return_value = sample_user_dto
        
        # Act
        result = user_signup_service.process_admin_user_creation(user_data, sample_current_user, mock_db)
        
        # Assert
        call_args = mock_create_user.call_args[0][0]
        assert call_args["modified_by"] == sample_current_user["user_id"]

    @patch('app.services.user_signup_service.create_user_with_validation')
    @patch('secrets.choice')
    def test_process_admin_user_creation_generates_temp_password(self, mock_secrets, mock_create_user, sample_current_user, mock_db, sample_user_dto):
        """Test that admin user creation generates temporary password when none provided."""
        # Arrange
        user_data = {
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "institution_id": str(UUID("12345678-1234-1234-1234-123456789012")),
            "role_type": "Customer",
            "role_name": "Comensal"
        }
        mock_create_user.return_value = sample_user_dto
        mock_secrets.return_value = 'a'  # Mock random character
        
        # Act
        result = user_signup_service.process_admin_user_creation(user_data, sample_current_user, mock_db)
        
        # Assert
        call_args = mock_create_user.call_args[0][0]
        assert "hashed_password" in call_args
        assert "password" not in call_args

    def test_validate_user_permissions_requires_authentication(self, mock_db):
        """Test that user permission validation requires authentication."""
        # Arrange
        no_user = None
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.validate_user_permissions(no_user)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authentication required" in str(exc_info.value.detail)

    def test_validate_user_permissions_requires_user_id(self, mock_db):
        """Test that user permission validation requires user_id."""
        # Arrange
        user_without_id = {"username": "admin"}
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.validate_user_permissions(user_without_id)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authentication required" in str(exc_info.value.detail)

    def test_validate_user_permissions_allows_authenticated_user(self, sample_current_user):
        """Test that authenticated users pass permission validation."""
        # Act & Assert - Should not raise exception
        user_signup_service.validate_user_permissions(sample_current_user)

    def test_get_signup_constants_returns_correct_values(self):
        """Test that signup constants are returned correctly."""
        # Act
        constants = user_signup_service.get_signup_constants()
        
        # Assert
        assert constants["customer_institution"] == UserSignupService.CUSTOMER_INSTITUTION
        assert constants["customer_role_type"] == UserSignupService.CUSTOMER_ROLE_TYPE.value
        assert constants["customer_role_name"] == UserSignupService.CUSTOMER_ROLE_NAME.value
        assert constants["bot_user_id"] == UserSignupService.BOT_USER_ID

    def test_apply_customer_signup_rules_sets_defaults(self, sample_user_data):
        """Test that customer signup rules set correct default values."""
        # Arrange
        user_data = sample_user_data.copy()
        
        # Act
        user_signup_service._apply_customer_signup_rules(user_data)
        
        # Assert
        assert user_data["institution_id"] == UserSignupService.CUSTOMER_INSTITUTION
        assert user_data["role_type"] == UserSignupService.CUSTOMER_ROLE_TYPE
        assert user_data["role_name"] == UserSignupService.CUSTOMER_ROLE_NAME
        assert user_data["modified_by"] == UserSignupService.BOT_USER_ID
        assert user_data["is_archived"] is False
        from app.config import Status
        assert user_data["status"] == Status.ACTIVE
        assert user_data["email"] == sample_user_data["email"].lower()

    def test_apply_admin_creation_rules_sets_defaults(self, sample_current_user):
        """Test that admin creation rules set correct default values."""
        # Arrange
        user_data = {
            "email": "TEST@EXAMPLE.COM",  # Should be lowercased
            "first_name": "John",
            "last_name": "Doe"
        }
        
        # Act
        user_signup_service._apply_admin_creation_rules(user_data, sample_current_user)
        
        # Assert
        assert user_data["modified_by"] == sample_current_user["user_id"]
        assert user_data["email"] == "test@example.com"  # Should be lowercase
        assert user_data["is_archived"] is False
        assert user_data["status"] == "Active"

    @patch('app.auth.security.hash_password')
    def test_process_password_security_hashes_password(self, mock_hash_password, sample_user_data):
        """Test that password security processing hashes password correctly."""
        # Arrange
        user_data = sample_user_data.copy()
        mock_hash_password.return_value = "hashed_password_123"
        
        # Act
        user_signup_service._process_password_security(user_data)
        
        # Assert
        mock_hash_password.assert_called_once_with(sample_user_data["password"])
        assert user_data["hashed_password"] == "hashed_password_123"
        assert "password" not in user_data

    def test_process_password_security_handles_missing_password(self):
        """Test that password security processing handles missing password gracefully."""
        # Arrange
        user_data = {"email": "test@example.com"}  # No password
        
        # Act - Should not raise exception
        user_signup_service._process_password_security(user_data)
        
        # Assert
        assert "hashed_password" not in user_data
        assert "password" not in user_data
