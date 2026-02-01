"""
Centralized Scoping System

This module provides a unified scoping system for access control based on:
- Institution Scoping: Restricts access to resources within a user's institution
- User Scoping: Restricts access to resources owned by a specific user

All scope classes follow a consistent pattern:
- `is_global`: Returns True if the user has global access (no restrictions)
- `matches(resource_id)`: Returns True if the resource matches the scope
- `enforce(resource_id)`: Raises HTTPException if the resource doesn't match
"""

from dataclasses import dataclass
from typing import Optional, Any, Tuple, Dict
from uuid import UUID

from fastapi import HTTPException


def _normalize(value: Any) -> Optional[str]:
    """Convert UUID/str values to a comparable string representation."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    return str(value)


@dataclass
class InstitutionScope:
    """
    Represents the institution access scope for the current user.
    
    Used for resources that belong to institutions (restaurants, products, plates, etc.).
    
    Behavior:
    - Employee Admin/Super Admin: Global access (can see all institutions)
    - Employee Management: Scoped to their institution_id
    - Employee Operator: No management capabilities (self-updates only)
    - Suppliers: Scoped to their institution_id
    - Customers: Not typically used (customers use UserScope instead)
    """

    institution_id: Optional[str]
    role_type: str
    role_name: Optional[str] = None

    def __post_init__(self) -> None:
        self.institution_id = _normalize(self.institution_id)

    @property
    def is_global(self) -> bool:
        """
        Returns True if the user has global access (can see all institutions).
        
        Only Employee Admin and Employee Super Admin have global access.
        Employee Management has institution scope.
        Employee Operator has no management capabilities.
        """
        if self.role_type != "Employee":
            return False
        
        # Check role_name for Employees
        if self.role_name in ["Admin", "Super Admin"]:
            return True
        
        return False

    @property
    def is_employee(self) -> bool:
        """
        Returns True if the user is an Employee (Vianda Enterprises staff).
        
        Employee users can have different access levels:
        - Admin/Super Admin: Global access
        - Management: Institution-scoped access
        - Operator: Self-updates only
        """
        return self.role_type == "Employee"

    def matches(self, resource_institution_id: Optional[Any]) -> bool:
        """Returns True if the resource's institution_id matches this scope."""
        if self.is_global:
            return True
        if self.institution_id is None:
            return False
        return _normalize(resource_institution_id) == self.institution_id

    def enforce(self, resource_institution_id: Optional[Any]) -> None:
        """Raises HTTPException if the resource doesn't match this scope."""
        if self.matches(resource_institution_id):
            return
        raise HTTPException(
            status_code=403,
            detail="Forbidden: institution mismatch"
        )


