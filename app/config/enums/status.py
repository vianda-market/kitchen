"""
Status Enumeration

Defines the valid status values used across all entities in the system.
Status is a system enum list (static, compile-time constants), not operational data.
"""
from enum import Enum


class Status(str, Enum):
    """Valid status values - fixed at compile time"""
    # General statuses
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    
    # Order statuses
    PENDING = "Pending"
    ARRIVED = "Arrived"
    COMPLETE = "Complete"
    CANCELLED = "Cancelled"
    
    # Transaction statuses
    PROCESSED = "Processed"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid status values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid status"""
        return value in cls.values()
    
    @classmethod
    def get_by_category(cls, category: str) -> list[str]:
        """Get status values by category (for backward compatibility)"""
        category_map = {
            'general': [cls.ACTIVE, cls.INACTIVE],
            'order': [cls.PENDING, cls.ARRIVED, cls.COMPLETE, cls.CANCELLED],
            'transaction': [cls.PROCESSED],
        }
        return [s.value for s in category_map.get(category, [])]

