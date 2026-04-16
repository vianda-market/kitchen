"""
Unit tests for CityMapService (static map snapshot generation and caching).
"""

from unittest.mock import MagicMock, Mock, patch

from app.services.city_map_service import CityMapService


class TestCityMapServiceGetSnapshot:
    def _make_service(self):
        return CityMapService()

    @patch("app.services.city_map_service.db_read")
    def test_no_restaurants_returns_empty(self, mock_db_read):
        mock_db_read.return_value = []
        svc = self._make_service()
        result = svc.get_snapshot(
            center_lat=-34.59,
            center_lng=-58.40,
            city="Buenos Aires",
            country_code="AR",
            width=600,
            height=400,
            retina=True,
            style="light",
            db=MagicMock(),
        )
        assert result["image_url"] is None
        assert result["markers"] == []
        assert result["zoom"] == 14

    @patch("app.services.city_map_service.get_settings")
    @patch("app.services.city_map_service.db_read")
    def test_restaurants_outside_frame_excluded(self, mock_db_read, mock_settings):
        mock_settings.return_value = Mock(
            MAPBOX_SNAPSHOT_ZOOM=14,
            MAPBOX_SNAPSHOT_MAX_PINS=30,
            MAPBOX_SNAPSHOT_CACHE_SECONDS=86400,
            MAPBOX_PIN_COLOR="4a7c59",
            MAPBOX_STYLE_LIGHT="mapbox/light-v11",
            MAPBOX_STYLE_DARK="mapbox/dark-v11",
            GCS_INTERNAL_BUCKET="",
        )
        # One restaurant near center, one far away
        mock_db_read.return_value = [
            {"restaurant_id": "aaa", "name": "Near", "latitude": -34.590, "longitude": -58.400},
            {"restaurant_id": "bbb", "name": "Far", "latitude": -35.000, "longitude": -59.000},
        ]
        svc = self._make_service()
        result = svc.get_snapshot(
            center_lat=-34.59,
            center_lng=-58.40,
            city="Buenos Aires",
            country_code="AR",
            width=600,
            height=400,
            retina=True,
            style="light",
            db=MagicMock(),
        )
        # Only the near restaurant should be in markers
        names = [m["name"] for m in result["markers"]]
        assert "Near" in names
        assert "Far" not in names

    @patch("app.services.city_map_service.get_settings")
    @patch("app.services.city_map_service.db_read")
    def test_max_pins_cap(self, mock_db_read, mock_settings):
        mock_settings.return_value = Mock(
            MAPBOX_SNAPSHOT_ZOOM=14,
            MAPBOX_SNAPSHOT_MAX_PINS=5,
            MAPBOX_SNAPSHOT_CACHE_SECONDS=86400,
            MAPBOX_PIN_COLOR="4a7c59",
            MAPBOX_STYLE_LIGHT="mapbox/light-v11",
            MAPBOX_STYLE_DARK="mapbox/dark-v11",
            GCS_INTERNAL_BUCKET="",
        )
        # 10 restaurants all near center
        mock_db_read.return_value = [
            {"restaurant_id": f"r{i}", "name": f"R{i}", "latitude": -34.59 + i * 0.0001, "longitude": -58.40}
            for i in range(10)
        ]
        svc = self._make_service()
        result = svc.get_snapshot(
            center_lat=-34.59,
            center_lng=-58.40,
            city="Buenos Aires",
            country_code="AR",
            width=600,
            height=400,
            retina=True,
            style="light",
            db=MagicMock(),
        )
        assert len(result["markers"]) <= 5

    @patch("app.services.city_map_service.get_settings")
    @patch("app.services.city_map_service.db_read")
    def test_markers_have_pixel_positions(self, mock_db_read, mock_settings):
        mock_settings.return_value = Mock(
            MAPBOX_SNAPSHOT_ZOOM=14,
            MAPBOX_SNAPSHOT_MAX_PINS=30,
            MAPBOX_SNAPSHOT_CACHE_SECONDS=86400,
            MAPBOX_PIN_COLOR="4a7c59",
            MAPBOX_STYLE_LIGHT="mapbox/light-v11",
            MAPBOX_STYLE_DARK="mapbox/dark-v11",
            GCS_INTERNAL_BUCKET="",
        )
        mock_db_read.return_value = [
            {"restaurant_id": "aaa", "name": "Test", "latitude": -34.590, "longitude": -58.400},
        ]
        svc = self._make_service()
        result = svc.get_snapshot(
            center_lat=-34.59,
            center_lng=-58.40,
            city="Buenos Aires",
            country_code="AR",
            width=600,
            height=400,
            retina=True,
            style="light",
            db=MagicMock(),
        )
        assert len(result["markers"]) == 1
        m = result["markers"][0]
        assert "pixel_x" in m
        assert "pixel_y" in m
        assert isinstance(m["pixel_x"], int)
        assert isinstance(m["pixel_y"], int)
        # Center restaurant should be near image center
        assert 250 < m["pixel_x"] < 350
        assert 150 < m["pixel_y"] < 250
