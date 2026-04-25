"""
Unit tests for authentication dependency functions.

Tests permission checks, role validation, and access control logic
for all dependency functions in app/auth/dependencies.py.

K7: Updated assertions to check envelope detail shape (code field)
instead of bare-string detail content.
"""

import pytest
from fastapi import HTTPException

from app.auth.dependencies import (
    get_admin_user,
    get_client_or_employee_user,
    get_client_user,
    get_employee_user,
    get_super_admin_user,
)


def _assert_permission_denied(exc_info, expected_code: str = "security.insufficient_permissions") -> None:
    """Helper: assert the exception is a 403 with the expected envelope code."""
    assert exc_info.value.status_code == 403
    detail = exc_info.value.detail
    assert isinstance(detail, dict), f"Expected envelope dict, got: {detail!r}"
    assert detail.get("code") == expected_code, f"Expected code={expected_code!r}, got: {detail.get('code')!r}"


class TestInternalUserAccess:
    """Test cases for get_employee_user() dependency"""

    def test_allows_employee(self, sample_employee_user):
        """Test that get_employee_user() allows Internal role_type"""
        result = get_employee_user(sample_employee_user)
        assert result == sample_employee_user

    def test_allows_super_admin(self, sample_super_admin_user):
        """Test that get_employee_user() allows Super Admin (Internal role_type)"""
        result = get_employee_user(sample_super_admin_user)
        assert result == sample_super_admin_user

    def test_rejects_supplier(self, sample_supplier_user):
        """Test that get_employee_user() rejects Supplier role_type"""
        with pytest.raises(HTTPException) as exc_info:
            get_employee_user(sample_supplier_user)
        _assert_permission_denied(exc_info)

    def test_rejects_customer(self, sample_customer_user):
        """Test that get_employee_user() rejects Customer role_type"""
        with pytest.raises(HTTPException) as exc_info:
            get_employee_user(sample_customer_user)
        _assert_permission_denied(exc_info)


class TestSuperAdminUserAccess:
    """Test cases for get_super_admin_user() dependency"""

    def test_allows_super_admin(self, sample_super_admin_user):
        """Test that get_super_admin_user() allows Super Admin (Internal + Super Admin)"""
        result = get_super_admin_user(sample_super_admin_user)
        assert result == sample_super_admin_user

    def test_rejects_employee(self, sample_employee_user):
        """Test that get_super_admin_user() rejects regular Internal (Admin)"""
        with pytest.raises(HTTPException) as exc_info:
            get_super_admin_user(sample_employee_user)
        _assert_permission_denied(exc_info)

    def test_rejects_supplier(self, sample_supplier_user):
        """Test that get_super_admin_user() rejects Supplier"""
        with pytest.raises(HTTPException) as exc_info:
            get_super_admin_user(sample_supplier_user)
        _assert_permission_denied(exc_info)

    def test_rejects_customer(self, sample_customer_user):
        """Test that get_super_admin_user() rejects Customer"""
        with pytest.raises(HTTPException) as exc_info:
            get_super_admin_user(sample_customer_user)
        _assert_permission_denied(exc_info)


class TestAdminUserAccess:
    """Test cases for get_admin_user() dependency"""

    def test_allows_employee_admin(self, sample_employee_user):
        """Test that get_admin_user() allows Internal with Admin role_name"""
        result = get_admin_user(sample_employee_user)
        assert result == sample_employee_user

    def test_allows_super_admin(self, sample_super_admin_user):
        """Test that get_admin_user() allows Super Admin (Internal + Super Admin)"""
        result = get_admin_user(sample_super_admin_user)
        assert result == sample_super_admin_user

    def test_rejects_supplier(self, sample_supplier_user):
        """Test that get_admin_user() rejects Supplier Admin"""
        with pytest.raises(HTTPException) as exc_info:
            get_admin_user(sample_supplier_user)
        _assert_permission_denied(exc_info)

    def test_rejects_customer(self, sample_customer_user):
        """Test that get_admin_user() rejects Customer"""
        with pytest.raises(HTTPException) as exc_info:
            get_admin_user(sample_customer_user)
        _assert_permission_denied(exc_info)


class TestClientUserAccess:
    """Test cases for get_client_user() dependency"""

    def test_allows_customer(self, sample_customer_user):
        """Test that get_client_user() allows Customer role_type"""
        result = get_client_user(sample_customer_user)
        assert result == sample_customer_user

    def test_rejects_employee(self, sample_employee_user):
        """Test that get_client_user() rejects Internal"""
        with pytest.raises(HTTPException) as exc_info:
            get_client_user(sample_employee_user)
        _assert_permission_denied(exc_info)

    def test_rejects_super_admin(self, sample_super_admin_user):
        """Test that get_client_user() rejects Super Admin"""
        with pytest.raises(HTTPException) as exc_info:
            get_client_user(sample_super_admin_user)
        _assert_permission_denied(exc_info)

    def test_rejects_supplier(self, sample_supplier_user):
        """Test that get_client_user() rejects Supplier"""
        with pytest.raises(HTTPException) as exc_info:
            get_client_user(sample_supplier_user)
        _assert_permission_denied(exc_info)


class TestClientOrInternalUserAccess:
    """Test cases for get_client_or_employee_user() dependency"""

    def test_allows_customer(self, sample_customer_user):
        """Test that get_client_or_employee_user() allows Customer"""
        result = get_client_or_employee_user(sample_customer_user)
        assert result == sample_customer_user

    def test_allows_employee(self, sample_employee_user):
        """Test that get_client_or_employee_user() allows Internal"""
        result = get_client_or_employee_user(sample_employee_user)
        assert result == sample_employee_user

    def test_allows_super_admin(self, sample_super_admin_user):
        """Test that get_client_or_employee_user() allows Super Admin (Internal)"""
        result = get_client_or_employee_user(sample_super_admin_user)
        assert result == sample_super_admin_user

    def test_rejects_supplier(self, sample_supplier_user):
        """Test that get_client_or_employee_user() rejects Supplier"""
        with pytest.raises(HTTPException) as exc_info:
            get_client_or_employee_user(sample_supplier_user)
        _assert_permission_denied(exc_info)


class TestEnvelopeShape:
    """K7 regression: verify that 403 responses carry proper envelope detail."""

    def test_get_employee_user_403_has_envelope_code(self, sample_supplier_user):
        """403 from get_employee_user carries envelope dict with code field."""
        with pytest.raises(HTTPException) as exc_info:
            get_employee_user(sample_supplier_user)
        detail: dict = exc_info.value.detail  # type: ignore[assignment]
        assert "code" in detail
        assert "message" in detail
        assert "params" in detail
        assert detail["code"] == "security.insufficient_permissions"

    def test_get_super_admin_user_403_has_envelope_code(self, sample_customer_user):
        """403 from get_super_admin_user carries envelope dict with code field."""
        with pytest.raises(HTTPException) as exc_info:
            get_super_admin_user(sample_customer_user)
        detail: dict = exc_info.value.detail  # type: ignore[assignment]
        assert detail["code"] == "security.insufficient_permissions"
