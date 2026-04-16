"""
Street Type Enumeration

Defines the valid street type abbreviations used in the address_info table.
Street types represent common address line type abbreviations.
"""

from enum import Enum


class StreetType(str, Enum):
    """Valid street type abbreviations"""

    STREET = "st"
    AVENUE = "ave"
    BOULEVARD = "blvd"
    ROAD = "rd"
    DRIVE = "dr"
    LANE = "ln"
    WAY = "way"
    COURT = "ct"
    PLACE = "pl"
    CIRCLE = "cir"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid street type values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid street type"""
        return value in cls.values()
