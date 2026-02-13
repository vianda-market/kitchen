"""
Location Information Routes

DEPRECATED: These endpoints are legacy city-based timezone lookups.
Use the Markets API and province-based timezone deduction instead:
- GET /api/v1/markets/ - Get available countries with country_code
- Timezone is automatically calculated from country_code + province during address creation

These endpoints are maintained for backward compatibility but will log deprecation warnings.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict
import psycopg2.extensions
from app.services.timezone_service import TimezoneService
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning

router = APIRouter(
    prefix="/location-info",
    tags=["Location Information (Deprecated)"]
)

@router.get("/multi-timezone-countries", response_model=List[str])
def get_multi_timezone_countries():
    """
    Get list of country codes that have multiple timezones.
    
    These countries require province/state for accurate timezone deduction.
    
    Returns:
        List of country codes (e.g., ["USA", "BRA", "CAN", "MEX"])
    """
    countries = TimezoneService.get_supported_multi_timezone_countries()
    log_info(f"Returning {len(countries)} multi-timezone countries")
    return countries

@router.get("/countries/{country_code}/provinces", response_model=List[str])
def get_provinces_for_country(country_code: str):
    """
    Get list of supported provinces/states for a multi-timezone country.
    
    Args:
        country_code: ISO 3166-1 alpha-3 country code (e.g., "USA", "BRA", "CAN")
        
    Returns:
        List of province/state names and codes. Empty list for single-timezone countries.
    """
    provinces = TimezoneService.get_supported_provinces(country_code.upper())
    log_info(f"Returning {len(provinces)} provinces for {country_code}")
    return provinces

@router.get("/countries", response_model=List[str], deprecated=True)
def get_countries():
    """
    DEPRECATED: Use GET /api/v1/markets/ instead.
    
    Get list of supported countries for timezone assignment.
    
    Returns:
        List of supported country names (deprecated format)
    """
    log_warning("DEPRECATED: /location-info/countries called. Use /api/v1/markets/ instead.")
    # Return empty list since old country names are deprecated
    return []

@router.get("/countries/{country}/cities", response_model=List[str], deprecated=True)
def get_cities_for_country(country: str):
    """
    DEPRECATED: Use province-based timezone deduction instead.
    
    Args:
        country: Country name (deprecated)
        
    Returns:
        Empty list (deprecated endpoint)
    """
    log_warning(f"DEPRECATED: /location-info/countries/{country}/cities called. Use province-based system instead.")
    return []

@router.get("/timezone/{country}/{city}", response_model=Dict[str, str], deprecated=True)
def get_timezone_for_city(country: str, city: str):
    """
    DEPRECATED: Use country_code + province for timezone deduction in address creation.
    
    Args:
        country: Country name (deprecated)
        city: City name (deprecated)
        
    Returns:
        Dictionary with timezone information (deprecated format)
    """
    log_warning(f"DEPRECATED: /location-info/timezone/{country}/{city} called. Use province-based system instead.")
    from app.services.timezone_service import get_timezone_for_location
    timezone = get_timezone_for_location(country, city)
    return {
        "country": country,
        "city": city,
        "timezone": timezone,
        "deprecated": True,
        "message": "Use country_code + province for timezone deduction. See /api/v1/markets/ for available countries."
    }

@router.get("/supported-locations", response_model=Dict[str, Dict], deprecated=True)
def get_all_supported_locations():
    """
    DEPRECATED: Use GET /api/v1/markets/ and province endpoints instead.
    
    Returns:
        Empty dictionary (deprecated endpoint)
    """
    log_warning("DEPRECATED: /location-info/supported-locations called. Use /api/v1/markets/ instead.")
    return {}
