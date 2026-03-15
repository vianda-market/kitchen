"""
Payment Method Provider Enumeration

Defines the valid payment method providers (aggregators) used in the payment_method table.
Payment methods represent saved payment methods from these providers only.
"""
from enum import Enum


class PaymentMethodProvider(str, Enum):
    """Valid payment method providers (aggregators only)"""
    STRIPE = "Stripe"
    MERCADO_PAGO = "Mercado Pago"
    PAYU = "PayU"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid provider values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid payment method provider"""
        return value in cls.values()


# Alias for backward compatibility where "PaymentMethodType" was used for validation
PaymentMethodType = PaymentMethodProvider
