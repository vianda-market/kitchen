"""
Institution bill payout status enumeration.

Used for billing.institution_bill_payout.status (PostgreSQL bill_payout_status_enum).
Append-only table — retries insert new rows; terminal states are never overwritten.
"""

from enum import Enum


class BillPayoutStatus(str, Enum):
    """Status of a single payout attempt on a bill."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid status values (for enum service / API)."""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Return True if value is a valid BillPayoutStatus."""
        return value in cls._value2member_map_
