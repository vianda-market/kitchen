"""
Supplier invoice type enumeration.

Used for billing.supplier_invoice.invoice_type (PostgreSQL supplier_invoice_type_enum).
Covers all supported markets: AR (Factura Electronica), PE (CPE), US (1099 NEC).
"""

from enum import Enum


class SupplierInvoiceType(str, Enum):
    """Type of supplier invoice by country compliance format."""

    FACTURA_ELECTRONICA = "factura_electronica"
    CPE = "cpe"
    IRS_1099_NEC = "1099_nec"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all valid type values."""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Return True if value is a valid SupplierInvoiceType."""
        return value in cls._value2member_map_
