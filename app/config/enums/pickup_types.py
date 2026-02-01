"""
Pickup Type Enumeration

Defines the valid pickup types for plate selection.
Pickup types are fixed at compile time and determine how plates are collected.
"""
from enum import Enum


class PickupType(str, Enum):
    """Valid pickup types - fixed at compile time"""
    SELF = "self"
    FOR_OTHERS = "for_others"
    BY_OTHERS = "by_others"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid pickup type values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid pickup type"""
        return value in cls.values()

