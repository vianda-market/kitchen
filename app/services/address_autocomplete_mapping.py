"""
Map Google Places API (Place Details) responses to backend address schema.

Backend schema fields: street_name, street_type, building_number, apartment_unit,
floor, city, province, postal_code, country_code (alpha-2).
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.gateways.google_places_gateway import country_alpha3_to_alpha2, country_name_to_alpha2

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
    Places API format: longText/shortText + types.
    """
    out: Dict[str, str] = {}
    for comp in components or []:
        # Place Details: { "longText": "2567", "shortText": "2567", "types": ["street_number"] }
        types_list = comp.get("types") or comp.get("type") or []
        text = comp.get("longText") or comp.get("shortText") or ""
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


def get_city_candidates_from_place_details(place_details: Dict[str, Any]) -> List[str]:
    """
    Return city candidates (locality, sublocality_level_1, sublocality) for validation.
    Google may put the city in locality or in sublocality when locality is a neighborhood.
    """
    components = place_details.get("addressComponents") or place_details.get("address_components") or []
    by_type = _extract_by_type(components, "types")
    candidates = []
    for key in ("locality", "sublocality_level_1", "sublocality"):
        v = (by_type.get(key) or "").strip()
        if v and v not in candidates:
            candidates.append(v)
    return candidates


def map_place_details_to_address(
    place_details: Dict[str, Any],
    country_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Map Place Details response (id, formattedAddress, addressComponents) to backend address shape.
    country_override: if set, use this as country_code (alpha-2); else derive from components.
    """
    components = place_details.get("addressComponents") or place_details.get("address_components") or []
    by_type = _extract_by_type(components, "types")

    street_number = by_type.get("street_number", "").strip()
    route = (by_type.get("route") or "").strip()
    locality = (by_type.get("locality") or "").strip()
    sublocality_level_1 = (by_type.get("sublocality_level_1") or "").strip()
    sublocality = (by_type.get("sublocality") or "").strip()
    admin1 = (by_type.get("administrative_area_level_1") or "").strip()
    postal_code = (by_type.get("postal_code") or "").strip()
    country_short = (by_type.get("country") or "").strip()

    street_type, street_name = _route_to_street_type_and_name(route) if route else ("St", "")

    # City: Google may return locality=city or locality=neighborhood with sublocality_level_1=city (e.g. Seattle).
    # Use locality first, fall back to sublocality_level_1 then sublocality.
    city = locality or sublocality_level_1 or sublocality or ""

    # Subpremise: apartment_unit / floor (optional)
    subpremise = (by_type.get("subpremise") or "").strip()
    # Could split floor vs unit by pattern; keep simple and put in apartment_unit if present
    apartment_unit = subpremise or None
    floor = None

    # Use alpha-2 only in API responses
    if country_override:
        country_alpha2 = (country_override or "")[:2].upper()
    elif country_short:
        cs = country_short.strip()
        if len(cs) == 2 and cs.isalpha():
            country_alpha2 = cs.upper()
        elif len(cs) == 3 and cs.isalpha():
            country_alpha2 = country_alpha3_to_alpha2(cs)
        else:
            # Google may return full name (e.g. "United States"); resolve via name map
            country_alpha2 = (country_name_to_alpha2(cs) or "").upper() or ""
    else:
        country_alpha2 = ""

    return {
        "street_name": street_name or "—",
        "street_type": street_type,
        "building_number": street_number or "—",
        "apartment_unit": apartment_unit,
        "floor": floor,
        "city": city or "—",
        "province": admin1 or "—",
        "postal_code": postal_code or "—",
        "country_code": country_alpha2,
        "formatted_address": place_details.get("formattedAddress") or place_details.get("formatted_address"),
    }


def extract_place_details_geolocation(place_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract place_id, viewport, formatted_address_google, latitude, longitude from Place Details.

    viewport: { "low": { "latitude": float, "longitude": float }, "high": { ... } }
    Returns dict with: place_id, viewport, formatted_address_google, latitude, longitude.
    """
    place_id = place_details.get("id") or ""
    formatted = place_details.get("formattedAddress") or place_details.get("formatted_address") or ""
    location = place_details.get("location") or {}
    lat = location.get("latitude")
    lng = location.get("longitude")
    if lat is None or lng is None:
        return {
            "place_id": place_id or None,
            "viewport": None,
            "formatted_address_google": formatted or None,
            "latitude": None,
            "longitude": None,
        }
    # Normalize viewport to our schema: { low: { lat, lng }, high: { lat, lng } }
    raw_viewport = place_details.get("viewport") or {}
    low = raw_viewport.get("low") or raw_viewport.get("southwest") or {}
    high = raw_viewport.get("high") or raw_viewport.get("northeast") or {}
    viewport = None
    if low and high:
        viewport = {
            "low": {"lat": float(low.get("latitude", low.get("lat", 0))), "lng": float(low.get("longitude", low.get("lng", 0)))},
            "high": {"lat": float(high.get("latitude", high.get("lat", 0))), "lng": float(high.get("longitude", high.get("lng", 0)))},
        }
    return {
        "place_id": place_id or None,
        "viewport": viewport,
        "formatted_address_google": formatted or None,
        "latitude": float(lat),
        "longitude": float(lng),
    }
