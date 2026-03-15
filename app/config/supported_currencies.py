"""
Supported currencies for B2B (Create Credit Currency dropdown and validation).

Single source of truth: list of (currency_name, currency_code) for dropdown and for
resolving currency_code from currency_name on credit currency create.
Used by GET /api/v1/currencies/ and by POST /api/v1/credit-currencies/ validation.
"""

from typing import List, Optional

# (currency_name, currency_code) - ISO 4217. Names must be unique for name→code lookup.
# Americas-focused plus common; sorted by code for maintainability; API returns sorted by name.
# currency_name max 50 chars (credit_currency_info.currency_name).
SUPPORTED_CURRENCIES: List[tuple] = [
    ("Argentine Peso", "ARS"),
    ("Bahamian Dollar", "BSD"),
    ("Barbadian Dollar", "BBD"),
    ("Belize Dollar", "BZD"),
    ("Bolivian Boliviano", "BOB"),
    ("Brazilian Real", "BRL"),
    ("Canadian Dollar", "CAD"),
    ("Chilean Peso", "CLP"),
    ("Colombian Peso", "COP"),
    ("Costa Rican Colón", "CRC"),
    ("Cuban Peso", "CUP"),
    ("Dominican Peso", "DOP"),
    ("East Caribbean Dollar", "XCD"),
    ("Ecuadorian US Dollar", "USD"),  # Ecuador uses USD
    ("Guatemalan Quetzal", "GTQ"),
    ("Guyanese Dollar", "GYD"),
    ("Haitian Gourde", "HTG"),
    ("Honduran Lempira", "HNL"),
    ("Jamaican Dollar", "JMD"),
    ("Mexican Peso", "MXN"),
    ("Nicaraguan Córdoba", "NIO"),
    ("Panamanian Balboa", "PAB"),
    ("Paraguayan Guaraní", "PYG"),
    ("Peruvian Sol", "PEN"),
    ("Surinamese Dollar", "SRD"),
    ("Trinidad and Tobago Dollar", "TTD"),
    ("US Dollar", "USD"),
    ("Uruguayan Peso", "UYU"),
    ("Venezuelan Bolívar Soberano", "VES"),
]

# For validation: set of supported codes (derived from list).
SUPPORTED_CURRENCY_CODES = frozenset(code for _, code in SUPPORTED_CURRENCIES)

# Name → code lookup (unique names).
_NAME_TO_CODE = {name: code for name, code in SUPPORTED_CURRENCIES}


def get_supported_currencies_sorted_by_name() -> List[dict]:
    """
    Return list of { "currency_name": str, "currency_code": str } for supported currencies,
    sorted by currency_name (case-insensitive).
    """
    out = [{"currency_name": name, "currency_code": code} for name, code in SUPPORTED_CURRENCIES]
    out.sort(key=lambda x: x["currency_name"].lower())
    return out


def get_currency_code_by_name(currency_name: Optional[str]) -> Optional[str]:
    """
    Return the ISO 4217 currency code for the given currency name, or None if not supported.
    Uses exact match on the supported list.
    """
    if currency_name is None:
        return None
    return _NAME_TO_CODE.get(currency_name.strip())
