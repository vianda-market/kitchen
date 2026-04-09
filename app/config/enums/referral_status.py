"""
Referral Status Enumeration

Defines the valid referral status values used in the referral_info table.
Referral status tracks the lifecycle state of a referral from pending to rewarded/expired.
"""
from enum import Enum


class ReferralStatus(str, Enum):
    """Valid referral status values"""
    PENDING = "pending"
    QUALIFIED = "qualified"
    REWARDED = "rewarded"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid referral status values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid referral status"""
        return value in cls.values()
