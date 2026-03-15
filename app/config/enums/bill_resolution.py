"""
Institution bill resolution enumeration.

Used for institution_bill_info.resolution (PostgreSQL bill_resolution_enum).
A bill can be Pending, Paid, or Rejected (e.g. payout rejected).
"""

from enum import Enum


class BillResolution(str, Enum):
    """Valid resolution values for institution bills."""
    PENDING = "Pending"
    PAID = "Paid"
    REJECTED = "Rejected"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid resolution values (for enum service / API)."""
        return [item.value for item in cls]
