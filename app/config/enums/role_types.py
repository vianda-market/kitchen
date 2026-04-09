"""
Role Type Enumeration

Defines the valid role types in the system.
Role types are fixed at compile time and determine user access categories.
"""
from enum import Enum


class RoleType(str, Enum):
    """Valid role types - fixed at compile time. Also used for institution_type. Employer = benefit-program institution and role_type."""
    INTERNAL = "internal"
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    EMPLOYER = "employer"  # Role type (benefit-program managers) and institution_type

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid role type values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid role type"""
        return value in cls.values()

