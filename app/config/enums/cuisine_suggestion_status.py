"""
Cuisine Suggestion Status Enumeration

Defines the valid status values for cuisine suggestion workflow:
Pending (awaiting review), Approved (promoted to cuisine), Rejected.
"""

from enum import Enum


class CuisineSuggestionStatus(str, Enum):
    """Valid status values for cuisine suggestions."""
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid suggestion status values."""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid suggestion status."""
        return value in cls.values()
