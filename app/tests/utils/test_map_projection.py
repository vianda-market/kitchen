"""
Unit tests for map projection utilities (Web Mercator, pixel conversion, grid cells, bounding box).
"""

import pytest

from app.utils.map_projection import (
    _SINGLE_MARKER_EXPANSION_DEG,
    compute_bounding_box,
    distance_from_center,
    grid_cell,
    is_within_frame,
    lat_lng_to_pixel,
    slugify_city,
)


class TestLatLngToPixel:
    def test_center_point_maps_to_image_center(self):
        """A point at the map center should be at the image center."""
        px, py = lat_lng_to_pixel(-34.59, -58.40, -34.59, -58.40, 14, 600, 400)
        assert px == 300  # width / 2
        assert py == 200  # height / 2

    def test_point_east_of_center_has_higher_x(self):
        """A point east of center should have pixel_x > width/2."""
        px, py = lat_lng_to_pixel(-34.59, -58.39, -34.59, -58.40, 14, 600, 400)
        assert px > 300

    def test_point_north_of_center_has_lower_y(self):
        """A point north of center should have pixel_y < height/2 (y increases downward)."""
        px, py = lat_lng_to_pixel(-34.58, -58.40, -34.59, -58.40, 14, 600, 400)
        assert py < 200

    def test_buenos_aires_known_coordinates(self):
        """Verify with known Buenos Aires coordinates at zoom 14."""
        px, py = lat_lng_to_pixel(-34.5880634, -58.4023328, -34.59, -58.40, 14, 600, 400)
        assert isinstance(px, int)
        assert isinstance(py, int)
        # Should be near center but slightly offset
        assert 200 < px < 400
        assert 100 < py < 300

    def test_returns_integers(self):
        px, py = lat_lng_to_pixel(-34.59, -58.40, -34.59, -58.40, 14, 600, 400)
        assert isinstance(px, int)
        assert isinstance(py, int)


class TestIsWithinFrame:
    def test_center_is_within(self):
        assert is_within_frame(300, 200, 600, 400) is True

    def test_edge_with_margin_is_outside(self):
        assert is_within_frame(5, 200, 600, 400, margin=20) is False

    def test_edge_without_margin_is_within(self):
        assert is_within_frame(0, 0, 600, 400, margin=0) is True

    def test_negative_is_outside(self):
        assert is_within_frame(-10, 200, 600, 400) is False

    def test_beyond_width_is_outside(self):
        assert is_within_frame(610, 200, 600, 400) is False


class TestGridCell:
    def test_rounding_consistency(self):
        """Two nearby points should map to the same grid cell."""
        c1 = grid_cell(-34.5880, -58.4023)
        c2 = grid_cell(-34.5899, -58.4001)
        assert c1 == c2  # Both round to -34.59, -58.40

    def test_different_cells(self):
        """Points >1km apart should map to different cells."""
        c1 = grid_cell(-34.59, -58.40)
        c2 = grid_cell(-34.60, -58.41)
        assert c1 != c2

    def test_format(self):
        cell = grid_cell(-34.5880, -58.4023)
        assert "lat" in cell
        assert "lng" in cell


class TestSlugifyCity:
    def test_basic(self):
        assert slugify_city("Buenos Aires") == "buenos-aires"

    def test_accents(self):
        assert slugify_city("São Paulo") == "sao-paulo"

    def test_special_chars(self):
        assert slugify_city("New York, NY") == "new-york-ny"

    def test_empty(self):
        assert slugify_city("") == ""

    def test_single_word(self):
        assert slugify_city("Lima") == "lima"


class TestDistanceFromCenter:
    def test_same_point_is_zero(self):
        assert distance_from_center(-34.59, -58.40, -34.59, -58.40) == 0.0

    def test_closer_point_has_smaller_distance(self):
        d1 = distance_from_center(-34.59, -58.40, -34.59, -58.41)
        d2 = distance_from_center(-34.59, -58.40, -34.59, -58.45)
        assert d1 < d2


