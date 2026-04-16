"""
Market-specific address display formatting.

Street block order differs by market:
- USA: building_number, street_name, street_type (e.g. "123 Main St")
- Argentina, Peru: street_type, street_name, building_number (e.g. "Av Santa Fe 100")
"""

from app.config.market_config import MarketConfiguration


def format_street_display(
    country_code: str,
    street_type: str | None,
    street_name: str | None,
    building_number: str | None,
) -> str:
    """
    Format street components for display according to market conventions.

    Args:
        country_code: ISO country code (e.g. US, AR, PE) to determine display order
        street_type: Street type (e.g. St, Ave, Av)
        street_name: Street name
        building_number: Building/house number

    Returns:
        Formatted street string (e.g. "123 Main St" or "Av Santa Fe 100").
        Empty string if all parts are empty.
    """
    config = MarketConfiguration.get_market_config(country_code or "")
    if config and hasattr(config, "address_street_order"):
        order = config.address_street_order
    else:
        order = ["street_name", "building_number", "street_type"]

    parts_map = {
        "street_type": (street_type or "").strip(),
        "street_name": (street_name or "").strip(),
        "building_number": (building_number or "").strip(),
    }

    parts = [parts_map.get(k, "") for k in order if k in parts_map]
    result = " ".join(p for p in parts if p)
    return result.strip()


def format_address_display(
    country_code: str,
    street_type: str | None,
    street_name: str | None,
    building_number: str | None,
    city: str | None = None,
    postal_code: str | None = None,
) -> str:
    """
    Format full address for display: market-aware street + city + postal_code.
    Used for enriched address formatted_address field.
    """
    street_part = format_street_display(country_code, street_type, street_name, building_number)
    parts = [street_part] if street_part else []
    if city and (city := (city or "").strip()):
        parts.append(city)
    if postal_code and (postal_code := (postal_code or "").strip()):
        parts.append(postal_code)
    return " · ".join(parts) if parts else ""
