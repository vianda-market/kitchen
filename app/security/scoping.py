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
from typing import Any
from uuid import UUID

from fastapi import HTTPException  # noqa: F401 — used in raise HTTPException(**error) patterns below

from app.i18n.envelope import build_envelope, envelope_exception
from app.i18n.error_codes import ErrorCode


def _normalize(value: Any) -> str | None:
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

    Used for resources that belong to institutions (restaurants, products, viandas, etc.).

    Behavior:
    - Internal Admin/Super Admin: Global access (can see all institutions)
    - Internal Management: Scoped to their institution_id
    - Internal Operator: No management capabilities (self-updates only)
    - Suppliers: Scoped to their institution_id
    - Employer: Scoped to their institution_id (institution-scoped like Supplier)
    - Customers: Not typically used (customers use UserScope instead)
    """

    institution_id: str | None
    role_type: str
    role_name: str | None = None

    def __post_init__(self) -> None:
        self.institution_id = _normalize(self.institution_id)

    @property
    def is_global(self) -> bool:
        """
        Returns True if the user has global access (can see all institutions).

        Only Internal Admin and Internal Super Admin have global access.
        Internal Management has institution scope.
        Internal Operator has no management capabilities.
        Supplier and Employer are institution-scoped.
        """
        if self.role_type != "internal":
            return False

        # Check role_name for Internal users
        return self.role_name in ["admin", "super_admin"]

    @property
    def is_employee(self) -> bool:
        """
        Returns True if the user is Internal (Vianda Enterprises staff).

        Internal users can have different access levels:
        - Admin/Super Admin: Global access
        - Manager: Institution-scoped access
        - Operator: Self-updates only
        """
        return self.role_type == "internal"

    def matches(self, resource_institution_id: Any | None) -> bool:
        """Returns True if the resource's institution_id matches this scope."""
        if self.is_global:
            return True
        if self.institution_id is None:
            return False
        return _normalize(resource_institution_id) == self.institution_id

    def enforce(self, resource_institution_id: Any | None) -> None:
        """Raises HTTPException if the resource doesn't match this scope."""
        if self.matches(resource_institution_id):
            return
        # locale not available in scope helper; default to "en" (decision C)
        raise envelope_exception(ErrorCode.SECURITY_INSTITUTION_MISMATCH, status=403, locale="en")


def resolve_institution_filter(request_institution_id: UUID | None, scope: InstitutionScope | None) -> UUID | None:
    """
    Validate that the current user may filter list results by the given institution_id.
    Used by list/enriched endpoints that accept optional institution_id query parameter.

    - If request_institution_id is None, returns None (no extra filter).
    - If scope is None or scope.is_global, returns request_institution_id (allowed).
    - If not scope.is_global and scope.matches(request_institution_id), returns request_institution_id.
    - Otherwise raises HTTPException 403 Forbidden.
    """
    if request_institution_id is None:
        return None
    if scope is None or scope.is_global:
        return request_institution_id
    if scope.matches(request_institution_id):
        return request_institution_id
    raise envelope_exception(ErrorCode.SECURITY_INSTITUTION_MISMATCH, status=403, locale="en")


