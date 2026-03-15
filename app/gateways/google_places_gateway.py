"""
Google Places API Gateway.

Handles:
- Places API (New) – Autocomplete: address suggestions from partial input
- Places API (New) – Place Details: structured address components for a place ID

In DEV_MODE: Uses mock responses from app/mocks/address_autocomplete_mocks.json
In PROD_MODE: Makes real API calls. Requires Places API enabled on the API key.
"""

import logging
from typing import Any, Dict, List, Optional

import requests

from app.gateways.base_gateway import BaseGateway, ExternalServiceError

logger = logging.getLogger(__name__)

# ISO 3166-1 alpha-2 to alpha-3 map (used only when mapping from external 2-letter to internal; API uses alpha-2 only)
# Places API uses alpha-2 in includedRegionCodes; we store and return alpha-2 everywhere
_COUNTRY_ALPHA2_TO_ALPHA3: Dict[str, str] = {
    "AR": "ARG", "US": "USA", "BR": "BRA", "MX": "MEX", "CA": "CAN",
    "CL": "CHL", "CO": "COL", "PE": "PER", "UY": "URY", "PY": "PRY",
    "EC": "ECU", "BO": "BOL", "VE": "VEN", "GB": "GBR", "ES": "ESP",
    "FR": "FRA", "DE": "DEU", "IT": "ITA", "JP": "JPN", "AU": "AUS",
}

# Normalized country name (lowercase) -> alpha-2 for suggest when user types name
_COUNTRY_NAME_TO_ALPHA2: Dict[str, str] = {
    "argentina": "AR", "united states": "US", "usa": "US", "united states of america": "US",
    "brazil": "BR", "brasil": "BR", "mexico": "MX", "méxico": "MX", "canada": "CA",
    "chile": "CL", "colombia": "CO", "peru": "PE", "perú": "PE",
    "uruguay": "UY", "paraguay": "PY", "ecuador": "EC", "bolivia": "BO",
    "venezuela": "VE", "venezuela (bolivarian republic of)": "VE",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "england": "GB",
    "spain": "ES", "españa": "ES", "france": "FR", "germany": "DE", "deutschland": "DE",
    "italy": "IT", "italia": "IT", "japan": "JP", "australia": "AU",
}


def country_alpha2_to_alpha3(alpha2: str) -> str:
    """Convert ISO 3166-1 alpha-2 to alpha-3. Returns upper input if not in map."""
    if not alpha2 or len(alpha2) != 2:
        return (alpha2 or "").upper()
    return _COUNTRY_ALPHA2_TO_ALPHA3.get(alpha2.upper(), alpha2.upper())


def country_alpha3_to_alpha2(alpha3: str) -> str:
    """Convert alpha-3 to alpha-2 for Google API (includedRegionCodes)."""
    rev = {v: k for k, v in _COUNTRY_ALPHA2_TO_ALPHA3.items()}
    if alpha3 and len(alpha3) == 3:
        return rev.get(alpha3.upper(), alpha3.upper()[:2])
    return (alpha3 or "")[:2].upper()


def country_name_to_alpha2(name: str) -> Optional[str]:
    """Resolve country name (e.g. 'Argentina') to ISO 3166-1 alpha-2. Returns None if not found."""
    if not name or not name.strip():
        return None
    key = name.strip().lower()
    return _COUNTRY_NAME_TO_ALPHA2.get(key)


