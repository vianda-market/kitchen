"""Lead interest source enumeration."""

from enum import Enum


class LeadInterestSource(str, Enum):
    """Where the lead interest was submitted from."""

    MARKETING_SITE = "marketing_site"
    B2C_APP = "b2c_app"
