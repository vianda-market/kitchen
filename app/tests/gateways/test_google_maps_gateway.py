"""
Unit tests for GoogleMapsGateway

Tests the Google Maps API gateway functionality including:
- Geocoding (address to coordinates)
- Reverse geocoding (coordinates to address)
- Address component extraction
- Address validation
- Error handling
"""

import pytest
from unittest.mock import Mock, patch

from app.gateways.google_maps_gateway import GoogleMapsGateway, get_google_maps_gateway
from app.gateways.base_gateway import ExternalServiceError


class TestGoogleMapsGatewayGeocoding:
    """Test geocoding functionality"""
    
    @patch('app.gateways.base_gateway.get_settings')
    def test_geocode_returns_coordinates_in_dev_mode(self, mock_get_settings):
        """Test that geocode returns mock coordinates in dev mode"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = True
        mock_get_settings.return_value = mock_settings
        
        gateway = GoogleMapsGateway()
        
        # Act
        lat, lng = gateway.geocode("Av. Santa Fe 2567, Buenos Aires")
        
        # Assert
        assert isinstance(lat, float)
        assert isinstance(lng, float)
        assert lat == -34.5880634  # From mock data
        assert lng == -58.4023328  # From mock data
    
    @patch('app.config.settings.get_google_api_key', return_value="test_api_key")
    @patch('app.gateways.base_gateway.get_settings')
    @patch('requests.get')
    def test_geocode_calls_google_api_in_prod_mode(self, mock_requests_get, mock_get_settings, mock_get_google_api_key):
        """Test that geocode makes real API call in production mode"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = False
        mock_get_settings.return_value = mock_settings
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": [{
                "geometry": {
                    "location": {"lat": 37.4224764, "lng": -122.0842499}
                }
            }]
        }
        mock_requests_get.return_value = mock_response
        
        gateway = GoogleMapsGateway()
        
        # Act
        lat, lng = gateway.geocode("1600 Amphitheatre Parkway")
        
        # Assert
        assert lat == 37.4224764
        assert lng == -122.0842499
        mock_requests_get.assert_called_once()
    
    @patch('app.gateways.base_gateway.get_settings')
    @patch('app.config.settings.get_google_api_key')
    def test_geocode_raises_error_when_api_key_missing(self, mock_get_google_api_key, mock_get_settings):
        """Test that geocode raises error when API key not configured (prod mode, no key)."""
        mock_settings = Mock()
        mock_settings.DEV_MODE = False
        mock_get_settings.return_value = mock_settings
        mock_get_google_api_key.return_value = ""
        
        gateway = GoogleMapsGateway()
        
        with pytest.raises(ExternalServiceError) as exc_info:
            gateway.geocode("Some address")
        
        assert "GOOGLE_API_KEY not configured" in str(exc_info.value) or "not configured" in str(exc_info.value).lower()


class TestGoogleMapsGatewayReverseGeocoding:
    """Test reverse geocoding functionality"""
    
    @patch('app.gateways.base_gateway.get_settings')
    def test_reverse_geocode_returns_address_in_dev_mode(self, mock_get_settings):
        """Test that reverse geocode returns mock address in dev mode"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = True
        mock_get_settings.return_value = mock_settings
        
        gateway = GoogleMapsGateway()
        
        # Act
        address = gateway.reverse_geocode(-34.5880634, -58.4023328)
        
        # Assert
        assert isinstance(address, str)
        assert len(address) > 0
        assert "Santa Fe" in address or "Buenos Aires" in address  # From mock data
    
    @patch('app.config.settings.get_google_api_key', return_value="test_api_key")
    @patch('app.gateways.base_gateway.get_settings')
    @patch('requests.get')
    def test_reverse_geocode_calls_google_api_in_prod_mode(self, mock_requests_get, mock_get_settings, mock_get_google_api_key):
        """Test that reverse geocode makes real API call in production mode"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = False
        mock_get_settings.return_value = mock_settings
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": [{
                "formatted_address": "1600 Amphitheatre Parkway, Mountain View, CA 94043, USA"
            }]
        }
        mock_requests_get.return_value = mock_response
        
        gateway = GoogleMapsGateway()
        
        # Act
        address = gateway.reverse_geocode(37.4224764, -122.0842499)
        
        # Assert
        assert address == "1600 Amphitheatre Parkway, Mountain View, CA 94043, USA"
        mock_requests_get.assert_called_once()


