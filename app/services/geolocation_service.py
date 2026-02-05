"""
Geolocation Service - Google Maps API Integration

This service provides geocoding (address → coordinates) and reverse geocoding 
(coordinates → address) using Google Maps Geocoding API.

Setup:
1. Get API key from Google Cloud Console (see docs/ENV_SETUP.md)
2. Add to .env: GOOGLE_MAPS_API_KEY=your_api_key_here
3. Enable Geocoding API in Google Cloud Console

Pricing:
- Free tier: $200 credit/month (~28,500 requests)
- After free tier: $5 per 1,000 requests

API Documentation:
https://developers.google.com/maps/documentation/geocoding/overview
"""

import os
import requests
from typing import Optional, Dict, Any, Tuple
from math import radians, cos, sin, asin, sqrt

from app.utils.log import log_info, log_warning, log_error


class GeolocationService:
    """
    Service for geocoding and distance calculations using Google Maps API.
    """
    
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_MAPS_API_KEY', '')
        self.base_url = "https://maps.googleapis.com/maps/api/geocode/json"
        self.timeout = 5  # seconds
        
        if not self.api_key:
            log_warning("Google Maps API key not configured. Set GOOGLE_MAPS_API_KEY in .env")
    
    def is_configured(self) -> bool:
        """Check if Google Maps API key is configured."""
        return bool(self.api_key)
    
    def geocode_address(
        self,
        address: str,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        postal_code: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Convert address to geographic coordinates using Google Maps API.
        
        Args:
            address: Street address
            city: City name (optional, improves accuracy)
            state: State/province (optional)
            country: Country code or name (optional, highly recommended)
            postal_code: Postal/ZIP code (optional)
        
        Returns:
            dict with:
                - latitude: float
                - longitude: float
                - formatted_address: str (Google's formatted version)
                - place_id: str (Google's unique place identifier)
                - address_components: dict (structured address data)
            or None if geocoding fails
        
        Example:
            result = geocode_address(
                address="1600 Amphitheatre Parkway",
                city="Mountain View",
                state="CA",
                country="USA"
            )
            # Returns: {'latitude': 37.423, 'longitude': -122.084, ...}
        """
        if not self.is_configured():
            log_error("Cannot geocode: Google Maps API key not configured")
            return None
        
        # Build full address string
        address_parts = [address]
        if city:
            address_parts.append(city)
        if state:
            address_parts.append(state)
        if postal_code:
            address_parts.append(postal_code)
        if country:
            address_parts.append(country)
        
        full_address = ", ".join(address_parts)
        
        try:
            # Call Google Maps Geocoding API
            params = {
                'address': full_address,
                'key': self.api_key
            }
            
            log_info(f"Geocoding address: {full_address}")
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Check API response status
            if data['status'] == 'OK' and data['results']:
                result = data['results'][0]  # Get first (best) result
                
                location = result['geometry']['location']
                
                geocode_result = {
                    'latitude': location['lat'],
                    'longitude': location['lng'],
                    'formatted_address': result['formatted_address'],
                    'place_id': result['place_id'],
                    'address_components': result.get('address_components', []),
                    'location_type': result['geometry'].get('location_type', 'APPROXIMATE')
                }
                
                log_info(f"Geocoded successfully: {geocode_result['formatted_address']} → "
                        f"({geocode_result['latitude']}, {geocode_result['longitude']})")
                
                return geocode_result
            
            elif data['status'] == 'ZERO_RESULTS':
                log_warning(f"No results found for address: {full_address}")
                return None
            
            elif data['status'] == 'OVER_QUERY_LIMIT':
                log_error("Google Maps API quota exceeded")
                return None
            
            elif data['status'] == 'REQUEST_DENIED':
                log_error(f"Google Maps API request denied: {data.get('error_message', 'No error message')}")
                return None
            
            elif data['status'] == 'INVALID_REQUEST':
                log_error(f"Invalid geocoding request: {full_address}")
                return None
            
            else:
                log_error(f"Geocoding failed with status: {data['status']}")
                return None
        
        except requests.exceptions.Timeout:
            log_error(f"Geocoding request timed out for: {full_address}")
            return None
        
        except requests.exceptions.RequestException as e:
            log_error(f"Error calling Google Maps API: {str(e)}")
            return None
        
        except Exception as e:
            log_error(f"Unexpected error geocoding address: {str(e)}")
            return None
    
    def reverse_geocode(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[Dict[str, Any]]:
        """
        Convert geographic coordinates to address using Google Maps API.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
        
        Returns:
            dict with:
                - formatted_address: str
                - address_components: dict (street, city, state, country, etc.)
                - place_id: str
            or None if reverse geocoding fails
        
        Example:
            result = reverse_geocode(37.423, -122.084)
            # Returns: {'formatted_address': '1600 Amphitheatre Parkway, ...', ...}
        """
        if not self.is_configured():
            log_error("Cannot reverse geocode: Google Maps API key not configured")
            return None
        
        try:
            params = {
                'latlng': f"{latitude},{longitude}",
                'key': self.api_key
            }
            
            log_info(f"Reverse geocoding coordinates: ({latitude}, {longitude})")
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                result = data['results'][0]
                
                reverse_result = {
                    'formatted_address': result['formatted_address'],
                    'address_components': result.get('address_components', []),
                    'place_id': result['place_id']
                }
                
                log_info(f"Reverse geocoded successfully: ({latitude}, {longitude}) → "
                        f"{reverse_result['formatted_address']}")
                
                return reverse_result
            
            else:
                log_warning(f"Reverse geocoding failed with status: {data['status']}")
                return None
        
        except Exception as e:
            log_error(f"Error reverse geocoding: {str(e)}")
            return None
    
    def calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        unit: str = 'km'
    ) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.
        
        Args:
            lat1: Latitude of first point
            lon1: Longitude of first point
            lat2: Latitude of second point
            lon2: Longitude of second point
            unit: 'km' for kilometers or 'mi' for miles
        
        Returns:
            float: Distance in specified unit
        
        Example:
            distance = calculate_distance(37.423, -122.084, 37.774, -122.419)
            # Returns: ~49.08 km (San Francisco to Mountain View)
        """
        # Convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        
        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        # Radius of earth in kilometers
        r_km = 6371
        
        distance_km = c * r_km
        
        if unit == 'mi':
            return distance_km * 0.621371  # Convert to miles
        
        return distance_km
    
    def is_within_radius(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        radius_km: float
    ) -> bool:
        """
        Check if two points are within a specified radius.
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            radius_km: Maximum distance in kilometers
        
        Returns:
            bool: True if within radius, False otherwise
        
        Example:
            is_close = is_within_radius(37.423, -122.084, 37.774, -122.419, 50)
            # Returns: True (San Francisco and Mountain View are ~49 km apart)
        """
        distance = self.calculate_distance(lat1, lon1, lat2, lon2)
        return distance <= radius_km
    
    def extract_address_component(
        self,
        address_components: list,
        component_type: str
    ) -> Optional[str]:
        """
        Extract specific component from Google Maps address_components.
        
        Args:
            address_components: List from Google Maps API response
            component_type: Type to extract (e.g., 'locality', 'country', 'postal_code')
        
        Returns:
            str: Component value or None if not found
        
        Common types:
            - 'street_number': Street number
            - 'route': Street name
            - 'locality': City
            - 'administrative_area_level_1': State/province
            - 'country': Country
            - 'postal_code': Postal/ZIP code
        
        Example:
            city = extract_address_component(address_components, 'locality')
            # Returns: "Mountain View"
        """
        for component in address_components:
            if component_type in component.get('types', []):
                return component.get('long_name') or component.get('short_name')
        
        return None


# Singleton instance
geolocation_service = GeolocationService()


# Legacy function for backwards compatibility
def call_geocode_api(full_address: str) -> dict:
    """
    Legacy function for backwards compatibility.
    Use geolocation_service.geocode_address() instead.
    """
    log_warning("call_geocode_api() is deprecated. Use geolocation_service.geocode_address()")
    
    result = geolocation_service.geocode_address(full_address)
    
    if result:
        return {
            'lat': result['latitude'],
            'lng': result['longitude'],
            'formatted_address': result['formatted_address']
        }
    
    return {}


def get_timezone_from_location(country: str, city: str) -> str:
    """
    Map country and city to a timezone string.
    Returns a default timezone if no mapping is found.
    
    This function uses the centralized TimezoneService for consistency.
    """
    from app.services.timezone_service import get_timezone_for_location
    return get_timezone_for_location(country, city)
