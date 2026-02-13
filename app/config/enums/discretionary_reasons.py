# app/config/discretionary_reasons.py
"""
Discretionary Request Category Enum

Defines valid category values for discretionary credit requests.
Categories classify the type of discretionary credit action:
- Marketing Campaign: Credits issued for marketing/promotional purposes
- Credit Refund: General credit refunds for customers
- Order incorrectly marked as not collected: Restaurant-specific issue requiring restaurant context
- Full Order Refund: Complete order refund requiring restaurant context
"""
from enum import Enum


class DiscretionaryReason(str, Enum):
    """Valid categories for discretionary credit requests (formerly 'reasons')"""
    
    # General categories (user or restaurant)
    MARKETING_CAMPAIGN = "Marketing Campaign"
    CREDIT_REFUND = "Credit Refund"
    
    # Restaurant-specific categories (require restaurant_id)
    ORDER_INCORRECTLY_MARKED = "Order incorrectly marked as not collected"
    FULL_ORDER_REFUND = "Full Order Refund"
    
    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid discretionary category values"""
        return [item.value for item in cls]
    
    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid discretionary category"""
        return value in cls.values()
    
    @classmethod
    def requires_restaurant(cls, category: 'DiscretionaryReason') -> bool:
        """
        Check if a category requires restaurant_id to be specified.
        
        Categories that require restaurant context:
        - ORDER_INCORRECTLY_MARKED: Needs restaurant for order verification
        - FULL_ORDER_REFUND: Needs restaurant for refund processing
        
        Returns:
            bool: True if restaurant_id is required, False otherwise
        """
        restaurant_required = [
            cls.ORDER_INCORRECTLY_MARKED,
            cls.FULL_ORDER_REFUND
        ]
        return category in restaurant_required

