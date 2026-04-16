"""
Unit tests for map projection utilities (Web Mercator, pixel conversion, grid cells).
"""

from app.utils.map_projection import (
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
