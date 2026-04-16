"""
Cuisine Origin Source Enumeration

Tracks provenance of cuisine records: 'seed' for initial data,
'supplier' for records submitted through the suggestion flow.
"""

from enum import Enum


class CuisineOriginSource(str, Enum):
    """Valid origin source values for cuisine records."""

    SEED = "seed"
    SUPPLIER = "supplier"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid origin source values."""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid origin source."""
        return value in cls.values()
