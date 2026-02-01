"""
Unit tests for Address Service.

Tests the business logic for address operations including
geocoding integration, timezone calculation, and address validation.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import UUID, uuid4
from datetime import datetime
from fastapi import HTTPException

from app.services.address_service import AddressBusinessService, address_business_service
from app.dto.models import AddressDTO, GeolocationDTO


class TestAddressService:
    """Test suite for AddressBusinessService business logic."""

    def test_create_address_with_geocoding_sets_timezone(self, sample_current_user, mock_db):
        """Test that address creation sets timezone based on country and city."""
        # Arrange
        address_data = {
            "building_number": "123",
            "street_name": "Main St",
            "city": "New York",
            "province": "NY",
            "country": "US",
            "address_type": "home"  # Not restaurant to avoid geocoding
        }
        
        mock_address = Mock()
        mock_address.address_id = uuid4()
        
        with patch('app.services.address_service.address_service') as mock_address_service, \
             patch('app.services.address_service.get_timezone_from_location') as mock_get_timezone:
            
            mock_address_service.create.return_value = mock_address
            mock_get_timezone.return_value = "America/New_York"
            
            # Act
            result = address_business_service.create_address_with_geocoding(
                address_data, sample_current_user, mock_db
            )
            
            # Assert
            mock_get_timezone.assert_called_once_with(
                address_data["country"], 
                address_data["city"]
            )
            assert address_data["timezone"] == "America/New_York"
            assert address_data["modified_by"] == sample_current_user["user_id"]

    def test_create_address_with_geocoding_calls_api_for_restaurants(self, sample_current_user, mock_db):
        """Test that address creation calls geocoding API for restaurant addresses."""
        # Arrange
        restaurant_address_data = {
            "building_number": "123",
            "street_name": "Main St",
            "city": "New York",
            "province": "NY",
            "country": "US",
            "address_type": ["Restaurant"]  # Must be a list with "Restaurant" (capitalized)
        }
        
        mock_address = Mock()
        mock_address.address_id = uuid4()
        mock_geolocation = Mock()
        mock_geolocation.geolocation_id = uuid4()
        
        with patch('app.services.address_service.address_service') as mock_address_service, \
             patch('app.services.address_service.get_timezone_from_location') as mock_get_timezone, \
             patch('app.services.address_service.call_geocode_api') as mock_geocode_api, \
             patch('app.services.address_service.geolocation_service') as mock_geo_service:
            
            mock_address_service.create.return_value = mock_address
            mock_get_timezone.return_value = "America/New_York"
            mock_geocode_api.return_value = {
                "latitude": 40.7128,
                "longitude": -74.0060
            }
            mock_geo_service.create.return_value = mock_geolocation
            
            # Act
            result = address_business_service.create_address_with_geocoding(
                restaurant_address_data, sample_current_user, mock_db
            )
            
            # Assert
            mock_geocode_api.assert_called_once()
            mock_geo_service.create.assert_called_once()
            
            # Verify geolocation data
            from app.config import Status
            geo_call_args = mock_geo_service.create.call_args[0][0]
            assert geo_call_args["address_id"] == mock_address.address_id
            assert geo_call_args["latitude"] == 40.7128
            assert geo_call_args["longitude"] == -74.0060
            assert geo_call_args["status"] == Status.ACTIVE
            assert geo_call_args["modified_by"] == sample_current_user["user_id"]

    def test_create_address_with_geocoding_handles_api_failure(self, sample_current_user, mock_db):
        """Test that address creation handles geocoding API failure gracefully (non-blocking)."""
        # Arrange
        restaurant_address_data = {
            "building_number": "123",
            "street_name": "Main St",
            "city": "New York",
            "province": "NY",
            "country": "US",
            "address_type": ["Restaurant"]  # Must be a list with "Restaurant" (capitalized)
        }
        
        mock_address = Mock()
        mock_address.address_id = uuid4()
        
        with patch('app.services.address_service.address_service') as mock_address_service, \
             patch('app.services.address_service.get_timezone_from_location') as mock_get_timezone, \
             patch('app.services.address_service.call_geocode_api') as mock_geocode_api:
            
            mock_address_service.create.return_value = mock_address
            mock_get_timezone.return_value = "America/New_York"
            mock_geocode_api.return_value = None  # API failure
            
            # Act - geocoding failures are now non-blocking
            result = address_business_service.create_address_with_geocoding(
                restaurant_address_data, sample_current_user, mock_db
            )
            
            # Assert - address should be created successfully even if geocoding fails
            assert result is not None
            assert result.address_id == mock_address.address_id
            mock_address_service.create.assert_called_once()
            # Geocoding API should still be called, but failure doesn't block creation
            mock_geocode_api.assert_called_once()

    def test_validate_address_data_checks_required_fields(self, mock_db):
        """Test that address validation checks required fields for restaurant addresses."""
        # Arrange
        incomplete_data = {
            "building_number": "123",
            "street_name": "Main St",
            # Missing city, province, country
            "address_type": ["Restaurant"]
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            address_business_service.validate_address_data(incomplete_data)
        
        assert exc_info.value.status_code == 400
        # Country validation happens first, so error message is about country code
        assert "Country" in str(exc_info.value.detail) or "required" in str(exc_info.value.detail).lower()
        assert "city" in str(exc_info.value.detail)

    def test_validate_address_data_validates_country_code(self, mock_db):
        """Test that address validation validates country code format."""
        # Arrange
        invalid_country_data = {
            "building_number": "123",
            "street_name": "Main St",
            "city": "New York",
            "province": "NY",
            "country": "USA",  # Invalid - should be 2 letters
            "address_type": "restaurant"
        }
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            address_business_service.validate_address_data(invalid_country_data)
        
        assert exc_info.value.status_code == 400
        assert "Country must be a 2-letter country code" in str(exc_info.value.detail)

    def test_build_full_address_string_formats_correctly(self, mock_db):
        """Test that full address string is built correctly for geocoding."""
        # Arrange
        address_data = {
            "building_number": "123",
            "street_name": "Main St",
            "city": "New York",
            "province": "NY",
            "country": "US"
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
        
        with patch('app.services.address_service.address_service') as mock_address_service, \
             patch('app.services.address_service.geolocation_service') as mock_geo_service:
            
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
        
        with patch('app.services.address_service.address_service') as mock_address_service:
            mock_address_service.get_by_id.return_value = None
            
            # Act
            result = address_business_service.get_address_with_geolocation(address_id, mock_db)
            
            # Assert
            assert result is None

    def test_update_address_with_geocoding_regeocodes_on_location_change(self, sample_current_user, mock_db):
        """Test that address update re-geocodes when location fields change."""
        # Arrange
        address_id = uuid4()
        update_data = {
            "building_number": "456",
            "street_name": "New St",
            "city": "Boston",
            "province": "MA",
            "country": "US"
        }
        
        mock_updated_address = Mock()
        mock_updated_address.building_number = "456"
        mock_updated_address.street_name = "New St"
        mock_updated_address.city = "Boston"
        mock_updated_address.province = "MA"
        mock_updated_address.country = "US"
        
        with patch('app.services.address_service.address_service') as mock_address_service, \
             patch('app.services.address_service.get_timezone_from_location') as mock_get_timezone, \
             patch('app.services.address_service.call_geocode_api') as mock_geocode_api, \
             patch('app.services.address_service.geolocation_service') as mock_geo_service:
            
            mock_address_service.get_by_id.return_value = mock_updated_address
            mock_address_service.update.return_value = mock_updated_address
            mock_get_timezone.return_value = "America/New_York"
            mock_geocode_api.return_value = {
                "latitude": 42.3601,
                "longitude": -71.0589
            }
            mock_geo_service.get_by_address.return_value = None  # No existing geolocation
            mock_geo_service.create.return_value = Mock()
            
            # Act
            result = address_business_service.update_address_with_geocoding(
                address_id, update_data, sample_current_user, mock_db
            )
            
            # Assert
            mock_geocode_api.assert_called_once()
            mock_geo_service.create.assert_called_once()
            
            # Verify geolocation data
            geo_call_args = mock_geo_service.create.call_args[0][0]
            assert geo_call_args["latitude"] == 42.3601
            assert geo_call_args["longitude"] == -71.0589
            assert geo_call_args["status"] == "Active"

    def test_update_address_with_geocoding_updates_existing_geolocation(self, sample_current_user, mock_db):
        """Test that address update updates existing geolocation when location changes."""
        # Arrange
        address_id = uuid4()
        update_data = {
            "building_number": "456",
            "street_name": "New St"
        }
        
        mock_updated_address = Mock()
        mock_updated_address.building_number = "456"
        mock_updated_address.street_name = "New St"
        mock_updated_address.city = "Boston"
        mock_updated_address.province = "MA"
        mock_updated_address.country = "US"
        
        mock_existing_geo = Mock()
        mock_existing_geo.geolocation_id = uuid4()
        
        with patch('app.services.address_service.address_service') as mock_address_service, \
             patch('app.services.address_service.call_geocode_api') as mock_geocode_api, \
             patch('app.services.address_service.geolocation_service') as mock_geo_service:
            
            mock_address_service.get_by_id.return_value = mock_updated_address
            mock_address_service.update.return_value = mock_updated_address
            mock_geocode_api.return_value = {
                "latitude": 42.3601,
                "longitude": -71.0589
            }
            mock_geo_service.get_by_address.return_value = mock_existing_geo
            mock_geo_service.update.return_value = Mock()
            
            # Act
            result = address_business_service.update_address_with_geocoding(
                address_id, update_data, sample_current_user, mock_db
            )
            
            # Assert
            mock_geo_service.update.assert_called_once()
            update_call_args = mock_geo_service.update.call_args[0][1]  # update_data
            assert update_call_args["latitude"] == 42.3601
            assert update_call_args["longitude"] == -71.0589

    def test_update_address_with_geocoding_handles_address_not_found(self, sample_current_user, mock_db):
        """Test that address update handles address not found."""
        # Arrange
        address_id = uuid4()
        update_data = {"building_number": "456"}
        
        with patch('app.services.address_service.address_service') as mock_address_service:
            mock_address_service.update.return_value = None
            
            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                address_business_service.update_address_with_geocoding(
                    address_id, update_data, sample_current_user, mock_db
                )
            
            assert exc_info.value.status_code == 404
            assert "Address not found" in str(exc_info.value.detail)
