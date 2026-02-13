"""
Map Google Places / Address Validation API responses to backend address schema.

Backend schema fields: street_name, street_type, building_number, apartment_unit,
floor, city, province, postal_code, country_code (alpha-3).
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.gateways.google_places_gateway import country_alpha2_to_alpha3

# Route prefix patterns to street_type (short). Order matters: longer matches first.
_ROUTE_PREFIXES = [
    ("avenida", "Ave"), ("av.", "Ave"), ("av ", "Ave"), ("av. ", "Ave"),
    ("calle", "St"), ("cal ", "St"), ("cal. ", "St"),
    ("boulevard", "Blvd"), ("bulevar", "Blvd"), ("blvd.", "Blvd"), ("blvd ", "Blvd"),
    ("road", "Rd"), ("rd.", "Rd"), ("rd ", "Rd"),
    ("drive", "Dr"), ("dr.", "Dr"), ("dr ", "Dr"),
    ("lane", "Ln"), ("ln.", "Ln"), ("ln ", "Ln"),
    ("way", "Way"), ("court", "Ct"), ("ct.", "Ct"), ("place", "Pl"), ("circle", "Cir"),
    ("cir.", "Cir"), ("circuit", "Cir"),
]


def _extract_by_type(components: List[Dict[str, Any]], type_key: str = "types") -> Dict[str, str]:
    """
    Build a map from component type (e.g. 'street_number') to value.
    Supports both Places API format (longText/shortText + types) and
    Address Validation format (componentName.text + componentType).
    """
    out: Dict[str, str] = {}
    for comp in components or []:
        if type_key == "types":
            # Place Details: { "longText": "2567", "shortText": "2567", "types": ["street_number"] }
            types_list = comp.get("types") or comp.get("type") or []
            text = comp.get("longText") or comp.get("shortText") or ""
        else:
            # Address Validation: { "componentName": { "text": "2567" }, "componentType": "street_number" }
            comp_type = comp.get("componentType") or (comp.get("types") or [None])[0]
            types_list = [comp_type] if comp_type else []
            name = comp.get("componentName") or {}
            text = name.get("text", "") if isinstance(name, dict) else str(name)
        for t in types_list:
            if t and text:
                out[t] = text.strip()
    return out


def _route_to_street_type_and_name(route: str) -> Tuple[str, str]:
    """
    Split route (e.g. 'Av. Corrientes', 'Avenida Santa Fe') into street_type and street_name.
    Returns (street_type, street_name). street_type defaults to 'St' if no match.
    """
    if not (route and route.strip()):
        return "St", ""
    r = route.strip()
    r_lower = r.lower()
    for prefix, st in _ROUTE_PREFIXES:
        if r_lower.startswith(prefix):
            rest = r[len(prefix):].strip()
            # Remove leading punctuation/dot
            rest = re.sub(r"^[\s.,]+", "", rest)
            return st, rest or r
    return "St", r


def map_place_details_to_address(
    place_details: Dict[str, Any],
    country_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Map Place Details response (id, formattedAddress, addressComponents) to backend address shape.
    country_override: if set, use this as country_code (alpha-3); else derive from components.
    """
    components = place_details.get("addressComponents") or place_details.get("address_components") or []
    by_type = _extract_by_type(components, "types")

    street_number = by_type.get("street_number", "").strip()
    route = (by_type.get("route") or "").strip()
    locality = (by_type.get("locality") or "").strip()
    admin1 = (by_type.get("administrative_area_level_1") or "").strip()
    postal_code = (by_type.get("postal_code") or "").strip()
    country_short = (by_type.get("country") or "").strip()

    street_type, street_name = _route_to_street_type_and_name(route) if route else ("St", "")

    # Subpremise: apartment_unit / floor (optional)
    subpremise = (by_type.get("subpremise") or "").strip()
    # Could split floor vs unit by pattern; keep simple and put in apartment_unit if present
    apartment_unit = subpremise or None
    floor = None

    country_code = country_override
    if not country_code and country_short:
        country_code = country_alpha2_to_alpha3(country_short[:2])

    return {
        "street_name": street_name or "—",
        "street_type": street_type,
        "building_number": street_number or "—",
        "apartment_unit": apartment_unit,
        "floor": floor,
        "city": locality or "—",
        "province": admin1 or "—",
        "postal_code": postal_code or "—",
        "country_code": (country_code or "").upper(),
        "formatted_address": place_details.get("formattedAddress") or place_details.get("formatted_address"),
    }


def map_validation_result_to_address(
    validation_response: Dict[str, Any],
) -> Tuple[bool, Optional[Dict[str, Any]], str, str, Optional[str]]:
    """
    Map Address Validation API response to (is_valid, normalized_dict, formatted_address, confidence, message).
    normalized_dict uses same keys as map_place_details_to_address output.
    """
    result = validation_response.get("result") or {}
    verdict = result.get("verdict") or {}
    address = result.get("address")

    address_complete = verdict.get("addressComplete", False)
    granularity = (verdict.get("validationGranularity") or "OTHER").upper()
    confidence = "high" if address_complete and granularity in ("PREMISE", "SUB_PREMISE") else "medium" if address_complete else "low"
    if not address_complete and not address:
        return False, None, "", "none", "Address could not be validated. Please check and try again."

    if not address:
        return False, None, "", confidence, verdict.get("unconfirmedComponentIndices") and "Some components could not be verified." or "Address could not be validated."

    # Address Validation API returns addressComponents with componentName.text and componentType
    comps = address.get("addressComponents") or []
    by_type: Dict[str, str] = {}
    for comp in comps:
        ctype = comp.get("componentType")
        name = comp.get("componentName")
        text = name.get("text", "").strip() if isinstance(name, dict) else ""
        if ctype and text:
            by_type[ctype] = text

    street_number = by_type.get("street_number", "").strip()
    route = (by_type.get("route") or "").strip()
    locality = (by_type.get("locality") or "").strip()
    admin1 = (by_type.get("administrative_area_level_1") or "").strip()
    postal_code = (by_type.get("postal_code") or "").strip()
    country_short = (by_type.get("country") or "").strip()

    street_type, street_name = _route_to_street_type_and_name(route) if route else ("St", "")
    country_code = country_alpha2_to_alpha3(country_short[:2]) if country_short else ""

    normalized = {
        "street_name": street_name or "—",
        "street_type": street_type,
        "building_number": street_number or "—",
        "apartment_unit": by_type.get("subpremise") or None,
        "floor": None,
        "city": locality or "—",
        "province": admin1 or "—",
        "postal_code": postal_code or "—",
        "country_code": (country_code or "").upper(),
    }
    formatted = address.get("formattedAddress") or ""

    return True, normalized, formatted, confidence, None


def build_validation_api_request(
    street_name: str,
    street_type: str,
    building_number: str,
    city: str,
    province: str,
    postal_code: str,
    country_code: str,
    apartment_unit: Optional[str] = None,
    floor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build request body for Address Validation API (regionCode is alpha-2, addressLines array).
    """
    from app.gateways.google_places_gateway import country_alpha3_to_alpha2
    region = country_alpha3_to_alpha2(country_code)
    line1 = " ".join(filter(None, [street_type, street_name, building_number])).strip()
    if apartment_unit or floor:
        line1 += f", {apartment_unit or ''} {floor or ''}".strip().strip(",")
    lines = [line1.strip()]
    if not lines[0]:
        lines = []
    payload = {
        "regionCode": region,
        "addressLines": lines,
        "locality": city or "",
        "administrativeArea": province or "",
        "postalCode": postal_code or "",
    }
    return {k: v for k, v in payload.items() if v is not None and v != ""}