class GooglePlacesGateway(BaseGateway):
    """Gateway for Google Places API (New).

    When API key is set: always uses live API (ignores DEV_MODE).
    When API key is missing: raises clear error (no mocks for address autocomplete).
    """

    PLACES_BASE = "https://places.googleapis.com/v1"

    def __init__(self):
        super().__init__()
        from app.config.settings import get_google_api_key
        api_key = get_google_api_key()
        if api_key:
            self.dev_mode = False
            logger.info(f"Google Places Gateway using live API (key configured)")

    @property
    def service_name(self) -> str:
        return "Google Places API"

    def _load_mock_responses(self) -> Dict[str, Any]:
        """Load mock responses from JSON file."""
        return self._load_mock_file("address_autocomplete_mocks.json")

    def _get_mock_response(self, operation: str, **kwargs) -> Any:
        """Override to support place_details keyed by place_id."""
        if not self._mock_data:
            raise ExternalServiceError("Mock data not loaded")
        if operation == "place_details":
            data = self._mock_data.get("place_details")
            if isinstance(data, dict):
                place_id = kwargs.get("place_id", "")
                # First key that is not a place_id is ignored; use place_id to look up
                if place_id in data:
                    out = data[place_id]
                    logger.info(f"🎭 Returning mock response for {self.service_name}.{operation} (place_id={place_id})")
                    return out
                # Fallback: use first available place details
                first_key = next((k for k in data if isinstance(data.get(k), dict)), None)
                if first_key:
                    out = data[first_key]
                    logger.info(f"🎭 Returning mock response for {self.service_name}.{operation} (fallback)")
                    return out
            raise ExternalServiceError(f"Mock response not configured for operation '{operation}' with place_id")
        if operation not in self._mock_data:
            raise ExternalServiceError(
                f"Mock response not configured for operation '{operation}'. "
                f"Available: {list(self._mock_data.keys())}"
            )
        logger.info(f"🎭 Returning mock response for {self.service_name}.{operation}")
        return self._mock_data[operation]

    def _make_request(self, operation: str, **kwargs) -> Any:
        """
        Make actual API request to Google Places API.
        operation: 'places_autocomplete' | 'place_details'
        """
        from app.config.settings import get_google_api_key
        api_key = get_google_api_key()
        if not api_key:
            raise ExternalServiceError(
                "Google API key required for address autocomplete. Set GOOGLE_API_KEY_DEV (or _STAGING/_PROD) in .env and enable Places API."
            )
        headers = {"X-Goog-Api-Key": api_key, "Content-Type": "application/json"}

        if operation == "places_autocomplete":
            input_text = kwargs.get("input", "") or kwargs.get("q", "")
            if not input_text:
                raise ExternalServiceError("Missing 'input' or 'q' for places_autocomplete")
            region_codes = kwargs.get("includedRegionCodes")
            location_restriction = kwargs.get("locationRestriction")
            body = {"input": input_text}
            if region_codes:
                body["includedRegionCodes"] = region_codes
            if location_restriction:
                body["locationRestriction"] = location_restriction
            resp = requests.post(
                f"{self.PLACES_BASE}/places:autocomplete",
                json=body,
                headers=headers,
                timeout=10,
            )
        elif operation == "place_details":
            place_id = kwargs.get("place_id")
            if not place_id:
                raise ExternalServiceError("Missing 'place_id' for place_details")
            resp = requests.get(
                f"{self.PLACES_BASE}/places/{place_id}",
                params={"fields": "id,formattedAddress,addressComponents,location,viewport"},
                headers=headers,
                timeout=10,
            )
        else:
            raise ExternalServiceError(f"Unknown operation: {operation}")

        if not resp.ok:
            try:
                err_body = resp.json() if resp.content else {}
                logger.error(
                    "Google Places API error %s: %s",
                    resp.status_code,
                    err_body.get("error", {}).get("message", err_body) or resp.text[:500],
                )
            except Exception:
                logger.error("Google Places API error %s: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        data = resp.json() if resp.content else {}

        return data

    def places_autocomplete(
        self,
        input_text: str,
        included_region_codes: Optional[List[str]] = None,
        location_restriction: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Call Places API (New) Autocomplete.
        included_region_codes: optional list of ISO 3166-1 alpha-2 codes (e.g. ["ar", "us"]).
        location_restriction: optional rectangle {rectangle: {low: {latitude, longitude}, high: {latitude, longitude}}}.
        Returns raw API response with 'suggestions' (list of placePrediction with placeId and text).
        """
        kwargs = {"input": input_text, "q": input_text}
        if included_region_codes:
            kwargs["includedRegionCodes"] = [c[:2].upper() for c in included_region_codes]
        if location_restriction:
            kwargs["locationRestriction"] = location_restriction
        return self.call("places_autocomplete", **kwargs)

    def place_details(self, place_id: str) -> Dict[str, Any]:
        """
        Call Places API (New) Place Details for address components.
        Returns dict with id, formattedAddress, addressComponents, location, viewport.
        """
        return self.call("place_details", place_id=place_id)


# Singleton
_google_places_gateway: Optional[GooglePlacesGateway] = None


def get_google_places_gateway() -> GooglePlacesGateway:
    """Get the Google Places Gateway singleton instance."""
    global _google_places_gateway
    if _google_places_gateway is None:
        _google_places_gateway = GooglePlacesGateway()
    return _google_places_gateway
