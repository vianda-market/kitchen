"""
Resolve ISO 3166-1 alpha-2 country code to official country name.
Normalize country_code at API boundary (single place for uppercase / alpha-3→alpha-2 / default).

Accepts ISO 3166-1 alpha-2 or alpha-3; converts alpha-3 to alpha-2 at entry and logs the conversion.
Store and return only alpha-2. Uses pycountry (offline, no API key).
"""

import logging
from typing import Optional

import pycountry
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def normalize_country_code(value: Optional[str], default: Optional[str] = None) -> str:
    """
    Normalize country_code for storage: strip, uppercase; accept alpha-2 or alpha-3, return alpha-2.
    When alpha-3 is supplied, convert to alpha-2 and log. Use at API boundary so services receive alpha-2.

    Args:
        value: Raw country_code from client (e.g. " us ", "ar", "ARG").
        default: Returned when value is None or blank after strip.

    Returns:
        Uppercase alpha-2 string, or default, or "".
    """
    if value is None or not isinstance(value, str):
        return default if default is not None else ""
    s = value.strip().upper()
    if not s:
        return default if default is not None else ""
    if len(s) == 3:
        country = pycountry.countries.get(alpha_3=s)
        if country is not None:
            logger.info("country_code alpha-3 converted to alpha-2: %s -> %s", s, country.alpha_2)
            return country.alpha_2
        # Invalid alpha-3; return as-is so downstream validation can reject with clear message
        return s
    if len(s) >= 2:
        return s[:2]
    return default if default is not None else ""


def resolve_country_name(country_code: str) -> str:
    """
    Resolve an ISO 3166-1 alpha-2 country code to the official country name.

    Args:
        country_code: Two-letter country code (e.g. "AR", "DE"). Normalized via normalize_country_code.

    Returns:
        Official country name (e.g. "Argentina", "Germany").

    Raises:
        HTTPException: 400 Bad Request with detail "Invalid country_code" if the code is not found.
    """
    if not country_code or not isinstance(country_code, str):
        raise HTTPException(status_code=400, detail="Invalid country_code")
    normalized = normalize_country_code(country_code) or ""
    if len(normalized) != 2:
        raise HTTPException(status_code=400, detail="Invalid country_code")
    country = pycountry.countries.get(alpha_2=normalized)
    if country is None:
        raise HTTPException(status_code=400, detail="Invalid country_code")
    return country.name
