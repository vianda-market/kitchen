"""
Tax classification enumeration for IRS W-9 form.

Used for billing.supplier_w9.tax_classification.
Values are lowercase to match IRS form categories.
"""

from enum import Enum


class TaxClassification(str, Enum):
    """IRS W-9 tax classification categories."""

    INDIVIDUAL = "individual"
    C_CORP = "c_corp"
    S_CORP = "s_corp"
    PARTNERSHIP = "partnership"
    LLC = "llc"
    OTHER = "other"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid classification values."""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Return True if value is a valid TaxClassification."""
        return value in cls._value2member_map_
