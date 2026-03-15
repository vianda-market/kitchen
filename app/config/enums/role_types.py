"""
Role Type Enumeration

Defines the valid role types in the system.
Role types are fixed at compile time and determine user access categories.
"""
from enum import Enum


class RoleType(str, Enum):
    """Valid role types - fixed at compile time. Also used for institution_type (Employer = benefits-program institution)."""
    EMPLOYEE = "Employee"
    SUPPLIER = "Supplier"
    CUSTOMER = "Customer"
    EMPLOYER = "Employer"  # Institution type only: benefits-program company; users in it have role_type Customer

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid role type values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid role type"""
        return value in cls.values()

