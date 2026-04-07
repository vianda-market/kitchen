"""
Mapbox Geocoding API v6 Gateway.

Handles:
- Forward geocoding: address string -> coordinates
- Reverse geocoding: coordinates -> address string
- Structured geocoding: individual address fields -> coordinates

Phase 1: Uses temporary (ephemeral) geocoding (permanent=false, the default).
Phase 2: Will add permanent=true for DB storage.

In DEV_MODE: Uses mock responses from app/mocks/mapbox_geocoding_mocks.json
In PROD_MODE: Makes real API calls. Requires Mapbox access token.
"""

import logging
from typing import Any, Dict, Optional, Tuple

import requests

from app.gateways.base_gateway import BaseGateway, ExternalServiceError

logger = logging.getLogger(__name__)


class MapboxGeocodingGateway(BaseGateway):
    """Gateway for Mapbox Geocoding API v6.

    When access token is set: always uses live API (ignores DEV_MODE).
    When access token is missing and DEV_MODE: uses mock responses.
    """

    GEOCODE_BASE = "https://api.mapbox.com/search/geocode/v6"

    def __init__(self):
        super().__init__()
        from app.config.settings import get_mapbox_access_token
        token = get_mapbox_access_token()
        if token:
            self.dev_mode = False
            logger.info("Mapbox Geocoding Gateway using live API (token configured)")

    @property
    def service_name(self) -> str:
        return "Mapbox Geocoding API"

    def _load_mock_responses(self) -> Dict[str, Any]:
        return self._load_mock_file("mapbox_geocoding_mocks.json")

    def _make_request(self, operation: str, **kwargs) -> Any:
        """
        Make actual API request to Mapbox Geocoding API v6.
        operation: 'geocode' | 'reverse_geocode'
        """
        from app.config.settings import get_mapbox_access_token
        token = get_mapbox_access_token()
        if not token:
            raise ExternalServiceError(
                "Mapbox access token required for geocoding. Set MAPBOX_ACCESS_TOKEN_DEV (or _STAGING/_PROD) in .env."
            )

        if operation == "geocode":
            query = kwargs.get("q", "")
            if not query:
                raise ExternalServiceError("Missing 'q' for geocode")
            params = {
                "q": query,
                "access_token": token,
            }
            if kwargs.get("country"):
                params["country"] = kwargs["country"].upper()
            if kwargs.get("language"):
                params["language"] = kwargs["language"]
            if kwargs.get("limit"):
                params["limit"] = str(kwargs["limit"])
            if kwargs.get("types"):
                params["types"] = kwargs["types"]
            resp = requests.get(
                f"{self.GEOCODE_BASE}/forward",
                params=params,
                timeout=10,
            )

        elif operation == "reverse_geocode":
            longitude = kwargs.get("longitude")
            latitude = kwargs.get("latitude")
            if longitude is None or latitude is None:
                raise ExternalServiceError("Missing 'longitude' and/or 'latitude' for reverse_geocode")
            params = {
                "longitude": str(longitude),
                "latitude": str(latitude),
                "access_token": token,
            }
            if kwargs.get("language"):
                params["language"] = kwargs["language"]
            resp = requests.get(
                f"{self.GEOCODE_BASE}/reverse",
                params=params,
                timeout=10,
            )

        else:
            raise ExternalServiceError(f"Unknown operation: {operation}")

        if not resp.ok:
            try:
                err_body = resp.json() if resp.content else {}
                logger.error(
                    "Mapbox Geocoding API error %s: %s",
                    resp.status_code,
                    err_body.get("message", err_body) or resp.text[:500],
                )
            except Exception:
                logger.error("Mapbox Geocoding API error %s: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        return data

    # -------------------------------------------------------------------------
    # Public methods — signatures match GoogleMapsGateway for provider compat
    # -------------------------------------------------------------------------

    def geocode(self, address: str, country: Optional[str] = None, language: str = "es") -> Tuple[float, float]:
        """
        Convert address string to coordinates.
        Returns (latitude, longitude) — note: GeoJSON is [lng, lat], we swap.
        """
        result = self.call("geocode", q=address, country=country, language=language, limit=1)
        features = result.get("features", [])
        if not features:
            raise ExternalServiceError(f"No geocoding results for address: {address}")
        coords = features[0].get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            raise ExternalServiceError(f"Invalid coordinates in geocoding response for: {address}")
        # GeoJSON: [longitude, latitude] — swap to (latitude, longitude)
        return (coords[1], coords[0])

    def reverse_geocode(self, latitude: float, longitude: float, language: str = "es") -> str:
        """
        Convert coordinates to formatted address string.
        """
        result = self.call("reverse_geocode", latitude=latitude, longitude=longitude, language=language)
        features = result.get("features", [])
        if not features:
            raise ExternalServiceError(f"No reverse geocoding results for ({latitude}, {longitude})")
        return features[0].get("properties", {}).get("full_address", "")

    def geocode_full(self, address: str, country: Optional[str] = None, language: str = "es") -> Dict[str, Any]:
        """
        Full geocoding result with coordinates, mapbox_id, formatted address, and context.
        Used by geolocation_service for richer data.
        """
        result = self.call("geocode", q=address, country=country, language=language, limit=1)
        features = result.get("features", [])
        if not features:
            return {}
        feature = features[0]
        coords = feature.get("geometry", {}).get("coordinates", [])
        props = feature.get("properties", {})
        return {
            "latitude": coords[1] if len(coords) >= 2 else None,
            "longitude": coords[0] if len(coords) >= 2 else None,
            "mapbox_id": props.get("mapbox_id", ""),
            "formatted_address": props.get("full_address", ""),
            "context": props.get("context", {}),
        }

    def get_address_components(self, address: str, country: Optional[str] = None) -> Dict[str, str]:
        """
        Extract structured address components from geocoding result.
        Returns flat dict compatible with Google's component-type keying.
        """
        result = self.call("geocode", q=address, country=country, limit=1)
        features = result.get("features", [])
        if not features:
            return {}
        context = features[0].get("properties", {}).get("context", {})
        components = {}
        if context.get("address", {}).get("address_number"):
            components["street_number"] = context["address"]["address_number"]
        if context.get("street", {}).get("name"):
            components["route"] = context["street"]["name"]
        if context.get("place", {}).get("name"):
            components["locality"] = context["place"]["name"]
        if context.get("region", {}).get("name"):
            components["administrative_area_level_1"] = context["region"]["name"]
        if context.get("postcode", {}).get("name"):
            components["postal_code"] = context["postcode"]["name"]
        if context.get("country", {}).get("name"):
            components["country"] = context["country"]["name"]
        if context.get("neighborhood", {}).get("name"):
            components["neighborhood"] = context["neighborhood"]["name"]
        if context.get("district", {}).get("name"):
            components["sublocality_level_1"] = context["district"]["name"]
        return components

    def validate_address(self, address: str) -> bool:
        """Basic validation: try to geocode and return True if results found."""
        try:
            self.geocode(address)
            return True
        except (ExternalServiceError, Exception):
            return False


# Singleton
_mapbox_geocoding_gateway: Optional[MapboxGeocodingGateway] = None


def get_mapbox_geocoding_gateway() -> MapboxGeocodingGateway:
    """Get the Mapbox Geocoding Gateway singleton instance."""
    global _mapbox_geocoding_gateway
    if _mapbox_geocoding_gateway is None:
        _mapbox_geocoding_gateway = MapboxGeocodingGateway()
    return _mapbox_geocoding_gateway
