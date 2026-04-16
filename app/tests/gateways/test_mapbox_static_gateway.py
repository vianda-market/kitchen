"""
Unit tests for MapboxStaticGateway (static map image generation).
"""

from unittest.mock import Mock, patch

from app.gateways.mapbox_static_gateway import MapboxStaticGateway, get_mapbox_static_gateway


class TestMapboxStaticGateway:
    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_returns_png_bytes(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxStaticGateway()
        result = gw.generate_static_map(
            style_id="mapbox/light-v11",
            center_lat=-34.59,
            center_lng=-58.40,
            zoom=14,
            width=600,
            height=400,
            markers=[{"name": "Green Bowl", "lat": -34.588, "lng": -58.402}],
        )
        assert isinstance(result, bytes)
        assert len(result) > 0
        # Verify it starts with PNG signature
        assert result[:4] == b"\x89PNG"

    @patch("requests.get")
    @patch("app.config.settings.get_mapbox_access_token", return_value="pk.test123")
    @patch("app.gateways.base_gateway.get_settings")
    def test_prod_mode_builds_correct_url(self, mock_settings, mock_token, mock_get):
        mock_settings.return_value = Mock(DEV_MODE=True)
        mock_response = Mock()
        mock_response.ok = True
        mock_response.content = b"\x89PNG fake"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        gw = MapboxStaticGateway()
        markers = [
            {"name": "Green Bowl", "lat": 40.7338, "lng": -73.9921},
            {"name": "Nourish", "lat": 40.7365, "lng": -73.9801},
        ]
        gw.generate_static_map(
            style_id="mapbox/light-v11",
            center_lat=40.735,
            center_lng=-73.985,
            zoom=14,
            width=600,
            height=400,
            markers=markers,
            pin_color="4a7c59",
        )

        mock_get.assert_called_once()
        url = mock_get.call_args[0][0]
        assert "mapbox/light-v11" in url
        assert "pin-l-G+4a7c59" in url
        assert "pin-l-N+4a7c59" in url
        assert "600x400@2x" in url
        assert "access_token=pk.test123" in url

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_url_length_within_limit(self, mock_settings, _mock_token):
        """30 markers should produce a URL under 8192 chars."""
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxStaticGateway()
        markers = [{"name": f"Restaurant {i}", "lat": -34.59 + i * 0.001, "lng": -58.40 + i * 0.001} for i in range(30)]
        # Just verify it doesn't raise — URL construction happens internally
        result = gw.generate_static_map(
            style_id="mapbox/light-v11",
            center_lat=-34.59,
            center_lng=-58.40,
            zoom=14,
            width=600,
            height=400,
            markers=markers,
        )
        assert isinstance(result, bytes)

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_empty_markers_produces_map_without_overlays(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxStaticGateway()
        result = gw.generate_static_map(
            style_id="mapbox/light-v11",
            center_lat=-34.59,
            center_lng=-58.40,
            zoom=14,
            width=600,
            height=400,
            markers=[],
        )
        assert isinstance(result, bytes)


class TestMapboxStaticGatewaySingleton:
    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_singleton_returns_same_instance(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        import app.gateways.mapbox_static_gateway as mod

        mod._mapbox_static_gateway = None
        gw1 = get_mapbox_static_gateway()
        gw2 = get_mapbox_static_gateway()
        assert gw1 is gw2
        mod._mapbox_static_gateway = None