class TestComputeBoundingBox:
    def test_empty_list_returns_none(self):
        """Empty markers list must return None."""
        assert compute_bounding_box([]) is None

    def test_single_marker_returns_expanded_box(self):
        """A single marker should produce a ±EXPANSION box around it."""
        lat, lng = -12.046374, -77.042793  # Lima, Peru
        result = compute_bounding_box([{"lat": lat, "lng": lng}])
        assert result is not None
        exp = _SINGLE_MARKER_EXPANSION_DEG
        assert result["ne"]["lat"] == pytest.approx(lat + exp)
        assert result["ne"]["lng"] == pytest.approx(lng + exp)
        assert result["sw"]["lat"] == pytest.approx(lat - exp)
        assert result["sw"]["lng"] == pytest.approx(lng - exp)

    def test_single_marker_ne_is_greater_than_sw(self):
        """NE coordinates must always be >= SW for a single marker."""
        result = compute_bounding_box([{"lat": 0.0, "lng": 0.0}])
        assert result is not None
        assert result["ne"]["lat"] > result["sw"]["lat"]
        assert result["ne"]["lng"] > result["sw"]["lng"]

    def test_two_markers_tight_bbox(self):
        """Two markers → bbox with no extra padding."""
        markers = [
            {"lat": -12.046374, "lng": -77.042793},
            {"lat": -12.100000, "lng": -77.050000},
        ]
        result = compute_bounding_box(markers)
        assert result is not None
        assert result["ne"]["lat"] == pytest.approx(-12.046374)
        assert result["ne"]["lng"] == pytest.approx(-77.042793)
        assert result["sw"]["lat"] == pytest.approx(-12.100000)
        assert result["sw"]["lng"] == pytest.approx(-77.050000)

    def test_multi_marker_ne_sw_corners(self):
        """ne = (max_lat, max_lng), sw = (min_lat, min_lng) over all markers."""
        markers = [
            {"lat": -34.5880, "lng": -58.4023},  # Buenos Aires cluster
            {"lat": -34.6000, "lng": -58.4100},
            {"lat": -34.5700, "lng": -58.3900},
        ]
        result = compute_bounding_box(markers)
        assert result is not None
        assert result["ne"]["lat"] == pytest.approx(-34.5700)
        assert result["ne"]["lng"] == pytest.approx(-58.3900)
        assert result["sw"]["lat"] == pytest.approx(-34.6000)
        assert result["sw"]["lng"] == pytest.approx(-58.4100)

    def test_ne_lat_always_gte_sw_lat(self):
        """NE lat must always be >= SW lat for any valid input."""
        markers = [
            {"lat": 40.7128, "lng": -74.0060},  # New York
            {"lat": 34.0522, "lng": -118.2437},  # Los Angeles
        ]
        result = compute_bounding_box(markers)
        assert result is not None
        assert result["ne"]["lat"] >= result["sw"]["lat"]

    def test_single_marker_at_lat_lng_zero(self):
        """Edge case: marker exactly at (0.0, 0.0) must not produce NaN or wrong signs."""
        result = compute_bounding_box([{"lat": 0.0, "lng": 0.0}])
        assert result is not None
        exp = _SINGLE_MARKER_EXPANSION_DEG
        assert result["ne"]["lat"] == pytest.approx(exp)
        assert result["sw"]["lat"] == pytest.approx(-exp)
        assert result["ne"]["lng"] == pytest.approx(exp)
        assert result["sw"]["lng"] == pytest.approx(-exp)

    def test_markers_with_identical_coordinates(self):
        """Multiple markers at identical coordinates should produce the single-marker expansion."""
        markers = [
            {"lat": -12.046374, "lng": -77.042793},
            {"lat": -12.046374, "lng": -77.042793},
        ]
        result = compute_bounding_box(markers)
        assert result is not None
        # min == max, so the box is a zero-width point (no expansion for N>1)
        assert result["ne"]["lat"] == pytest.approx(-12.046374)
        assert result["sw"]["lat"] == pytest.approx(-12.046374)
