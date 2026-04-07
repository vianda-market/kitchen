"""Payment Frequency Enumeration for supplier terms."""
from enum import Enum


class PaymentFrequency(str, Enum):
    """How frequently the supplier is paid out."""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