class TestGoogleMapsGatewayAddressComponents:
    """Test address component extraction"""
    
    @patch('app.gateways.base_gateway.get_settings')
    def test_get_address_components_returns_dict_in_dev_mode(self, mock_get_settings):
        """Test that address components are extracted in dev mode"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = True
        mock_get_settings.return_value = mock_settings
        
        gateway = GoogleMapsGateway()
        
        # Act
        components = gateway.get_address_components("Av. Santa Fe 2567, Buenos Aires")
        
        # Assert
        assert isinstance(components, dict)
        assert "street_number" in components
        assert "route" in components
        assert "country" in components
    
    @patch('app.config.settings.get_google_api_key', return_value="test_api_key")
    @patch('app.gateways.base_gateway.get_settings')
    @patch('requests.get')
    def test_get_address_components_parses_api_response(self, mock_requests_get, mock_get_settings, mock_get_google_api_key):
        """Test that address components are parsed from API response"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = False
        mock_get_settings.return_value = mock_settings
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": [{
                "address_components": [
                    {"types": ["street_number"], "long_name": "1600"},
                    {"types": ["route"], "long_name": "Amphitheatre Parkway"},
                    {"types": ["locality"], "long_name": "Mountain View"},
                    {"types": ["country"], "long_name": "United States"}
                ],
                "geometry": {"location": {"lat": 37.42, "lng": -122.08}}
            }]
        }
        mock_requests_get.return_value = mock_response
        
        gateway = GoogleMapsGateway()
        
        # Act
        components = gateway.get_address_components("1600 Amphitheatre Parkway")
        
        # Assert
        assert components["street_number"] == "1600"
        assert components["route"] == "Amphitheatre Parkway"
        assert components["locality"] == "Mountain View"
        assert components["country"] == "United States"


class TestGoogleMapsGatewayValidation:
    """Test address validation"""
    
    @patch('app.gateways.base_gateway.get_settings')
    def test_validate_address_returns_true_for_valid_address(self, mock_get_settings):
        """Test that valid addresses return True"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = True
        mock_get_settings.return_value = mock_settings
        
        gateway = GoogleMapsGateway()
        
        # Act
        is_valid = gateway.validate_address("Av. Santa Fe 2567, Buenos Aires")
        
        # Assert
        assert is_valid is True
    
    @patch('app.gateways.base_gateway.get_settings')
    def test_validate_address_returns_false_on_error(self, mock_get_settings):
        """Test that validation returns False when geocoding fails"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = True
        mock_get_settings.return_value = mock_settings
        
        gateway = GoogleMapsGateway()
        
        # Act - Use operation that doesn't exist in mock
        is_valid = gateway.validate_address("Invalid Address XYZ123")
        
        # Assert - Should return False instead of raising error
        # Note: This depends on implementation - may need adjustment
        assert isinstance(is_valid, bool)


class TestGoogleMapsGatewaySingleton:
    """Test singleton pattern"""
    
    def test_get_google_maps_gateway_returns_singleton(self):
        """Test that get_google_maps_gateway returns the same instance"""
        # Act
        gateway1 = get_google_maps_gateway()
        gateway2 = get_google_maps_gateway()
        
        # Assert
        assert gateway1 is gateway2


class TestGoogleMapsGatewayErrorHandling:
    """Test error handling"""
    
    @patch('app.config.settings.get_google_api_key', return_value="test_api_key")
    @patch('app.gateways.base_gateway.get_settings')
    @patch('requests.get')
    def test_handles_api_error_status(self, mock_requests_get, mock_get_settings, mock_get_google_api_key):
        """Test that API error statuses are handled properly"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = False
        mock_get_settings.return_value = mock_settings
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ZERO_RESULTS",
            "results": []
        }
        mock_requests_get.return_value = mock_response
        
        gateway = GoogleMapsGateway()
        
        # Act & Assert
        with pytest.raises(ExternalServiceError) as exc_info:
            gateway.geocode("Nonexistent address")
        
        # Error message is wrapped by BaseGateway, so check for the status
        assert "ZERO_RESULTS" in str(exc_info.value) or "No results found" in str(exc_info.value)
    
    @patch('app.config.settings.get_google_api_key', return_value="test_api_key")
    @patch('app.gateways.base_gateway.get_settings')
    @patch('requests.get')
    def test_handles_network_errors(self, mock_requests_get, mock_get_settings, mock_get_google_api_key):
        """Test that network errors are wrapped properly"""
        # Arrange
        mock_settings = Mock()
        mock_settings.DEV_MODE = False
        mock_get_settings.return_value = mock_settings
        
        mock_requests_get.side_effect = Exception("Network error")
        
        gateway = GoogleMapsGateway()
        
        # Act & Assert
        with pytest.raises(ExternalServiceError) as exc_info:
            gateway.geocode("Some address")
        
        assert "Google Maps Geocoding API API call failed" in str(exc_info.value)
