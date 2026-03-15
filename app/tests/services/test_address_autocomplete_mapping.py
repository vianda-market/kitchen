"""
Unit tests for address autocomplete mapping (Google → backend schema).
"""

import pytest
from app.services.address_autocomplete_mapping import (
    map_place_details_to_address,
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
        assert out["country_code"] == "AR"
        assert out["formatted_address"] == place_details["formattedAddress"]

    def test_country_override(self):
        place_details = {
            "addressComponents": [
                {"longText": "AR", "types": ["country"]},
            ],
        }
        out = map_place_details_to_address(place_details, country_override="USA")
        assert out["country_code"] == "US"
