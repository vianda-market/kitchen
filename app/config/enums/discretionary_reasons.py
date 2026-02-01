# app/config/discretionary_reasons.py
"""
Discretionary Request Reason Enum

Defines valid reason values for discretionary credit requests.
Reasons are category-specific:
- Client: Marketing Campaign, Credit Refund
- Supplier: Order incorrectly marked as not collected, Full Order Refund, Marketing Campaign
"""
from enum import Enum


class DiscretionaryReason(str, Enum):
    """Valid reasons for discretionary credit requests"""
    
    # Client reasons
    MARKETING_CAMPAIGN = "Marketing Campaign"
    CREDIT_REFUND = "Credit Refund"
    
    # Supplier reasons
    ORDER_INCORRECTLY_MARKED = "Order incorrectly marked as not collected"
    FULL_ORDER_REFUND = "Full Order Refund"
    # Note: Marketing Campaign is also valid for Supplier
    
    @classmethod
    def get_valid_for_category(cls, category: str) -> list[str]:
        """Get valid reason values for a given category"""
        if category == "Client":
            return [cls.MARKETING_CAMPAIGN.value, cls.CREDIT_REFUND.value]
        elif category == "Supplier":
            return [
                cls.ORDER_INCORRECTLY_MARKED.value,
                cls.FULL_ORDER_REFUND.value,
                cls.MARKETING_CAMPAIGN.value
            ]
        return []
    
    @classmethod
    def is_valid_for_category(cls, reason: str, category: str) -> bool:
        """Check if a reason is valid for a given category"""
        valid_reasons = cls.get_valid_for_category(category)
        return reason in valid_reasons

