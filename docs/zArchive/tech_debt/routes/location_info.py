"""
Location Information Routes - ARCHIVED 2026-03-14

DEPRECATED: These endpoints are legacy city-based timezone lookups.
Use the Markets API and province-based timezone deduction instead:
- GET /api/v1/markets/ - Get available countries with country_code
- Timezone is automatically calculated from country_code + province during address creation

This file was removed from app/routes/ for API docs cleanup.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict
import psycopg2.extensions
from app.services.timezone_service import TimezoneService
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning
from app.utils.country import normalize_country_code

router = APIRouter(
    prefix="/location-info",
    tags=["Location Information (Deprecated)"]
)

@router.get("/multi-timezone-countries", response_model=List[str])
def get_multi_timezone_countries():
    countries = TimezoneService.get_supported_multi_timezone_countries()
    log_info(f"Returning {len(countries)} multi-timezone countries")
    return countries

@router.get("/countries/{country_code}/provinces", response_model=List[str])
def get_provinces_for_country(country_code: str):
    country = normalize_country_code(country_code)
    provinces = TimezoneService.get_supported_provinces(country)
    log_info(f"Returning {len(provinces)} provinces for {country_code}")
    return provinces

@router.get("/countries", response_model=List[str], deprecated=True)
def get_countries():
    log_warning("DEPRECATED: /location-info/countries called. Use /api/v1/markets/ instead.")
    return []

@router.get("/countries/{country}/cities", response_model=List[str], deprecated=True)
def get_cities_for_country(country: str):
    log_warning(f"DEPRECATED: /location-info/countries/{country}/cities called. Use province-based system instead.")
    return []

@router.get("/timezone/{country}/{city}", response_model=Dict[str, str], deprecated=True)
def get_timezone_for_city(country: str, city: str):
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
    log_warning("DEPRECATED: /location-info/supported-locations called. Use /api/v1/markets/ instead.")
    return {}
