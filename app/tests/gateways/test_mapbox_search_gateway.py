"""
Unit tests for MapboxSearchGateway (suggest + retrieve).
"""

from unittest.mock import Mock, patch

from app.gateways.mapbox_search_gateway import MapboxSearchGateway, get_mapbox_search_gateway


class TestMapboxSearchGatewaySuggest:
    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_returns_mock_suggestions(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxSearchGateway()
        result = gw.suggest(query="Av. Santa Fe")
        assert "suggestions" in result
        assert len(result["suggestions"]) > 0
        assert "mapbox_id" in result["suggestions"][0]

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_retrieve_returns_feature(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxSearchGateway()
        result = gw.retrieve(mapbox_id="dXJuOm1ieHBsYzo0NTk2Mjg")
        assert result.get("type") == "Feature"
        assert "geometry" in result
        assert "properties" in result

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_retrieve_fallback_to_first(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxSearchGateway()
        result = gw.retrieve(mapbox_id="nonexistent-id")
        assert result.get("type") == "Feature"

    @patch("requests.get")
    @patch("app.config.settings.get_mapbox_access_token", return_value="pk.test123")
    @patch("app.gateways.base_gateway.get_settings")
    def test_prod_mode_suggest_makes_http_call(self, mock_settings, mock_token, mock_get):
        mock_settings.return_value = Mock(DEV_MODE=True)
        mock_response = Mock()
        mock_response.ok = True
        mock_response.content = b'{"suggestions": []}'
        mock_response.json.return_value = {"suggestions": []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        gw = MapboxSearchGateway()
        gw.suggest(query="test", country="AR", session_token="tok-123")

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "suggest" in call_args[0][0]
        assert call_args[1]["params"]["q"] == "test"
        assert call_args[1]["params"]["country"] == "AR"
        assert call_args[1]["params"]["session_token"] == "tok-123"


class TestMapboxSearchGatewaySingleton:
    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_singleton_returns_same_instance(self, mock_settings, _mock_token):
        mock_settings.return_value = Mock(DEV_MODE=True)
        import app.gateways.mapbox_search_gateway as mod

        mod._mapbox_search_gateway = None
        gw1 = get_mapbox_search_gateway()
        gw2 = get_mapbox_search_gateway()
        assert gw1 is gw2
        mod._mapbox_search_gateway = None
