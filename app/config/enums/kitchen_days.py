"""
Kitchen Day Enumeration

Defines the valid kitchen days (weekdays) when plates are available.
Kitchen days are fixed at compile time (Monday through Friday).
"""
from enum import Enum


class KitchenDay(str, Enum):
    """Valid kitchen days - fixed at compile time"""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid kitchen day values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid kitchen day"""
        return value in cls.values()

