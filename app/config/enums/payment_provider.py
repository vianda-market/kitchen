"""
Payment Provider Enumeration

Identifies the payment provider that processed a billing.payment_attempt row.
New providers (e.g. Mercado Pago) are added here; no schema change to
customer.subscription_payment is needed.
"""

from enum import Enum


class PaymentProvider(str, Enum):
    """Valid payment provider identifiers."""

    STRIPE = "stripe"
    MERCADO_PAGO = "mercado_pago"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid provider values."""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid payment provider."""
        return value in cls.values()
