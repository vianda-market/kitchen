"""Billing Cycle Enumeration for employer benefits program."""

from enum import Enum


class BillingCycle(str, Enum):
    """How frequently the employer is invoiced."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
