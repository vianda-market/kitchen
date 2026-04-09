"""
Tests for field-level access policies.
"""

import pytest
from fastapi import HTTPException

from app.security.field_policies import (
    ensure_can_edit_supplier_terms,
    SUPPLIER_TERMS_EDIT_ROLES,
)


class TestEnsureCanEditSupplierTerms:
    """Tests for ensure_can_edit_supplier_terms."""

    def test_internal_manager_can_edit(self):
        """Internal Manager can edit supplier terms."""
        ensure_can_edit_supplier_terms({
            "role_type": "internal",
            "role_name": "manager",
        })

    def test_internal_global_manager_can_edit(self):
        """Internal Global Manager can edit supplier terms."""
        ensure_can_edit_supplier_terms({
            "role_type": "internal",
            "role_name": "global_manager",
        })

    def test_internal_admin_can_edit(self):
        """Internal Admin can edit supplier terms."""
        ensure_can_edit_supplier_terms({
            "role_type": "internal",
            "role_name": "admin",
        })

    def test_internal_super_admin_can_edit(self):
        """Internal Super Admin can edit supplier terms."""
        ensure_can_edit_supplier_terms({
            "role_type": "internal",
            "role_name": "super_admin",
        })

    def test_supplier_admin_cannot_edit(self):
        """Supplier Admin cannot edit supplier terms."""
        with pytest.raises(HTTPException) as exc_info:
            ensure_can_edit_supplier_terms({
                "role_type": "supplier",
                "role_name": "admin",
            })
        assert exc_info.value.status_code == 403
        assert "supplier terms" in str(exc_info.value.detail).lower()

    def test_internal_operator_cannot_edit(self):
        """Internal Operator cannot edit supplier terms."""
        with pytest.raises(HTTPException) as exc_info:
            ensure_can_edit_supplier_terms({
                "role_type": "internal",
                "role_name": "operator",
            })
        assert exc_info.value.status_code == 403

    def test_customer_cannot_edit(self):
        """Customer cannot edit supplier terms."""
        with pytest.raises(HTTPException) as exc_info:
            ensure_can_edit_supplier_terms({
                "role_type": "customer",
                "role_name": "comensal",
            })
        assert exc_info.value.status_code == 403
