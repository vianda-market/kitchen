"""
Tests for field-level access policies.
"""

import pytest
from fastapi import HTTPException

from app.security.field_policies import (
    ensure_can_edit_institution_no_show_discount,
    INSTITUTION_NO_SHOW_DISCOUNT_EDIT_ROLES,
)


class TestEnsureCanEditInstitutionNoShowDiscount:
    """Tests for ensure_can_edit_institution_no_show_discount."""

    def test_employee_manager_can_edit(self):
        """Internal Manager can edit no_show_discount."""
        ensure_can_edit_institution_no_show_discount({
            "role_type": "Internal",
            "role_name": "Manager",
        })

    def test_employee_global_manager_can_edit(self):
        """Employee Global Manager can edit no_show_discount."""
        ensure_can_edit_institution_no_show_discount({
            "role_type": "Internal",
            "role_name": "Global Manager",
        })

    def test_employee_admin_can_edit(self):
        """Internal Admin can edit no_show_discount."""
        ensure_can_edit_institution_no_show_discount({
            "role_type": "Internal",
            "role_name": "Admin",
        })

    def test_employee_super_admin_can_edit(self):
        """Internal Super Admin can edit no_show_discount."""
        ensure_can_edit_institution_no_show_discount({
            "role_type": "Internal",
            "role_name": "Super Admin",
        })

    def test_supplier_admin_cannot_edit(self):
        """Supplier Admin cannot edit no_show_discount."""
        with pytest.raises(HTTPException) as exc_info:
            ensure_can_edit_institution_no_show_discount({
                "role_type": "Supplier",
                "role_name": "Admin",
            })
        assert exc_info.value.status_code == 403
        assert "no_show_discount" in str(exc_info.value.detail).lower()

    def test_employee_operator_cannot_edit(self):
        """Internal Operator cannot edit no_show_discount."""
        with pytest.raises(HTTPException) as exc_info:
            ensure_can_edit_institution_no_show_discount({
                "role_type": "Internal",
                "role_name": "Operator",
            })
        assert exc_info.value.status_code == 403

    def test_customer_cannot_edit(self):
        """Customer cannot edit no_show_discount."""
        with pytest.raises(HTTPException) as exc_info:
            ensure_can_edit_institution_no_show_discount({
                "role_type": "Customer",
                "role_name": "Comensal",
            })
        assert exc_info.value.status_code == 403
