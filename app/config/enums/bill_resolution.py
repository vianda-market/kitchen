"""
Institution bill resolution enumeration.

Used for institution_bill_info.resolution (PostgreSQL bill_resolution_enum).
A bill can be Pending, Paid, Rejected, or Failed.
- Rejected: admin-rejected (e.g. fraud review). Reserved for human review workflows.
- Failed: payout provider failure (e.g. Stripe transfer reversed or payout failed).
"""

from enum import Enum


class BillResolution(str, Enum):
    """Valid resolution values for institution bills."""

    PENDING = "pending"
    PAID = "paid"
    REJECTED = "rejected"
    FAILED = "failed"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid resolution values (for enum service / API)."""
        return [item.value for item in cls]
