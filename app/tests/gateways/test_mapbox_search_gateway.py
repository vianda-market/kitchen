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

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_suggest_routes_by_country_pe(self, mock_settings, _mock_token):
        """suggest(country='PE') returns the suggest_PE mock entry, not the generic AR one."""
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxSearchGateway()
        result = gw.suggest(query="Grau 323, Barranco, Lima", country="PE")
        assert "suggestions" in result
        assert len(result["suggestions"]) > 0
        country_code = result["suggestions"][0].get("context", {}).get("country", {}).get("country_code", "")
        assert country_code == "PE", f"Expected PE, got {country_code}"

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_suggest_routes_by_country_us(self, mock_settings, _mock_token):
        """suggest(country='US') returns the suggest_US mock entry."""
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxSearchGateway()
        result = gw.suggest(query="Pike Street, Seattle", country="US")
        assert "suggestions" in result
        country_code = result["suggestions"][0].get("context", {}).get("country", {}).get("country_code", "")
        assert country_code == "US", f"Expected US, got {country_code}"

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_suggest_falls_back_to_generic_when_no_country(self, mock_settings, _mock_token):
        """suggest with no country falls back to the generic 'suggest' key (AR data)."""
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxSearchGateway()
        result = gw.suggest(query="some address")
        assert "suggestions" in result
        # Generic fallback is AR data
        country_code = result["suggestions"][0].get("context", {}).get("country", {}).get("country_code", "")
        assert country_code == "AR", f"Expected AR fallback, got {country_code}"

    @patch("app.config.settings.get_mapbox_access_token", return_value=None)
    @patch("app.gateways.base_gateway.get_settings")
    def test_dev_mode_retrieve_pe_place_id_returns_pe_feature(self, mock_settings, _mock_token):
        """retrieve with a PE geocoding-cache place_id returns a PE Feature."""
        mock_settings.return_value = Mock(DEV_MODE=True)
        gw = MapboxSearchGateway()
        # This place_id comes from the geocoding cache (Grau 323, Barranco, Lima)
        pe_place_id = "dXJuOm1ieGFkcjowNjFhMjM5Ni02ZDAyLTRmMDItYmU0OS0zNTQ0YzFkYWUyMTQ"
        result = gw.retrieve(mapbox_id=pe_place_id)
        assert result.get("type") == "Feature"
        country_code = result.get("properties", {}).get("context", {}).get("country", {}).get("country_code", "")
        assert country_code == "PE", f"Expected PE, got {country_code}"


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
