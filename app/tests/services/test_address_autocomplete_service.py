"""
Unit tests for AddressAutocompleteService (suggest and validate).
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
    def test_suggest_calls_gateway_and_maps_results(self, mock_get_gateway):
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
        mock_gateway.place_details.return_value = {
            "formattedAddress": "Av. Santa Fe 2567, C1425 CABA, Argentina",
            "addressComponents": [
                {"longText": "2567", "types": ["street_number"]},
                {"longText": "Avenida Santa Fe", "types": ["route"]},
                {"longText": "Buenos Aires", "types": ["locality"]},
                {"longText": "Buenos Aires", "types": ["administrative_area_level_1"]},
                {"longText": "Argentina", "shortText": "AR", "types": ["country"]},
                {"longText": "C1425", "types": ["postal_code"]},
            ],
        }
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        result = svc.suggest(q="Av. Santa Fe", limit=5)

        assert len(result) == 1
        assert result[0]["country_code"] == "ARG"
        assert result[0]["building_number"] == "2567"
        mock_gateway.places_autocomplete.assert_called_once()
        mock_gateway.place_details.assert_called_once_with("ChIJB_KWWvXKvJURs8VJkFcGiNE")

    @patch("app.services.address_autocomplete_service.get_google_places_gateway")
    def test_suggest_respects_limit(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.places_autocomplete.return_value = {
            "suggestions": [
                {"placePrediction": {"placeId": f"place_{i}", "text": {"text": f"Address {i}"}}}
                for i in range(5)
            ]
        }
        mock_gateway.place_details.return_value = {
            "addressComponents": [
                {"longText": "1", "types": ["street_number"]},
                {"longText": "Main St", "types": ["route"]},
                {"longText": "City", "types": ["locality"]},
                {"longText": "State", "types": ["administrative_area_level_1"]},
                {"longText": "US", "types": ["country"]},
                {"longText": "12345", "types": ["postal_code"]},
            ],
        }
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        result = svc.suggest(q="Main", limit=2)
        assert len(result) <= 2
        assert mock_gateway.place_details.call_count == min(2, len(result))

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


class TestAddressAutocompleteServiceValidate:
    @patch("app.services.address_autocomplete_service.get_google_places_gateway")
    def test_validate_returns_result_shape(self, mock_get_gateway):
        mock_gateway = MagicMock()
        mock_gateway.validate_address.return_value = {
            "result": {
                "verdict": {"addressComplete": True},
                "address": {
                    "formattedAddress": "Av. Santa Fe 2567, CABA, Argentina",
                    "addressComponents": [
                        {"componentName": {"text": "2567"}, "componentType": "street_number"},
                        {"componentName": {"text": "Avenida Santa Fe"}, "componentType": "route"},
                        {"componentName": {"text": "Buenos Aires"}, "componentType": "locality"},
                        {"componentName": {"text": "CABA"}, "componentType": "administrative_area_level_1"},
                        {"componentName": {"text": "Argentina"}, "componentType": "country"},
                        {"componentName": {"text": "C1425"}, "componentType": "postal_code"},
                    ],
                },
            },
        }
        mock_get_gateway.return_value = mock_gateway

        svc = AddressAutocompleteService()
        body = {
            "street_name": "Santa Fe",
            "street_type": "Ave",
            "building_number": "2567",
            "city": "Buenos Aires",
            "province": "CABA",
            "postal_code": "C1425",
            "country_code": "ARG",
        }
        result = svc.validate(body)

        assert "is_valid" in result
        assert "normalized" in result
        assert "formatted_address" in result
        assert "confidence" in result
        assert "message" in result
        assert result["is_valid"] is True
        assert result["normalized"]["country_code"] == "ARG"
