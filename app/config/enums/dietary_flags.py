"""
DietaryFlag Enumeration

Defines the structured dietary restriction/preference flags for products.
Replaces the free-text VARCHAR(255) dietary field with a validated multi-select.
Stored as TEXT[] on product_info; validated at the API layer by this enum.
"""
from enum import Enum


class DietaryFlag(str, Enum):
    VEGAN = "vegan"
    VEGETARIAN = "vegetarian"
    GLUTEN_FREE = "gluten_free"
    DAIRY_FREE = "dairy_free"
    NUT_FREE = "nut_free"
    HALAL = "halal"
    KOSHER = "kosher"

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in cls]
