"""
Unit tests for MapboxGeocodingGateway (geocode + reverse_geocode).
"""

from unittest.mock import Mock, patch

import pytest

from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway, get_mapbox_geocoding_gateway


class TestMapboxGeocodingGatewayGeocode:
    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_geocode_returns_lat_lng(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxGeocodingGateway()
        lat, lng = gw.geocode("Av. Santa Fe 2567, Buenos Aires")
        assert isinstance(lat, float)
        assert isinstance(lng, float)
        # Verify coordinate swap: GeoJSON [lng, lat] -> (lat, lng)
        assert lat == pytest.approx(-34.5880634)
        assert lng == pytest.approx(-58.4023328)

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_reverse_geocode_returns_address(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxGeocodingGateway()
        address = gw.reverse_geocode(-34.5880634, -58.4023328)
        assert isinstance(address, str)
        assert "Santa Fe" in address

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_geocode_full_returns_dict(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxGeocodingGateway()
        result = gw.geocode_full("Av. Santa Fe 2567")
        assert result["latitude"] == pytest.approx(-34.5880634)
        assert result["longitude"] == pytest.approx(-58.4023328)
        assert result["mapbox_id"]
        assert result["formatted_address"]

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_get_address_components(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxGeocodingGateway()
        components = gw.get_address_components("Av. Santa Fe 2567")
        assert "street_number" in components
        assert components["street_number"] == "2567"
        assert "locality" in components
        assert components["locality"] == "Buenos Aires"

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_validate_address(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxGeocodingGateway()
        assert gw.validate_address("Av. Santa Fe 2567") is True

    @patch("requests.get")
    @patch("app.config.settings.get_mapbox_access_token", return_value="pk.test123")
    @patch("app.gateways.base_gateway.get_settings")
    def test_prod_mode_geocode_makes_http_call(self, mock_settings, mock_token, mock_get):
        mock_settings.return_value = Mock(DEV_MODE=True)
        mock_response = Mock()
        mock_response.ok = True
        mock_response.content = b'{"features": [{"geometry": {"coordinates": [-58.40, -34.58]}, "properties": {"mapbox_id": "test", "full_address": "Test"}}]}'
        mock_response.json.return_value = {
            "features": [
                {
                    "geometry": {"coordinates": [-58.40, -34.58]},
                    "properties": {"mapbox_id": "test", "full_address": "Test"},
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        gw = MapboxGeocodingGateway()
        lat, lng = gw.geocode("test address")
        assert lat == pytest.approx(-34.58)
        assert lng == pytest.approx(-58.40)
        mock_get.assert_called_once()


class TestMapboxGeocodingGatewayForwardSearch:
    """Tests for the forward_search method (autocomplete-style partial-input search)."""

    @patch("app.config.settings.get_mapbox_access_token", return_value="sk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def test_forward_search_calls_forward_search_operation(self, mock_settings, _mock_token, monkeypatch):
        """forward_search delegates to call('forward_search', ...) so cache key is 'forward_search|...'."""
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "bypass")
        mock_settings.return_value = Mock(DEV_MODE=False)
        gw = MapboxGeocodingGateway(permanent=True)

        captured_ops = []

        def fake_make_request(self_gw, operation, **kwargs):
            captured_ops.append(operation)
            return {"features": [], "type": "FeatureCollection"}

        with patch.object(MapboxGeocodingGateway, "_make_request", fake_make_request):
            gw.forward_search(query="av santa fe", country="AR", limit=5)

        assert captured_ops == ["forward_search"]

    @patch("app.config.settings.get_mapbox_access_token", return_value="sk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def test_forward_search_returns_features_dict(self, mock_settings, _mock_token, monkeypatch):
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "bypass")
        mock_settings.return_value = Mock(DEV_MODE=False)
        mock_features = {"features": [{"id": "f1"}], "type": "FeatureCollection"}

        gw = MapboxGeocodingGateway(permanent=True)
        with patch.object(MapboxGeocodingGateway, "_make_request", return_value=mock_features):
            result = gw.forward_search(query="test", country="AR", limit=3)

        assert result == mock_features

    @patch("requests.get")
    @patch("app.config.settings.get_mapbox_access_token", return_value="sk.test")
    @patch("app.gateways.base_gateway.get_settings")
    def test_forward_search_sends_autocomplete_true_in_request(self, mock_settings, _mock_token, mock_get, monkeypatch):
        """HTTP request to Mapbox v6 must include autocomplete=true and permanent=true."""
        monkeypatch.setenv("MAPBOX_CACHE_MODE", "bypass")
        mock_settings.return_value = Mock(DEV_MODE=False)
        mock_response = Mock()
        mock_response.ok = True
        mock_response.content = b'{"features": [], "type": "FeatureCollection"}'
        mock_response.json.return_value = {"features": [], "type": "FeatureCollection"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        gw = MapboxGeocodingGateway(permanent=True)
        gw.forward_search(query="av santa fe", country="AR")

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        url = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("url", "")
        # The URL should hit the /forward endpoint
        assert "/forward" in url or "/forward" in str(call_kwargs)
        # autocomplete and permanent flags must be present
        all_args = str(call_kwargs)
        assert "autocomplete" in all_args
        assert "permanent" in all_args


class TestMapboxGeocodingGatewaySingleton:
    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_singleton_returns_same_instance(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        import app.gateways.mapbox_geocoding_gateway as mod

        mod._mapbox_geocoding_gateway_ephemeral = None
        gw1 = get_mapbox_geocoding_gateway()
        gw2 = get_mapbox_geocoding_gateway()
        assert gw1 is gw2
        mod._mapbox_geocoding_gateway_ephemeral = None
