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
            patch("app.services.address_service.call_geocode_api") as mock_geocode_api,
            patch("app.services.address_service.geolocation_service") as mock_geo_service,
            patch("app.services.address_service.db_read") as mock_db_read,
            patch("app.services.address_service.db_insert") as mock_db_insert,
        ):
            mock_address_service.create.return_value = mock_address
            mock_address_service.get_by_id.return_value = mock_address
            mock_get_timezone.return_value = "America/New_York"
            mock_derive.return_value = ["restaurant"]  # Derived from linkage
            mock_market.get_by_country_code.return_value = {"country_code": "US", "country_name": "United States"}
            mock_geocode_api.return_value = {"latitude": 40.7128, "longitude": -74.0060}
            mock_geo_service.create.return_value = mock_geolocation
            mock_db_read.side_effect = lambda q, *a, **kw: (
                {"tz": "America/New_York", "country_iso": "US"} if "city_metadata" in (q or "") else None
            )
            mock_db_insert.return_value = None

            # Act
            address_business_service.create_address_with_geocoding(
                restaurant_address_data, sample_current_user, mock_db
            )

            # Assert
            mock_geocode_api.assert_called_once()
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
            patch("app.services.address_service.call_geocode_api") as mock_geocode_api,
            patch("app.services.address_service.db_read") as mock_db_read,
            patch("app.services.address_service.db_insert") as mock_db_insert,
        ):
            mock_address_service.create.return_value = mock_address
            mock_address_service.get_by_id.return_value = mock_address
            mock_get_timezone.return_value = "America/New_York"
            mock_derive.return_value = ["restaurant"]
            mock_market.get_by_country_code.return_value = {"country_code": "US", "country_name": "United States"}
            mock_geocode_api.return_value = None  # API failure
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
            mock_geocode_api.assert_called_once()

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
