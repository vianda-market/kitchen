"""
Portion Size Display Enumeration

Defines the valid portion_size display values returned to B2C and B2B clients.
Derived from average_portion_size (1-3) when vianda has enough reviews.
"""

from enum import Enum


class PortionSizeDisplay(str, Enum):
    """Valid portion size display values for vianda review feedback."""

    LIGHT = "light"
    STANDARD = "standard"
    LARGE = "large"
    INSUFFICIENT_REVIEWS = "insufficient_reviews"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid portion size display values."""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid portion size display."""
        return value in cls.values()
