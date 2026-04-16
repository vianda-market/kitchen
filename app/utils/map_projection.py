"""
Map projection utilities for static map image generation.

Converts geographic coordinates (lat/lng) to pixel positions on a static map image
using Web Mercator projection, matching Mapbox Static Images API rendering.

All pixel coordinates are in CSS pixels (not physical pixels), so frontends can
position overlays using standard layout units regardless of @2x retina.
"""

import math
import re
import unicodedata


def lat_lng_to_pixel(
    lat: float,
    lng: float,
    center_lat: float,
    center_lng: float,
    zoom: int,
    width: int,
    height: int,
) -> tuple[int, int]:
    """
    Convert lat/lng to CSS pixel position on a static map image.

    Uses Web Mercator projection matching Mapbox Static Images API.
    Returns (pixel_x, pixel_y) where (0, 0) is the top-left corner.
    """
    scale = 256 * (2**zoom)

    pixel_x = width / 2 + (lng - center_lng) * scale / 360

    lat_rad = math.radians(lat)
    center_lat_rad = math.radians(center_lat)
    mercator_y = math.log(math.tan(math.pi / 4 + lat_rad / 2))
    center_mercator_y = math.log(math.tan(math.pi / 4 + center_lat_rad / 2))
    pixel_y = height / 2 - (mercator_y - center_mercator_y) * scale / (2 * math.pi)

    return round(pixel_x), round(pixel_y)


def is_within_frame(pixel_x: int, pixel_y: int, width: int, height: int, margin: int = 20) -> bool:
    """
    Check if a pixel position is within the image bounds (with optional margin).
    Margin prevents pins from being clipped at the edges.
    """
    return margin <= pixel_x <= (width - margin) and margin <= pixel_y <= (height - margin)


def grid_cell(lat: float, lng: float) -> str:
    """
    Round lat/lng to a ~500m grid cell for cache key grouping.

    Uses rounding to 2 decimal places (~1.1 km at the equator, tighter at higher latitudes).
    Users within the same grid cell share the same cached map image.

    Returns a string like 'lat-34.59-lng-58.40' for use in cache keys.
    """
    rounded_lat = round(lat, 2)
    rounded_lng = round(lng, 2)
    return f"lat{rounded_lat}-lng{rounded_lng}"


def slugify_city(city: str) -> str:
    """
    Convert city name to URL-safe slug for cache key construction.
    'Buenos Aires' -> 'buenos-aires'
    'São Paulo' -> 'sao-paulo'
    """
    if not city:
        return ""
    # Normalize unicode (remove accents)
    normalized = unicodedata.normalize("NFKD", city)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    # Lowercase, replace non-alphanumeric with hyphens, collapse multiples
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug


def distance_from_center(lat: float, lng: float, center_lat: float, center_lng: float) -> float:
    """
    Approximate distance in degrees from center point.
    Used for sorting restaurants by proximity to center (not for actual distance calculation).
    """
    return math.sqrt((lat - center_lat) ** 2 + (lng - center_lng) ** 2)