@dataclass
class UserScope:
    """
    Represents the user access scope for the current user.
    
    Used for resources that belong to individual users (user records, addresses, etc.).
    
    Behavior:
    - Employee Admin/Super Admin: Global access (can see all users)
    - Employee Management: Scoped to users within their institution_id
    - Employee Operator: Scoped to their own user_id only (self-updates)
    - Suppliers: Scoped to users within their institution_id
    - Customers: Scoped to their own user_id only
    
    For addresses specifically:
    - Customers: Can only manage addresses where user_id == their own user_id
    - Suppliers: Can manage addresses for any user within their institution_id
    - Employee Admin/Super Admin: Global access
    - Employee Management: Can manage addresses for users within their institution
    - Employee Operator: Can only manage their own addresses
    """

    user_id: Optional[str]
    institution_id: Optional[str]
    role_type: str
    role_name: Optional[str] = None

    def __post_init__(self) -> None:
        self.user_id = _normalize(self.user_id)
        self.institution_id = _normalize(self.institution_id)

    @property
    def is_global(self) -> bool:
        """
        Returns True if the user has global access (can see all users).
        
        Only Employee Admin and Employee Super Admin have global access.
        Employee Management has institution scope.
        Employee Operator has no management capabilities.
        """
        if self.role_type != "Employee":
            return False
        
        # Check role_name for Employees
        role_name = getattr(self, 'role_name', None)
        if role_name in ["Admin", "Super Admin"]:
            return True
        
        return False

    @property
    def is_customer(self) -> bool:
        """Returns True if the user is a Customer."""
        return self.role_type == "Customer"

    @property
    def is_supplier(self) -> bool:
        """Returns True if the user is a Supplier."""
        return self.role_type == "Supplier"

    def matches_user(self, resource_user_id: Optional[Any]) -> bool:
        """
        Returns True if the resource's user_id matches this scope.
        
        - Customers: Must match their own user_id
        - Employee Operator: Must match their own user_id
        - Suppliers: Must match a user_id within their institution
        - Employee Management: Must match a user_id within their institution
        - Employee Admin/Super Admin: Always matches (global access)
        """
        if self.is_global:
            return True
        
        # Employee Operator: self-scope only
        if self.role_type == "Employee" and self.role_name == "Operator":
            return _normalize(resource_user_id) == self.user_id
        
        if self.is_customer:
            # Customers can only access their own user_id
            return _normalize(resource_user_id) == self.user_id
        
        if self.is_supplier:
            # Suppliers can access users within their institution
            # Note: This requires a database check to verify the user belongs to the institution
            # For now, we return True and let the route/service layer handle institution validation
            return True
        
        # Employee Management: institution-scoped (handled in route/service layer)
        if self.role_type == "Employee" and self.role_name == "Management":
            return True  # Institution validation happens in route/service layer
        
        return False

    def enforce_user(self, resource_user_id: Optional[Any]) -> None:
        """
        Raises HTTPException if the resource's user_id doesn't match this scope.
        
        For Customers: Must be their own user_id
        For Employee Operator: Must be their own user_id
        For Suppliers: Must validate via institution_id (handled in route/service layer)
        For Employee Management: Must validate via institution_id (handled in route/service layer)
        For Employee Admin/Super Admin: Global access (no enforcement needed)
        """
        # Employee Operator: self-scope only
        if self.role_type == "Employee" and self.role_name == "Operator":
            if _normalize(resource_user_id) != self.user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: Employee Operators can only access their own records"
                )
            return
        
        if self.is_customer and _normalize(resource_user_id) != self.user_id:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: customers can only access their own records"
            )
        # For Suppliers, Employee Management, and Employee Admin/Super Admin, 
        # additional validation happens in route/service layer

    def can_assign_user_id(self, target_user_id: Optional[Any], target_user_institution_id: Optional[Any]) -> bool:
        """
        Returns True if the current user can assign user_id to the target user.
        
        Used for address creation/update where user_id can be assigned.
        
        - Customers: Can only assign their own user_id
        - Employee Operator: Can only assign their own user_id
        - Suppliers: Can assign user_id to any user within their institution_id
        - Employee Management: Can assign user_id to any user within their institution_id
        - Employee Admin/Super Admin: Can assign to any user (global access)
        """
        if self.is_global:
            return True
        
        # Employee Operator: self-scope only
        if self.role_type == "Employee" and self.role_name == "Operator":
            return _normalize(target_user_id) == self.user_id
        
        if self.is_customer:
            # Customers can only assign their own user_id
            return _normalize(target_user_id) == self.user_id
        
        if self.is_supplier:
            # Suppliers can assign to users within their institution
            return _normalize(target_user_institution_id) == self.institution_id
        
        # Employee Management: institution-scoped
        if self.role_type == "Employee" and self.role_name == "Management":
            return _normalize(target_user_institution_id) == self.institution_id
        
        return False

    def enforce_user_assignment(self, target_user_id: Optional[Any], target_user_institution_id: Optional[Any]) -> None:
        """
        Raises HTTPException if the current user cannot assign user_id to the target user.
        """
        if not self.can_assign_user_id(target_user_id, target_user_institution_id):
            if self.is_customer:
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: customers can only assign addresses to themselves"
                )
            elif self.role_type == "Employee" and self.role_name == "Operator":
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: Employee Operators can only assign addresses to themselves"
                )
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: cannot assign address to user outside your institution"
                )


