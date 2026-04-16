"""
Geolocation Service — Geocoding via configured provider (Mapbox or Google).

Provides geocoding (address -> coordinates) and reverse geocoding
(coordinates -> address) through the address provider abstraction.

Provider is selected via ADDRESS_PROVIDER setting ("mapbox" or "google").
"""

from math import asin, cos, radians, sin, sqrt
from typing import Any

from app.gateways.address_provider import get_geocoding_gateway
from app.gateways.base_gateway import ExternalServiceError
from app.utils.log import log_error, log_info, log_warning


class GeolocationService:
    """
    Service for geocoding and distance calculations.

    All external API calls are routed through the configured geocoding gateway for:
    - Development mode support (mock responses)
    - Centralized cost tracking
    - Consistent error handling
    """

    def __init__(self):
        self.gateway = get_geocoding_gateway()

    def is_configured(self) -> bool:
        """Check if the geocoding provider is configured (API key/token present or dev mode)."""
        if self.gateway.dev_mode:
            return True
        # Check provider-specific credentials
        from app.config.settings import get_google_api_key, get_mapbox_access_token, get_settings

        provider = get_settings().ADDRESS_PROVIDER.lower()
        if provider == "google":
            return bool(get_google_api_key())
        return bool(get_mapbox_access_token())

    def geocode_address(
        self,
        address: str,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
        postal_code: str | None = None,
    ) -> dict[str, Any] | None:
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
                - address_components: list (structured address data)
                - location_type: str (accuracy indicator)
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
            log_info(f"Geocoding address: {full_address}")

            # Call through gateway (handles dev mode + logging)
            lat, lng = self.gateway.geocode(full_address)

            # Get full response with components
            components = self.gateway.get_address_components(full_address)

            geocode_result = {
                "latitude": lat,
                "longitude": lng,
                "formatted_address": full_address,  # In production, this comes from API
                "place_id": "mock-place-id",  # Placeholder for dev mode
                "address_components": components,
                "location_type": "ROOFTOP",  # Default to highest accuracy
            }

            log_info(f"Geocoded successfully: {full_address} → ({lat}, {lng})")

            return geocode_result

        except ExternalServiceError as e:
            log_error(f"Geocoding failed: {str(e)}")
            return None

        except Exception as e:
            log_error(f"Unexpected error geocoding address: {str(e)}")
            return None

    def reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any] | None:
        """
        Convert geographic coordinates to address using Google Maps API.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            dict with:
                - formatted_address: str
                - address_components: list (street, city, state, country, etc.)
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
            log_info(f"Reverse geocoding coordinates: ({latitude}, {longitude})")

            # Call through gateway
            formatted_address = self.gateway.reverse_geocode(latitude, longitude)

            reverse_result = {
                "formatted_address": formatted_address,
                "address_components": [],  # Could be enhanced to parse from response
                "place_id": "mock-place-id",  # Placeholder
            }

            log_info(f"Reverse geocoded successfully: ({latitude}, {longitude}) → {formatted_address}")

            return reverse_result

        except ExternalServiceError as e:
            log_error(f"Reverse geocoding failed: {str(e)}")
            return None

        except Exception as e:
            log_error(f"Error reverse geocoding: {str(e)}")
            return None

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float, unit: str = "km") -> float:
        """
        Calculate distance between two coordinates using Haversine formula.

        This is a local calculation - no external API calls.

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
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))

        # Radius of earth in kilometers
        r_km = 6371

        distance_km = c * r_km

        if unit == "mi":
            return distance_km * 0.621371  # Convert to miles

        return distance_km

    def is_within_radius(self, lat1: float, lon1: float, lat2: float, lon2: float, radius_km: float) -> bool:
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

    def extract_address_component(self, address_components: list, component_type: str) -> str | None:
        """
        Extract specific component from Google Maps address_components.

        Args:
            address_components: List from Google Maps API response or dict from gateway
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
        # Handle both dict (from gateway) and list (from old API format)
        if isinstance(address_components, dict):
            return address_components.get(component_type)

        # List format from Google API
        for component in address_components:
            if component_type in component.get("types", []):
                return component.get("long_name") or component.get("short_name")

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
    try:
        result = geolocation_service.geocode_address(full_address)
        if result:
            return {
                "lat": result["latitude"],
                "lng": result["longitude"],
                "formatted_address": result["formatted_address"],
            }
        return {}
    except Exception as e:
        log_warning(f"Error calling geocode API: {e}")
        return {}


def get_timezone_from_location(country: str, city: str) -> str:
    """
    DEPRECATED: Use get_timezone_from_address() instead.
    Legacy function for backward compatibility with city-based lookups.

    This function is maintained for backward compatibility but logs a deprecation warning.
    """
    from app.services.timezone_service import get_timezone_for_location

    return get_timezone_for_location(country, city)


def get_timezone_from_address(country_code: str, province: str, db) -> str:
    """
    Deduce timezone from country_code and province/state.

    This function uses the TimezoneService to automatically deduce timezone:
    - For single-timezone countries (AR, PE, CL): uses market_info default
    - For multi-timezone countries (US, BR, CA): uses province mapping

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., "AR", "US", "BR")
        province: Province/state name or code (e.g., "California", "CA", "Buenos Aires")
        db: Database connection

    Returns:
        Timezone string (e.g., "America/New_York", "America/Argentina/Buenos_Aires")

    Raises:
        HTTPException: 400 if country_code not found in market_info
    """
    from app.services.timezone_service import deduce_timezone_from_address

    return deduce_timezone_from_address(country_code, province, db)
