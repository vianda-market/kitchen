"""Lead interest status enumeration."""

from enum import Enum


class LeadInterestStatus(str, Enum):
    """Status of a lead interest record."""

    ACTIVE = "active"
    NOTIFIED = "notified"
    UNSUBSCRIBED = "unsubscribed"
