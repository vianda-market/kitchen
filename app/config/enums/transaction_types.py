"""
Transaction Type Enumeration

Defines the valid transaction types in the system.
Transaction types are fixed at compile time and categorize financial transactions.
"""
from enum import Enum


class TransactionType(str, Enum):
    """Valid transaction types - fixed at compile time"""
    # Restaurant transaction types
    ORDER = "order"

    # Client transaction types
    CREDIT = "credit"
    DEBIT = "debit"
    REFUND = "refund"
    DISCRETIONARY = "discretionary"

    # Institution transaction types
    PAYMENT = "payment"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid transaction type values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid transaction type"""
        return value in cls.values()
    
    @classmethod
    def get_by_category(cls, category: str) -> list[str]:
        """Get transaction types by category (for backward compatibility)"""
        category_map = {
            'restaurant': [cls.ORDER],
            'client': [cls.CREDIT, cls.DEBIT, cls.REFUND, cls.DISCRETIONARY],
            'institution': [cls.PAYMENT],
        }
        return [tt.value for tt in category_map.get(category, [])]

