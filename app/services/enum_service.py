"""
Enum Service

Service for retrieving all system enum values.
Provides a centralized way to access all enum values used throughout the system,
primarily for frontend dropdown population.
"""

from typing import Dict, List
from app.config.enums import (
    Status, AddressType, RoleType, RoleName,
    TransactionType, KitchenDay, PickupType,
    DiscretionaryReason, SubscriptionStatus,
    PaymentMethodType, BankAccountType, StreetType
)


class EnumService:
    """
    Service for retrieving all system enum values.
    
    This service provides a centralized way to access all enum values
    used throughout the system, primarily for frontend dropdown population.
    """
    
    @staticmethod
    def get_all_enums() -> Dict[str, List[str]]:
        """
        Get all enum values as a dictionary.
        
        Returns:
            Dictionary mapping enum type names to their valid values.
            
        Example:
            {
                "status": ["Active", "Inactive", "Pending", ...],
                "address_type": ["Restaurant", "Entity Billing", ...],
                ...
            }
        """
        return {
            # Core enums (used across entities)
            "status": Status.values(),
            "address_type": AddressType.values(),
            
            # User and role enums
            "role_type": RoleType.values(),
            "role_name": RoleName.values(),
            
            # Subscription enums
            "subscription_status": SubscriptionStatus.values(),
            
            # Payment enums
            "method_type": PaymentMethodType.values(),
            "account_type": BankAccountType.values(),
            
            # Transaction enums
            "transaction_type": TransactionType.values(),
            
            # Address enums
            "street_type": StreetType.values(),
            
            # Kitchen and pickup enums
            "kitchen_day": KitchenDay.values(),
            "pickup_type": PickupType.values(),
            
            # Discretionary enums
            "discretionary_reason": DiscretionaryReason.values(),
        }
    
    @staticmethod
    def get_enum_by_name(enum_name: str) -> List[str]:
        """
        Get values for a specific enum type.
        
        Args:
            enum_name: Name of the enum type (e.g., 'status', 'role_type')
            
        Returns:
            List of valid values for the enum
            
        Raises:
            ValueError: If enum_name is not recognized
            
        Example:
            >>> EnumService.get_enum_by_name('status')
            ['Active', 'Inactive', 'Pending', 'Arrived', 'Complete', 'Cancelled', 'Processed']
        """
        all_enums = EnumService.get_all_enums()
        if enum_name not in all_enums:
            raise ValueError(f"Unknown enum type: {enum_name}")
        return all_enums[enum_name]


# Singleton instance
enum_service = EnumService()
