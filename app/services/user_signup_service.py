"""
User Signup Business Logic Service

This service contains all business logic related to user signup operations,
including password hashing, role assignment, institution assignment, and validation.
"""

from uuid import UUID
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
import psycopg2.extensions

from app.dto.models import UserDTO
from app.services.entity_service import create_user_with_validation
from app.utils.log import log_info, log_warning
from app.security.institution_scope import InstitutionScope
from app.config import RoleType, RoleName, Status


class UserSignupService:
    """Service for handling user signup business logic"""
    
    # Seeded constants for customer self-registration
    CUSTOMER_INSTITUTION = UUID("44444444-4444-4444-4444-444444444444")
    # Role constants - using enum values instead of UUIDs
    CUSTOMER_ROLE_TYPE = RoleType.CUSTOMER
    CUSTOMER_ROLE_NAME = RoleName.COMENSAL
    BOT_USER_ID = UUID("22222222-2222-2222-2222-222222222222")
    
    def __init__(self):
        pass
    
    def process_customer_signup(
        self, 
        user_data: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> UserDTO:
        """
        Process customer self-registration with business rules.
        
        Args:
            user_data: User data dictionary from signup form
            db: Database connection
            
        Returns:
            Created user DTO
            
        Raises:
            HTTPException: For validation or creation failures
        """
        # Validate signup data
        self._validate_signup_data(user_data)
        
        # Process password security
        self._process_password_security(user_data)
        
        # Apply business rules for customer signup
        self._apply_customer_signup_rules(user_data)
        
        # Create user with validation
        new_user = create_user_with_validation(user_data, db)
        
        log_info(f"Customer self-signed up: {new_user.user_id}")
        return new_user
    
    def process_admin_user_creation(
        self, 
        user_data: Dict[str, Any], 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection,
        *,
        scope: Optional[InstitutionScope] = None
    ) -> UserDTO:
        """
        Process admin user creation with business rules.
        
        Args:
            user_data: User data dictionary
            current_user: Current admin user information
            db: Database connection
            
        Returns:
            Created user DTO
            
        Raises:
            HTTPException: For validation or creation failures
        """
        # Validate user data
        self._validate_user_data(user_data)
        
        # Process password security
        self._process_password_security(user_data)
        
        # Apply admin creation rules
        self._apply_admin_creation_rules(user_data, current_user)

        # Enforce institution scope for non-global users
        self._apply_scope_constraints(user_data, scope)
        
        # Create user with validation
        new_user = create_user_with_validation(user_data, db, scope=scope)
        
        log_info(f"Admin created user: {new_user.user_id}")
        return new_user
    
    def _validate_signup_data(self, user_data: Dict[str, Any]) -> None:
        """
        Validate customer signup data.
        
        Args:
            user_data: User data dictionary
            
        Raises:
            HTTPException: For validation failures
        """
        required_fields = ["email", "password"]
        missing_fields = [field for field in required_fields if not user_data.get(field)]
        
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Validate email format (basic validation)
        email = user_data.get("email", "").strip().lower()
        if "@" not in email or "." not in email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Validate password strength (basic validation)
        password = user_data.get("password", "")
        if len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
    
    def _validate_user_data(self, user_data: Dict[str, Any]) -> None:
        """
        Validate general user data for admin creation.
        
        Args:
            user_data: User data dictionary
            
        Raises:
            HTTPException: For validation failures
        """
        required_fields = ["email"]
        missing_fields = [field for field in required_fields if not user_data.get(field)]
        
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Validate email format
        email = user_data.get("email", "").strip().lower()
        if "@" not in email or "." not in email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Validate required fields for admin creation
        if not user_data.get("institution_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Institution ID is required for user creation"
            )
        
        if not user_data.get("role_type") or not user_data.get("role_name"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role type and role name are required for user creation"
            )
    
    def _process_password_security(self, user_data: Dict[str, Any]) -> None:
        """
        Process password security (hashing and cleanup).
        
        Args:
            user_data: User data dictionary (modified in place)
        """
        if "password" in user_data:
            from app.auth.security import hash_password
            hashed_pwd = hash_password(user_data["password"])
            user_data["hashed_password"] = hashed_pwd
            del user_data["password"]  # Remove the plain password
            
            log_info(f"🔐 Password hashed successfully:")
            log_info(f"   Hash length: {len(hashed_pwd)}")
            log_info(f"   Hash starts with: {hashed_pwd[:20]}...")
        else:
            log_warning("❌ No password found in user data")
    
    def _apply_customer_signup_rules(self, user_data: Dict[str, Any]) -> None:
        """
        Apply business rules for customer self-registration.
        
        Args:
            user_data: User data dictionary (modified in place)
        """
        # Override to seeded values for customer signup
        user_data["institution_id"] = self.CUSTOMER_INSTITUTION
        user_data["role_type"] = self.CUSTOMER_ROLE_TYPE
        user_data["role_name"] = self.CUSTOMER_ROLE_NAME
        user_data["modified_by"] = self.BOT_USER_ID
        
        # Ensure email is lowercase
        if "email" in user_data:
            user_data["email"] = user_data["email"].strip().lower()
        
        # Set default values for customer signup
        user_data.setdefault("is_archived", False)
        user_data.setdefault("status", Status.ACTIVE)
        
        log_info(f"Applied customer signup rules: institution={self.CUSTOMER_INSTITUTION}, role_type={self.CUSTOMER_ROLE_TYPE.value}, role_name={self.CUSTOMER_ROLE_NAME.value}")
    
    def _apply_admin_creation_rules(self, user_data: Dict[str, Any], current_user: Dict[str, Any]) -> None:
        """
        Apply business rules for admin user creation.
        
        Args:
            user_data: User data dictionary (modified in place)
            current_user: Current admin user information
        """
        # Set modified_by to current admin user
        user_data["modified_by"] = current_user["user_id"]
        
        # Ensure email is lowercase
        if "email" in user_data:
            user_data["email"] = user_data["email"].strip().lower()
        
        # Set default values
        user_data.setdefault("is_archived", False)
        user_data.setdefault("status", Status.ACTIVE)
        
        # If no password provided, generate a temporary one (admin should set it later)
        if "password" not in user_data and "hashed_password" not in user_data:
            # Generate a random temporary password
            import secrets
            import string
            temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            user_data["password"] = temp_password
            self._process_password_security(user_data)
            log_info("Generated temporary password for admin-created user")
        
        log_info(f"Applied admin creation rules: modified_by={current_user['user_id']}")

    def _apply_scope_constraints(
        self,
        user_data: Dict[str, Any],
        scope: Optional[InstitutionScope]
    ) -> None:
        """
        Apply institution scoping constraints for admin-created users.

        Args:
            user_data: User data dictionary (modified in place)
            scope: Institution scope for the current admin
        """
        if not scope or scope.is_global:
            return

        if not scope.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: missing institution scope"
            )

        target_institution = user_data.get("institution_id")
        if target_institution:
            scope.enforce(target_institution)
        else:
            user_data["institution_id"] = UUID(scope.institution_id)
    
    def validate_user_permissions(
        self, 
        current_user: Dict[str, Any], 
        target_institution_id: Optional[UUID] = None
    ) -> None:
        """
        Validate user permissions for user creation.
        
        Args:
            current_user: Current user information
            target_institution_id: Target institution ID (if creating for specific institution)
            
        Raises:
            HTTPException: For permission failures
        """
        # Basic permission check - user must be authenticated
        if not current_user or not current_user.get("user_id"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Additional permission checks can be added here based on role/institution
        # For now, we'll allow any authenticated user to create users
        # This can be enhanced with role-based access control
        
        log_info(f"User permissions validated for user creation: {current_user['user_id']}")
    
    def get_signup_constants(self) -> Dict[str, UUID]:
        """
        Get signup constants for external use.
        
        Returns:
            Dictionary of signup constants
        """
        return {
            "customer_institution": self.CUSTOMER_INSTITUTION,
            "customer_role_type": self.CUSTOMER_ROLE_TYPE.value,
            "customer_role_name": self.CUSTOMER_ROLE_NAME.value,
            "bot_user_id": self.BOT_USER_ID
        }


# Create service instance
user_signup_service = UserSignupService()
