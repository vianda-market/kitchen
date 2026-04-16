"""
Unit tests for address autocomplete mapping (Mapbox GeoJSON -> backend schema).
"""

import pytest

from app.services.address_autocomplete_mapping import (
    _route_to_street_type_and_name,
    extract_place_details_geolocation,
    get_city_candidates_from_place_details,
    map_place_details_to_address,
)

# Shared fixture: Mapbox GeoJSON Feature
MAPBOX_FEATURE_SANTA_FE = {
    "type": "Feature",
    "geometry": {
        "type": "Point",
        "coordinates": [-58.4023328, -34.5880634],
    },
    "properties": {
        "mapbox_id": "dXJuOm1ieHBsYzo0NTk2Mjg",
        "full_address": "Avenida Santa Fe 2567, C1425 Buenos Aires, Argentina",
        "bbox": [-58.4033, -34.5891, -58.4013, -34.5871],
        "context": {
            "country": {"country_code": "AR", "name": "Argentina"},
            "region": {"name": "Buenos Aires"},
            "place": {"name": "Buenos Aires"},
            "postcode": {"name": "C1425"},
            "street": {"name": "Avenida Santa Fe"},
            "address": {"address_number": "2567"},
        },
    },
}


class TestRouteToStreetTypeAndName:
    def test_avenida(self):
        st, name = _route_to_street_type_and_name("Avenida Corrientes")
        assert st == "ave"
        assert name == "Corrientes"

    def test_av_prefix(self):
        st, name = _route_to_street_type_and_name("Av. Santa Fe")
        assert st == "ave"
        assert "Santa Fe" in name

    def test_calle(self):
        st, name = _route_to_street_type_and_name("Calle Florida")
        assert st == "st"
        assert name == "Florida"

    def test_unknown_prefix_defaults_to_st(self):
        st, name = _route_to_street_type_and_name("Some Road Name")
        assert st == "st"
        assert name == "Some Road Name"

    def test_empty_input(self):
        st, name = _route_to_street_type_and_name("")
        assert st == "st"
        assert name == ""


class TestMapPlaceDetailsToAddress:
    def test_full_mapbox_feature(self):
        out = map_place_details_to_address(MAPBOX_FEATURE_SANTA_FE)
        assert out["building_number"] == "2567"
        assert out["street_type"] == "ave"
        assert "Santa Fe" in out["street_name"]
        assert out["city"] == "Buenos Aires"
        assert out["province"] == "Buenos Aires"
        assert out["postal_code"] == "C1425"
        assert out["country_code"] == "AR"
        assert "Avenida Santa Fe 2567" in out["formatted_address"]

    def test_country_override(self):
        out = map_place_details_to_address(MAPBOX_FEATURE_SANTA_FE, country_override="US")
        assert out["country_code"] == "US"

    def test_missing_context_uses_defaults(self):
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {
                "mapbox_id": "test",
                "full_address": "Unknown",
                "context": {},
            },
        }
        out = map_place_details_to_address(feature)
        assert out["street_name"] == "\u2014"
        assert out["city"] == "\u2014"
        assert out["country_code"] == ""


class TestExtractPlaceDetailsGeolocation:
    def test_coordinates_swapped_from_geojson(self):
        geo = extract_place_details_geolocation(MAPBOX_FEATURE_SANTA_FE)
        # GeoJSON is [lng, lat]; our schema is (lat, lng)
        assert geo["latitude"] == pytest.approx(-34.5880634)
        assert geo["longitude"] == pytest.approx(-58.4023328)

    def test_mapbox_id_stored_as_place_id(self):
        geo = extract_place_details_geolocation(MAPBOX_FEATURE_SANTA_FE)
        assert geo["place_id"] == "dXJuOm1ieHBsYzo0NTk2Mjg"

    def test_formatted_address_in_google_column(self):
        geo = extract_place_details_geolocation(MAPBOX_FEATURE_SANTA_FE)
        assert "Avenida Santa Fe 2567" in geo["formatted_address_google"]

    def test_bbox_converted_to_viewport(self):
        geo = extract_place_details_geolocation(MAPBOX_FEATURE_SANTA_FE)
        assert geo["viewport"] is not None
        assert geo["viewport"]["low"]["lat"] == pytest.approx(-34.5891)
        assert geo["viewport"]["high"]["lng"] == pytest.approx(-58.4013)

    def test_missing_coordinates_returns_none(self):
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": []},
            "properties": {"mapbox_id": "test", "full_address": "Test"},
        }
        geo = extract_place_details_geolocation(feature)
        assert geo["latitude"] is None
        assert geo["longitude"] is None


class TestGetCityCandidates:
    def test_city_from_place_context(self):
        candidates = get_city_candidates_from_place_details(MAPBOX_FEATURE_SANTA_FE)
        assert "Buenos Aires" in candidates

    def test_multiple_candidates(self):
        feature = {
            "properties": {
                "context": {
                    "place": {"name": "Buenos Aires"},
                    "district": {"name": "Palermo"},
                    "neighborhood": {"name": "Alto Palermo"},
                },
            },
        }
        candidates = get_city_candidates_from_place_details(feature)
        assert candidates == ["Buenos Aires", "Palermo", "Alto Palermo"]

    def test_empty_context(self):
        feature = {"properties": {"context": {}}}
        candidates = get_city_candidates_from_place_details(feature)
        assert candidates == []
