"""Employer Bill Payment Status Enumeration."""

from enum import Enum


class EmployerBillPaymentStatus(str, Enum):
    """Payment status for employer bills."""

    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    OVERDUE = "overdue"
