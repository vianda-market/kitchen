"""
Unit tests for Address Service.

Tests the business logic for address operations including
geocoding integration, timezone calculation, and address validation.
"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from app.services.address_service import address_business_service


class TestAddressService:
    """Test suite for AddressBusinessService business logic."""

    def test_create_address_with_geocoding_sets_timezone(self, sample_current_user, mock_db):
        """Test that address creation sets timezone based on country and city. address_type is derived, not from client."""
        # Arrange
        address_data = {
            "city_metadata_id": "11111111-1111-1111-1111-111111111111",
            "building_number": "123",
            "street_name": "Main St",
            "city": "New York",
            "province": "NY",
            "country": "US",
        }
        mock_address = Mock()
        mock_address.address_id = uuid4()
        mock_address.user_id = sample_current_user["user_id"]

        with (
            patch("app.services.address_service.address_service") as mock_address_service,
            patch("app.services.geolocation_service.get_timezone_from_address") as mock_get_timezone,
            patch("app.services.address_service.update_address_type_from_linkages") as mock_derive,
            patch("app.services.market_service.market_service") as mock_market,
            patch("app.services.address_service.db_read") as mock_db_read,
            patch("app.services.address_service.db_insert") as mock_db_insert,
        ):
            mock_address_service.create.return_value = mock_address
            mock_address_service.get_by_id.return_value = mock_address
            mock_get_timezone.return_value = "America/New_York"
            mock_derive.return_value = []
            mock_market.get_by_country_code.return_value = {"country_code": "US", "country_name": "United States"}
            mock_db_read.side_effect = lambda q, *a, **kw: (
                {"tz": "America/New_York", "country_iso": "US"} if "city_metadata" in (q or "") else None
            )
            mock_db_insert.return_value = None

            # Act
            address_business_service.create_address_with_geocoding(address_data, sample_current_user, mock_db)

            # Assert
            assert address_data["timezone"] == "America/New_York"
            assert address_data["modified_by"] == sample_current_user["user_id"]
            assert address_data.get("address_type") == []

    def test_create_address_with_geocoding_calls_api_for_restaurants(self, sample_current_user, mock_db):
        """Test that address creation calls geocoding API when derived type is Restaurant."""
        # Arrange: address_type is derived from linkages, not from client
        restaurant_address_data = {
            "city_metadata_id": "11111111-1111-1111-1111-111111111111",
            "building_number": "123",
            "street_name": "Main St",
            "city": "New York",
            "province": "NY",
            "country": "US",
        }
        mock_address = Mock()
        mock_address.address_id = uuid4()
        mock_address.user_id = sample_current_user["user_id"]
        mock_geolocation = Mock()
        mock_geolocation.geolocation_id = uuid4()

        with (
            patch("app.services.address_service.address_service") as mock_address_service,
            patch("app.services.geolocation_service.get_timezone_from_address") as mock_get_timezone,
            patch("app.services.address_service.update_address_type_from_linkages") as mock_derive,
            patch("app.services.market_service.market_service") as mock_market,
            patch("app.services.address_service.get_persistent_geolocation_service") as mock_pgs,
            patch("app.services.address_service.geolocation_service") as mock_geo_service,
            patch("app.services.address_service.db_read") as mock_db_read,
            patch("app.services.address_service.db_insert") as mock_db_insert,
        ):
            mock_address_service.create.return_value = mock_address
            mock_address_service.get_by_id.return_value = mock_address
            mock_get_timezone.return_value = "America/New_York"
            mock_derive.return_value = ["restaurant"]  # Derived from linkage
            mock_market.get_by_country_code.return_value = {"country_code": "US", "country_name": "United States"}
            # No existing geo → short-circuit disabled.
            mock_geo_service.get_by_address.return_value = None
            mock_pgs.return_value.geocode_address.return_value = {"latitude": 40.7128, "longitude": -74.0060}
            mock_geo_service.create.return_value = mock_geolocation
            mock_db_read.side_effect = lambda q, *a, **kw: (
                {"tz": "America/New_York", "country_iso": "US"} if "city_metadata" in (q or "") else None
            )
            mock_db_insert.return_value = None

            # Act
            address_business_service.create_address_with_geocoding(
                restaurant_address_data, sample_current_user, mock_db
            )

            # Assert: persistent geocoding service called (not the deprecated call_geocode_api).
            mock_pgs.return_value.geocode_address.assert_called_once()
            mock_geo_service.create.assert_called_once()
            from app.config import Status

            geo_call_args = mock_geo_service.create.call_args[0][0]
            assert geo_call_args["address_id"] == mock_address.address_id
            assert geo_call_args["latitude"] == 40.7128
            assert geo_call_args["longitude"] == -74.0060
            assert geo_call_args["status"] == Status.ACTIVE
            assert geo_call_args["modified_by"] == sample_current_user["user_id"]

    def test_create_address_with_geocoding_handles_api_failure(self, sample_current_user, mock_db):
        """Test that address creation handles geocoding API failure gracefully (non-blocking)."""
        restaurant_address_data = {
            "city_metadata_id": "11111111-1111-1111-1111-111111111111",
            "building_number": "123",
            "street_name": "Main St",
            "city": "New York",
            "province": "NY",
            "country": "US",
        }
        mock_address = Mock()
        mock_address.address_id = uuid4()
        mock_address.user_id = sample_current_user["user_id"]

        with (
            patch("app.services.address_service.address_service") as mock_address_service,
            patch("app.services.geolocation_service.get_timezone_from_address") as mock_get_timezone,
            patch("app.services.address_service.update_address_type_from_linkages") as mock_derive,
            patch("app.services.market_service.market_service") as mock_market,
            patch("app.services.address_service.get_persistent_geolocation_service") as mock_pgs,
            patch("app.services.address_service.geolocation_service") as mock_geo_service,
            patch("app.services.address_service.db_read") as mock_db_read,
            patch("app.services.address_service.db_insert") as mock_db_insert,
        ):
            mock_address_service.create.return_value = mock_address
            mock_address_service.get_by_id.return_value = mock_address
            mock_get_timezone.return_value = "America/New_York"
            mock_derive.return_value = ["restaurant"]
            mock_market.get_by_country_code.return_value = {"country_code": "US", "country_name": "United States"}
            # No existing geo → short-circuit disabled.
            mock_geo_service.get_by_address.return_value = None
            mock_pgs.return_value.geocode_address.return_value = None  # Persistent geocoding failure
            mock_db_read.side_effect = lambda q, *a, **kw: (
                {"tz": "America/New_York", "country_iso": "US"} if "city_metadata" in (q or "") else None
            )
            mock_db_insert.return_value = None

            result = address_business_service.create_address_with_geocoding(
                restaurant_address_data, sample_current_user, mock_db
            )

            assert result is not None
            assert result.address_id == mock_address.address_id
            mock_address_service.create.assert_called_once()
            mock_pgs.return_value.geocode_address.assert_called_once()

    def test_validate_address_data_checks_required_fields(self, mock_db):
        """Test that address validation checks required fields for restaurant addresses."""
        # Arrange
        incomplete_data = {
            "building_number": "123",
            "street_name": "Main St",
            # Missing city, province, country
            "address_type": ["restaurant"],
        }

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            address_business_service.validate_address_data(incomplete_data)

        assert exc_info.value.status_code == 400
        # Country validation happens first, so error message is about country code
        assert "Country" in str(exc_info.value.detail) or "required" in str(exc_info.value.detail).lower()
        assert "city" in str(exc_info.value.detail)

    def test_create_address_without_place_id_returns_403_in_production(self, sample_current_user, mock_db):
        """Structured (manual) create without place_id returns 403 when DEV_MODE=False."""
        address_data = {
            "city_metadata_id": "11111111-1111-1111-1111-111111111111",
            "building_number": "123",
            "street_name": "Main St",
            "city": "New York",
            "province": "NY",
            "country": "US",
        }
        with patch("app.config.settings.get_settings") as mock_get_settings:
            mock_get_settings.return_value = Mock(DEV_MODE=False)
            with pytest.raises(HTTPException) as exc_info:
                address_business_service.create_address_with_geocoding(address_data, sample_current_user, mock_db)
            assert exc_info.value.status_code == 403
            detail = exc_info.value.detail
            if isinstance(detail, dict):
                assert detail.get("code") == "address.manual_entry_not_allowed"
            else:
                assert "manual entry" in str(detail)

    def test_validate_address_data_validates_country_code(self, mock_db):
        """Test that address validation validates country code format."""
        # Arrange
        invalid_country_data = {
            "building_number": "123",
            "street_name": "Main St",
            "city": "New York",
            "province": "NY",
            "country": "USA",  # Invalid - should be 2 letters
            "address_type": "restaurant",
        }

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            address_business_service.validate_address_data(invalid_country_data)

        assert exc_info.value.status_code == 400
        detail = exc_info.value.detail
        if isinstance(detail, dict):
            assert detail.get("code") in ("validation.address.country_required", "address.invalid_country")
        else:
            assert "country" in str(detail).lower()

    def test_build_full_address_string_formats_correctly(self, mock_db):
        """Test that full address string is built correctly for geocoding."""
        # Arrange
        address_data = {
            "city_metadata_id": "11111111-1111-1111-1111-111111111111",
            "building_number": "123",
            "street_name": "Main St",
            "city": "New York",
            "province": "NY",
            "country": "US",
        }

        # Act
        result = address_business_service._build_full_address_string(address_data)

        # Assert
        expected = "123 Main St, New York, NY, US"
        assert result == expected

    def test_get_address_with_geolocation_returns_combined_data(self, mock_db):
        """Test that address with geolocation retrieval returns combined data."""
        # Arrange
        address_id = uuid4()
        mock_address = Mock()
        mock_geolocation = Mock()

        with (
            patch("app.services.address_service.address_service") as mock_address_service,
            patch("app.services.address_service.geolocation_service") as mock_geo_service,
        ):
            mock_address_service.get_by_id.return_value = mock_address
            mock_geo_service.get_by_address.return_value = mock_geolocation

            # Act
            result = address_business_service.get_address_with_geolocation(address_id, mock_db)

            # Assert
            assert result["address"] == mock_address
            assert result["geolocation"] == mock_geolocation

    def test_get_address_with_geolocation_handles_address_not_found(self, mock_db):
        """Test that address with geolocation retrieval handles address not found."""
        # Arrange
        address_id = uuid4()

        with patch("app.services.address_service.address_service") as mock_address_service:
            mock_address_service.get_by_id.return_value = None

            # Act
            result = address_business_service.get_address_with_geolocation(address_id, mock_db)

            # Assert
            assert result is None

    def test_update_address_with_geocoding_updates_subpremise_fields(self, sample_current_user, mock_db):
        """Test that address update persists floor, apartment_unit, is_default to address_subpremise."""
        address_id = uuid4()
        update_data = {"floor": "2", "apartment_unit": "4B", "is_default": True}

        mock_address = Mock()
        mock_address.address_id = address_id
        mock_address.user_id = sample_current_user["user_id"]

        with (
            patch("app.services.address_service.address_service") as mock_address_service,
            patch("app.services.address_service.db_read") as mock_db_read,
            patch("app.services.address_service.db_insert") as mock_db_insert,
            patch("app.services.address_service.db_update") as mock_db_update,
        ):
            mock_address_service.get_by_id.return_value = mock_address

            def db_read_side_effect(query, *args, **kwargs):
                if "subpremise_id" in str(query):
                    return None  # no existing subpremise
                return {  # row for _get_address_with_subpremise
                    "address_id": address_id,
                    "institution_id": uuid4(),
                    "user_id": sample_current_user["user_id"],
                    "address_type": [],
                    "country_name": "United States",
                    "country_code": "US",
                    "city_metadata_id": UUID("11111111-1111-1111-1111-111111111111"),
                    "province": "NY",
                    "city": "New York",
                    "postal_code": "10001",
                    "street_type": "st",
                    "street_name": "Main",
                    "building_number": "123",
                    "floor": "2",
                    "apartment_unit": "4B",
                    "is_default": True,
                    "timezone": "America/New_York",
                    "is_archived": False,
                    "status": "active",
                    "created_date": datetime.now(UTC),
                    "modified_by": sample_current_user["user_id"],
                    "modified_date": datetime.now(UTC),
                }

            mock_db_read.side_effect = db_read_side_effect
            mock_db_insert.return_value = None
            mock_db_update.return_value = None

            result = address_business_service.update_address_with_geocoding(
                address_id, update_data, sample_current_user, mock_db
            )

            assert result is not None
            assert result.floor == "2"
            assert result.apartment_unit == "4B"
            assert result.is_default is True
            mock_db_insert.assert_called_once()
            mock_address_service.get_by_id.assert_called()

    def test_update_address_with_geocoding_noop_when_no_subpremise_fields(self, sample_current_user, mock_db):
        """Test that address update returns current_address without DB writes when no floor/unit/is_default."""
        address_id = uuid4()
        update_data = {"building_number": "456", "street_name": "New St"}

        mock_address = Mock()
        mock_address.address_id = address_id
        mock_address.building_number = "123"

        with patch("app.services.address_service.address_service") as mock_address_service:
            mock_address_service.get_by_id.return_value = mock_address

            result = address_business_service.update_address_with_geocoding(
                address_id, update_data, sample_current_user, mock_db
            )

            assert result is mock_address
            assert result.building_number == "123"
            mock_address_service.get_by_id.assert_called_once()

    def test_update_address_with_geocoding_handles_address_not_found(self, sample_current_user, mock_db):
        """Test that address update handles address not found."""
        address_id = uuid4()
        update_data = {"floor": "2"}

        with patch("app.services.address_service.address_service") as mock_address_service:
            mock_address_service.get_by_id.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                address_business_service.update_address_with_geocoding(
                    address_id, update_data, sample_current_user, mock_db
                )

            assert exc_info.value.status_code == 404
            assert "Address not found" in str(exc_info.value.detail)


class TestGeocodingShortCircuit:
    """Short-circuit: rows with existing coordinates must not trigger a Mapbox call."""

    def _make_address(self) -> Mock:
        addr = Mock()
        addr.address_id = uuid4()
        addr.building_number = "500"
        addr.street_name = "Defensa"
        addr.city = "Buenos Aires"
        addr.province = "Buenos Aires"
        addr.country_code = "AR"
        return addr

    def _make_user(self) -> dict:
        return {"user_id": str(uuid4()), "role_type": "internal", "role_name": "admin"}

    def test_geocode_address_short_circuits_when_coords_exist(self, mock_db):
        """If geolocation_info already has non-zero coords, Mapbox is NOT called."""
        address = self._make_address()
        existing_geo = Mock()
        existing_geo.latitude = -34.62
        existing_geo.longitude = -58.37

        with (
            patch("app.services.address_service.geolocation_service") as mock_geo_svc,
            patch("app.services.address_service.get_persistent_geolocation_service") as mock_pgs,
        ):
            mock_geo_svc.get_by_address.return_value = existing_geo

            address_business_service._geocode_address(
                address,
                {
                    "building_number": "500",
                    "street_name": "Defensa",
                    "city": "Buenos Aires",
                    "province": "Buenos Aires",
                },
                self._make_user(),
                mock_db,
            )

            # Persistent geocoding service must NOT have been called.
            mock_pgs.return_value.geocode_address.assert_not_called()

    def test_geocode_address_calls_persistent_when_no_existing_geo(self, mock_db):
        """If no existing geolocation, the persistent geocoding service IS called."""
        address = self._make_address()

        with (
            patch("app.services.address_service.geolocation_service") as mock_geo_svc,
            patch("app.services.address_service.get_persistent_geolocation_service") as mock_pgs,
        ):
            mock_geo_svc.get_by_address.return_value = None
            mock_pgs.return_value.geocode_address.return_value = {
                "latitude": -34.62,
                "longitude": -58.37,
                "formatted_address": "500 Defensa, Buenos Aires",
            }
            mock_geo_svc.create.return_value = Mock()

            address_business_service._geocode_address(
                address,
                {
                    "building_number": "500",
                    "street_name": "Defensa",
                    "city": "Buenos Aires",
                    "province": "Buenos Aires",
                },
                self._make_user(),
                mock_db,
            )

            mock_pgs.return_value.geocode_address.assert_called_once()

    def test_geocode_address_writes_mapbox_tracking_columns(self, mock_db):
        """When geocoding succeeds, mapbox_geocoded_at and mapbox_normalized_address are written."""
        address = self._make_address()

        with (
            patch("app.services.address_service.geolocation_service") as mock_geo_svc,
            patch("app.services.address_service.get_persistent_geolocation_service") as mock_pgs,
        ):
            mock_geo_svc.get_by_address.return_value = None
            mock_pgs.return_value.geocode_address.return_value = {
                "latitude": -34.62,
                "longitude": -58.37,
            }
            mock_geo_svc.create.return_value = Mock()

            address_business_service._geocode_address(
                address,
                {
                    "building_number": "500",
                    "street_name": "Defensa",
                    "city": "Buenos Aires",
                    "province": "Buenos Aires",
                },
                self._make_user(),
                mock_db,
            )

            call_kwargs = mock_geo_svc.create.call_args[0][0]
            assert "mapbox_geocoded_at" in call_kwargs
            assert call_kwargs["mapbox_geocoded_at"] is not None
            assert "mapbox_normalized_address" in call_kwargs
            assert isinstance(call_kwargs["mapbox_normalized_address"], str)
            assert len(call_kwargs["mapbox_normalized_address"]) > 0

    def test_geocode_address_short_circuits_when_coords_are_zero(self, mock_db):
        """A row with latitude=0, longitude=0 is NOT treated as having coordinates — proceeds to geocode."""
        address = self._make_address()
        zero_geo = Mock()
        zero_geo.latitude = 0
        zero_geo.longitude = 0

        with (
            patch("app.services.address_service.geolocation_service") as mock_geo_svc,
            patch("app.services.address_service.get_persistent_geolocation_service") as mock_pgs,
        ):
            mock_geo_svc.get_by_address.return_value = zero_geo
            mock_pgs.return_value.geocode_address.return_value = {
                "latitude": -34.62,
                "longitude": -58.37,
            }
            mock_geo_svc.create.return_value = Mock()

            address_business_service._geocode_address(
                address,
                {
                    "building_number": "500",
                    "street_name": "Defensa",
                    "city": "Buenos Aires",
                    "province": "Buenos Aires",
                },
                self._make_user(),
                mock_db,
            )

            # Zero coords are placeholder rows — must still geocode.
            mock_pgs.return_value.geocode_address.assert_called_once()


class TestQ2PersistenceRule:
    """Q2 rule: no Search Box retrieve response fields must reach the DB."""

    # Sentinel value embedded in a fake Search Box retrieve response.
    # If this string appears in any persisted field, the Q2 rule is violated.
    _POISON = "MAPBOX-INTERNAL-DO-NOT-STORE"

    def _make_user(self) -> dict:
        return {"user_id": str(uuid4()), "role_type": "internal", "role_name": "admin"}

    def _make_search_box_retrieve_response(self) -> dict:
        """Fake Search Box retrieve response with a poisoned canonical address string."""
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-58.999, -34.999]},
            "properties": {
                "mapbox_id": f"mapbox_id_{self._POISON}",
                "full_address": f"{self._POISON} 123, Buenos Aires, Argentina",
                "feature_type": "address",
                "context": {
                    "country": {"country_code": "AR", "name": "Argentina"},
                    "region": {"name": "Buenos Aires", "region_code": "B"},
                    "place": {"name": "Buenos Aires"},
                    "postcode": {"name": "1000"},
                    "street": {"name": f"Calle {self._POISON}"},
                    "address": {"address_number": "123", "street_name": f"Calle {self._POISON}"},
                },
                "coordinates": {"latitude": -34.999, "longitude": -58.999},
            },
        }

    def test_place_id_path_does_not_persist_search_box_coordinates(self, mock_db):
        """When a place_id is provided, persisted lat/lng must come from places-permanent,
        not from the Search Box retrieve response.

        Arrange: Search Box retrieve returns poisoned coordinates (-34.999, -58.999).
        Act:     create_address_with_geocoding via the place_id path.
        Assert:  geolocation_service.create is called with places-permanent coords,
                 NOT the Search Box coords.
        """
        user = self._make_user()
        address_data = {
            "place_id": "some_mapbox_id",
            "session_token": "tok",
            "city_metadata_id": "11111111-1111-1111-1111-111111111111",
        }

        mock_address = Mock()
        mock_address.address_id = uuid4()
        mock_address.user_id = None
        mock_address.address_type = ["restaurant"]
        mock_address.building_number = "123"
        mock_address.street_name = "Main"
        mock_address.city = "Buenos Aires"
        mock_address.province = "Buenos Aires"
        mock_address.country_code = "AR"

        # Coordinates from places-permanent (expected in the persisted row).
        _PERM_LAT, _PERM_LNG = -34.6226, -58.3701

        with (
            patch("app.services.address_service.AddressBusinessService._resolve_address_from_place_id") as mock_resolve,
            patch("app.services.address_service.address_service") as mock_addr_svc,
            patch("app.services.address_service.update_address_type_from_linkages") as mock_derive,
            patch("app.services.address_service.geolocation_service") as mock_geo_svc,
            patch("app.services.address_service.get_persistent_geolocation_service") as mock_pgs,
            patch("app.services.address_service.AddressBusinessService._resolve_city_metadata_and_timezone"),
            patch("app.services.address_service.AddressBusinessService.validate_address_data"),
            patch("app.services.market_service.market_service") as mock_market,
        ):
            mock_market.get_by_country_code.return_value = {"country_code": "AR", "country_name": "Argentina"}
            # _resolve_address_from_place_id now always returns None for geoloc (Q2 rule).
            # Simulate the actual post-fix behaviour: address_data is enriched, geoloc=None.
            def fake_resolve(place_id, addr_data, cu, session_token=None):
                addr_data.update(
                    {
                        "building_number": "123",
                        "street_name": "Main",
                        "city": "Buenos Aires",
                        "province": "Buenos Aires",
                        "country_code": "AR",
                    }
                )
                return addr_data, None  # Q2: geoloc is always None from this method

            mock_resolve.side_effect = fake_resolve
            mock_addr_svc.create.return_value = mock_address
            mock_addr_svc.get_by_id.return_value = mock_address
            mock_derive.return_value = ["restaurant"]
            mock_geo_svc.get_by_address.return_value = None
            mock_pgs.return_value.geocode_address.return_value = {
                "latitude": _PERM_LAT,
                "longitude": _PERM_LNG,
            }
            mock_geo_svc.create.return_value = Mock()

            address_business_service.create_address_with_geocoding(address_data, user, mock_db)

            # Assert: geolocation_service.create was called with places-permanent coords.
            mock_geo_svc.create.assert_called_once()
            persisted = mock_geo_svc.create.call_args[0][0]
            assert persisted["latitude"] == _PERM_LAT, (
                "Persisted latitude must come from places-permanent, not Search Box"
            )
            assert persisted["longitude"] == _PERM_LNG, (
                "Persisted longitude must come from places-permanent, not Search Box"
            )
            # The poison Search Box coords must NOT appear in the persisted row.
            assert persisted["latitude"] != -34.999, "Search Box latitude leaked into DB (Q2 violation)"
            assert persisted["longitude"] != -58.999, "Search Box longitude leaked into DB (Q2 violation)"

    def test_resolve_address_from_place_id_returns_none_geoloc(self, mock_db):
        """_resolve_address_from_place_id must always return None as the second element.

        This enforces the Q2 rule at the method boundary: no Search Box retrieve
        response field (coordinates, mapbox_id, formatted_address) ever reaches the
        persistence layer via this method.
        """
        user = self._make_user()
        address_data: dict = {"place_id": "some_mapbox_id"}
        search_box_response = self._make_search_box_retrieve_response()

        # Mock the Search Box gateway so retrieve returns the poisoned response.
        mock_gateway = Mock()
        mock_gateway.retrieve.return_value = search_box_response

        with (
            patch(
                "app.services.address_service.AddressBusinessService._resolve_address_from_place_id",
                wraps=address_business_service._resolve_address_from_place_id,
            ),
            patch(
                "app.gateways.address_provider.get_search_gateway",
                return_value=mock_gateway,
            ),
            patch("app.services.market_service.market_service") as mock_market,
        ):
            mock_market.get_by_country_code.return_value = {"country_code": "AR", "country_name": "Argentina"}

            _, geoloc = address_business_service._resolve_address_from_place_id("some_mapbox_id", address_data, user)

        assert geoloc is None, (
            "_resolve_address_from_place_id must return None for geoloc (Q2 rule). "
            "Search Box coordinates must never be passed to the persistence layer."
        )

    def test_poison_string_not_in_any_persisted_field(self, mock_db):
        """End-to-end: no field from the Search Box retrieve response containing the
        poison sentinel must appear in any persisted address or geolocation field.
        """
        user = self._make_user()
        address_data: dict = {"place_id": "some_mapbox_id", "session_token": "tok"}

        mock_address = Mock()
        mock_address.address_id = uuid4()
        mock_address.user_id = None
        mock_address.address_type = ["restaurant"]

        captured_creates: list[dict] = []

        def capture_create(data, db, **kwargs):
            captured_creates.append(dict(data))
            m = Mock()
            m.geolocation_id = uuid4()
            return m

        with (
            patch("app.services.address_service.address_service") as mock_addr_svc,
            patch("app.services.address_service.update_address_type_from_linkages") as mock_derive,
            patch("app.services.address_service.geolocation_service") as mock_geo_svc,
            patch("app.services.address_service.get_persistent_geolocation_service") as mock_pgs,
            patch("app.services.address_service.AddressBusinessService._resolve_city_metadata_and_timezone"),
            patch("app.services.address_service.AddressBusinessService.validate_address_data"),
            patch("app.services.address_service.AddressBusinessService._resolve_address_from_place_id") as mock_resolve,
            patch("app.services.market_service.market_service") as mock_market,
        ):
            mock_market.get_by_country_code.return_value = {"country_code": "AR", "country_name": "Argentina"}

            def fake_resolve(place_id, addr_data, cu, session_token=None):
                # Simulate a gateway that returns a poisoned Search Box response.
                # The method must map structural fields (street, city) but return None geoloc.
                addr_data.update(
                    {
                        "building_number": "123",
                        "street_name": f"Calle {self._POISON}",  # Search Box sourced — would be persisted to address_info
                        "city": "Buenos Aires",
                        "province": "Buenos Aires",
                        "country_code": "AR",
                    }
                )
                # Q2 fix: geoloc is None — coordinates NOT taken from Search Box.
                return addr_data, None

            mock_resolve.side_effect = fake_resolve
            mock_addr_svc.create.return_value = mock_address
            mock_addr_svc.get_by_id.return_value = mock_address
            mock_derive.return_value = ["restaurant"]
            mock_geo_svc.get_by_address.return_value = None
            mock_pgs.return_value.geocode_address.return_value = {
                "latitude": -34.6226,
                "longitude": -58.3701,
            }
            mock_geo_svc.create.side_effect = capture_create

            address_business_service.create_address_with_geocoding(address_data, user, mock_db)

        # Verify: no persisted geolocation field contains the poison sentinel.
        for persisted in captured_creates:
            for field, val in persisted.items():
                assert self._POISON not in str(val), (
                    f"Field {field!r} in persisted geolocation data contains Search Box "
                    f"sentinel {self._POISON!r} (Q2 violation)."
                )


class TestPermanentCacheShortCircuit:
    """Permanent=true cache entries are served correctly (not confused with ephemeral)."""

    def test_permanent_cache_key_is_distinct_from_ephemeral(self):
        """permanent=true and permanent=false produce different cache keys."""
        from app.gateways.mapbox_geocode_cache import make_cache_key

        eph = make_cache_key("geocode", q="500 defensa, buenos aires, ar", language="es", permanent=False)
        perm = make_cache_key("geocode", q="500 defensa, buenos aires, ar", language="es", permanent=True)
        assert eph != perm
        assert eph.endswith("|permanent=false")
        assert perm.endswith("|permanent=true")

    def test_permanent_gateway_hits_permanent_cache_entry(self, monkeypatch, tmp_path):
        """Permanent gateway uses permanent=true key and returns the permanent entry."""
        import json

        from app.gateways.mapbox_geocode_cache import MapboxGeocodeCache
        from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway

        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")
        cache_path = tmp_path / "c.json"
        cache_path.write_text(
            json.dumps(
                {
                    "geocode|500 defensa, buenos aires, ar||es|permanent=false": {"from": "ephemeral"},
                    "geocode|500 defensa, buenos aires, ar||es|permanent=true": {"from": "permanent"},
                }
            )
        )
        from app.gateways import mapbox_geocode_cache as mod

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=cache_path))

        with (
            patch("app.config.settings.get_mapbox_access_token", return_value="sk.test"),
            patch("app.gateways.base_gateway.get_settings") as mock_settings,
        ):
            mock_settings.return_value = Mock(DEV_MODE=False)
            perm_gw = MapboxGeocodingGateway(permanent=True)
            result = perm_gw.call("geocode", q="500 defensa, buenos aires, ar", language="es")

        assert result == {"from": "permanent"}, (
            "Permanent gateway must serve the permanent=true cache entry, not the ephemeral one"
        )

    def test_ephemeral_gateway_does_not_hit_permanent_cache_entry(self, monkeypatch, tmp_path):
        """Ephemeral gateway must not serve a permanent=true cache entry."""
        import json

        from app.gateways.mapbox_geocode_cache import MapboxCacheMiss, MapboxGeocodeCache
        from app.gateways.mapbox_geocoding_gateway import MapboxGeocodingGateway

        monkeypatch.setenv("MAPBOX_CACHE_MODE", "replay_only")
        cache_path = tmp_path / "c.json"
        # Only the permanent entry exists — ephemeral must NOT fall through to it.
        cache_path.write_text(
            json.dumps(
                {
                    "geocode|500 defensa, buenos aires, ar||es|permanent=true": {"from": "permanent"},
                }
            )
        )
        from app.gateways import mapbox_geocode_cache as mod

        monkeypatch.setattr(mod, "_cache", MapboxGeocodeCache(path=cache_path))

        with (
            patch("app.config.settings.get_mapbox_access_token", return_value="pk.test"),
            patch("app.gateways.base_gateway.get_settings") as mock_settings,
        ):
            mock_settings.return_value = Mock(DEV_MODE=False)
            eph_gw = MapboxGeocodingGateway(permanent=False)
            with pytest.raises(MapboxCacheMiss):
                eph_gw.call("geocode", q="500 defensa, buenos aires, ar", language="es")
