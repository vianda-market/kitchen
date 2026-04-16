"""
Favorite Entity Type Enumeration

Defines the valid entity types that can be favorited (plate or restaurant).
"""

from enum import Enum


class FavoriteEntityType(str, Enum):
    """Valid favorite entity types - plate or restaurant"""

    PLATE = "plate"
    RESTAURANT = "restaurant"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid favorite entity type values"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid favorite entity type"""
        return value in cls.values()
