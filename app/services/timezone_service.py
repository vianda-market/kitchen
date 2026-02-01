"""
Timezone Service

Handles automatic timezone assignment based on country and city combinations.
This service provides a mapping of supported countries/cities to their timezones.
"""

from typing import Dict, Optional
from app.utils.log import log_info, log_warning

class TimezoneService:
    """Service for managing timezone assignments"""
    
    # Mapping of country -> city -> timezone
    # Focused on North and South American countries
    TIMEZONE_MAPPING = {
        "Argentina": {
            "default": "America/Argentina/Buenos_Aires",
            "Ciudad Autonoma de Buenos Aires": "America/Argentina/Buenos_Aires",
            "Buenos Aires": "America/Argentina/Buenos_Aires",
            "Cordoba": "America/Argentina/Cordoba",
            "Rosario": "America/Argentina/Buenos_Aires",
            "Mendoza": "America/Argentina/Mendoza",
            "La Plata": "America/Argentina/Buenos_Aires",
            "Tucuman": "America/Argentina/Tucuman",
            "Mar del Plata": "America/Argentina/Buenos_Aires",
        },
        "United States": {
            "default": "America/New_York",
            "New York": "America/New_York",
            "Los Angeles": "America/Los_Angeles",
            "Chicago": "America/Chicago",
            "Houston": "America/Chicago",
            "Phoenix": "America/Phoenix",
            "Philadelphia": "America/New_York",
            "San Antonio": "America/Chicago",
            "San Diego": "America/Los_Angeles",
            "Dallas": "America/Chicago",
            "San Jose": "America/Los_Angeles",
            "Austin": "America/Chicago",
            "Jacksonville": "America/New_York",
            "Fort Worth": "America/Chicago",
            "Columbus": "America/New_York",
            "Charlotte": "America/New_York",
            "San Francisco": "America/Los_Angeles",
            "Indianapolis": "America/New_York",
            "Seattle": "America/Los_Angeles",
            "Denver": "America/Denver",
            "Washington": "America/New_York",
            "Boston": "America/New_York",
            "El Paso": "America/Denver",
            "Nashville": "America/Chicago",
            "Detroit": "America/New_York",
            "Oklahoma City": "America/Chicago",
            "Portland": "America/Los_Angeles",
            "Las Vegas": "America/Los_Angeles",
            "Memphis": "America/Chicago",
            "Louisville": "America/New_York",
            "Baltimore": "America/New_York",
        },
        "Brazil": {
            "default": "America/Sao_Paulo",
            "Sao Paulo": "America/Sao_Paulo",
            "Rio de Janeiro": "America/Sao_Paulo",
            "Brasilia": "America/Sao_Paulo",
            "Salvador": "America/Bahia",
            "Fortaleza": "America/Fortaleza",
            "Belo Horizonte": "America/Sao_Paulo",
            "Manaus": "America/Manaus",
            "Curitiba": "America/Sao_Paulo",
            "Recife": "America/Recife",
            "Goiania": "America/Sao_Paulo",
            "Porto Alegre": "America/Sao_Paulo",
            "Belem": "America/Belem",
            "Guarulhos": "America/Sao_Paulo",
            "Campinas": "America/Sao_Paulo",
        },
        "Mexico": {
            "default": "America/Mexico_City",
            "Mexico City": "America/Mexico_City",
            "Guadalajara": "America/Mexico_City",
            "Monterrey": "America/Monterrey",
            "Puebla": "America/Mexico_City",
            "Tijuana": "America/Tijuana",
            "Leon": "America/Mexico_City",
            "Juarez": "America/Ciudad_Juarez",
            "Torreon": "America/Monterrey",
            "Queretaro": "America/Mexico_City",
            "San Luis Potosi": "America/Mexico_City",
            "Zapopan": "America/Mexico_City",
            "Merida": "America/Merida",
            "Mexicali": "America/Tijuana",
            "Aguascalientes": "America/Mexico_City",
        },
        "Canada": {
            "default": "America/Toronto",
            "Toronto": "America/Toronto",
            "Montreal": "America/Toronto",
            "Vancouver": "America/Vancouver",
            "Calgary": "America/Edmonton",
            "Edmonton": "America/Edmonton",
            "Ottawa": "America/Toronto",
            "Winnipeg": "America/Winnipeg",
            "Quebec City": "America/Toronto",
            "Hamilton": "America/Toronto",
            "Kitchener": "America/Toronto",
            "London": "America/Toronto",
            "Victoria": "America/Vancouver",
            "Halifax": "America/Halifax",
            "Oshawa": "America/Toronto",
        },
        "Colombia": {
            "default": "America/Bogota",
            "Bogota": "America/Bogota",
            "Medellin": "America/Bogota",
            "Cali": "America/Bogota",
            "Barranquilla": "America/Bogota",
            "Cartagena": "America/Bogota",
            "Cucuta": "America/Bogota",
            "Bucaramanga": "America/Bogota",
            "Pereira": "America/Bogota",
            "Santa Marta": "America/Bogota",
            "Ibague": "America/Bogota",
            "Pasto": "America/Bogota",
            "Manizales": "America/Bogota",
            "Neiva": "America/Bogota",
            "Villavicencio": "America/Bogota",
        },
        "Ecuador": {
            "default": "America/Guayaquil",
            "Quito": "America/Guayaquil",
            "Guayaquil": "America/Guayaquil",
            "Cuenca": "America/Guayaquil",
            "Santo Domingo": "America/Guayaquil",
            "Machala": "America/Guayaquil",
            "Manta": "America/Guayaquil",
            "Portoviejo": "America/Guayaquil",
            "Ambato": "America/Guayaquil",
            "Riobamba": "America/Guayaquil",
            "Quevedo": "America/Guayaquil",
            "Loja": "America/Guayaquil",
            "Ibarra": "America/Guayaquil",
            "Milagro": "America/Guayaquil",
            "Esmeraldas": "America/Guayaquil",
        },
        "Peru": {
            "default": "America/Lima",
            "Lima": "America/Lima",
            "Arequipa": "America/Lima",
            "Trujillo": "America/Lima",
            "Cusco": "America/Lima",
            "Chiclayo": "America/Lima",
            "Piura": "America/Lima",
            "Iquitos": "America/Lima",
            "Huancayo": "America/Lima",
            "Tacna": "America/Lima",
            "Ica": "America/Lima",
            "Juliaca": "America/Lima",
            "Cajamarca": "America/Lima",
            "Pucallpa": "America/Lima",
            "Chimbote": "America/Lima",
        },
        "Chile": {
            "default": "America/Santiago",
            "Santiago": "America/Santiago",
            "Valparaiso": "America/Santiago",
            "Concepcion": "America/Santiago",
            "La Serena": "America/Santiago",
            "Antofagasta": "America/Santiago",
            "Temuco": "America/Santiago",
            "Rancagua": "America/Santiago",
            "Talca": "America/Santiago",
            "Arica": "America/Santiago",
            "Chillan": "America/Santiago",
            "Iquique": "America/Santiago",
            "Los Angeles": "America/Santiago",
            "Puerto Montt": "America/Santiago",
            "Valdivia": "America/Santiago",
        },
        "Paraguay": {
            "default": "America/Asuncion",
            "Asuncion": "America/Asuncion",
            "Ciudad del Este": "America/Asuncion",
            "San Lorenzo": "America/Asuncion",
            "Lambare": "America/Asuncion",
            "Fernando de la Mora": "America/Asuncion",
            "Limpio": "America/Asuncion",
            "Nemby": "America/Asuncion",
            "Encarnacion": "America/Asuncion",
            "Villa Elisa": "America/Asuncion",
            "Capiatá": "America/Asuncion",
            "Lambarén": "America/Asuncion",
            "Concepción": "America/Asuncion",
            "Coronel Oviedo": "America/Asuncion",
            "Pedro Juan Caballero": "America/Asuncion",
        },
        "Panama": {
            "default": "America/Panama",
            "Panama City": "America/Panama",
            "San Miguelito": "America/Panama",
            "Tocumen": "America/Panama",
            "David": "America/Panama",
            "Arraijan": "America/Panama",
            "Colon": "America/Panama",
            "Las Cumbres": "America/Panama",
            "La Chorrera": "America/Panama",
            "Pacora": "America/Panama",
            "Santiago": "America/Panama",
            "Chitre": "America/Panama",
            "Vista Alegre": "America/Panama",
            "Chilibre": "America/Panama",
            "Cativa": "America/Panama",
        },
        "Uruguay": {
            "default": "America/Montevideo",
            "Montevideo": "America/Montevideo",
            "Salto": "America/Montevideo",
            "Paysandu": "America/Montevideo",
            "Las Piedras": "America/Montevideo",
            "Rivera": "America/Montevideo",
            "Maldonado": "America/Montevideo",
            "Tacuarembo": "America/Montevideo",
            "Melo": "America/Montevideo",
            "Mercedes": "America/Montevideo",
            "Artigas": "America/Montevideo",
            "Minas": "America/Montevideo",
            "San Jose de Mayo": "America/Montevideo",
            "Durazno": "America/Montevideo",
            "Florida": "America/Montevideo",
        }
    }
    
    @classmethod
    def get_timezone_for_location(cls, country: str, city: str) -> str:
        """
        Get timezone for a given country and city combination.
        
        Args:
            country: Country name
            city: City name
            
        Returns:
            Timezone string (e.g., "America/New_York")
        """
        if not country or not city:
            log_warning(f"Missing location data: country='{country}', city='{city}'")
            return cls._get_fallback_timezone()
        
        # Normalize inputs
        country = country.strip()
        city = city.strip()
        
        # Check if country exists in mapping
        if country not in cls.TIMEZONE_MAPPING:
            log_warning(f"Country '{country}' not found in timezone mapping")
            return cls._get_fallback_timezone()
        
        country_mapping = cls.TIMEZONE_MAPPING[country]
        
        # Check if city exists in country mapping
        if city in country_mapping:
            timezone = country_mapping[city]
            log_info(f"Found timezone for {city}, {country}: {timezone}")
            return timezone
        
        # Use default timezone for the country
        if "default" in country_mapping:
            timezone = country_mapping["default"]
            log_info(f"Using default timezone for {country}: {timezone}")
            return timezone
        
        # Fallback to global default
        log_warning(f"No timezone mapping found for {city}, {country}")
        return cls._get_fallback_timezone()
    
    @classmethod
    def get_supported_countries(cls) -> list:
        """
        Get list of supported countries.
        
        Returns:
            List of supported country names
        """
        return list(cls.TIMEZONE_MAPPING.keys())
    
    @classmethod
    def get_supported_cities(cls, country: str) -> list:
        """
        Get list of supported cities for a given country.
        
        Args:
            country: Country name
            
        Returns:
            List of supported city names (excluding 'default')
        """
        if country not in cls.TIMEZONE_MAPPING:
            return []
        
        cities = list(cls.TIMEZONE_MAPPING[country].keys())
        return [city for city in cities if city != "default"]
    
    @classmethod
    def _get_fallback_timezone(cls) -> str:
        """
        Get fallback timezone when no mapping is found.
        
        Returns:
            Fallback timezone string
        """
        log_warning("Using fallback timezone: America/New_York")
        return "America/New_York"
    
    @classmethod
    def validate_timezone(cls, timezone: str) -> bool:
        """
        Validate if a timezone string is valid.
        
        Args:
            timezone: Timezone string to validate
            
        Returns:
            True if timezone is valid, False otherwise
        """
        try:
            import pytz
            pytz.timezone(timezone)
            return True
        except Exception:
            return False

# Convenience functions for easy import
def get_timezone_for_location(country: str, city: str) -> str:
    """Get timezone for a given country and city combination."""
    return TimezoneService.get_timezone_for_location(country, city)

def get_supported_countries() -> list:
    """Get list of supported countries."""
    return TimezoneService.get_supported_countries()

def get_supported_cities(country: str) -> list:
    """Get list of supported cities for a given country."""
    return TimezoneService.get_supported_cities(country)
