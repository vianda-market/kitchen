"""
Address Type Enumeration

Defines the valid address types that can be assigned to addresses.
Addresses can have multiple types (array), but each type must be from this enum.
"""
from enum import Enum


class AddressType(str, Enum):
    """Valid address types"""
    RESTAURANT = "restaurant"
    ENTITY_BILLING = "entity_billing"
    ENTITY_ADDRESS = "entity_address"
    CUSTOMER_HOME = "customer_home"
    CUSTOMER_BILLING = "customer_billing"
    CUSTOMER_EMPLOYER = "customer_employer"
    CUSTOMER_OTHER = "customer_other"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid address type values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid address type"""
        return value in cls.values()

