"""
Subscription Status Enumeration

Defines the valid subscription status values used in the subscription_info table.
Subscription status tracks the lifecycle state of a user's subscription.
"""
from enum import Enum


class SubscriptionStatus(str, Enum):
    """Valid subscription status values"""
    ACTIVE = "Active"
    ON_HOLD = "On Hold"
    PENDING = "Pending"
    EXPIRED = "Expired"
    CANCELLED = "Cancelled"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid subscription status values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid subscription status"""
        return value in cls.values()
