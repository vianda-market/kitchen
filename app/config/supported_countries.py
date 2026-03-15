"""
Supported countries for new markets (Create Market dropdown and validation).

Single source of truth: Americas from Canada to Argentina (North, Central, Caribbean, South).
More regions can be added later. Used by GET /api/v1/countries/ and by market create/update validation.
"""

# ISO 3166-1 alpha-2 codes: Americas (sovereign states), Canada to Argentina.
# North America, Central America, Caribbean, South America. Sorted by code for maintainability;
# API returns sorted by country_name.
SUPPORTED_COUNTRY_CODES = (
    "AG",  # Antigua and Barbuda
    "AR",  # Argentina
    "BS",  # Bahamas
    "BB",  # Barbados
    "BZ",  # Belize
    "BO",  # Bolivia
    "BR",  # Brazil
    "CA",  # Canada
    "CL",  # Chile
    "CO",  # Colombia
    "CR",  # Costa Rica
    "CU",  # Cuba
    "DM",  # Dominica
    "DO",  # Dominican Republic
    "EC",  # Ecuador
    "SV",  # El Salvador
    "GD",  # Grenada
    "GT",  # Guatemala
    "GY",  # Guyana
    "HT",  # Haiti
    "HN",  # Honduras
    "JM",  # Jamaica
    "MX",  # Mexico
    "NI",  # Nicaragua
    "PA",  # Panama
    "PY",  # Paraguay
    "PE",  # Peru
    "KN",  # Saint Kitts and Nevis
    "LC",  # Saint Lucia
    "VC",  # Saint Vincent and the Grenadines
    "SR",  # Suriname
    "TT",  # Trinidad and Tobago
    "US",  # United States
    "UY",  # Uruguay
    "VE",  # Venezuela
)


def get_supported_countries_sorted_by_name():
    """
    Return list of { "country_code": str, "country_name": str } for supported countries,
    sorted by country_name. Uses pycountry for official names (consistent with resolve_country_name).
    """
    import pycountry

    out = []
    for code in SUPPORTED_COUNTRY_CODES:
        country = pycountry.countries.get(alpha_2=code)
        name = country.name if country else code
        out.append({"country_code": code, "country_name": name})
    out.sort(key=lambda x: x["country_name"].lower())
    return out
