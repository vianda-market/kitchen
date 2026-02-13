"""
Unit tests for address autocomplete mapping (Google → backend schema).
"""

import pytest
from app.services.address_autocomplete_mapping import (
    map_place_details_to_address,
    map_validation_result_to_address,
    build_validation_api_request,
    _route_to_street_type_and_name,
)


class TestRouteToStreetTypeAndName:
    def test_avenida(self):
        st, name = _route_to_street_type_and_name("Avenida Corrientes")
        assert st == "Ave"
        assert name == "Corrientes"

    def test_av_prefix(self):
        st, name = _route_to_street_type_and_name("Av. Santa Fe")
        assert st == "Ave"
        assert "Santa Fe" in name

    def test_calle(self):
        st, name = _route_to_street_type_and_name("Calle Florida")
        assert st == "St"
        assert name == "Florida"

    def test_unknown_prefix_defaults_to_st(self):
        st, name = _route_to_street_type_and_name("Some Road Name")
        assert st == "St"
        assert name == "Some Road Name"


class TestMapPlaceDetailsToAddress:
    def test_full_components(self):
        place_details = {
            "formattedAddress": "Av. Santa Fe 2567, C1425 CABA, Argentina",
            "addressComponents": [
                {"longText": "2567", "shortText": "2567", "types": ["street_number"]},
                {"longText": "Avenida Santa Fe", "shortText": "Av. Santa Fe", "types": ["route"]},
                {"longText": "Buenos Aires", "shortText": "CABA", "types": ["locality"]},
                {"longText": "Buenos Aires", "shortText": "Buenos Aires", "types": ["administrative_area_level_1"]},
                {"longText": "Argentina", "shortText": "AR", "types": ["country"]},
                {"longText": "C1425", "shortText": "C1425", "types": ["postal_code"]},
            ],
        }
        out = map_place_details_to_address(place_details)
        assert out["building_number"] == "2567"
        assert out["street_type"] == "Ave"
        assert "Santa Fe" in out["street_name"]
        assert out["city"] == "Buenos Aires"
        assert out["province"] == "Buenos Aires"
        assert out["postal_code"] == "C1425"
        assert out["country_code"] == "ARG"
        assert out["formatted_address"] == place_details["formattedAddress"]

    def test_country_override(self):
        place_details = {
            "addressComponents": [
                {"longText": "AR", "types": ["country"]},
            ],
        }
        out = map_place_details_to_address(place_details, country_override="USA")
        assert out["country_code"] == "USA"


class TestMapValidationResultToAddress:
    def test_valid_result(self):
        raw = {
            "result": {
                "verdict": {"addressComplete": True, "validationGranularity": "PREMISE"},
                "address": {
                    "formattedAddress": "Av. Santa Fe 2567, C1425 CABA, Argentina",
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
        is_valid, normalized, formatted, confidence, message = map_validation_result_to_address(raw)
        assert is_valid is True
        assert normalized is not None
        assert normalized["country_code"] == "ARG"
        assert formatted == raw["result"]["address"]["formattedAddress"]
        assert confidence in ("high", "medium", "low")

    def test_invalid_result(self):
        raw = {
            "result": {
                "verdict": {"addressComplete": False},
                "address": None,
            },
        }
        is_valid, normalized, formatted, confidence, message = map_validation_result_to_address(raw)
        assert is_valid is False
        assert normalized is None
        assert "could not be validated" in (message or "")


class TestBuildValidationApiRequest:
    def test_basic(self):
        payload = build_validation_api_request(
            street_name="Corrientes",
            street_type="Ave",
            building_number="1234",
            city="Buenos Aires",
            province="CABA",
            postal_code="C1043",
            country_code="ARG",
        )
        assert payload["regionCode"] == "AR"
        assert "1234" in payload["addressLines"][0]
        assert payload["locality"] == "Buenos Aires"
        assert payload["administrativeArea"] == "CABA"
        assert payload["postalCode"] == "C1043"
