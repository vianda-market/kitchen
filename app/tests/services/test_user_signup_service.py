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
from app.config import RoleType, RoleName, Status
from app.config.settings import get_vianda_customers_institution_id


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

    @patch('app.services.user_signup_service.city_service')
    @patch('app.services.user_signup_service.market_service')
    @patch('app.services.user_signup_service.create_user_with_validation')
    def test_process_customer_signup_hashes_password(self, mock_create_user, mock_market_service, mock_city_service, sample_user_data, mock_db, sample_user_dto):
        """Test that password is hashed during customer signup process."""
        from app.tests.conftest import SAMPLE_MARKET_ID
        mock_market_service.get_by_country_code.return_value = {"market_id": SAMPLE_MARKET_ID, "is_archived": False}
        mock_market_service.get_by_id.return_value = {"is_archived": False}
        mock_city_service.get_by_id.return_value = MagicMock(is_archived=False, country_code="US")
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

    @patch('app.services.user_signup_service.city_service')
    @patch('app.services.user_signup_service.market_service')
    @patch('app.services.user_signup_service.create_user_with_validation')
    def test_process_customer_signup_applies_customer_rules(self, mock_create_user, mock_market_service, mock_city_service, sample_user_data, mock_db, sample_user_dto):
        """Test that customer signup applies correct business rules; country_code is resolved to market_id."""
        from app.tests.conftest import SAMPLE_MARKET_ID
        mock_market_service.get_by_country_code.return_value = {"market_id": SAMPLE_MARKET_ID, "is_archived": False}
        mock_market_service.get_by_id.return_value = {"is_archived": False}
        mock_city_service.get_by_id.return_value = MagicMock(is_archived=False, country_code="US")
        mock_create_user.return_value = sample_user_dto

        result = user_signup_service.process_customer_signup(sample_user_data, mock_db)

        call_args = mock_create_user.call_args[0][0]
        assert call_args["institution_id"] == get_vianda_customers_institution_id()
        assert call_args["role_type"] == UserSignupService.CUSTOMER_ROLE_TYPE
        assert call_args["role_name"] == UserSignupService.CUSTOMER_ROLE_NAME
        assert call_args["modified_by"] == UserSignupService.BOT_USER_ID
        assert call_args["email"] == sample_user_data["email"].lower()
        assert call_args["market_id"] == SAMPLE_MARKET_ID  # Resolved from country_code
        assert call_args["city_id"] == sample_user_data["city_id"]

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
        # Validation fails on role_type/role_name or institution_id
        detail = str(exc_info.value.detail)
        assert "role" in detail.lower() or "institution" in detail.lower()

    @patch('app.services.user_signup_service.market_service')
    @patch('app.services.user_signup_service.city_service')
    def test_process_admin_user_creation_validates_institution_required(
        self, mock_city_service, mock_market_service, mock_db
    ):
        """Test that admin user creation requires institution_id for non-Customer/Internal roles."""
        mock_market_service.get_by_id.return_value = {"is_archived": False}
        mock_city_service.get_by_id.return_value = MagicMock(is_archived=False, country_code="US")
        # Arrange - Supplier requires institution_id
        data_without_institution = {
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "role_type": "Supplier",
            "role_name": "Admin"
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

    @patch('app.services.user_signup_service.market_service')
    @patch('app.services.user_signup_service.create_user_with_validation')
    def test_process_admin_user_creation_sets_modified_by(self, mock_create_user, mock_market_service, sample_current_user, mock_db, sample_user_dto):
        """Test that admin user creation sets modified_by to current user."""
        mock_market_service.get_by_id.return_value = {"is_archived": False}
        # Arrange - use Employee Admin (no institution market check, no db cursor)
        user_data = {
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "password": "Password123!",
            "role_type": "Internal",
            "role_name": "Admin"
        }
        mock_create_user.return_value = sample_user_dto
        
        # Act
        result = user_signup_service.process_admin_user_creation(user_data, sample_current_user, mock_db)
        
        # Assert
        call_args = mock_create_user.call_args[0][0]
        assert call_args["modified_by"] == sample_current_user["user_id"]

    @patch.object(user_signup_service, '_send_b2b_invite_email')
    @patch('app.services.user_signup_service.market_service')
    @patch('app.services.user_signup_service.create_user_with_validation')
    @patch('secrets.choice')
    def test_process_admin_user_creation_generates_temp_password_and_sends_invite(
        self, mock_secrets, mock_create_user, mock_market_service, mock_send_invite, sample_current_user, mock_db, sample_user_dto
    ):
        """Test that admin user creation generates placeholder hash and sends invite email when no password provided."""
        mock_market_service.get_by_id.return_value = {"is_archived": False}
        mock_send_invite.return_value = None
        # Arrange - no password triggers B2B invite flow; Internal Admin avoids institution/DB cursor
        user_data = {
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "role_type": "Internal",
            "role_name": "Admin"
        }
        mock_create_user.return_value = sample_user_dto
        mock_secrets.return_value = 'a'  # Mock random character

        # Act
        result = user_signup_service.process_admin_user_creation(user_data, sample_current_user, mock_db)

        # Assert
        call_args = mock_create_user.call_args[0][0]
        assert "hashed_password" in call_args
        assert "password" not in call_args
        assert call_args["status"] == Status.INACTIVE
        mock_send_invite.assert_called_once_with(
            sample_user_dto.user_id,
            sample_user_dto.email,
            sample_user_dto.first_name,
            mock_db,
        )

    @patch.object(user_signup_service, '_send_b2b_invite_email')
    @patch('app.services.user_signup_service.market_service')
    @patch('app.services.user_signup_service.create_user_with_validation')
    def test_process_admin_user_creation_with_password_does_not_send_invite(
        self, mock_create_user, mock_market_service, mock_send_invite, sample_current_user, mock_db, sample_user_dto
    ):
        """Test that admin user creation with password does NOT send invite email (backward compat)."""
        mock_market_service.get_by_id.return_value = {"is_archived": False}
        mock_create_user.return_value = sample_user_dto
        user_data = {
            "email": "test@example.com",
            "first_name": "John",
            "password": "SecurePass123!",
            "role_type": "Internal",
            "role_name": "Admin"
        }

        result = user_signup_service.process_admin_user_creation(user_data, sample_current_user, mock_db)

        # Assert - with password, user gets status = Active (Postman/testing path only)
        call_args = mock_create_user.call_args[0][0]
        assert call_args["status"] == Status.ACTIVE
        assert result == sample_user_dto
        mock_send_invite.assert_not_called()

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
        assert constants["customer_institution"] == get_vianda_customers_institution_id()
        assert constants["customer_role_type"] == UserSignupService.CUSTOMER_ROLE_TYPE.value
        assert constants["customer_role_name"] == UserSignupService.CUSTOMER_ROLE_NAME.value
        assert constants["bot_user_id"] == UserSignupService.BOT_USER_ID

    @patch('app.services.user_signup_service.city_service')
    @patch('app.services.user_signup_service.market_service')
    def test_apply_customer_signup_rules_sets_defaults(self, mock_market_service, mock_city_service, sample_user_data, mock_db):
        """Test that customer signup rules set correct default values; market_id and city_id are preserved from input."""
        from app.tests.conftest import SAMPLE_MARKET_ID
        mock_city_service.get_by_id.return_value = MagicMock(is_archived=False, country_code="US")
        mock_market_service.get_by_id.return_value = {"is_archived": False}
        user_data = sample_user_data.copy()
        user_data["market_id"] = SAMPLE_MARKET_ID  # Simulates resolved value from country_code

        user_signup_service._apply_customer_signup_rules(user_data, mock_db)

        assert user_data["institution_id"] == get_vianda_customers_institution_id()
        assert user_data["role_type"] == UserSignupService.CUSTOMER_ROLE_TYPE
        assert user_data["role_name"] == UserSignupService.CUSTOMER_ROLE_NAME
        assert user_data["modified_by"] == UserSignupService.BOT_USER_ID
        assert user_data["is_archived"] is False
        assert user_data["status"] == Status.ACTIVE
        assert user_data["market_id"] == SAMPLE_MARKET_ID
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
        
        # Assert - no hashed_password = invite flow, status = Inactive
        assert user_data["modified_by"] == sample_current_user["user_id"]
        assert user_data["email"] == "test@example.com"  # Should be lowercase
        assert user_data["is_archived"] is False
        assert user_data["status"] == Status.INACTIVE

    def test_apply_admin_creation_rules_with_password_sets_active(self, sample_current_user):
        """Test that admin creation rules set status = Active when password/hash is provided (Postman path)."""
        # Arrange - hashed_password present = admin-set password path
        user_data = {
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "hashed_password": "already_hashed"
        }
        # Act
        user_signup_service._apply_admin_creation_rules(user_data, sample_current_user)
        # Assert
        assert user_data["status"] == Status.ACTIVE

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

    def test_process_password_security_skips_none_password(self):
        """Test that password security processing skips when password is None (B2B invite flow)."""
        # Arrange
        user_data = {"email": "test@example.com", "password": None}

        # Act - Should not raise, should not hash
        user_signup_service._process_password_security(user_data)

        # Assert
        assert "hashed_password" not in user_data

    # ========== Email verification flow: request_customer_signup ==========

    @patch('app.services.user_signup_service.city_service')
    @patch('app.services.user_signup_service.market_service')
    @patch('app.services.user_signup_service.email_service')
    @patch('app.services.user_signup_service.get_user_by_email')
    @patch('app.services.user_signup_service.get_user_by_username')
    def test_request_customer_signup_returns_success_and_sends_email(
        self, mock_get_by_username, mock_get_by_email, mock_email_service, mock_market_service,
        mock_city_service, sample_user_data, mock_db
    ):
        """request_customer_signup stores pending and sends email when email/username free."""
        from app.tests.conftest import SAMPLE_MARKET_ID
        mock_market_service.get_by_country_code.return_value = {"market_id": SAMPLE_MARKET_ID, "is_archived": False, "country_code": "US"}
        mock_market_service.get_by_id.return_value = {"is_archived": False, "country_code": "US"}
        mock_city_service.get_by_id.return_value = MagicMock(is_archived=False, country_code="US")
        sample_user_data["mobile_number"] = "+14155552671"
        mock_get_by_username.return_value = None
        mock_get_by_email.return_value = None
        mock_email_service.send_signup_verification_email.return_value = True
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_db.cursor.return_value = mock_cursor
        mock_db.commit = MagicMock()

        result = user_signup_service.request_customer_signup(sample_user_data, mock_db)

        assert result["success"] is True
        assert result["already_registered"] is False
        assert "verification code" in result["message"].lower() or "sent" in result["message"].lower()
        mock_email_service.send_signup_verification_email.assert_called_once()

    @patch('app.services.user_signup_service.city_service')
    @patch('app.services.user_signup_service.market_service')
    @patch('app.services.user_signup_service.get_user_by_email')
    @patch('app.services.user_signup_service.get_user_by_username')
    def test_request_customer_signup_raises_when_username_exists(
        self, mock_get_by_username, mock_get_by_email, mock_market_service, mock_city_service,
        sample_user_data, mock_db
    ):
        """request_customer_signup returns 400 when username already in user_info."""
        from app.tests.conftest import SAMPLE_MARKET_ID
        mock_market_service.get_by_country_code.return_value = {"market_id": SAMPLE_MARKET_ID, "is_archived": False, "country_code": "US"}
        mock_market_service.get_by_id.return_value = {"is_archived": False, "country_code": "US"}
        mock_city_service.get_by_id.return_value = MagicMock(is_archived=False, country_code="US")
        sample_user_data["mobile_number"] = "+14155552671"
        mock_get_by_username.return_value = MagicMock()  # user exists
        mock_get_by_email.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.request_customer_signup(sample_user_data, mock_db)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Username already exists" in str(exc_info.value.detail)

    @patch('app.services.user_signup_service.city_service')
    @patch('app.services.user_signup_service.market_service')
    @patch('app.services.user_signup_service.get_user_by_email')
    @patch('app.services.user_signup_service.get_user_by_username')
    def test_request_customer_signup_returns_already_registered_when_email_exists(
        self, mock_get_by_username, mock_get_by_email, mock_market_service, mock_city_service,
        sample_user_data, mock_db
    ):
        """When email already registered, return already_registered true and message to log in; no email sent."""
        from app.tests.conftest import SAMPLE_MARKET_ID
        mock_market_service.get_by_country_code.return_value = {"market_id": SAMPLE_MARKET_ID, "is_archived": False, "country_code": "US"}
        mock_market_service.get_by_id.return_value = {"is_archived": False, "country_code": "US"}
        mock_city_service.get_by_id.return_value = MagicMock(is_archived=False, country_code="US")
        sample_user_data["mobile_number"] = "+14155552671"
        mock_get_by_username.return_value = None
        mock_get_by_email.return_value = MagicMock()  # email already in user_info

        result = user_signup_service.request_customer_signup(sample_user_data, mock_db)

        assert result["success"] is True
        assert result["already_registered"] is True
        assert "already registered" in result["message"].lower() and "log in" in result["message"].lower()

    def test_request_customer_signup_raises_when_country_code_missing(self, sample_user_data, mock_db):
        """request_customer_signup returns 400 when country_code is missing."""
        sample_user_data.pop("country_code", None)
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.request_customer_signup(sample_user_data, mock_db)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "country_code" in str(exc_info.value.detail).lower()

    @patch('app.services.user_signup_service.city_service')
    @patch('app.services.user_signup_service.market_service')
    def test_request_customer_signup_raises_when_country_code_invalid(self, mock_market_service, mock_city_service, sample_user_data, mock_db):
        """request_customer_signup returns 400 when country_code has no market or market is archived."""
        mock_market_service.get_by_country_code.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.request_customer_signup(sample_user_data, mock_db)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "market" in str(exc_info.value.detail).lower()

    @patch('app.services.user_signup_service.city_service')
    @patch('app.services.user_signup_service.market_service')
    def test_request_customer_signup_raises_when_country_resolves_to_global(self, mock_market_service, mock_city_service, sample_user_data, mock_db):
        """request_customer_signup returns 400 when country resolves to Global Marketplace (B2C cannot use Global)."""
        from app.services.market_service import GLOBAL_MARKET_ID
        mock_market_service.get_by_country_code.return_value = {"market_id": GLOBAL_MARKET_ID, "is_archived": False}
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.request_customer_signup(sample_user_data, mock_db)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Global" in str(exc_info.value.detail)

    @patch('app.services.user_signup_service.market_service')
    @patch('app.services.user_signup_service.city_service')
    def test_request_customer_signup_raises_when_city_id_missing(
        self, mock_city_service, mock_market_service, sample_user_data, mock_db
    ):
        """request_customer_signup returns 400 when city_id is missing."""
        from app.tests.conftest import SAMPLE_MARKET_ID
        mock_market_service.get_by_country_code.return_value = {"market_id": SAMPLE_MARKET_ID, "is_archived": False, "country_code": "US"}
        mock_market_service.get_by_id.return_value = {"is_archived": False, "country_code": "US"}
        sample_user_data.pop("city_id", None)
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.request_customer_signup(sample_user_data, mock_db)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "city_id" in str(exc_info.value.detail).lower()

    @patch('app.services.user_signup_service.city_service')
    @patch('app.services.user_signup_service.market_service')
    def test_request_customer_signup_raises_when_city_id_global(self, mock_market_service, mock_city_service, sample_user_data, mock_db):
        """request_customer_signup returns 400 when city_id is Global (B2C customers cannot get Global city)."""
        from app.config.supported_cities import GLOBAL_CITY_ID
        from app.tests.conftest import SAMPLE_MARKET_ID
        mock_market_service.get_by_country_code.return_value = {"market_id": SAMPLE_MARKET_ID, "is_archived": False, "country_code": "US"}
        mock_market_service.get_by_id.return_value = {"is_archived": False, "country_code": "US"}
        mock_city_service.get_by_id.return_value = MagicMock(is_archived=False, country_code="GL")
        sample_user_data["city_id"] = GLOBAL_CITY_ID
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.request_customer_signup(sample_user_data, mock_db)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Global" in str(exc_info.value.detail)

    # ========== Email verification flow: verify_and_complete_signup ==========

    @patch('app.services.user_signup_service.set_user_market_assignments')
    @patch('app.services.user_signup_service.city_service')
    @patch('app.services.user_signup_service.market_service')
    @patch('app.services.user_signup_service.create_access_token')
    @patch('app.services.user_signup_service.create_user_with_validation')
    def test_verify_and_complete_signup_creates_user_and_returns_token(
        self, mock_create_user, mock_create_token, mock_market_service, mock_city_service, mock_set_assignments, sample_user_dto, mock_db
    ):
        """verify_and_complete_signup loads pending (incl. market_id, city_id), creates user, sets market assignment, marks used, returns user and JWT."""
        from datetime import datetime, timezone, timedelta
        from app.tests.conftest import SAMPLE_MARKET_ID
        mock_market_service.get_by_id.return_value = {
            "is_archived": False,
            "country_code": "AR",
            "language": "es",
        }
        mock_city_service.get_by_id.return_value = MagicMock(is_archived=False, country_code="AR")
        mock_create_user.return_value = sample_user_dto
        mock_create_token.return_value = "fake.jwt.token"

        from app.tests.conftest import SAMPLE_CITY_ID
        pending_row = {
            "pending_id": "11111111-1111-1111-1111-111111111111",
            "email": "test@example.com",
            "verification_code": "123456",
            "username": "johndoe",
            "hashed_password": "hashed",
            "first_name": "John",
            "last_name": "Doe",
            "mobile_number": "+14155552671",
            "market_id": SAMPLE_MARKET_ID,
            "city_id": SAMPLE_CITY_ID,
            "used": False,
            "token_expiry": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = pending_row
        mock_cursor.execute = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_db.cursor.return_value = mock_cursor
        mock_db.commit = MagicMock()

        user_dto, access_token = user_signup_service.verify_and_complete_signup("123456", mock_db)

        assert user_dto == sample_user_dto
        assert access_token == "fake.jwt.token"
        mock_create_user.assert_called_once()
        call_user_data = mock_create_user.call_args[0][0]
        assert call_user_data["market_id"] == SAMPLE_MARKET_ID
        assert call_user_data["city_id"] == SAMPLE_CITY_ID
        assert call_user_data["locale"] == "es"
        assert call_user_data["mobile_number"] == "+14155552671"
        assert call_user_data["email_verified"] is True
        assert "email_verified_at" in call_user_data
        mock_set_assignments.assert_called_once_with(sample_user_dto.user_id, [SAMPLE_MARKET_ID], mock_db)
        assert mock_cursor.execute.call_count >= 2  # SELECT then UPDATE

    def test_verify_and_complete_signup_raises_for_empty_code(self, mock_db):
        """verify_and_complete_signup raises 400 for empty code."""
        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.verify_and_complete_signup("", mock_db)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid or expired" in str(exc_info.value.detail)

    def test_verify_and_complete_signup_raises_when_pending_not_found(self, mock_db):
        """verify_and_complete_signup raises 400 when no pending row for code."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.execute = MagicMock()
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_db.cursor.return_value = mock_cursor

        with pytest.raises(HTTPException) as exc_info:
            user_signup_service.verify_and_complete_signup("999999", mock_db)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid or expired" in str(exc_info.value.detail)
