"""
Location config for cron scheduling.

Maps location_id (timezone-region) to timezone. Single-timezone markets (AR, PE) use
country as location; US is split by timezone region (Eastern, Central, Mountain, Pacific).
Aligned with TimezoneService.PROVINCE_TIMEZONE_MAPPING for US.
"""

from typing import List, Dict, Optional

LOCATIONS: List[Dict[str, str]] = [
    {"location": "AR", "market": "AR", "timezone": "America/Argentina/Buenos_Aires"},
    {"location": "PE", "market": "PE", "timezone": "America/Lima"},
    {"location": "US-Eastern", "market": "US", "timezone": "America/New_York"},
    {"location": "US-Central", "market": "US", "timezone": "America/Chicago"},
    {"location": "US-Mountain", "market": "US", "timezone": "America/Denver"},
    {"location": "US-Pacific", "market": "US", "timezone": "America/Los_Angeles"},
]


def get_location_config(location_id: str) -> Optional[Dict[str, str]]:
    """Get config for location_id (e.g. AR, US-Eastern)."""
    loc = next((l for l in LOCATIONS if l["location"] == location_id), None)
    return loc


def get_all_locations() -> List[Dict[str, str]]:
    """Get all location configs."""
    return list(LOCATIONS)


def get_locations_for_market(market: str) -> List[Dict[str, str]]:
    """Get locations for a market (e.g. US returns US-Eastern, US-Central, etc.)."""
    return [l for l in LOCATIONS if l["market"] == market]


def get_location_id_for_timezone(tz: str) -> Optional[str]:
    """Map IANA timezone to location_id. e.g. America/Los_Angeles -> US-Pacific."""
    for loc in LOCATIONS:
        if loc["timezone"] == tz:
            return loc["location"]
    return None
