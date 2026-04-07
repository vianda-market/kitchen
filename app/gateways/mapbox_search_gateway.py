"""
Mapbox Search Box API Gateway.

Handles:
- Search Box API – Suggest: address suggestions from partial input
- Search Box API – Retrieve: full address + coordinates for a mapbox_id

In DEV_MODE: Uses mock responses from app/mocks/mapbox_search_mocks.json
In PROD_MODE: Makes real API calls. Requires Mapbox access token.

Session billing: Mapbox bills per session (one or more suggest calls + one retrieve call
sharing the same session_token UUIDv4). Max 50 suggest calls per session; session expires
after 180 seconds of inactivity.
"""

import logging
from typing import Any, Dict, Optional

import requests

from app.gateways.base_gateway import BaseGateway, ExternalServiceError

logger = logging.getLogger(__name__)


class MapboxSearchGateway(BaseGateway):
    """Gateway for Mapbox Search Box API (suggest + retrieve).

    When access token is set: always uses live API (ignores DEV_MODE).
    When access token is missing and DEV_MODE: uses mock responses.
    """

    SEARCH_BASE = "https://api.mapbox.com/search/searchbox/v1"

    def __init__(self):
        super().__init__()
        from app.config.settings import get_mapbox_access_token
        token = get_mapbox_access_token()
        if token:
            self.dev_mode = False
            logger.info("Mapbox Search Gateway using live API (token configured)")

    @property
    def service_name(self) -> str:
        return "Mapbox Search Box API"

    def _load_mock_responses(self) -> Dict[str, Any]:
        return self._load_mock_file("mapbox_search_mocks.json")

    def _get_mock_response(self, operation: str, **kwargs) -> Any:
        """Override to support retrieve keyed by mapbox_id."""
        if not self._mock_data:
            raise ExternalServiceError("Mock data not loaded")
        if operation == "retrieve":
            data = self._mock_data.get("retrieve")
            if isinstance(data, dict):
                mapbox_id = kwargs.get("mapbox_id", "")
                if mapbox_id in data:
                    logger.info(f"Returning mock response for {self.service_name}.{operation} (mapbox_id={mapbox_id})")
                    return data[mapbox_id]
                first_key = next((k for k in data if isinstance(data.get(k), dict)), None)
                if first_key:
                    logger.info(f"Returning mock response for {self.service_name}.{operation} (fallback)")
                    return data[first_key]
            raise ExternalServiceError(f"Mock response not configured for operation '{operation}' with mapbox_id")
        if operation not in self._mock_data:
            raise ExternalServiceError(
                f"Mock response not configured for operation '{operation}'. "
                f"Available: {list(self._mock_data.keys())}"
            )
        logger.info(f"Returning mock response for {self.service_name}.{operation}")
        return self._mock_data[operation]

    def _make_request(self, operation: str, **kwargs) -> Any:
        """
        Make actual API request to Mapbox Search Box API.
        operation: 'suggest' | 'retrieve'
        """
        from app.config.settings import get_mapbox_access_token
        token = get_mapbox_access_token()
        if not token:
            raise ExternalServiceError(
                "Mapbox access token required for address search. Set MAPBOX_ACCESS_TOKEN_DEV (or _STAGING/_PROD) in .env."
            )

        if operation == "suggest":
            query = kwargs.get("q", "")
            if not query:
                raise ExternalServiceError("Missing 'q' for suggest")
            params = {
                "q": query,
                "access_token": token,
                "types": "address",
            }
            if kwargs.get("session_token"):
                params["session_token"] = kwargs["session_token"]
            if kwargs.get("country"):
                params["country"] = kwargs["country"].upper()
            if kwargs.get("language"):
                params["language"] = kwargs["language"]
            if kwargs.get("limit"):
                params["limit"] = str(kwargs["limit"])
            resp = requests.get(
                f"{self.SEARCH_BASE}/suggest",
                params=params,
                timeout=10,
            )

        elif operation == "retrieve":
            mapbox_id = kwargs.get("mapbox_id")
            if not mapbox_id:
                raise ExternalServiceError("Missing 'mapbox_id' for retrieve")
            params = {"access_token": token}
            if kwargs.get("session_token"):
                params["session_token"] = kwargs["session_token"]
            resp = requests.get(
                f"{self.SEARCH_BASE}/retrieve/{mapbox_id}",
                params=params,
                timeout=10,
            )

        else:
            raise ExternalServiceError(f"Unknown operation: {operation}")

        if not resp.ok:
            try:
                err_body = resp.json() if resp.content else {}
                logger.error(
                    "Mapbox Search API error %s: %s",
                    resp.status_code,
                    err_body.get("message", err_body) or resp.text[:500],
                )
            except Exception:
                logger.error("Mapbox Search API error %s: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        return data

    def suggest(
        self,
        query: str,
        country: Optional[str] = None,
        language: str = "es",
        session_token: Optional[str] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Call Mapbox Search Box Suggest.
        Returns raw API response with 'suggestions' list.
        """
        return self.call(
            "suggest",
            q=query,
            country=country,
            language=language,
            session_token=session_token,
            limit=limit,
        )

    def retrieve(self, mapbox_id: str, session_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Call Mapbox Search Box Retrieve for full address + coordinates.
        Returns the first Feature from the GeoJSON FeatureCollection.
        """
        result = self.call("retrieve", mapbox_id=mapbox_id, session_token=session_token)
        # In live mode, retrieve returns a FeatureCollection; extract first feature
        if "features" in result and result["features"]:
            return result["features"][0]
        # Mock data may already be a single Feature
        if result.get("type") == "Feature":
            return result
        return result


# Singleton
_mapbox_search_gateway: Optional[MapboxSearchGateway] = None


def get_mapbox_search_gateway() -> MapboxSearchGateway:
    """Get the Mapbox Search Gateway singleton instance."""
    global _mapbox_search_gateway
    if _mapbox_search_gateway is None:
        _mapbox_search_gateway = MapboxSearchGateway()
    return _mapbox_search_gateway
