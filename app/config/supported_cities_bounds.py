"""
City bounds for Google Places Autocomplete locationRestriction.

Key: (country_code, province_code, city_name). Value: {south, west, north, east}.
Used to restrict suggestions to city area and reduce "outside service area" failures.
"""

from typing import Any

# south < north, west < east (typically). Bounding box for each supported city.
CITY_BOUNDS: dict[tuple, dict[str, float]] = {
    # Argentina
    ("AR", "CABA", "Buenos Aires"): {"south": -34.70, "west": -58.55, "north": -34.52, "east": -58.35},
    ("AR", "CO", "Cordoba"): {"south": -31.50, "west": -64.30, "north": -31.35, "east": -64.10},
    ("AR", "BA", "La Plata"): {"south": -34.95, "west": -58.00, "north": -34.88, "east": -57.90},
    ("AR", "MN", "Mendoza"): {"south": -32.95, "west": -68.90, "north": -32.82, "east": -68.78},
    ("AR", "MI", "Misiones"): {"south": -27.00, "west": -54.55, "north": -26.75, "east": -54.35},
    ("AR", "SF", "Rosario"): {"south": -33.00, "west": -60.70, "north": -32.88, "east": -60.58},
    ("AR", "TF", "Tierra del Fuego"): {"south": -54.85, "west": -68.40, "north": -54.75, "east": -68.25},
    # Brazil
    ("BR", "RJ", "Rio de Janeiro"): {"south": -23.00, "west": -43.30, "north": -22.80, "east": -43.10},
    ("BR", "SP", "Sao Paulo"): {"south": -23.65, "west": -46.75, "north": -23.45, "east": -46.55},
    # Chile
    ("CL", "RM", "Santiago"): {"south": -33.55, "west": -70.75, "north": -33.35, "east": -70.55},
    # Mexico
    ("MX", "CDMX", "Mexico DF"): {"south": 19.30, "west": -99.25, "north": 19.55, "east": -99.05},
    ("MX", "NL", "Monterrey"): {"south": 25.65, "west": -100.40, "north": 25.75, "east": -100.25},
    # Peru
    ("PE", "ARE", "Arequipa"): {"south": -16.45, "west": -71.60, "north": -16.35, "east": -71.48},
    ("PE", "LIM", "Lima"): {"south": -12.15, "west": -77.10, "north": -11.95, "east": -76.95},
    ("PE", "LAL", "Trujillo"): {"south": -8.15, "west": -79.08, "north": -8.05, "east": -78.98},
    # United States
    ("US", "TX", "Austin"): {"south": 30.20, "west": -97.85, "north": 30.40, "east": -97.65},
    ("US", "IL", "Chicago"): {"south": 41.75, "west": -87.75, "north": 42.00, "east": -87.50},
    ("US", "CA", "Los Angeles"): {"south": 33.95, "west": -118.40, "north": 34.15, "east": -118.15},
    ("US", "CA", "San Francisco"): {"south": 37.70, "west": -122.50, "north": 37.85, "east": -122.35},
    ("US", "FL", "Miami"): {"south": 25.70, "west": -80.30, "north": 25.85, "east": -80.10},
    ("US", "NY", "New York"): {"south": 40.65, "west": -74.05, "north": 40.85, "east": -73.85},
    ("US", "WA", "Seattle"): {"south": 47.55, "west": -122.45, "north": 47.70, "east": -122.25},
}


def get_city_bounds(
    country_code: str,
    province_code: str | None,
    city_name: str | None = None,
) -> dict[str, float] | None:
    """
    Return bounds {south, west, north, east} for a supported city.
    Tries (country_code, province_code, city_name) first, then first match for province.
    """
    if not country_code or not province_code:
        return None
    cc = country_code.strip().upper()
    pc = province_code.strip()
    if city_name:
        key = (cc, pc, city_name.strip())
        if key in CITY_BOUNDS:
            return CITY_BOUNDS[key]
    for k, v in CITY_BOUNDS.items():
        if len(k) >= 2 and k[0] == cc and k[1] == pc:
            return v
    return None


def get_city_bounds_by_name(country_code: str, city_name: str) -> dict[str, float] | None:
    """Return bounds for a supported city by name."""
    from app.config.supported_cities import get_supported_cities_sorted_by_country_and_name

    cities = get_supported_cities_sorted_by_country_and_name(country_code=country_code)
    city_lower = (city_name or "").strip().lower()
    for c in cities:
        if (c.get("city_name") or "").strip().lower() == city_lower:
            return get_city_bounds(c["country_code"], c.get("province_code"), c.get("city_name"))
    return None


def bounds_to_location_restriction(bounds: dict[str, float]) -> dict[str, Any]:
    """
    Convert {south, west, north, east} to Google Places API locationRestriction rectangle.
    """
    return {
        "rectangle": {
            "low": {"latitude": bounds["south"], "longitude": bounds["west"]},
            "high": {"latitude": bounds["north"], "longitude": bounds["east"]},
        }
    }
