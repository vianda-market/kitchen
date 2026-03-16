"""
Unit tests for authentication dependency functions.

Tests permission checks, role validation, and access control logic
for all dependency functions in app/auth/dependencies.py.
"""

import pytest
from fastapi import HTTPException
from uuid import uuid4

from app.auth.dependencies import (
    get_employee_user,
    get_super_admin_user,
    get_admin_user,
    get_client_user,
    get_client_or_employee_user
)


class TestInternalUserAccess:
    """Test cases for get_employee_user() dependency"""
    
    def test_allows_employee(self, sample_employee_user):
        """Test that get_employee_user() allows Internal role_type"""
        # Act
        result = get_employee_user(sample_employee_user)
        
        # Assert
        assert result == sample_employee_user
    
    def test_allows_super_admin(self, sample_super_admin_user):
        """Test that get_employee_user() allows Super Admin (Internal role_type)"""
        # Act
        result = get_employee_user(sample_super_admin_user)
        
        # Assert
        assert result == sample_super_admin_user
    
    def test_rejects_supplier(self, sample_supplier_user):
        """Test that get_employee_user() rejects Supplier role_type"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_employee_user(sample_supplier_user)
        
        assert exc_info.value.status_code == 403
        assert "Internal access required" in str(exc_info.value.detail)
    
    def test_rejects_customer(self, sample_customer_user):
        """Test that get_employee_user() rejects Customer role_type"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_employee_user(sample_customer_user)
        
        assert exc_info.value.status_code == 403
        assert "Internal access required" in str(exc_info.value.detail)


class TestSuperAdminUserAccess:
    """Test cases for get_super_admin_user() dependency"""
    
    def test_allows_super_admin(self, sample_super_admin_user):
        """Test that get_super_admin_user() allows Super Admin (Internal + Super Admin)"""
        # Act
        result = get_super_admin_user(sample_super_admin_user)
        
        # Assert
        assert result == sample_super_admin_user
    
    def test_rejects_employee(self, sample_employee_user):
        """Test that get_super_admin_user() rejects regular Internal (Admin)"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_super_admin_user(sample_employee_user)
        
        assert exc_info.value.status_code == 403
        assert "Super-admin access required" in str(exc_info.value.detail)
    
    def test_rejects_supplier(self, sample_supplier_user):
        """Test that get_super_admin_user() rejects Supplier"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_super_admin_user(sample_supplier_user)
        
        assert exc_info.value.status_code == 403
        assert "Super-admin access required" in str(exc_info.value.detail)
    
    def test_rejects_customer(self, sample_customer_user):
        """Test that get_super_admin_user() rejects Customer"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_super_admin_user(sample_customer_user)
        
        assert exc_info.value.status_code == 403
        assert "Super-admin access required" in str(exc_info.value.detail)


class TestAdminUserAccess:
    """Test cases for get_admin_user() dependency"""
    
    def test_allows_employee_admin(self, sample_employee_user):
        """Test that get_admin_user() allows Internal with Admin role_name"""
        # Act
        result = get_admin_user(sample_employee_user)
        
        # Assert
        assert result == sample_employee_user
    
    def test_allows_super_admin(self, sample_super_admin_user):
        """Test that get_admin_user() allows Super Admin (Internal + Super Admin)"""
        # Act
        result = get_admin_user(sample_super_admin_user)
        
        # Assert
        assert result == sample_super_admin_user
    
    def test_rejects_supplier(self, sample_supplier_user):
        """Test that get_admin_user() rejects Supplier Admin"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_admin_user(sample_supplier_user)
        
        assert exc_info.value.status_code == 403
        assert "Admin access required" in str(exc_info.value.detail)
    
    def test_rejects_customer(self, sample_customer_user):
        """Test that get_admin_user() rejects Customer"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_admin_user(sample_customer_user)
        
        assert exc_info.value.status_code == 403
        assert "Admin access required" in str(exc_info.value.detail)


class TestClientUserAccess:
    """Test cases for get_client_user() dependency"""
    
    def test_allows_customer(self, sample_customer_user):
        """Test that get_client_user() allows Customer role_type"""
        # Act
        result = get_client_user(sample_customer_user)
        
        # Assert
        assert result == sample_customer_user
    
    def test_rejects_employee(self, sample_employee_user):
        """Test that get_client_user() rejects Internal"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_client_user(sample_employee_user)
        
        assert exc_info.value.status_code == 403
        assert "Customer access required" in str(exc_info.value.detail)
    
    def test_rejects_super_admin(self, sample_super_admin_user):
        """Test that get_client_user() rejects Super Admin"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_client_user(sample_super_admin_user)
        
        assert exc_info.value.status_code == 403
        assert "Customer access required" in str(exc_info.value.detail)
    
    def test_rejects_supplier(self, sample_supplier_user):
        """Test that get_client_user() rejects Supplier"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_client_user(sample_supplier_user)
        
        assert exc_info.value.status_code == 403
        assert "Customer access required" in str(exc_info.value.detail)


class TestClientOrInternalUserAccess:
    """Test cases for get_client_or_employee_user() dependency"""
    
    def test_allows_customer(self, sample_customer_user):
        """Test that get_client_or_employee_user() allows Customer"""
        # Act
        result = get_client_or_employee_user(sample_customer_user)
        
        # Assert
        assert result == sample_customer_user
    
    def test_allows_employee(self, sample_employee_user):
        """Test that get_client_or_employee_user() allows Internal"""
        # Act
        result = get_client_or_employee_user(sample_employee_user)
        
        # Assert
        assert result == sample_employee_user
    
    def test_allows_super_admin(self, sample_super_admin_user):
        """Test that get_client_or_employee_user() allows Super Admin (Internal)"""
        # Act
        result = get_client_or_employee_user(sample_super_admin_user)
        
        # Assert
        assert result == sample_super_admin_user
    
    def test_rejects_supplier(self, sample_supplier_user):
        """Test that get_client_or_employee_user() rejects Supplier"""
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            get_client_or_employee_user(sample_supplier_user)
        
        assert exc_info.value.status_code == 403
        assert "Customer or Internal access required" in str(exc_info.value.detail)