@dataclass
class UserScope:
    """
    Represents the user access scope for the current user.

    Used for resources that belong to individual users (user records, addresses, etc.).

    Behavior:
    - Internal Admin/Super Admin: Global access (can see all users)
    - Internal Management: Scoped to users within their institution_id
    - Internal Operator: Scoped to their own user_id only (self-updates)
    - Suppliers: Scoped to users within their institution_id
    - Employer: Scoped to users within their institution_id (institution-scoped like Supplier)
    - Customers: Scoped to their own user_id only

    For addresses specifically:
    - Customers: Can only manage addresses where user_id == their own user_id
    - Suppliers: Can manage addresses for any user within their institution_id
    - Internal Admin/Super Admin: Global access
    - Internal Management: Can manage addresses for users within their institution
    - Internal Operator: Can only manage their own addresses
    """

    user_id: str | None
    institution_id: str | None
    role_type: str
    role_name: str | None = None

    def __post_init__(self) -> None:
        self.user_id = _normalize(self.user_id)
        self.institution_id = _normalize(self.institution_id)

    @property
    def is_global(self) -> bool:
        """
        Returns True if the user has global access (can see all users).

        Only Internal Admin and Internal Super Admin have global access.
        Internal Management has institution scope.
        Internal Operator has no management capabilities.
        Supplier and Employer are institution-scoped.
        """
        if self.role_type != "internal":
            return False

        # Check role_name for Internal users
        role_name = getattr(self, "role_name", None)
        return role_name in ["admin", "super_admin"]

    @property
    def is_customer(self) -> bool:
        """Returns True if the user is a Customer."""
        return self.role_type == "customer"

    @property
    def is_supplier(self) -> bool:
        """Returns True if the user is a Supplier."""
        return self.role_type == "supplier"

    def matches_user(self, resource_user_id: Any | None) -> bool:
        """
        Returns True if the resource's user_id matches this scope.

        - Customers: Must match their own user_id
        - Internal Operator: Must match their own user_id
        - Suppliers: Must match a user_id within their institution
        - Employer: Must match a user_id within their institution
        - Internal Management: Must match a user_id within their institution
        - Internal Admin/Super Admin: Always matches (global access)
        """
        if self.is_global:
            return True

        # Internal Operator: self-scope only
        if self.role_type == "internal" and self.role_name == "operator":
            return _normalize(resource_user_id) == self.user_id

        if self.is_customer:
            # Customers can only access their own user_id
            return _normalize(resource_user_id) == self.user_id

        if self.is_supplier:
            # Suppliers can access users within their institution
            # Note: This requires a database check to verify the user belongs to the institution
            # For now, we return True and let the route/service layer handle institution validation
            return True

        # Internal Management: institution-scoped (handled in route/service layer)
        if self.role_type == "internal" and self.role_name == "manager":
            return True  # Institution validation happens in route/service layer

        return False

    def enforce_user(self, resource_user_id: Any | None) -> None:
        """
        Raises HTTPException if the resource's user_id doesn't match this scope.

        For Customers: Must be their own user_id
        For Internal Operator: Must be their own user_id
        For Suppliers: Must validate via institution_id (handled in route/service layer)
        For Internal Management: Must validate via institution_id (handled in route/service layer)
        For Internal Admin/Super Admin: Global access (no enforcement needed)
        """
        # Internal Operator: self-scope only
        if self.role_type == "internal" and self.role_name == "operator":
            if _normalize(resource_user_id) != self.user_id:
                raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=403, locale="en")
            return

        if self.is_customer and _normalize(resource_user_id) != self.user_id:
            raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=403, locale="en")
        # For Suppliers, Internal Management, and Internal Admin/Super Admin,
        # additional validation happens in route/service layer

    def can_assign_user_id(self, target_user_id: Any | None, target_user_institution_id: Any | None) -> bool:
        """
        Returns True if the current user can assign user_id to the target user.

        Used for address creation/update where user_id can be assigned.

        - Customers: Can only assign their own user_id
        - Internal Operator: Can only assign their own user_id
        - Suppliers: Can assign user_id to any user within their institution_id
        - Internal Management: Can assign user_id to any user within their institution_id
        - Internal Admin/Super Admin: Can assign to any user (global access)
        """
        if self.is_global:
            return True

        # Internal Operator: self-scope only
        if self.role_type == "internal" and self.role_name == "operator":
            return _normalize(target_user_id) == self.user_id

        if self.is_customer:
            # Customers can only assign their own user_id
            return _normalize(target_user_id) == self.user_id

        if self.is_supplier:
            # Suppliers can assign to users within their institution
            return _normalize(target_user_institution_id) == self.institution_id

        # Internal Management: institution-scoped
        if self.role_type == "internal" and self.role_name == "manager":
            return _normalize(target_user_institution_id) == self.institution_id

        return False

    def enforce_user_assignment(self, target_user_id: Any | None, target_user_institution_id: Any | None) -> None:
        """
        Raises HTTPException if the current user cannot assign user_id to the target user.
        """
        if not self.can_assign_user_id(target_user_id, target_user_institution_id):
            raise envelope_exception(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, status=403, locale="en")


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
    role_name = current_user.get("role_name")
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
    role_name = current_user.get("role_name")
    return UserScope(user_id=user_id, institution_id=institution_id, role_type=role_type, role_name=role_name)


