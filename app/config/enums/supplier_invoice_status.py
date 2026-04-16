"""
Supplier invoice status enumeration.

Used for billing.supplier_invoice.status (PostgreSQL supplier_invoice_status_enum).
Tracks the review lifecycle: Pending Review → Approved or Rejected.
"""

from enum import Enum


class SupplierInvoiceStatus(str, Enum):
    """Status of a supplier invoice through the review process."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid status values."""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Return True if value is a valid SupplierInvoiceStatus."""
        return value in cls._value2member_map_
