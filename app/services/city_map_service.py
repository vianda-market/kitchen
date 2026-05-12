"""
City Map Service — generates and caches static map images for the B2C Explore tab.

Centers the map on the user's selected address (home, work, or other) and overlays
restaurant pins within the visible frame. Images are cached in GCS with grid-cell
keys so nearby users share the same cached image.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg2.extensions

from app.config.settings import get_settings
from app.gateways.mapbox_static_gateway import get_mapbox_static_gateway
from app.utils.db import db_read
from app.utils.log import log_info, log_warning
from app.utils.map_projection import (
    compute_bounding_box,
    distance_from_center,
    grid_cell,
    is_within_frame,
    lat_lng_to_pixel,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTLIER_DISTANCE_KM = 10.0  # user-anchor → city-fallback threshold
MAX_MARKERS_PER_REQUEST = 20  # default + cap for `limit` query param

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
    ) -> dict[str, Any]:
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
            restaurants,
            center_lat,
            center_lng,
            zoom,
            width,
            height,
            max_pins,
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
                style_id,
                center_lat,
                center_lng,
                zoom,
                width,
                height,
                retina,
                visible_markers,
                pin_color,
                blob_name,
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

    def get_pins(
        self,
        city: str,
        country_code: str,
        db: psycopg2.extensions.connection,
        *,
        center_lat: float | None = None,
        center_lng: float | None = None,
        limit: int = MAX_MARKERS_PER_REQUEST,
    ) -> dict[str, Any]:
        """
        Lean pins-only response for the interactive Mapbox map.

        Implements three branches based on whether a user anchor is provided
        and whether it is within OUTLIER_DISTANCE_KM of any restaurant:

        Branch A — user-anchor inside cluster (center_lat/lng provided AND
          nearest restaurant ≤ OUTLIER_DISTANCE_KM away):
          Returns restaurants ordered by distance from anchor; centroid is
          the nearest restaurant's coordinates (source='user_nearest').

        Branch B — user-anchor outlier (center_lat/lng provided BUT nearest
          restaurant > OUTLIER_DISTANCE_KM away):
          Falls back to city centroid ordering; centroid source='city_fallback'.

        Branch C — no user-anchor (center_lat/lng both null):
          Orders by distance from city centroid; centroid source='city'.

        All branches set more_available=True and omitted_count when the city
        has more restaurants than the requested limit.

        Returns dict matching CityPinsResponseSchema:
        { markers, recommended_viewport, centroid, more_available, omitted_count }
        """
        user_anchor = center_lat is not None and center_lng is not None

        if user_anchor:
            assert center_lat is not None
            assert center_lng is not None
            markers, total_count = self._query_restaurants_ordered(
                city, country_code, center_lat, center_lng, limit, db
            )
            if not markers:
                # Degenerate: city has zero restaurants — behave like Branch C
                city_centroid = self._get_city_centroid(city, country_code, db)
                return self._build_response([], city_centroid, "city", total_count, limit)

            # Check if the nearest restaurant is within the outlier threshold
            nearest_distance = markers[0].get("_distance_km", 0.0)
            if nearest_distance > OUTLIER_DISTANCE_KM:
                # Branch B — city fallback
                city_centroid = self._get_city_centroid(city, country_code, db)
                if city_centroid is None:
                    # city centroid not available yet — recompute with city anchor using existing rows
                    # but we need to re-query from city mean; markers already ordered by user anchor
                    # fall through: use what we have but re-order from city avg
                    avg_lat = sum(m["lat"] for m in markers) / len(markers)
                    avg_lng = sum(m["lng"] for m in markers) / len(markers)
                    city_centroid = (avg_lat, avg_lng)
                    # re-query ordered by city mean so viewport is sensible
                    markers, total_count = self._query_restaurants_ordered(
                        city, country_code, city_centroid[0], city_centroid[1], limit, db
                    )
                else:
                    markers, total_count = self._query_restaurants_ordered(
                        city, country_code, city_centroid[0], city_centroid[1], limit, db
                    )
                return self._build_response(markers, city_centroid, "city_fallback", total_count, limit)
            # Branch A — user nearest
            nearest_coords = (markers[0]["lat"], markers[0]["lng"])
            return self._build_response(markers, nearest_coords, "user_nearest", total_count, limit)
        # Branch C — no user anchor
        city_centroid = self._get_city_centroid(city, country_code, db)
        if city_centroid is None:
            # Safety net: compute mean inline for fresh-DB / pre-cron scenarios
            all_restaurants = self._query_restaurants(city, country_code, db)
            if not all_restaurants:
                return self._build_response([], None, "city", 0, limit)
            avg_lat = sum(m["lat"] for m in all_restaurants) / len(all_restaurants)
            avg_lng = sum(m["lng"] for m in all_restaurants) / len(all_restaurants)
            city_centroid = (avg_lat, avg_lng)

        markers, total_count = self._query_restaurants_ordered(
            city, country_code, city_centroid[0], city_centroid[1], limit, db
        )
        return self._build_response(markers, city_centroid, "city", total_count, limit)

    def _get_city_centroid(
        self,
        city: str,
        country_code: str,
        db: psycopg2.extensions.connection,
    ) -> tuple[float, float] | None:
        """
        Read precomputed centroid_lat/lng from core.city_metadata for this city/country.

        Returns (lat, lng) tuple if populated, None if NULL (not yet computed).
        Uses city_metadata_id FK on address_info for the join.
        """
        query = """
            SELECT cm.centroid_lat, cm.centroid_lng
              FROM core.city_metadata cm
             WHERE cm.city_metadata_id = (
                   SELECT DISTINCT a.city_metadata_id
                     FROM address_info a
                    WHERE TRIM(a.city) = %s
                      AND a.country_code = %s
                      AND a.is_archived = FALSE
                    LIMIT 1
                   )
               AND cm.centroid_lat IS NOT NULL
               AND cm.centroid_lng IS NOT NULL
        """
        raw = db_read(query, (city, country_code), connection=db)
        rows: list[dict[str, Any]] = raw if isinstance(raw, list) else []
        if not rows:
            return None
        row = rows[0]
        return (float(row["centroid_lat"]), float(row["centroid_lng"]))

    def _query_restaurants_ordered(
        self,
        city: str,
        country_code: str,
        anchor_lat: float,
        anchor_lng: float,
        limit: int,
        db: psycopg2.extensions.connection,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Query active restaurants in the city ordered by haversine distance from
        the given anchor, capped at limit rows.  Also returns the total count of
        geocoded restaurants in the city for more_available / omitted_count.

        Returns (markers, total_count).  Uses a single round-trip via window function.
        """
        query = """
            WITH ranked AS (
                SELECT
                    r.restaurant_id,
                    r.name,
                    g.latitude,
                    g.longitude,
                    2 * 6371 * asin(sqrt(
                        sin(radians((g.latitude  - %(anchor_lat)s) / 2)) ^ 2
                        + cos(radians(%(anchor_lat)s))
                          * cos(radians(g.latitude))
                          * sin(radians((g.longitude - %(anchor_lng)s) / 2)) ^ 2
                    )) AS distance_km,
                    COUNT(*) OVER () AS total_count
                FROM restaurant_info r
                INNER JOIN address_info a
                        ON r.address_id = a.address_id
                INNER JOIN geolocation_info g
                        ON g.address_id = a.address_id
                       AND g.is_archived = FALSE
                WHERE a.country_code = %(country_code)s
                  AND TRIM(a.city) = %(city)s
                  AND a.is_archived = FALSE
                  AND r.is_archived = FALSE
                  AND r.status = 'active'
                  AND g.latitude IS NOT NULL
                  AND g.longitude IS NOT NULL
                ORDER BY distance_km
                LIMIT %(limit)s
            )
            SELECT * FROM ranked
        """
        params: Any = {
            "anchor_lat": anchor_lat,
            "anchor_lng": anchor_lng,
            "country_code": country_code,
            "city": city,
            "limit": limit,
        }
        raw = db_read(query, params, connection=db)
        rows: list[dict[str, Any]] = raw if isinstance(raw, list) else []
        if not rows:
            return [], 0
        total_count = int(rows[0]["total_count"])
        markers = [
            {
                "restaurant_id": str(row["restaurant_id"]),
                "name": row["name"] or "",
                "lat": float(row["latitude"]),
                "lng": float(row["longitude"]),
                "_distance_km": float(row["distance_km"]),
            }
            for row in rows
            if row.get("latitude") is not None and row.get("longitude") is not None
        ]
        return markers, total_count

    def _build_response(
        self,
        markers: list[dict[str, Any]],
        centroid_coords: tuple[float, float] | None,
        source: str,
        total_count: int,
        limit: int,
    ) -> dict[str, Any]:
        """Assemble the CityPinsResponseSchema dict from computed parts."""
        # Strip the internal _distance_km field before returning
        clean_markers = [{k: v for k, v in m.items() if k != "_distance_km"} for m in markers]
        viewport = compute_bounding_box(clean_markers) if clean_markers else None
        centroid = (
            {"lat": centroid_coords[0], "lng": centroid_coords[1], "source": source}
            if centroid_coords is not None
            else None
        )
        omitted = max(0, total_count - len(clean_markers))
        return {
            "markers": clean_markers,
            "recommended_viewport": viewport,
            "centroid": centroid,
            "more_available": omitted > 0,
            "omitted_count": omitted,
        }

    def _query_restaurants(
        self,
        city: str,
        country_code: str,
        db: psycopg2.extensions.connection,
    ) -> list[dict[str, Any]]:
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
        restaurants: list[dict[str, Any]],
        center_lat: float,
        center_lng: float,
        zoom: int,
        width: int,
        height: int,
        max_pins: int,
    ) -> list[dict[str, Any]]:
        """Filter restaurants to those visible in the frame and cap at max_pins."""
        visible = []
        for r in restaurants:
            px, py = lat_lng_to_pixel(r["lat"], r["lng"], center_lat, center_lng, zoom, width, height)
            if is_within_frame(px, py, width, height):
                visible.append(
                    {
                        **r,
                        "pixel_x": px,
                        "pixel_y": py,
                    }
                )

        if len(visible) > max_pins:
            visible.sort(key=lambda m: distance_from_center(m["lat"], m["lng"], center_lat, center_lng))
            visible = visible[:max_pins]

        return visible

    def _get_cached_url(self, blob_name: str, cache_seconds: int) -> str | None:
        """Check if a fresh cached image exists in GCS. Returns signed URL or None."""
        settings = get_settings()
        bucket = settings.GCS_INTERNAL_BUCKET
        if not bucket:
            return None

        try:
            from app.utils.gcs import generate_signed_url, get_gcs_client

            client = get_gcs_client()
            bucket_obj = client.bucket(bucket)
            blob = bucket_obj.blob(blob_name)

            if not blob.exists():
                return None

            blob.reload()
            if blob.updated:
                age = datetime.now(UTC) - blob.updated
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
        markers: list[dict[str, Any]],
        pin_color: str,
        blob_name: str,
    ) -> str | None:
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
            from app.utils.gcs import generate_signed_url, upload_file

            upload_file(bucket, blob_name, png_bytes, content_type="image/png")
            url = generate_signed_url(bucket, blob_name, expiration_seconds=settings.MAPBOX_SNAPSHOT_CACHE_SECONDS)
            log_info(f"Map generated and cached: {blob_name} ({len(png_bytes)} bytes)")
            return url
        except Exception as e:
            log_warning(f"GCS upload failed for {blob_name}: {e}")
            return None

    def _empty_response(
        self,
        center_lat: float,
        center_lng: float,
        zoom: int,
        width: int,
        height: int,
        retina: bool,
    ) -> dict[str, Any]:
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
