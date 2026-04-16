"""
Pickup Type Enumeration

Defines the valid pickup types for plate selection.
Pickup types are fixed at compile time and determine how plates are collected.
"""

from enum import Enum


class PickupType(str, Enum):
    """Valid pickup types - fixed at compile time. offer=user offers to pick up for others; request=user requests someone to pick up; self=user picks up own."""

    SELF = "self"
    OFFER = "offer"
    REQUEST = "request"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid pickup type values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid pickup type"""
        return value in cls.values()
