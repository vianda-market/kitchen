"""
Bank Account Type Enumeration

Defines the valid bank account types used in the institution_bank_account table.
Bank account types represent the different types of accounts used for payments.
"""
from enum import Enum


class BankAccountType(str, Enum):
    """Valid bank account types"""
    CHECKING = "Checking"
    SAVINGS = "Savings"
    BUSINESS = "Business"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid bank account type values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid bank account type"""
        return value in cls.values()
