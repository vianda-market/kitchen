"""
Role Name Enumeration

Defines the valid role names in the system.
Role names are fixed at compile time and determine specific permissions.
Must be used in combination with RoleType to form valid role combinations.
"""
from enum import Enum
from app.config.enums.role_types import RoleType


class RoleName(str, Enum):
    """Valid role names - fixed at compile time"""
    ADMIN = "Admin"
    SUPER_ADMIN = "Super Admin"
    MANAGEMENT = "Management"
    OPERATOR = "Operator"
    COMENSAL = "Comensal"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid role name values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid role name"""
        return value in cls.values()
    
    @classmethod
    def get_valid_for_role_type(cls, role_type: RoleType) -> list[str]:
        """Get valid role names for a given role type"""
        valid_combinations = {
            RoleType.EMPLOYEE: [cls.ADMIN, cls.SUPER_ADMIN, cls.MANAGEMENT, cls.OPERATOR],
            RoleType.SUPPLIER: [cls.ADMIN, cls.MANAGEMENT, cls.OPERATOR],
            RoleType.CUSTOMER: [cls.COMENSAL],
        }
        return [rn.value for rn in valid_combinations.get(role_type, [])]

