"""
Default (lat, lng) per supported city for Explore when user has no default address.
Used as focus for map center and radius distance when no user default.
"""

from typing import Optional, Dict, Any

# Key: (country_code, province_code, city_name) for cities with same province. Falls back to (country_code, province_code).
CITY_DEFAULT_LOCATION: Dict[tuple, Dict[str, float]] = {
    # Argentina
    ("AR", "CABA", "Buenos Aires"): {"lat": -34.6037, "lng": -58.3816},
    ("AR", "CO", "Cordoba"): {"lat": -31.4201, "lng": -64.1888},
    ("AR", "BA", "La Plata"): {"lat": -34.9215, "lng": -57.9545},
    ("AR", "MN", "Mendoza"): {"lat": -32.8895, "lng": -68.8458},
    ("AR", "MI", "Misiones"): {"lat": -26.8754, "lng": -54.4480},
    ("AR", "SF", "Rosario"): {"lat": -32.9468, "lng": -60.6393},
    ("AR", "TF", "Tierra del Fuego"): {"lat": -54.8019, "lng": -68.3030},
    # Brazil
    ("BR", "RJ", "Rio de Janeiro"): {"lat": -22.9068, "lng": -43.1729},
    ("BR", "SP", "Sao Paulo"): {"lat": -23.5505, "lng": -46.6333},
    # Chile
    ("CL", "RM", "Santiago"): {"lat": -33.4489, "lng": -70.6693},
    # Mexico
    ("MX", "CDMX", "Mexico DF"): {"lat": 19.4326, "lng": -99.1332},
    ("MX", "NL", "Monterrey"): {"lat": 25.6866, "lng": -100.3161},
    # Peru
    ("PE", "ARE", "Arequipa"): {"lat": -16.4090, "lng": -71.5375},
    ("PE", "LIM", "Lima"): {"lat": -12.0464, "lng": -77.0428},
    ("PE", "LAL", "Trujillo"): {"lat": -8.1116, "lng": -79.0282},
    # United States
    ("US", "TX", "Austin"): {"lat": 30.2672, "lng": -97.7431},
    ("US", "IL", "Chicago"): {"lat": 41.8781, "lng": -87.6298},
    ("US", "CA", "Los Angeles"): {"lat": 34.0522, "lng": -118.2437},
    ("US", "CA", "San Francisco"): {"lat": 37.7749, "lng": -122.4194},
    ("US", "FL", "Miami"): {"lat": 25.7617, "lng": -80.1918},
    ("US", "NY", "New York"): {"lat": 40.7128, "lng": -74.0060},
    ("US", "WA", "Seattle"): {"lat": 47.6062, "lng": -122.3321},
}


def get_city_default_location(
    country_code: str,
    province_code: Optional[str],
    city_name: Optional[str] = None,
) -> Optional[Dict[str, float]]:
    """
    Return default lat/lng for a supported city.
    Tries (country_code, province_code, city_name) first, then (country_code, province_code).
    """
    if not country_code or not province_code:
        return None
    cc = country_code.strip().upper()
    pc = province_code.strip()
    if city_name:
        key = (cc, pc, city_name.strip())
        if key in CITY_DEFAULT_LOCATION:
            return CITY_DEFAULT_LOCATION[key]
    # Fallback to first match for province
    for k, v in CITY_DEFAULT_LOCATION.items():
        if len(k) >= 2 and k[0] == cc and k[1] == pc:
            return v
    return None


def get_city_default_location_by_name(country_code: str, city_name: str) -> Optional[Dict[str, float]]:
    """
    Return default lat/lng for a supported city by name. Looks up province from supported_cities.
    """
    from app.config.supported_cities import get_supported_cities_sorted_by_country_and_name
    cities = get_supported_cities_sorted_by_country_and_name(country_code=country_code)
    city_lower = (city_name or "").strip().lower()
    for c in cities:
        if (c.get("city_name") or "").strip().lower() == city_lower:
            return get_city_default_location(
                c["country_code"], c.get("province_code"), c.get("city_name")
            )
    return None
