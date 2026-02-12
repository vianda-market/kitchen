"""
Google Maps API Gateway

Handles all interactions with Google Maps Geocoding API:
- Address to coordinates (geocoding)
- Coordinates to address (reverse geocoding)
- Distance calculations
- Address component extraction

In DEV_MODE: Uses mock responses from app/mocks/google_maps_responses.json
In PROD_MODE: Makes real API calls and logs for cost tracking
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.gateways.base_gateway import BaseGateway, ExternalServiceError

logger = logging.getLogger(__name__)


class GoogleMapsGateway(BaseGateway):
    """Gateway for Google Maps Geocoding API"""
    
    BASE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    
    @property
    def service_name(self) -> str:
        return "Google Maps Geocoding API"
    
    def _load_mock_responses(self) -> Dict[str, Any]:
        """Load mock responses from JSON file"""
        return self._load_mock_file("google_maps_responses.json")
    
    def _make_request(self, operation: str, **kwargs) -> Any:
        """
        Make actual API request to Google Maps.
        
        Args:
            operation: 'geocode' or 'reverse_geocode'
            **kwargs: address (str) or latlng (str)
            
        Returns:
            Parsed API response
            
        Raises:
            ExternalServiceError: If request fails
        """
        if not self.settings.GOOGLE_MAPS_API_KEY:
            raise ExternalServiceError(
                "GOOGLE_MAPS_API_KEY not configured. Set it in .env file."
            )
        
        params = {"key": self.settings.GOOGLE_MAPS_API_KEY}
        
        if operation == "geocode":
            if "address" not in kwargs:
                raise ExternalServiceError("Missing 'address' parameter for geocoding")
            params["address"] = kwargs["address"]
            
        elif operation == "reverse_geocode":
            if "latlng" not in kwargs:
                raise ExternalServiceError("Missing 'latlng' parameter for reverse geocoding")
            params["latlng"] = kwargs["latlng"]
            
        else:
            raise ExternalServiceError(f"Unknown operation: {operation}")
        
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "OK":
                error_msg = data.get("error_message", data.get("status", "Unknown error"))
                raise ExternalServiceError(f"Google Maps API error: {error_msg}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            raise ExternalServiceError(f"HTTP request failed: {str(e)}") from e
    
    def geocode(self, address: str) -> Tuple[float, float]:
        """
        Convert address to coordinates.
        
        Args:
            address: Full address string
            
        Returns:
            Tuple of (latitude, longitude)
            
        Raises:
            ExternalServiceError: If geocoding fails
        """
        response = self.call("geocode", address=address)
        
        if not response.get("results"):
            raise ExternalServiceError(f"No results found for address: {address}")
        
        location = response["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    
    def reverse_geocode(self, latitude: float, longitude: float) -> str:
        """
        Convert coordinates to address.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Formatted address string
            
        Raises:
            ExternalServiceError: If reverse geocoding fails
        """
        latlng = f"{latitude},{longitude}"
        response = self.call("reverse_geocode", latlng=latlng)
        
        if not response.get("results"):
            raise ExternalServiceError(
                f"No address found for coordinates: {latitude}, {longitude}"
            )
        
        return response["results"][0]["formatted_address"]
    
    def get_address_components(
        self,
        address: str
    ) -> Dict[str, str]:
        """
        Extract address components (country, city, postal code, etc.).
        
        Args:
            address: Full address string
            
        Returns:
            Dictionary of address components:
            {
                'street_number': '123',
                'route': 'Main St',
                'locality': 'City Name',
                'administrative_area_level_1': 'State',
                'country': 'Country',
                'postal_code': '12345',
                ...
            }
            
        Raises:
            ExternalServiceError: If geocoding fails
        """
        response = self.call("geocode", address=address)
        
        if not response.get("results"):
            raise ExternalServiceError(f"No results found for address: {address}")
        
        components = {}
        for component in response["results"][0]["address_components"]:
            # Use the first type as the key
            comp_type = component["types"][0]
            components[comp_type] = component["long_name"]
        
        return components
    
    def validate_address(self, address: str) -> bool:
        """
        Check if an address can be geocoded (basic validation).
        
        Args:
            address: Full address string
            
        Returns:
            True if address is valid, False otherwise
        """
        try:
            response = self.call("geocode", address=address)
            return bool(response.get("results"))
        except ExternalServiceError:
            return False


# Singleton instance
_google_maps_gateway: Optional[GoogleMapsGateway] = None


def get_google_maps_gateway() -> GoogleMapsGateway:
    """
    Get the Google Maps Gateway singleton instance.
    
    Returns:
        GoogleMapsGateway instance
    """
    global _google_maps_gateway
    if _google_maps_gateway is None:
        _google_maps_gateway = GoogleMapsGateway()
    return _google_maps_gateway
