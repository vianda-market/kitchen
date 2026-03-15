"""
Location validation service.

Validates country-province-city combinations against supported_cities config.
Rejects invalid combinations (e.g., Florida + Seattle; Seattle is in Washington).
"""

from typing import Optional

from app.config.supported_provinces import SUPPORTED_PROVINCES
from app.config.supported_cities import SUPPORTED_CITIES


def _build_province_lookup() -> dict:
    """Build (country_code -> {normalized_input -> province_code}) for resolution."""
    lookup: dict = {}
    for cc, pcode, pname in SUPPORTED_PROVINCES:
        if cc not in lookup:
            lookup[cc] = {}
        lookup[cc][pcode.strip().upper()] = pcode
        lookup[cc][pcode.strip().lower()] = pcode
        lookup[cc][pcode.strip()] = pcode
        lookup[cc][pname.strip().lower()] = pcode
        lookup[cc][pname.strip().title()] = pcode
    return lookup


_PROVINCE_LOOKUP: Optional[dict] = None


def _get_province_lookup() -> dict:
    global _PROVINCE_LOOKUP
    if _PROVINCE_LOOKUP is None:
        _PROVINCE_LOOKUP = _build_province_lookup()
    return _PROVINCE_LOOKUP


def _resolve_province_code(country_code: str, province: str) -> Optional[str]:
    """Resolve province input (name or code) to canonical province_code, or None."""
    if not province or not country_code:
        return None
    cc = country_code.strip().upper()
    lookup = _get_province_lookup()
    if cc not in lookup:
        return None
    # Try exact matches
    key = province.strip()
    if key in lookup[cc]:
        return lookup[cc][key]
    key_upper = key.upper()
    if key_upper in lookup[cc]:
        return lookup[cc][key_upper]
    key_lower = key.lower()
    if key_lower in lookup[cc]:
        return lookup[cc][key_lower]
    key_title = key.title()
    if key_title in lookup[cc]:
        return lookup[cc][key_title]
    return None


def _build_city_set() -> set:
    """Build set of (country_code, province_code, city_name_normalized) for fast lookup."""
    out = set()
    for cc, pcode, cname in SUPPORTED_CITIES:
        out.add((cc.upper(), pcode, cname.strip().lower()))
    return out


_CITY_SET: Optional[set] = None


def _get_city_set() -> set:
    global _CITY_SET
    if _CITY_SET is None:
        _CITY_SET = _build_city_set()
    return _CITY_SET


def _get_city_province_map() -> dict:
    """Build (country_code, city_normalized) -> province_code for error messages."""
    out = {}
    for cc, pcode, cname in SUPPORTED_CITIES:
        key = (cc.upper(), cname.strip().lower())
        out[key] = pcode
    return out


_CITY_PROVINCE_MAP: Optional[dict] = None


def _get_city_province_map_cached() -> dict:
    global _CITY_PROVINCE_MAP
    if _CITY_PROVINCE_MAP is None:
        _CITY_PROVINCE_MAP = _get_city_province_map()
    return _CITY_PROVINCE_MAP


def _get_province_name_map() -> dict:
    """Build (country_code, province_code) -> province_name for error messages."""
    out = {}
    for cc, pcode, pname in SUPPORTED_PROVINCES:
        out[(cc.upper(), pcode)] = pname
    return out


_PROVINCE_NAME_MAP: Optional[dict] = None


def _get_province_name_map_cached() -> dict:
    global _PROVINCE_NAME_MAP
    if _PROVINCE_NAME_MAP is None:
        _PROVINCE_NAME_MAP = _get_province_name_map()
    return _PROVINCE_NAME_MAP


def validate_country_province_city(
    country_code: str,
    province: str,
    city: str,
) -> bool:
    """
    Validate that (country_code, province, city) is a valid combination.

    Province can be name or code (e.g. "Florida", "FL", "Washington", "WA").
    Returns True if valid, False otherwise.
    """
    if not country_code or not province or not city:
        return False
    cc = country_code.strip().upper()
    resolved = _resolve_province_code(cc, province)
    if not resolved:
        return False
    city_key = (cc, resolved, city.strip().lower())
    return city_key in _get_city_set()


def get_validation_error_detail(
    country_code: str,
    province: str,
    city: str,
) -> Optional[str]:
    """
    Return user-facing error message when validation fails, or None if valid.

    Example: "Seattle is in Washington, not Florida."
    """
    if validate_country_province_city(country_code, province, city):
        return None
    cc = (country_code or "").strip().upper()
    city_norm = (city or "").strip().lower()
    city_prov_map = _get_city_province_map_cached()
    correct_province_code = city_prov_map.get((cc, city_norm))
    if not correct_province_code:
        # City not in our supported list for this country
        return f"City '{city}' is not in the supported cities list for this country."
    prov_name_map = _get_province_name_map_cached()
    correct_province_name = prov_name_map.get((cc, correct_province_code), correct_province_code)
    return f"'{city}' is in {correct_province_name}, not {province}."
