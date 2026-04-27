"""
Payment Attempt Status Enumeration

Tracks the financial state of a billing.payment_attempt row.
Distinct from the admin/audit `status` (status_enum: active/inactive)
which tracks record lifecycle for internal ops.
"""

from enum import Enum


class PaymentAttemptStatus(str, Enum):
    """Financial state of a single payment attempt."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid payment attempt status values."""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid payment attempt status."""
        return value in cls.values()
