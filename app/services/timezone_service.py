"""
Timezone Service

Handles automatic timezone assignment based on country_code and province/state.
For single-timezone countries, uses market_info table as source of truth.
For multi-timezone countries, uses province/state mappings.
"""

from typing import Dict, Optional
import psycopg2.extensions
from fastapi import HTTPException
from app.utils.log import log_info, log_warning
from app.utils.db import db_read

class TimezoneService:
    """Service for managing timezone assignments based on country_code and province"""
    
    # Mapping for multi-timezone countries only (country_code alpha-2 -> province -> timezone)
    # Single-timezone countries (AR, PE, CL, etc.) use market_info table
    PROVINCE_TIMEZONE_MAPPING = {
        "US": {
            # States by full name
            "Alabama": "America/Chicago",
            "Alaska": "America/Anchorage",
            "Arizona": "America/Phoenix",
            "Arkansas": "America/Chicago",
            "California": "America/Los_Angeles",
            "Colorado": "America/Denver",
            "Connecticut": "America/New_York",
            "Delaware": "America/New_York",
            "Florida": "America/New_York",
            "Georgia": "America/New_York",
            "Hawaii": "Pacific/Honolulu",
            "Idaho": "America/Denver",
            "Illinois": "America/Chicago",
            "Indiana": "America/New_York",
            "Iowa": "America/Chicago",
            "Kansas": "America/Chicago",
            "Kentucky": "America/New_York",
            "Louisiana": "America/Chicago",
            "Maine": "America/New_York",
            "Maryland": "America/New_York",
            "Massachusetts": "America/New_York",
            "Michigan": "America/New_York",
            "Minnesota": "America/Chicago",
            "Mississippi": "America/Chicago",
            "Missouri": "America/Chicago",
            "Montana": "America/Denver",
            "Nebraska": "America/Chicago",
            "Nevada": "America/Los_Angeles",
            "New Hampshire": "America/New_York",
            "New Jersey": "America/New_York",
            "New Mexico": "America/Denver",
            "New York": "America/New_York",
            "North Carolina": "America/New_York",
            "North Dakota": "America/Chicago",
            "Ohio": "America/New_York",
            "Oklahoma": "America/Chicago",
            "Oregon": "America/Los_Angeles",
            "Pennsylvania": "America/New_York",
            "Rhode Island": "America/New_York",
            "South Carolina": "America/New_York",
            "South Dakota": "America/Chicago",
            "Tennessee": "America/Chicago",
            "Texas": "America/Chicago",
            "Utah": "America/Denver",
            "Vermont": "America/New_York",
            "Virginia": "America/New_York",
            "Washington": "America/Los_Angeles",
            "West Virginia": "America/New_York",
            "Wisconsin": "America/Chicago",
            "Wyoming": "America/Denver",
            # States by code
            "AL": "America/Chicago",
            "AK": "America/Anchorage",
            "AZ": "America/Phoenix",
            "AR": "America/Chicago",
            "CA": "America/Los_Angeles",
            "CO": "America/Denver",
            "CT": "America/New_York",
            "DE": "America/New_York",
            "FL": "America/New_York",
            "GA": "America/New_York",
            "HI": "Pacific/Honolulu",
            "ID": "America/Denver",
            "IL": "America/Chicago",
            "IN": "America/New_York",
            "IA": "America/Chicago",
            "KS": "America/Chicago",
            "KY": "America/New_York",
            "LA": "America/Chicago",
            "ME": "America/New_York",
            "MD": "America/New_York",
            "MA": "America/New_York",
            "MI": "America/New_York",
            "MN": "America/Chicago",
            "MS": "America/Chicago",
            "MO": "America/Chicago",
            "MT": "America/Denver",
            "NE": "America/Chicago",
            "NV": "America/Los_Angeles",
            "NH": "America/New_York",
            "NJ": "America/New_York",
            "NM": "America/Denver",
            "NY": "America/New_York",
            "NC": "America/New_York",
            "ND": "America/Chicago",
            "OH": "America/New_York",
            "OK": "America/Chicago",
            "OR": "America/Los_Angeles",
            "PA": "America/New_York",
            "RI": "America/New_York",
            "SC": "America/New_York",
            "SD": "America/Chicago",
            "TN": "America/Chicago",
            "TX": "America/Chicago",
            "UT": "America/Denver",
            "VT": "America/New_York",
            "VA": "America/New_York",
            "WA": "America/Los_Angeles",
            "WV": "America/New_York",
            "WI": "America/Chicago",
            "WY": "America/Denver",
        },
        "BRA": {
            # Brazilian states by name
            "Acre": "America/Rio_Branco",
            "Alagoas": "America/Maceio",
            "Amapa": "America/Belem",
            "Amazonas": "America/Manaus",
            "Bahia": "America/Bahia",
            "Ceara": "America/Fortaleza",
            "Distrito Federal": "America/Sao_Paulo",
            "Espirito Santo": "America/Sao_Paulo",
            "Goias": "America/Sao_Paulo",
            "Maranhao": "America/Fortaleza",
            "Mato Grosso": "America/Cuiaba",
            "Mato Grosso do Sul": "America/Campo_Grande",
            "Minas Gerais": "America/Sao_Paulo",
            "Para": "America/Belem",
            "Paraiba": "America/Fortaleza",
            "Parana": "America/Sao_Paulo",
            "Pernambuco": "America/Recife",
            "Piaui": "America/Fortaleza",
            "Rio de Janeiro": "America/Sao_Paulo",
            "Rio Grande do Norte": "America/Fortaleza",
            "Rio Grande do Sul": "America/Sao_Paulo",
            "Rondonia": "America/Porto_Velho",
            "Roraima": "America/Boa_Vista",
            "Santa Catarina": "America/Sao_Paulo",
            "Sao Paulo": "America/Sao_Paulo",
            "Sergipe": "America/Maceio",
            "Tocantins": "America/Araguaina",
        },
        "CA": {
            # Canadian provinces by name
            "Alberta": "America/Edmonton",
            "British Columbia": "America/Vancouver",
            "Manitoba": "America/Winnipeg",
            "New Brunswick": "America/Halifax",
            "Newfoundland and Labrador": "America/St_Johns",
            "Northwest Territories": "America/Yellowknife",
            "Nova Scotia": "America/Halifax",
            "Nunavut": "America/Iqaluit",
            "Ontario": "America/Toronto",
            "Prince Edward Island": "America/Halifax",
            "Quebec": "America/Toronto",
            "Saskatchewan": "America/Regina",
            "Yukon": "America/Whitehorse",
            # Provinces by code
            "AB": "America/Edmonton",
            "BC": "America/Vancouver",
            "MB": "America/Winnipeg",
            "NB": "America/Halifax",
            "NL": "America/St_Johns",
            "NT": "America/Yellowknife",
            "NS": "America/Halifax",
            "NU": "America/Iqaluit",
            "ON": "America/Toronto",
            "PE": "America/Halifax",
            "QC": "America/Toronto",
            "SK": "America/Regina",
            "YT": "America/Whitehorse",
        },
        "MX": {
            # Mexican states by name
            "Aguascalientes": "America/Mexico_City",
            "Baja California": "America/Tijuana",
            "Baja California Sur": "America/Mazatlan",
            "Campeche": "America/Merida",
            "Chiapas": "America/Mexico_City",
            "Chihuahua": "America/Chihuahua",
            "Coahuila": "America/Monterrey",
            "Colima": "America/Mexico_City",
            "Durango": "America/Monterrey",
            "Guanajuato": "America/Mexico_City",
            "Guerrero": "America/Mexico_City",
            "Hidalgo": "America/Mexico_City",
            "Jalisco": "America/Mexico_City",
            "Mexico": "America/Mexico_City",
            "Mexico City": "America/Mexico_City",
            "Michoacan": "America/Mexico_City",
            "Morelos": "America/Mexico_City",
            "Nayarit": "America/Mazatlan",
            "Nuevo Leon": "America/Monterrey",
            "Oaxaca": "America/Mexico_City",
            "Puebla": "America/Mexico_City",
            "Queretaro": "America/Mexico_City",
            "Quintana Roo": "America/Cancun",
            "San Luis Potosi": "America/Mexico_City",
            "Sinaloa": "America/Mazatlan",
            "Sonora": "America/Hermosillo",
            "Tabasco": "America/Mexico_City",
            "Tamaulipas": "America/Monterrey",
            "Tlaxcala": "America/Mexico_City",
            "Veracruz": "America/Mexico_City",
            "Yucatan": "America/Merida",
            "Zacatecas": "America/Mexico_City",
        }
    }
    
    @classmethod
    def deduce_timezone(cls, country_code: str, province: Optional[str], db: psycopg2.extensions.connection) -> str:
        """
        Deduce timezone from country_code and optional province/state.
        
        Logic:
        1. Query market_info for country's default timezone
        2. If country not found → raise HTTPException (400)
        3. If country has single timezone (not in PROVINCE_TIMEZONE_MAPPING) → return market default
        4. If country has multiple timezones:
           - If province provided → lookup in PROVINCE_TIMEZONE_MAPPING
           - If province found → return province timezone
           - If province not found or not provided → return market default + log warning
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code (e.g., "AR", "US", "BR")
            province: Province/state name or code (optional for single-TZ countries)
            db: Database connection
            
        Returns:
            Timezone string (e.g., "America/New_York", "America/Argentina/Buenos_Aires")
            
        Raises:
            HTTPException: 400 if country_code not found in market_info
        """
        if not country_code:
            raise HTTPException(status_code=400, detail="country_code is required for timezone deduction")
        
        # Callers (route, address_service) pass already-normalized country_code.
        
        # Query market_info for default timezone
        market_data = cls._get_market_timezone(country_code, db)
        if not market_data:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid country_code: {country_code}. Market not found in market_info."
            )
        
        default_timezone = market_data["timezone"]
        country_name = market_data["country_name"]
        
        # Check if this is a multi-timezone country
        if country_code not in cls.PROVINCE_TIMEZONE_MAPPING:
            # Single-timezone country - use market default
            log_info(f"Single-timezone country {country_name} ({country_code}): using {default_timezone}")
            return default_timezone
        
        # Multi-timezone country - check province
        if not province:
            log_warning(
                f"Multi-timezone country {country_name} ({country_code}) but no province provided. "
                f"Using default timezone: {default_timezone}"
            )
            return default_timezone
        
        # Normalize province name
        normalized_province = cls._normalize_province_name(province)
        
        # Lookup province in mapping
        province_mapping = cls.PROVINCE_TIMEZONE_MAPPING[country_code]
        if normalized_province in province_mapping:
            province_timezone = province_mapping[normalized_province]
            log_info(
                f"Found timezone for {normalized_province}, {country_name} ({country_code}): {province_timezone}"
            )
            return province_timezone
        
        # Province not found - use default + warning
        log_warning(
            f"Province '{province}' not found in timezone mapping for {country_name} ({country_code}). "
            f"Using default timezone: {default_timezone}. "
            f"Available provinces: {list(province_mapping.keys())[:10]}..."
        )
        return default_timezone
    
    # Primary timezone per seeded market (ops-curated; single-TZ countries use this directly,
    # multi-TZ countries (US, BR, CA, MX) use PROVINCE_TIMEZONE_MAPPING and fall back to this).
    # Replaces the former SELECT m.timezone from market_info (column dropped in PR2b).
    _MARKET_PRIMARY_TIMEZONE = {
        "XG": "UTC",
        "AR": "America/Argentina/Buenos_Aires",
        "PE": "America/Lima",
        "CL": "America/Santiago",
        "US": "America/New_York",
        "MX": "America/Mexico_City",
        "BR": "America/Sao_Paulo",
    }

    @classmethod
    def _get_market_timezone(cls, country_code: str, db: psycopg2.extensions.connection) -> Optional[Dict]:
        """
        Return a primary timezone for a country. Used by address-create fallback for
        single-TZ countries. `db` is unused (kept for signature compatibility with callers
        that pass a connection); the mapping is ops-curated in `_MARKET_PRIMARY_TIMEZONE`.

        Args:
            country_code: ISO 3166-1 alpha-2 country code
            db: Database connection (unused, kept for compat)

        Returns:
            Dict with 'timezone' and 'country_name' keys, or None if country_code unknown.
        """
        cc = (country_code or "").strip().upper()
        tz = cls._MARKET_PRIMARY_TIMEZONE.get(cc)
        if tz is None:
            return None
        return {"timezone": tz, "country_name": cc}
    
    @classmethod
    def _normalize_province_name(cls, province: str) -> str:
        """
        Normalize province/state name for consistent lookups.
        Handles variations like "New York" vs "NY" vs "New York State".
        
        Args:
            province: Province/state name or code
            
        Returns:
            Normalized province name
        """
        if not province:
            return ""
        
        # Strip whitespace and convert to title case
        normalized = province.strip().title()
        
        # Remove common suffixes
        suffixes_to_remove = [" State", " Province", " Territory"]
        for suffix in suffixes_to_remove:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
        
        # If it's already uppercase and 2 chars, assume it's a state code
        if province.strip().isupper() and len(province.strip()) == 2:
            normalized = province.strip().upper()
        
        return normalized
    
    @classmethod
    def get_supported_multi_timezone_countries(cls) -> list:
        """
        Get list of country codes with multiple timezones.
        
        Returns:
            List of country codes alpha-2 (e.g., ["US", "BR", "CA", "MX"])
        """
        return list(cls.PROVINCE_TIMEZONE_MAPPING.keys())
    
    @classmethod
    def get_supported_provinces(cls, country_code: str) -> list:
        """
        Get list of supported provinces/states for a multi-timezone country.
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code
            
        Returns:
            List of province names/codes, or empty list if single-timezone country
        """
        if country_code not in cls.PROVINCE_TIMEZONE_MAPPING:
            return []
        
        return list(cls.PROVINCE_TIMEZONE_MAPPING[country_code].keys())

# Convenience function for backward compatibility (deprecated)
def get_timezone_for_location(country: str, city: str) -> str:
    """
    DEPRECATED: Use deduce_timezone_from_address() instead.
    Legacy function for backward compatibility with city-based lookups.
    """
    log_warning(
        f"get_timezone_for_location(country='{country}', city='{city}') is deprecated. "
        f"Use deduce_timezone_from_address() with country_code and province instead."
    )
    # Fallback to a default timezone
    return "America/New_York"

def deduce_timezone_from_address(country_code: str, province: Optional[str], db: psycopg2.extensions.connection) -> str:
    """
    Deduce timezone from country_code and province.
    Convenience function that delegates to TimezoneService.deduce_timezone().
    
    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., "AR", "US")
        province: Province/state name or code (optional for single-TZ countries)
        db: Database connection
        
    Returns:
        Timezone string (e.g., "America/New_York")
    """
    return TimezoneService.deduce_timezone(country_code, province, db)
