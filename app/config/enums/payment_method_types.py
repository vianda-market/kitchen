"""
Payment Method Type Enumeration

Defines the valid payment method types used in the payment_method table.
Payment methods represent the different ways users can pay for subscriptions.
"""
from enum import Enum


class PaymentMethodType(str, Enum):
    """Valid payment method types"""
    CREDIT_CARD = "Credit Card"
    DEBIT_CARD = "Debit Card"
    BANK_TRANSFER = "Bank Transfer"
    CASH = "Cash"
    MERCADO_PAGO = "Mercado Pago"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid payment method type values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid payment method type"""
        return value in cls.values()
