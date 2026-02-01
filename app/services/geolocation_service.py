"""
Geolocation Service - Business Logic for Location and Timezone Operations

This service contains business logic for geocoding, timezone mapping,
and location-based calculations used throughout the application.
"""

import os
import requests
from app.utils.log import log_info, log_warning
import pytz
from typing import Optional

def call_geocode_api(full_address: str) -> dict:
    """
    Call the geocode API to get coordinates for an address.
    """
    try:
        # This is a placeholder - replace with actual geocoding service
        response = requests.get(f"https://api.example.com/geocode?address={full_address}")
        if response.status_code == 200:
            return response.json()
        else:
            log_warning(f"Geocode API returned status {response.status_code}")
            return {}
    except Exception as e:
        log_warning(f"Error calling geocode API: {e}")
        return {}

def get_timezone_from_location(country: str, city: str) -> str:
    """
    Map country and city to a timezone string.
    Returns a default timezone if no mapping is found.
    
    This function now uses the centralized TimezoneService for consistency.
    """
    from app.services.timezone_service import get_timezone_for_location
    return get_timezone_for_location(country, city)