# =============================================================================
# 3. ACCESS CONTROL PATTERNS
# =============================================================================


class EmployeeCustomerAccessControl:
    """
    Helper class for "Internal global + Customer self-scope" access pattern.

    This pattern is used for user-owned resources where:
    - Internal Admin/Super Admin: Have global access (can see all records)
    - Internal Management: Have institution-scoped access (can see records in their institution)
    - Internal Operator: Have self-scoped access (can only see their own records)
    - Customers: Have self-scoped access (can only see their own records)
    - Suppliers: Are blocked (403 Forbidden)

    Usage:
        user_id, error = EmployeeCustomerAccessControl.enforce_access(current_user)
        if error:
            raise HTTPException(**error)

        # Use user_id to filter queries for Customers and Internal Operators
        # For Internal Admin/Super Admin, user_id will be None (no filtering needed)
        # For Internal Management, scope is applied in route layer
    """

    @staticmethod
    def enforce_access(current_user: dict) -> tuple[UUID | None, dict[str, Any] | None]:
        """
        Enforce access control and return user_id filter if needed.

        Args:
            current_user: Current authenticated user dictionary

        Returns:
            Tuple of (user_id, error_dict):
            - user_id: UUID to filter by (for Customers), None for Internal users
            - error_dict: Dict with status_code and detail if access denied, None otherwise

        Example:
            user_id, error = EmployeeCustomerAccessControl.enforce_access(current_user)
            if error:
                raise HTTPException(**error)

            # For Customers: filter by user_id
            # For Internal: user_id is None (global access)
        """

        role_type = current_user.get("role_type")

        # Block Suppliers
        if role_type == "supplier":
            return None, {
                "status_code": 403,
                "detail": build_envelope(ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS, "en"),
            }

        # Customers: self-scope (filter by their own user_id)
        if role_type == "customer":
            user_id = current_user.get("user_id")
            if not user_id:
                return None, {
                    "status_code": 401,
                    "detail": build_envelope(ErrorCode.SECURITY_TOKEN_USER_ID_MISSING, "en"),
                }
            # Convert to UUID if it's a string
            if isinstance(user_id, str):
                try:
                    user_id = UUID(user_id)
                except ValueError:
                    return None, {
                        "status_code": 401,
                        "detail": build_envelope(ErrorCode.SECURITY_TOKEN_USER_ID_INVALID, "en"),
                    }
            return user_id, None

        # Internal: check role_name for access level
        if role_type == "internal":
            role_name = current_user.get("role_name")
            if role_name in ["admin", "super_admin"]:
                return None, None  # Global access
            if role_name == "manager":
                # Internal Management: institution-scoped (handled via scope in route)
                return None, None  # Scope applied in route layer
            if role_name == "operator":
                # Internal Operator: self-scope only (same as Customer)
                user_id = current_user.get("user_id")
                if not user_id:
                    return None, {
                        "status_code": 401,
                        "detail": build_envelope(ErrorCode.SECURITY_TOKEN_USER_ID_MISSING, "en"),
                    }
                if isinstance(user_id, str):
                    try:
                        user_id = UUID(user_id)
                    except ValueError:
                        return None, {
                            "status_code": 401,
                            "detail": build_envelope(ErrorCode.SECURITY_TOKEN_USER_ID_INVALID, "en"),
                        }
                return user_id, None
            # Unknown Internal role_name
            return None, {"status_code": 403, "detail": build_envelope(ErrorCode.SECURITY_FORBIDDEN, "en")}

        # Unknown role type
        return None, {"status_code": 403, "detail": build_envelope(ErrorCode.SECURITY_FORBIDDEN, "en")}

    @staticmethod
    def verify_ownership(record_user_id: UUID, current_user: dict) -> dict[str, Any] | None:
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
                raise envelope_exception(ErrorCode.SUBSCRIPTION_NOT_FOUND, status=404, locale="en")

            error = EmployeeCustomerAccessControl.verify_ownership(
                subscription.user_id,
                current_user
            )
            if error:
                raise HTTPException(**error)
        """
        role_type = current_user.get("role_type")

        # Internal: check role_name for access level
        if role_type == "internal":
            role_name = current_user.get("role_name")
            if role_name in ["admin", "super_admin"]:
                return None  # Global access
            if role_name == "manager":
                # Internal Management: institution-scoped (validation happens in route)
                return None  # Institution validation in route layer
            if role_name == "operator":
                # Internal Operator: self-scope only (same as Customer)
                user_id = current_user.get("user_id")
                if not user_id:
                    return {
                        "status_code": 401,
                        "detail": build_envelope(ErrorCode.SECURITY_TOKEN_USER_ID_MISSING, "en"),
                    }
                if isinstance(user_id, str):
                    try:
                        user_id = UUID(user_id)
                    except ValueError:
                        return {
                            "status_code": 401,
                            "detail": build_envelope(ErrorCode.SECURITY_TOKEN_USER_ID_INVALID, "en"),
                        }
                if record_user_id != user_id:
                    # Return 404 to avoid revealing existence of other records
                    return {
                        "status_code": 404,
                        "detail": build_envelope(ErrorCode.ENTITY_NOT_FOUND, "en", entity="Resource"),
                    }
            else:
                # Unknown Internal role_name
                return {"status_code": 403, "detail": build_envelope(ErrorCode.SECURITY_FORBIDDEN, "en")}
            return None

        # Customers can only access their own records
        if role_type == "customer":
            user_id = current_user.get("user_id")
            if not user_id:
                return {"status_code": 401, "detail": build_envelope(ErrorCode.SECURITY_TOKEN_USER_ID_MISSING, "en")}

            # Convert to UUID if needed
            if isinstance(user_id, str):
                try:
                    user_id = UUID(user_id)
                except ValueError:
                    return {
                        "status_code": 401,
                        "detail": build_envelope(ErrorCode.SECURITY_TOKEN_USER_ID_INVALID, "en"),
                    }

            # Verify ownership — return 404 to avoid revealing existence of other records
            if record_user_id != user_id:
                return {
                    "status_code": 404,
                    "detail": build_envelope(ErrorCode.ENTITY_NOT_FOUND, "en", entity="Resource"),
                }

        return None

    @staticmethod
    def get_scope_for_query(current_user: dict) -> tuple[InstitutionScope | None, UUID | None, dict[str, Any] | None]:
        """
        Get scope and user_id filter for database queries.

        This is a convenience method that combines enforce_access logic
        with scope determination (though scope is typically None for this pattern).

        Args:
            current_user: Current authenticated user dictionary

        Returns:
            Tuple of (scope, user_id, error_dict):
            - scope: InstitutionScope (typically None for this pattern)
            - user_id: UUID to filter by (for Customers), None for Internal users
            - error_dict: Dict with status_code and detail if access denied, None otherwise
        """

        user_id, error = EmployeeCustomerAccessControl.enforce_access(current_user)
        if error:
            return None, None, error

        # For this pattern, we don't use institution scoping
        # Internal users get global access, Customers get user_id filtering
        return None, user_id, None
