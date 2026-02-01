"""
Unit tests for Geolocation Service.

Tests the business logic for geocoding, timezone mapping,
and location-based calculations.
"""

import pytest
from unittest.mock import Mock, patch
import requests

from app.services.geolocation_service import (
    call_geocode_api, get_timezone_from_location
)


class TestGeolocationService:
    """Test suite for Geolocation Service business logic."""

    @patch('app.services.geolocation_service.requests.get')
    @patch('app.services.geolocation_service.log_warning')
    def test_call_geocode_api_returns_json_on_success(self, mock_log_warning, mock_get):
        """Test that call_geocode_api returns JSON data on successful API call."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"lat": -34.6037, "lng": -58.3816}
        mock_get.return_value = mock_response
        
        # Act
        result = call_geocode_api("Buenos Aires, Argentina")
        
        # Assert
        assert result == {"lat": -34.6037, "lng": -58.3816}
        mock_get.assert_called_once_with("https://api.example.com/geocode?address=Buenos Aires, Argentina")
        mock_log_warning.assert_not_called()

    @patch('app.services.geolocation_service.requests.get')
    @patch('app.services.geolocation_service.log_warning')
    def test_call_geocode_api_handles_non_200_status(self, mock_log_warning, mock_get):
        """Test that call_geocode_api handles non-200 status codes."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        # Act
        result = call_geocode_api("Invalid Address")
        
        # Assert
        assert result == {}
        mock_log_warning.assert_called_once_with("Geocode API returned status 404")

    @patch('app.services.geolocation_service.requests.get')
    @patch('app.services.geolocation_service.log_warning')
    def test_call_geocode_api_handles_request_exception(self, mock_log_warning, mock_get):
        """Test that call_geocode_api handles request exceptions."""
        # Arrange
        mock_get.side_effect = requests.RequestException("Connection error")
        
        # Act
        result = call_geocode_api("Test Address")
        
        # Assert
        assert result == {}
        mock_log_warning.assert_called_once_with("Error calling geocode API: Connection error")

    @patch('app.services.geolocation_service.requests.get')
    @patch('app.services.geolocation_service.log_warning')
    def test_call_geocode_api_handles_general_exception(self, mock_log_warning, mock_get):
        """Test that call_geocode_api handles general exceptions."""
        # Arrange
        mock_get.side_effect = Exception("Unexpected error")
        
        # Act
        result = call_geocode_api("Test Address")
        
        # Assert
        assert result == {}
        mock_log_warning.assert_called_once_with("Error calling geocode API: Unexpected error")

    def test_get_timezone_from_location_returns_exact_match(self):
        """Test that get_timezone_from_location returns exact country-city match."""
        # Act
        result = get_timezone_from_location("Argentina", "Buenos Aires")
        
        # Assert
        assert result == "America/Argentina/Buenos_Aires"

    def test_get_timezone_from_location_returns_country_fallback(self):
        """Test that get_timezone_from_location returns country fallback when city not found."""
        # Act
        result = get_timezone_from_location("Argentina", "Unknown City")
        
        # Assert
        assert result == "America/Argentina/Buenos_Aires"

    def test_get_timezone_from_location_returns_default_for_unknown_country(self):
        """Test that get_timezone_from_location returns default for unknown country."""
        # Act
        result = get_timezone_from_location("Unknown Country", "Unknown City")
        
        # Assert
        # Default timezone changed from Buenos Aires to New York
        assert result == "America/New_York"

    def test_get_timezone_from_location_handles_peru_cities(self):
        """Test timezone mapping for Peru cities."""
        # Act & Assert
        assert get_timezone_from_location("Peru", "Lima") == "America/Lima"
        assert get_timezone_from_location("Peru", "Arequipa") == "America/Lima"
        assert get_timezone_from_location("Peru", "Cusco") == "America/Lima"

    def test_get_timezone_from_location_handles_chile_cities(self):
        """Test timezone mapping for Chile cities."""
        # Act & Assert
        assert get_timezone_from_location("Chile", "Santiago") == "America/Santiago"
        assert get_timezone_from_location("Chile", "Valparaiso") == "America/Santiago"
        assert get_timezone_from_location("Chile", "Concepcion") == "America/Santiago"

    def test_get_timezone_from_location_handles_colombia_cities(self):
        """Test timezone mapping for Colombia cities."""
        # Act & Assert
        assert get_timezone_from_location("Colombia", "Bogota") == "America/Bogota"
        assert get_timezone_from_location("Colombia", "Medellin") == "America/Bogota"
        assert get_timezone_from_location("Colombia", "Cali") == "America/Bogota"

    def test_get_timezone_from_location_handles_mexico_cities(self):
        """Test timezone mapping for Mexico cities."""
        # Act & Assert
        assert get_timezone_from_location("Mexico", "Mexico City") == "America/Mexico_City"
        assert get_timezone_from_location("Mexico", "Guadalajara") == "America/Mexico_City"
        # Monterrey has its own timezone in the service mapping
        assert get_timezone_from_location("Mexico", "Monterrey") == "America/Monterrey"

    def test_get_timezone_from_location_handles_brazil_cities(self):
        """Test timezone mapping for Brazil cities."""
        # Act & Assert
        assert get_timezone_from_location("Brazil", "Sao Paulo") == "America/Sao_Paulo"
        assert get_timezone_from_location("Brazil", "Rio de Janeiro") == "America/Sao_Paulo"
        assert get_timezone_from_location("Brazil", "Brasilia") == "America/Sao_Paulo"

    def test_get_timezone_from_location_handles_us_cities(self):
        """Test timezone mapping for US cities."""
        # Act & Assert
        assert get_timezone_from_location("United States", "New York") == "America/New_York"
        assert get_timezone_from_location("United States", "Los Angeles") == "America/Los_Angeles"
        assert get_timezone_from_location("United States", "Chicago") == "America/Chicago"
        assert get_timezone_from_location("United States", "Miami") == "America/New_York"

    def test_get_timezone_from_location_handles_spain_cities(self):
        """Test timezone mapping for Spain cities."""
        # Act & Assert - Spain is not in the timezone mapping, so returns fallback
        assert get_timezone_from_location("Spain", "Madrid") == "America/New_York"  # Fallback
        assert get_timezone_from_location("Spain", "Barcelona") == "America/New_York"  # Fallback
        assert get_timezone_from_location("Spain", "Valencia") == "America/New_York"  # Fallback

    def test_get_timezone_from_location_handles_uruguay_cities(self):
        """Test timezone mapping for Uruguay cities."""
        # Act & Assert
        assert get_timezone_from_location("Uruguay", "Montevideo") == "America/Montevideo"
        assert get_timezone_from_location("Uruguay", "Salto") == "America/Montevideo"

    def test_get_timezone_from_location_handles_paraguay_cities(self):
        """Test timezone mapping for Paraguay cities."""
        # Act & Assert
        assert get_timezone_from_location("Paraguay", "Asuncion") == "America/Asuncion"

    def test_get_timezone_from_location_handles_bolivia_cities(self):
        """Test timezone mapping for Bolivia cities."""
        # Act & Assert - Bolivia is not in the timezone mapping, so returns fallback
        assert get_timezone_from_location("Bolivia", "La Paz") == "America/New_York"  # Fallback
        assert get_timezone_from_location("Bolivia", "Santa Cruz") == "America/New_York"  # Fallback

    def test_get_timezone_from_location_handles_ecuador_cities(self):
        """Test timezone mapping for Ecuador cities."""
        # Act & Assert
        assert get_timezone_from_location("Ecuador", "Quito") == "America/Guayaquil"
        assert get_timezone_from_location("Ecuador", "Guayaquil") == "America/Guayaquil"

    def test_get_timezone_from_location_handles_case_sensitivity(self):
        """Test that timezone mapping handles case (service normalizes inputs by stripping only)."""
        # Act & Assert - Service normalizes inputs by stripping whitespace, but case must match exactly
        # "argentina" (lowercase) doesn't match "Argentina" in mapping, so returns fallback
        assert get_timezone_from_location("argentina", "buenos aires") == "America/New_York"  # Country not found (case mismatch)
        assert get_timezone_from_location("ARGENTINA", "BUENOS AIRES") == "America/New_York"  # Country not found (case mismatch)

    def test_get_timezone_from_location_handles_whitespace(self):
        """Test that timezone mapping handles whitespace correctly."""
        # Act & Assert - Should return default for extra whitespace
        assert get_timezone_from_location(" Argentina ", " Buenos Aires ") == "America/Argentina/Buenos_Aires"  # Country fallback
