"""
Country code utilities — single source of truth for ISO 3166-1 conversions.

- normalize_country_code: alpha-3→alpha-2 normalization at API boundary (uses pycountry)
- resolve_country_name: alpha-2→official country name (uses pycountry)
- country_alpha2_to_alpha3 / country_alpha3_to_alpha2 / country_name_to_alpha2:
  fast lookups via static dicts (no pycountry dependency, used by address gateways)
"""

import logging
from typing import Dict, Optional

import pycountry
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static lookup dicts — used by address gateways for fast conversion
# ---------------------------------------------------------------------------

_COUNTRY_ALPHA2_TO_ALPHA3: Dict[str, str] = {
    "AR": "ARG", "US": "USA", "BR": "BRA", "MX": "MEX", "CA": "CAN",
    "CL": "CHL", "CO": "COL", "PE": "PER", "UY": "URY", "PY": "PRY",
    "EC": "ECU", "BO": "BOL", "VE": "VEN", "GB": "GBR", "ES": "ESP",
    "FR": "FRA", "DE": "DEU", "IT": "ITA", "JP": "JPN", "AU": "AUS",
}

_COUNTRY_NAME_TO_ALPHA2: Dict[str, str] = {
    "argentina": "AR", "united states": "US", "usa": "US", "united states of america": "US",
    "brazil": "BR", "brasil": "BR", "mexico": "MX", "méxico": "MX", "canada": "CA",
    "chile": "CL", "colombia": "CO", "peru": "PE", "perú": "PE",
    "uruguay": "UY", "paraguay": "PY", "ecuador": "EC", "bolivia": "BO",
    "venezuela": "VE", "venezuela (bolivarian republic of)": "VE",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "england": "GB",
    "spain": "ES", "españa": "ES", "france": "FR", "germany": "DE", "deutschland": "DE",
    "italy": "IT", "italia": "IT", "japan": "JP", "australia": "AU",
}


def country_alpha2_to_alpha3(alpha2: str) -> str:
    """Convert ISO 3166-1 alpha-2 to alpha-3. Returns upper input if not in map."""
    if not alpha2 or len(alpha2) != 2:
        return (alpha2 or "").upper()
    return _COUNTRY_ALPHA2_TO_ALPHA3.get(alpha2.upper(), alpha2.upper())


def country_alpha3_to_alpha2(alpha3: str) -> str:
    """Convert alpha-3 to alpha-2. Returns first two chars uppercased if not in map."""
    rev = {v: k for k, v in _COUNTRY_ALPHA2_TO_ALPHA3.items()}
    if alpha3 and len(alpha3) == 3:
        return rev.get(alpha3.upper(), alpha3.upper()[:2])
    return (alpha3 or "")[:2].upper()


def country_name_to_alpha2(name: str) -> Optional[str]:
    """Resolve country name (e.g. 'Argentina') to ISO 3166-1 alpha-2. Returns None if not found."""
    if not name or not name.strip():
        return None
    key = name.strip().lower()
    return _COUNTRY_NAME_TO_ALPHA2.get(key)


# ---------------------------------------------------------------------------
# pycountry-based utilities — richer but slower, used at API boundaries
# ---------------------------------------------------------------------------


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
