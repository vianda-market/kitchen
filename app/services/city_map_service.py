"""
City Map Service — generates and caches static map images for the B2C Explore tab.

Centers the map on the user's selected address (home, work, or other) and overlays
restaurant pins within the visible frame. Images are cached in GCS with grid-cell
keys so nearby users share the same cached image.
"""

import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

import psycopg2.extensions

from app.config.settings import get_settings
from app.gateways.mapbox_static_gateway import get_mapbox_static_gateway
from app.utils.db import db_read
from app.utils.map_projection import (
    lat_lng_to_pixel,
    is_within_frame,
    grid_cell,
    distance_from_center,
)
from app.utils.log import log_info, log_warning

logger = logging.getLogger(__name__)


class CityMapService:
    """Generate and cache static map snapshots centered on user's address."""

    def get_snapshot(
        self,
        center_lat: float,
        center_lng: float,
        city: str,
        country_code: str,
        width: int,
        height: int,
        retina: bool,
        style: str,
        db: psycopg2.extensions.connection,
    ) -> Dict[str, Any]:
        """
        Get a cached or freshly generated static map image for the given center point.

        Returns dict matching CitySnapshotResponseSchema:
        { image_url, center, zoom, width, height, retina, markers[] }
        """
        settings = get_settings()
        zoom = settings.MAPBOX_SNAPSHOT_ZOOM
        max_pins = settings.MAPBOX_SNAPSHOT_MAX_PINS
        cache_seconds = settings.MAPBOX_SNAPSHOT_CACHE_SECONDS
        pin_color = settings.MAPBOX_PIN_COLOR

        style_id = settings.MAPBOX_STYLE_LIGHT if style == "light" else settings.MAPBOX_STYLE_DARK

        # 1. Query restaurants with coordinates in this city
        restaurants = self._query_restaurants(city, country_code, db)

        if not restaurants:
            return self._empty_response(center_lat, center_lng, zoom, width, height, retina)

        # 2. Filter to restaurants within the zoom 14 frame and cap at max_pins
        visible_markers = self._filter_to_frame(
            restaurants, center_lat, center_lng, zoom, width, height, max_pins,
        )

        if not visible_markers:
            return self._empty_response(center_lat, center_lng, zoom, width, height, retina)

        # 3. Compute grid-snapped center for cache key
        cell = grid_cell(center_lat, center_lng)
        retina_suffix = "@2x" if retina else ""
        blob_name = f"maps/city-snapshots/{cell}-{country_code}-{style}-{width}x{height}{retina_suffix}.png"

        # 4. Check GCS cache
        image_url = self._get_cached_url(blob_name, cache_seconds)

        # 5. On cache miss: generate and upload
        if not image_url:
            image_url = self._generate_and_cache(
                style_id, center_lat, center_lng, zoom, width, height, retina,
                visible_markers, pin_color, blob_name,
            )

        return {
            "image_url": image_url,
            "center": {"lat": center_lat, "lng": center_lng},
            "zoom": zoom,
            "width": width,
            "height": height,
            "retina": retina,
            "markers": visible_markers,
        }

    def _query_restaurants(
        self, city: str, country_code: str, db: psycopg2.extensions.connection,
    ) -> List[Dict[str, Any]]:
        """Query active restaurants with valid coordinates in the city."""
        query = """
            SELECT r.restaurant_id, r.name, g.latitude, g.longitude
            FROM restaurant_info r
            INNER JOIN address_info a ON r.address_id = a.address_id
            INNER JOIN geolocation_info g ON g.address_id = a.address_id AND g.is_archived = FALSE
            WHERE a.country_code = %s
              AND TRIM(a.city) = %s
              AND a.is_archived = FALSE
              AND r.is_archived = FALSE
              AND r.status = 'active'
              AND g.latitude IS NOT NULL
              AND g.longitude IS NOT NULL
            ORDER BY r.name
        """
        rows = db_read(query, (country_code, city), connection=db) or []
        return [
            {
                "restaurant_id": str(row["restaurant_id"]),
                "name": row["name"] or "",
                "lat": float(row["latitude"]),
                "lng": float(row["longitude"]),
            }
            for row in rows
            if row.get("latitude") is not None and row.get("longitude") is not None
        ]

    def _filter_to_frame(
        self,
        restaurants: List[Dict[str, Any]],
        center_lat: float,
        center_lng: float,
        zoom: int,
        width: int,
        height: int,
        max_pins: int,
    ) -> List[Dict[str, Any]]:
        """Filter restaurants to those visible in the frame and cap at max_pins."""
        visible = []
        for r in restaurants:
            px, py = lat_lng_to_pixel(r["lat"], r["lng"], center_lat, center_lng, zoom, width, height)
            if is_within_frame(px, py, width, height):
                visible.append({
                    **r,
                    "pixel_x": px,
                    "pixel_y": py,
                })

        if len(visible) > max_pins:
            visible.sort(key=lambda m: distance_from_center(m["lat"], m["lng"], center_lat, center_lng))
            visible = visible[:max_pins]

        return visible

    def _get_cached_url(self, blob_name: str, cache_seconds: int) -> Optional[str]:
        """Check if a fresh cached image exists in GCS. Returns signed URL or None."""
        settings = get_settings()
        bucket = settings.GCS_INTERNAL_BUCKET
        if not bucket:
            return None

        try:
            from app.utils.gcs import get_gcs_client, generate_signed_url
            client = get_gcs_client()
            bucket_obj = client.bucket(bucket)
            blob = bucket_obj.blob(blob_name)

            if not blob.exists():
                return None

            blob.reload()
            if blob.updated:
                age = datetime.now(timezone.utc) - blob.updated
                if age < timedelta(seconds=cache_seconds):
                    url = generate_signed_url(bucket, blob_name, expiration_seconds=cache_seconds)
                    log_info(f"Map cache hit: {blob_name} (age: {age.total_seconds():.0f}s)")
                    return url

            log_info(f"Map cache stale: {blob_name}")
            return None
        except Exception as e:
            log_warning(f"GCS cache check failed for {blob_name}: {e}")
            return None

    def _generate_and_cache(
        self,
        style_id: str,
        center_lat: float,
        center_lng: float,
        zoom: int,
        width: int,
        height: int,
        retina: bool,
        markers: List[Dict[str, Any]],
        pin_color: str,
        blob_name: str,
    ) -> Optional[str]:
        """Generate a static map image via Mapbox and upload to GCS."""
        settings = get_settings()
        bucket = settings.GCS_INTERNAL_BUCKET

        try:
            gateway = get_mapbox_static_gateway()
            png_bytes = gateway.generate_static_map(
                style_id=style_id,
                center_lat=center_lat,
                center_lng=center_lng,
                zoom=zoom,
                width=width,
                height=height,
                markers=markers,
                retina=retina,
                pin_color=pin_color,
            )
        except Exception as e:
            log_warning(f"Mapbox Static Images API failed: {e}")
            return None

        if not png_bytes:
            return None

        if not bucket:
            log_warning("GCS_INTERNAL_BUCKET not configured; cannot cache map image")
            return None

        try:
            from app.utils.gcs import upload_file, generate_signed_url
            upload_file(bucket, blob_name, png_bytes, content_type="image/png")
            url = generate_signed_url(bucket, blob_name, expiration_seconds=settings.MAPBOX_SNAPSHOT_CACHE_SECONDS)
            log_info(f"Map generated and cached: {blob_name} ({len(png_bytes)} bytes)")
            return url
        except Exception as e:
            log_warning(f"GCS upload failed for {blob_name}: {e}")
            return None

    def _empty_response(
        self, center_lat: float, center_lng: float, zoom: int, width: int, height: int, retina: bool,
    ) -> Dict[str, Any]:
        return {
            "image_url": None,
            "center": {"lat": center_lat, "lng": center_lng},
            "zoom": zoom,
            "width": width,
            "height": height,
            "retina": retina,
            "markers": [],
        }


city_map_service = CityMapService()
