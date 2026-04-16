"""
Unit tests for zone haversine distance calculation.

Verifies the haversine function used for zone overlap detection
produces correct distances for known city pairs.
"""

import pytest

from app.services.ads.zone_service import _haversine_km


class TestHaversine:
    def test_same_point_is_zero(self):
        d = _haversine_km(-34.5880, -58.4300, -34.5880, -58.4300)
        assert d == pytest.approx(0.0, abs=0.01)

    def test_ba_palermo_to_recoleta(self):
        # Palermo to Recoleta ~3-4km
        d = _haversine_km(-34.5880, -58.4300, -34.5875, -58.3930)
        assert 2.5 < d < 5.0

    def test_ba_palermo_to_san_telmo(self):
        # Palermo to San Telmo ~5-7km
        d = _haversine_km(-34.5880, -58.4300, -34.6210, -58.3730)
        assert 5.0 < d < 8.0

    def test_short_distance_within_neighborhood(self):
        # Two points ~500m apart in Palermo
        d = _haversine_km(-34.5880, -58.4300, -34.5850, -58.4270)
        assert 0.3 < d < 1.0

    def test_cross_equator(self):
        # ~111km per degree of latitude at equator
        d = _haversine_km(0.0, 0.0, 1.0, 0.0)
        assert 110 < d < 112

    def test_symmetry(self):
        d1 = _haversine_km(-34.5880, -58.4300, -34.6037, -58.3816)
        d2 = _haversine_km(-34.6037, -58.3816, -34.5880, -58.4300)
        assert d1 == pytest.approx(d2, abs=0.001)

    def test_overlap_detection_logic(self):
        """Two 2km-radius zones 3km apart should overlap (3 < 2+2)."""
        center_a = (-34.5880, -58.4300)
        center_b = (-34.5850, -58.4000)
        d = _haversine_km(*center_a, *center_b)
        radius_a = 2.0
        radius_b = 2.0
        assert d < (radius_a + radius_b), "These zones should overlap"

    def test_non_overlap_detection_logic(self):
        """Two 1km-radius zones 10km apart should not overlap."""
        # Palermo to La Boca ~8-10km
        d = _haversine_km(-34.5880, -58.4300, -34.6350, -58.3630)
        assert d > 2.0, "These zones should not overlap at 1km radius each"
