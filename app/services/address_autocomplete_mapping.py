"""
Map Mapbox Search Box / Geocoding API responses to backend address schema.

Input: Mapbox GeoJSON Feature (from Search Box retrieve or Geocoding v6).
Output: Backend address fields (street_name, street_type, building_number,
apartment_unit, floor, city, province, postal_code, country_code).

Mapbox context hierarchy:
  country → region → postcode → district → place → locality → neighborhood → street → address
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.utils.country import country_alpha3_to_alpha2, country_name_to_alpha2, normalize_country_code

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


def _extract_from_context(context: Dict[str, Any]) -> Dict[str, str]:
    """Extract flat field values from Mapbox nested context hierarchy."""
    return {
        "country_code": (context.get("country", {}).get("country_code") or "").upper(),
        "country_name": context.get("country", {}).get("name", ""),
        "region": context.get("region", {}).get("name", ""),
        "place": context.get("place", {}).get("name", ""),
        "postcode": context.get("postcode", {}).get("name", ""),
        "street": context.get("street", {}).get("name", ""),
        "address_number": context.get("address", {}).get("address_number", ""),
        "neighborhood": context.get("neighborhood", {}).get("name", ""),
        "district": context.get("district", {}).get("name", ""),
        "locality": context.get("locality", {}).get("name", ""),
    }


def get_city_candidates_from_place_details(feature: Dict[str, Any]) -> List[str]:
    """
    Return city candidates from Mapbox Feature context.
    Priority: place > district > locality > neighborhood.
    """
    context = feature.get("properties", {}).get("context", {})
    if not context:
        context = feature.get("context", {})
    ctx = _extract_from_context(context)
    candidates = []
    for key in ("place", "district", "locality", "neighborhood"):
        v = (ctx.get(key) or "").strip()
        if v and v not in candidates:
            candidates.append(v)
    return candidates


def map_place_details_to_address(
    feature: Dict[str, Any],
    country_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Map a Mapbox GeoJSON Feature (from retrieve or geocode) to backend address schema.
    country_override: if set, use as country_code (alpha-2); else derive from context.
    """
    props = feature.get("properties", {})
    context = props.get("context", {})
    if not context:
        context = feature.get("context", {})
    ctx = _extract_from_context(context)

    street = ctx.get("street", "")
    address_number = ctx.get("address_number", "")
    city = ctx.get("place", "") or ctx.get("district", "") or ctx.get("locality", "") or ""
    province = ctx.get("region", "")
    postal_code = ctx.get("postcode", "")

    street_type, street_name = _route_to_street_type_and_name(street) if street else ("St", "")

    # Country code resolution
    if country_override:
        country_alpha2 = normalize_country_code(country_override) or (country_override or "")[:2].upper()
    else:
        raw_cc = ctx.get("country_code", "")
        if len(raw_cc) == 2 and raw_cc.isalpha():
            country_alpha2 = raw_cc.upper()
        elif len(raw_cc) == 3 and raw_cc.isalpha():
            country_alpha2 = country_alpha3_to_alpha2(raw_cc)
        else:
            country_name = ctx.get("country_name", "")
            country_alpha2 = (country_name_to_alpha2(country_name) or "").upper() if country_name else ""

    formatted_address = props.get("full_address") or feature.get("full_address") or ""

    return {
        "street_name": street_name or "\u2014",
        "street_type": street_type,
        "building_number": address_number or "\u2014",
        "apartment_unit": None,
        "floor": None,
        "city": city or "\u2014",
        "province": province or "\u2014",
        "postal_code": postal_code or "\u2014",
        "country_code": country_alpha2,
        "formatted_address": formatted_address,
    }


def extract_place_details_geolocation(feature: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract mapbox_id, viewport, formatted_address, latitude, longitude from Mapbox Feature.

    GeoJSON coordinates are [longitude, latitude] — swapped to (lat, lng) for our schema.
    mapbox_id is stored in the existing place_id column (Phase 1 compatibility).
    formatted_address is stored in the existing formatted_address_google column (Phase 2 renames).
    """
    props = feature.get("properties", {})
    mapbox_id = props.get("mapbox_id") or ""
    formatted = props.get("full_address") or ""

    coords = feature.get("geometry", {}).get("coordinates", [])
    lat = coords[1] if len(coords) >= 2 else None
    lng = coords[0] if len(coords) >= 2 else None

    if lat is None or lng is None:
        return {
            "place_id": mapbox_id or None,
            "viewport": None,
            "formatted_address_google": formatted or None,
            "latitude": None,
            "longitude": None,
        }

    # Mapbox bbox: [min_lng, min_lat, max_lng, max_lat] — convert to our viewport schema
    bbox = props.get("bbox") or feature.get("bbox")
    viewport = None
    if bbox and len(bbox) >= 4:
        viewport = {
            "low": {"lat": float(bbox[1]), "lng": float(bbox[0])},
            "high": {"lat": float(bbox[3]), "lng": float(bbox[2])},
        }

    return {
        "place_id": mapbox_id or None,
        "viewport": viewport,
        "formatted_address_google": formatted or None,
        "latitude": float(lat),
        "longitude": float(lng),
    }