def get_institution_scope(current_user: dict) -> InstitutionScope:
    """
    Create an InstitutionScope instance from the authenticated user payload.
    
    Args:
        current_user: Dictionary containing user information from JWT token
        
    Returns:
        InstitutionScope instance with role_name included
    """
    institution_id = current_user.get("institution_id")
    role_type = current_user.get("role_type", "Unknown")
    role_name = current_user.get("role_name", None)
    return InstitutionScope(institution_id=institution_id, role_type=role_type, role_name=role_name)


def get_user_scope(current_user: dict) -> UserScope:
    """
    Create a UserScope instance from the authenticated user payload.
    
    Args:
        current_user: Dictionary containing user information from JWT token
        
    Returns:
        UserScope instance with role_name included
    """
    user_id = current_user.get("user_id")
    institution_id = current_user.get("institution_id")
    role_type = current_user.get("role_type", "Unknown")
    role_name = current_user.get("role_name", None)
    return UserScope(user_id=user_id, institution_id=institution_id, role_type=role_type, role_name=role_name)



# =============================================================================
# 3. ACCESS CONTROL PATTERNS
# =============================================================================

class EmployeeCustomerAccessControl:
    """
    Helper class for "Employee global + Customer self-scope" access pattern.
    
    This pattern is used for user-owned resources where:
    - Employee Admin/Super Admin: Have global access (can see all records)
    - Employee Management: Have institution-scoped access (can see records in their institution)
    - Employee Operator: Have self-scoped access (can only see their own records)
    - Customers: Have self-scoped access (can only see their own records)
    - Suppliers: Are blocked (403 Forbidden)
    
    Usage:
        user_id, error = EmployeeCustomerAccessControl.enforce_access(current_user)
        if error:
            raise HTTPException(**error)
        
        # Use user_id to filter queries for Customers and Employee Operators
        # For Employee Admin/Super Admin, user_id will be None (no filtering needed)
        # For Employee Management, scope is applied in route layer
    """
    
    @staticmethod
    def enforce_access(current_user: dict) -> Tuple[Optional[UUID], Optional[Dict[str, Any]]]:
        """
        Enforce access control and return user_id filter if needed.
        
        Args:
            current_user: Current authenticated user dictionary
            
        Returns:
            Tuple of (user_id, error_dict):
            - user_id: UUID to filter by (for Customers), None for Employees
            - error_dict: Dict with status_code and detail if access denied, None otherwise
            
        Example:
            user_id, error = EmployeeCustomerAccessControl.enforce_access(current_user)
            if error:
                raise HTTPException(**error)
            
            # For Customers: filter by user_id
            # For Employees: user_id is None (global access)
        """
        
        role_type = current_user.get("role_type")
        
        # Block Suppliers
        if role_type == "Supplier":
            return None, {
                "status_code": 403,
                "detail": "Forbidden: Suppliers cannot access this resource"
            }
        
        # Customers: self-scope (filter by their own user_id)
        if role_type == "Customer":
            user_id = current_user.get("user_id")
            if not user_id:
                return None, {
                    "status_code": 401,
                    "detail": "User ID not found in token"
                }
            # Convert to UUID if it's a string
            if isinstance(user_id, str):
                try:
                    user_id = UUID(user_id)
                except ValueError:
                    return None, {
                        "status_code": 401,
                        "detail": "Invalid user ID format in token"
                    }
            return user_id, None
        
        # Employees: check role_name for access level
        if role_type == "Employee":
            role_name = current_user.get("role_name")
            if role_name in ["Admin", "Super Admin"]:
                return None, None  # Global access
            elif role_name == "Management":
                # Employee Management: institution-scoped (handled via scope in route)
                return None, None  # Scope applied in route layer
            elif role_name == "Operator":
                # Employee Operator: self-scope only (same as Customer)
                user_id = current_user.get("user_id")
                if not user_id:
                    return None, {
                        "status_code": 401,
                        "detail": "User ID not found in token"
                    }
                if isinstance(user_id, str):
                    try:
                        user_id = UUID(user_id)
                    except ValueError:
                        return None, {
                            "status_code": 401,
                            "detail": "Invalid user ID format in token"
                        }
                return user_id, None
            else:
                # Unknown Employee role_name
                return None, {
                    "status_code": 403,
                    "detail": "Access denied: unknown Employee role"
                }
        
        # Unknown role type
        return None, {
            "status_code": 403,
            "detail": "Access denied"
        }
    
    @staticmethod
    def verify_ownership(
        record_user_id: UUID,
        current_user: dict
    ) -> Optional[Dict[str, Any]]:
        """
        Verify that a record belongs to the current customer user.
        
        This is used when fetching a single record by ID to ensure Customers
        can only access their own records.
        
        Args:
            record_user_id: The user_id from the record being accessed
            current_user: Current authenticated user dictionary
            
        Returns:
            error_dict if access denied, None if allowed
            
        Example:
            subscription = get_subscription_by_id(subscription_id, db)
            if not subscription:
                raise HTTPException(status_code=404, detail="Subscription not found")
            
            error = EmployeeCustomerAccessControl.verify_ownership(
                subscription.user_id,
                current_user
            )
            if error:
                raise HTTPException(**error)
        """
        role_type = current_user.get("role_type")
        
        # Employees: check role_name for access level
        if role_type == "Employee":
            role_name = current_user.get("role_name")
            if role_name in ["Admin", "Super Admin"]:
                return None  # Global access
            elif role_name == "Management":
                # Employee Management: institution-scoped (validation happens in route)
                return None  # Institution validation in route layer
            elif role_name == "Operator":
                # Employee Operator: self-scope only (same as Customer)
                user_id = current_user.get("user_id")
                if not user_id:
                    return {
                        "status_code": 401,
                        "detail": "User ID not found in token"
                    }
                if isinstance(user_id, str):
                    try:
                        user_id = UUID(user_id)
                    except ValueError:
                        return {
                            "status_code": 401,
                            "detail": "Invalid user ID format in token"
                        }
                if record_user_id != user_id:
                    return {
                        "status_code": 404,
                        "detail": "Resource not found"  # Don't reveal existence of other records
                    }
            else:
                # Unknown Employee role_name
                return {
                    "status_code": 403,
                    "detail": "Access denied: unknown Employee role"
                }
            return None
        
        # Customers can only access their own records
        if role_type == "Customer":
            user_id = current_user.get("user_id")
            if not user_id:
                return {
                    "status_code": 401,
                    "detail": "User ID not found in token"
                }
            
            # Convert to UUID if needed
            if isinstance(user_id, str):
                try:
                    user_id = UUID(user_id)
                except ValueError:
                    return {
                        "status_code": 401,
                        "detail": "Invalid user ID format in token"
                    }
            
            # Verify ownership
            if record_user_id != user_id:
                return {
                    "status_code": 404,
                    "detail": "Resource not found"  # Don't reveal existence of other records
                }
        
        return None
    
    @staticmethod
    def get_scope_for_query(current_user: dict) -> tuple[Optional[InstitutionScope], Optional[UUID], Optional[Dict[str, Any]]]:
        """
        Get scope and user_id filter for database queries.
        
        This is a convenience method that combines enforce_access logic
        with scope determination (though scope is typically None for this pattern).
        
        Args:
            current_user: Current authenticated user dictionary
            
        Returns:
            Tuple of (scope, user_id, error_dict):
            - scope: InstitutionScope (typically None for this pattern)
            - user_id: UUID to filter by (for Customers), None for Employees
            - error_dict: Dict with status_code and detail if access denied, None otherwise
        """
        
        user_id, error = EmployeeCustomerAccessControl.enforce_access(current_user)
        if error:
            return None, None, error
        
        # For this pattern, we don't use institution scoping
        # Employees get global access, Customers get user_id filtering
        return None, user_id, None
