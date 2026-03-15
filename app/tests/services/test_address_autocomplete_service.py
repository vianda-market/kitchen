"""
Unit tests for AddressAutocompleteService (suggest - autocomplete only, returns place_id and display_text).
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.address_autocomplete_service import AddressAutocompleteService


class TestAddressAutocompleteServiceSuggest:
    @patch("app.services.address_autocomplete_service.get_google_places_gateway")
    def test_suggest_returns_empty_for_empty_input(self, mock_get_gateway):
        svc = AddressAutocompleteService()
        assert svc.suggest(q="") == []
        assert svc.suggest(q="   ") == []
        mock_get_gateway.assert_called_once()

    @patch("app.services.address_autocomplete_service.get_google_places_gateway")
    def test_suggest_calls_autocomplete_only_returns_place_id_display_text(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.places_autocomplete.return_value = {
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
        mock_gateway.places_autocomplete.assert_called_once()
        mock_gateway.place_details.assert_not_called()

    @patch("app.services.address_autocomplete_service.get_google_places_gateway")
    def test_suggest_respects_limit(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.places_autocomplete.return_value = {
            "suggestions": [
                {"placePrediction": {"placeId": f"place_{i}", "text": {"text": f"Address {i}"}}}
                for i in range(5)
            ]
        }
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        result = svc.suggest(q="Main", limit=2)
        assert len(result) <= 2
        mock_gateway.place_details.assert_not_called()

    @patch("app.services.address_autocomplete_service.get_google_places_gateway")
    def test_suggest_passes_country_as_region(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.places_autocomplete.return_value = {"suggestions": []}
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        svc.suggest(q="test", country="ARG")
        mock_gateway.places_autocomplete.assert_called_once()
        call_kw = mock_gateway.places_autocomplete.call_args[1]
        assert call_kw["included_region_codes"] == ["AR"]

    @patch("app.services.address_autocomplete_service.get_google_places_gateway")
    def test_suggest_resolves_country_name_to_region(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.places_autocomplete.return_value = {"suggestions": []}
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        svc.suggest(q="test", country="Argentina")
        mock_gateway.places_autocomplete.assert_called_once()
        call_kw = mock_gateway.places_autocomplete.call_args[1]
        assert call_kw["included_region_codes"] == ["AR"]

    @patch("app.services.address_autocomplete_service.get_google_places_gateway")
    def test_suggest_does_not_pass_location_restriction(self, mock_get_gateway):
        """Suggest returns addresses anywhere in the country; no city bounds restriction."""
        mock_gateway = MagicMock()
        mock_gateway.places_autocomplete.return_value = {"suggestions": []}
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        svc.suggest(q="Av. Corrientes", country="AR", city="CABA", limit=5)
        mock_gateway.places_autocomplete.assert_called_once()
        call_kw = mock_gateway.places_autocomplete.call_args[1]
        assert call_kw.get("location_restriction") is None
