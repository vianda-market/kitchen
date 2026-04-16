"""
Discretionary Status Enumeration

Defines the valid status values for discretionary requests.
Single enum for the full lifecycle: Pending, Cancelled, Approved, Rejected.
"""

from enum import Enum


class DiscretionaryStatus(str, Enum):
    """Valid discretionary status values."""

    PENDING = "pending"
    CANCELLED = "cancelled"
    APPROVED = "approved"
    REJECTED = "rejected"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid discretionary status values."""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid discretionary status."""
        return value in cls.values()
