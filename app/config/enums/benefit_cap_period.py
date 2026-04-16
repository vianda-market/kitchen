"""Benefit Cap Period Enumeration for employer benefits program."""

from enum import Enum


class BenefitCapPeriod(str, Enum):
    """How the benefit cap resets: per renewal or monthly."""

    PER_RENEWAL = "per_renewal"
    MONTHLY = "monthly"
