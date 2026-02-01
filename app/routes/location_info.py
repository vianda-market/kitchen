"""
Location Information Routes

Provides endpoints for getting supported countries, cities, and timezone information.
This helps frontend applications populate dropdowns and validate location data.
"""

from fastapi import APIRouter, HTTPException, status
from typing import List, Dict
from app.services.timezone_service import (
    get_supported_countries, 
    get_supported_cities, 
    get_timezone_for_location
)
from app.utils.log import log_info

router = APIRouter(
    prefix="/location-info",
    tags=["Location Information"]
)

@router.get("/countries", response_model=List[str])
def get_countries():
    """
    Get list of supported countries for timezone assignment.
    
    Returns:
        List of supported country names
    """
    countries = get_supported_countries()
    log_info(f"Returning {len(countries)} supported countries")
    return countries

@router.get("/countries/{country}/cities", response_model=List[str])
def get_cities_for_country(country: str):
    """
    Get list of supported cities for a specific country.
    
    Args:
        country: Country name
        
    Returns:
        List of supported city names for the country
    """
    cities = get_supported_cities(country)
    log_info(f"Returning {len(cities)} supported cities for {country}")
    return cities

@router.get("/timezone/{country}/{city}", response_model=Dict[str, str])
def get_timezone_for_city(country: str, city: str):
    """
    Get timezone for a specific country and city combination.
    
    Args:
        country: Country name
        city: City name
        
    Returns:
        Dictionary with timezone information
    """
    timezone = get_timezone_for_location(country, city)
    log_info(f"Timezone for {city}, {country}: {timezone}")
    return {
        "country": country,
        "city": city,
        "timezone": timezone
    }

@router.get("/supported-locations", response_model=Dict[str, Dict[str, List[str]]])
def get_all_supported_locations():
    """
    Get complete mapping of supported countries and their cities.
    
    Returns:
        Dictionary mapping countries to their supported cities
    """
    from app.services.timezone_service import TimezoneService
    
    result = {}
    for country in get_supported_countries():
        cities = get_supported_cities(country)
        result[country] = {
            "cities": cities,
            "default_timezone": TimezoneService.TIMEZONE_MAPPING[country]["default"]
        }
    
    log_info(f"Returning location mapping for {len(result)} countries")
    return result
