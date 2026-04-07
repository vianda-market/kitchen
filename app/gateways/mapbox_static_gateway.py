"""
Mapbox Static Images API Gateway.

Generates static map images with restaurant pin overlays.
Calls Mapbox Static Images API and returns raw PNG bytes.

In DEV_MODE: Returns a placeholder PNG from app/mocks/mapbox_static_mocks.json
In PROD_MODE: Makes real API calls. Requires Mapbox access token.
"""

import base64
import logging
from typing import Any, Dict, List, Optional

import requests

from app.gateways.base_gateway import BaseGateway, ExternalServiceError

logger = logging.getLogger(__name__)

# Maximum URL length for Mapbox Static Images API
MAX_URL_LENGTH = 8192


class MapboxStaticGateway(BaseGateway):
    """Gateway for Mapbox Static Images API.

    Generates static map PNGs with pin overlays for restaurant locations.
    When access token is set: always uses live API (ignores DEV_MODE).
    When access token is missing and DEV_MODE: returns placeholder PNG.
    """

    STATIC_BASE = "https://api.mapbox.com/styles/v1"

    def __init__(self):
        super().__init__()
        from app.config.settings import get_mapbox_access_token
        token = get_mapbox_access_token()
        if token:
            self.dev_mode = False
            logger.info("Mapbox Static Images Gateway using live API (token configured)")

    @property
    def service_name(self) -> str:
        return "Mapbox Static Images API"

    def _load_mock_responses(self) -> Dict[str, Any]:
        return self._load_mock_file("mapbox_static_mocks.json")

    def _get_mock_response(self, operation: str, **kwargs) -> Any:
        """Return placeholder PNG bytes for dev mode."""
        if not self._mock_data:
            raise ExternalServiceError("Mock data not loaded")
        png_b64 = self._mock_data.get("placeholder_png", "")
        if png_b64:
            logger.info(f"Returning mock response for {self.service_name}.{operation}")
            return base64.b64decode(png_b64)
        raise ExternalServiceError("Mock placeholder PNG not configured")

    def _make_request(self, operation: str, **kwargs) -> Any:
        """
        Make actual API request to Mapbox Static Images API.
        operation: 'generate'
        Returns raw PNG bytes.
        """
        from app.config.settings import get_mapbox_access_token
        token = get_mapbox_access_token()
        if not token:
            raise ExternalServiceError(
                "Mapbox access token required for static images. Set MAPBOX_ACCESS_TOKEN_DEV (or _STAGING/_PROD) in .env."
            )

        if operation != "generate":
            raise ExternalServiceError(f"Unknown operation: {operation}")

        url = kwargs.get("url", "")
        if not url:
            raise ExternalServiceError("Missing 'url' for generate operation")

        resp = requests.get(url, timeout=15)

        if not resp.ok:
            try:
                err_body = resp.json() if resp.content else {}
                logger.error(
                    "Mapbox Static Images API error %s: %s",
                    resp.status_code,
                    err_body.get("message", err_body) or resp.text[:500],
                )
            except Exception:
                logger.error("Mapbox Static Images API error %s: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        return resp.content

    def generate_static_map(
        self,
        style_id: str,
        center_lat: float,
        center_lng: float,
        zoom: int,
        width: int,
        height: int,
        markers: List[Dict[str, Any]],
        retina: bool = True,
        pin_color: str = "4a7c59",
    ) -> bytes:
        """
        Generate a static map image with restaurant pin overlays.

        Args:
            style_id: Mapbox style (e.g. 'mapbox/light-v11')
            center_lat, center_lng: Map center coordinates
            zoom: Zoom level (0-22)
            width, height: Image dimensions in CSS pixels (max 1280 each)
            markers: List of dicts with 'name', 'lat', 'lng' keys
            retina: If True, generate @2x image
            pin_color: Hex color for pins (without #)

        Returns:
            Raw PNG bytes of the generated map image
        """
        from app.config.settings import get_mapbox_access_token
        token = get_mapbox_access_token()

        # Build marker overlay string
        overlay_parts = []
        for marker in markers:
            label = (marker.get("name") or "?")[0].upper()
            lat = marker["lat"]
            lng = marker["lng"]
            overlay_parts.append(f"pin-l-{label}+{pin_color}({lng},{lat})")
        overlay_str = ",".join(overlay_parts) if overlay_parts else ""

        retina_suffix = "@2x" if retina else ""

        # Build URL
        if overlay_str:
            url = (
                f"{self.STATIC_BASE}/{style_id}/static/"
                f"{overlay_str}/"
                f"{center_lng},{center_lat},{zoom},0,0/"
                f"{width}x{height}{retina_suffix}"
                f"?access_token={token}"
            )
        else:
            url = (
                f"{self.STATIC_BASE}/{style_id}/static/"
                f"{center_lng},{center_lat},{zoom},0,0/"
                f"{width}x{height}{retina_suffix}"
                f"?access_token={token}"
            )

        if len(url) > MAX_URL_LENGTH:
            logger.warning(
                "Mapbox Static Images URL exceeds %d chars (%d). Trimming markers.",
                MAX_URL_LENGTH, len(url),
            )
            # Trim markers until URL fits
            while len(url) > MAX_URL_LENGTH and overlay_parts:
                overlay_parts.pop()
                overlay_str = ",".join(overlay_parts)
                url = (
                    f"{self.STATIC_BASE}/{style_id}/static/"
                    f"{overlay_str}/"
                    f"{center_lng},{center_lat},{zoom},0,0/"
                    f"{width}x{height}{retina_suffix}"
                    f"?access_token={token}"
                )

        return self.call("generate", url=url)


# Singleton
_mapbox_static_gateway: Optional[MapboxStaticGateway] = None


def get_mapbox_static_gateway() -> MapboxStaticGateway:
    """Get the Mapbox Static Images Gateway singleton instance."""
    global _mapbox_static_gateway
    if _mapbox_static_gateway is None:
        _mapbox_static_gateway = MapboxStaticGateway()
    return _mapbox_static_gateway
