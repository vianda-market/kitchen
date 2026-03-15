"""
Supported cuisines for restaurant create/edit dropdown.

Single source of truth. Used by GET /api/v1/cuisines/ and for validation on restaurant create/update.
"""

from typing import List

# Cuisine names for dropdown. Sorted alphabetically in API response.
# Easy to extend; add new cuisines here.
SUPPORTED_CUISINES = (
    "American",
    "Chinese",
    "French",
    "Indian",
    "Italian",
    "Japanese",
    "Mediterranean",
    "Mexican",
    "Thai",
)


def get_supported_cuisines_sorted() -> List[dict]:
    """
    Return list of { "cuisine_name": str } sorted alphabetically.
    Use for GET /api/v1/cuisines/ and validation.
    """
    out = [{"cuisine_name": name} for name in SUPPORTED_CUISINES]
    out.sort(key=lambda x: x["cuisine_name"].lower())
    return out


def is_supported_cuisine(cuisine: str) -> bool:
    """Return True if cuisine matches a supported cuisine (case-insensitive)."""
    if not cuisine or not (cuisine or "").strip():
        return True  # Empty/null is allowed (optional field)
    c = (cuisine or "").strip()
    return any(c.lower() == name.lower() for name in SUPPORTED_CUISINES)
