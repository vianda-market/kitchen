"""
Supported provinces/states for user onboarding and address scoping.

Single source of truth: Provinces that have at least one supported city.
Used by GET /api/v1/provinces/ and for location validation.
Derived from supported_cities config.
"""

# (country_code, province_code, province_name) - ISO 3166-1 alpha-2 for country.
# province_code: short code (e.g. WA, FL). province_name: full name for display.
# Sorted by country_code then province_name for maintainability.
SUPPORTED_PROVINCES = (
    # Argentina
    ("AR", "CABA", "Ciudad Autónoma de Buenos Aires"),
    ("AR", "BA", "Buenos Aires"),
    ("AR", "CO", "Córdoba"),
    ("AR", "MN", "Mendoza"),
    ("AR", "MI", "Misiones"),
    ("AR", "SF", "Santa Fe"),
    ("AR", "TF", "Tierra del Fuego"),
    # Brazil
    ("BR", "RJ", "Rio de Janeiro"),
    ("BR", "SP", "São Paulo"),
    # Chile
    ("CL", "RM", "Región Metropolitana"),
    # Mexico
    ("MX", "CDMX", "Ciudad de México"),
    ("MX", "NL", "Nuevo León"),
    # Peru
    ("PE", "ARE", "Arequipa"),
    ("PE", "LIM", "Lima"),
    ("PE", "LAL", "La Libertad"),
    # United States
    ("US", "TX", "Texas"),
    ("US", "IL", "Illinois"),
    ("US", "CA", "California"),
    ("US", "FL", "Florida"),
    ("US", "NY", "New York"),
    ("US", "WA", "Washington"),
)


def get_supported_provinces_by_country(country_code: str) -> list[dict]:
    """
    Return list of { "province_code": str, "province_name": str, "country_code": str }
    for the given country, sorted by province_name.
    """
    cc = (country_code or "").strip().upper()
    out = [
        {"province_code": pcode, "province_name": pname, "country_code": pcc}
        for pcc, pcode, pname in SUPPORTED_PROVINCES
        if pcc == cc
    ]
    out.sort(key=lambda x: x["province_name"].lower())
    return out


def get_all_supported_provinces() -> list[dict]:
    """
    Return list of { "province_code": str, "province_name": str, "country_code": str }
    for all supported provinces, sorted by country_code then province_name.
    """
    out = [
        {"province_code": pcode, "province_name": pname, "country_code": pcc}
        for pcc, pcode, pname in SUPPORTED_PROVINCES
    ]
    out.sort(key=lambda x: (x["country_code"], x["province_name"].lower()))
    return out
