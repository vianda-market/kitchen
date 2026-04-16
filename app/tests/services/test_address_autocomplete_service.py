"""
Unit tests for AddressAutocompleteService (suggest - autocomplete only, returns place_id and display_text).
Tests use Mapbox format as the default provider.
"""

from unittest.mock import MagicMock, patch

from app.services.address_autocomplete_service import AddressAutocompleteService


class TestAddressAutocompleteServiceSuggest:
    @patch("app.services.address_autocomplete_service.get_search_gateway")
    def test_suggest_returns_empty_for_empty_input(self, mock_get_gateway):
        svc = AddressAutocompleteService()
        assert svc.suggest(q="") == []
        assert svc.suggest(q="   ") == []
        mock_get_gateway.assert_called_once()

    @patch("app.services.address_autocomplete_service.get_search_gateway")
    def test_suggest_returns_mapbox_suggestions_as_place_id_display_text(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.suggest.return_value = {
            "suggestions": [
                {
                    "mapbox_id": "dXJuOm1ieHBsYzo0NTk2Mjg",
                    "name": "Avenida Santa Fe 2567",
                    "full_address": "Avenida Santa Fe 2567, C1425 Buenos Aires, Argentina",
                    "context": {
                        "country": {"country_code": "AR", "name": "Argentina"},
                    },
                },
            ]
        }
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        result = svc.suggest(q="Av. Santa Fe", limit=5)

        assert len(result) == 1
        assert result[0]["place_id"] == "dXJuOm1ieHBsYzo0NTk2Mjg"
        assert "Avenida Santa Fe 2567" in result[0]["display_text"]
        assert result[0]["country_code"] == "AR"
        mock_gateway.suggest.assert_called_once()

    @patch("app.services.address_autocomplete_service.get_search_gateway")
    def test_suggest_respects_limit(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.suggest.return_value = {
            "suggestions": [{"mapbox_id": f"id_{i}", "full_address": f"Address {i}"} for i in range(5)]
        }
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        result = svc.suggest(q="Main", limit=2)
        assert len(result) <= 2

    @patch("app.services.address_autocomplete_service.get_search_gateway")
    def test_suggest_passes_country_alpha2(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.suggest.return_value = {"suggestions": []}
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        svc.suggest(q="test", country="AR")
        mock_gateway.suggest.assert_called_once()
        call_kw = mock_gateway.suggest.call_args[1]
        assert call_kw["country"] == "AR"

    @patch("app.services.address_autocomplete_service.get_search_gateway")
    def test_suggest_resolves_alpha3_to_alpha2(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.suggest.return_value = {"suggestions": []}
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        svc.suggest(q="test", country="ARG")
        call_kw = mock_gateway.suggest.call_args[1]
        assert call_kw["country"] == "AR"

    @patch("app.services.address_autocomplete_service.get_search_gateway")
    def test_suggest_resolves_country_name(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.suggest.return_value = {"suggestions": []}
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        svc.suggest(q="test", country="Argentina")
        call_kw = mock_gateway.suggest.call_args[1]
        assert call_kw["country"] == "AR"

    @patch("app.services.address_autocomplete_service.get_search_gateway")
    def test_suggest_passes_session_token(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.suggest.return_value = {"suggestions": []}
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        svc.suggest(q="test", session_token="my-token-123")
        call_kw = mock_gateway.suggest.call_args[1]
        assert call_kw["session_token"] == "my-token-123"

    @patch("app.services.address_autocomplete_service.get_search_gateway")
    def test_suggest_generates_session_token_when_not_provided(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.suggest.return_value = {"suggestions": []}
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        svc.suggest(q="test")
        call_kw = mock_gateway.suggest.call_args[1]
        assert call_kw["session_token"] is not None
        assert len(call_kw["session_token"]) == 36  # UUID format

    @patch("app.services.address_autocomplete_service.get_search_gateway")
    def test_suggest_handles_google_format_fallback(self, mock_get_gateway):
        """When ADDRESS_PROVIDER=google, response has placePrediction format."""
        mock_gateway = MagicMock()
        mock_gateway.suggest.return_value = {
            "suggestions": [
                {
                    "placePrediction": {
                        "placeId": "ChIJB_KWWvXKvJURs8VJkFcGiNE",
                        "text": {"text": "Av. Santa Fe 2567, CABA, Argentina"},
                    }
                },
            ]
        }
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        result = svc.suggest(q="Av. Santa Fe", limit=5)

        assert len(result) == 1
        assert result[0]["place_id"] == "ChIJB_KWWvXKvJURs8VJkFcGiNE"
        assert result[0]["display_text"] == "Av. Santa Fe 2567, CABA, Argentina"
