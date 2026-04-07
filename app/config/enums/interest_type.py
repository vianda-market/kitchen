"""Interest type enumeration for lead interest capture."""
from enum import Enum


class InterestType(str, Enum):
    """Type of interest expressed by a lead."""
    CUSTOMER = "customer"
    EMPLOYER = "employer"
    SUPPLIER = "supplier"
