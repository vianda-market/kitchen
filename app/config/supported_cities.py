"""
Supported cities for user onboarding and address scoping.

Single source of truth: Cities managed by Vianda (business development).
Used by GET /api/v1/cities/ and for city_info seed. Users pick from this list.
"""

from typing import List, Optional
from uuid import UUID

# Global city for B2B users (Employee, Supplier). No city filter in queries.
# country_code 'GL' matches Global Marketplace. Seeded in seed.sql.
GLOBAL_CITY_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
GLOBAL_CITY_COUNTRY_CODE = "GL"
GLOBAL_CITY_NAME = "Global"


def is_global_city(city_id: Optional[UUID]) -> bool:
    """Return True if city_id is the Global city sentinel (B2B users, no city filter)."""
    return city_id is not None and city_id == GLOBAL_CITY_ID


# (country_code, province_code, city_name) - ISO 3166-1 alpha-2. Cities managed by Vianda.
# province_code must exist in supported_provinces. Sorted by country_code, province_code, city_name.
SUPPORTED_CITIES = (
    # Argentina
    ("AR", "CABA", "Buenos Aires"),
    ("AR", "CO", "Cordoba"),
    ("AR", "BA", "La Plata"),
    ("AR", "MN", "Mendoza"),
    ("AR", "MI", "Misiones"),
    ("AR", "SF", "Rosario"),
    ("AR", "TF", "Tierra del Fuego"),
    # Brazil
    ("BR", "RJ", "Rio de Janeiro"),
    ("BR", "SP", "Sao Paulo"),
    # Chile
    ("CL", "RM", "Santiago"),
    # Mexico
    ("MX", "CDMX", "Mexico DF"),
    ("MX", "NL", "Monterrey"),
    # Peru
    ("PE", "ARE", "Arequipa"),
    ("PE", "LIM", "Lima"),
    ("PE", "LAL", "Trujillo"),
    # United States
    ("US", "TX", "Austin"),
    ("US", "IL", "Chicago"),
    ("US", "CA", "Los Angeles"),
    ("US", "FL", "Miami"),
    ("US", "NY", "New York"),
    ("US", "CA", "San Francisco"),
    ("US", "WA", "Seattle"),
)


def get_supported_cities_sorted_by_country_and_name(
    country_code: Optional[str] = None,
    province_code: Optional[str] = None,
) -> List[dict]:
    """
    Return list of { "country_code": str, "province_code": str, "city_name": str }
    for supported cities, optionally filtered by country_code and/or province_code.
    Sorted by country_code, province_code, city_name (case-insensitive).
    """
    out = [
        {"country_code": cc, "province_code": pcode, "city_name": name}
        for cc, pcode, name in SUPPORTED_CITIES
    ]
    if country_code:
        ccu = (country_code or "").strip().upper()
        out = [x for x in out if x["country_code"] == ccu]
    if province_code:
        pcu = (province_code or "").strip()
        out = [x for x in out if x["province_code"] == pcu]
    out.sort(key=lambda x: (x["country_code"], x["province_code"], x["city_name"].lower()))
    return out
