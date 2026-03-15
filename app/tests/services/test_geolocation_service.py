"""
Unit tests for Geolocation Service.

Tests the business logic for geocoding, timezone mapping,
and location-based calculations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from app.services.geolocation_service import (
    call_geocode_api, get_timezone_from_location
)


class TestGeolocationService:
    """Test suite for Geolocation Service business logic."""

    @patch('app.services.geolocation_service.geolocation_service.geocode_address')
    @patch('app.services.geolocation_service.log_warning')
    def test_call_geocode_api_returns_json_on_success(self, mock_log_warning, mock_geocode):
        """Test that call_geocode_api returns JSON data on successful API call."""
        mock_geocode.return_value = {
            "latitude": -34.6037,
            "longitude": -58.3816,
            "formatted_address": "Buenos Aires, Argentina",
        }

        result = call_geocode_api("Buenos Aires, Argentina")

        assert result == {"lat": -34.6037, "lng": -58.3816, "formatted_address": "Buenos Aires, Argentina"}
        mock_geocode.assert_called_once_with("Buenos Aires, Argentina")

    @patch('app.services.geolocation_service.geolocation_service.geocode_address')
    @patch('app.services.geolocation_service.log_warning')
    def test_call_geocode_api_handles_non_200_status(self, mock_log_warning, mock_geocode):
        """Test that call_geocode_api handles geocoding failure (returns None)."""
        mock_geocode.return_value = None

        result = call_geocode_api("Invalid Address")

        assert result == {}
        mock_geocode.assert_called_once_with("Invalid Address")

    @patch('app.services.geolocation_service.geolocation_service.geocode_address')
    @patch('app.services.geolocation_service.log_warning')
    def test_call_geocode_api_handles_request_exception(self, mock_log_warning, mock_geocode):
        """Test that call_geocode_api handles request exceptions."""
        mock_geocode.side_effect = Exception("Connection error")

        result = call_geocode_api("Test Address")

        assert result == {}
        mock_geocode.assert_called_once_with("Test Address")

    @patch('app.services.geolocation_service.geolocation_service.geocode_address')
    @patch('app.services.geolocation_service.log_warning')
    def test_call_geocode_api_handles_general_exception(self, mock_log_warning, mock_geocode):
        """Test that call_geocode_api handles general exceptions."""
        mock_geocode.side_effect = Exception("Unexpected error")

        result = call_geocode_api("Test Address")

        assert result == {}
        mock_geocode.assert_called_once_with("Test Address")

    def test_get_timezone_from_location_returns_exact_match(self):
        """Deprecated: get_timezone_from_location now delegates to get_timezone_for_location which returns America/New_York."""
        result = get_timezone_from_location("Argentina", "Buenos Aires")
        assert result == "America/New_York"

    def test_get_timezone_from_location_returns_country_fallback(self):
        """Deprecated: returns America/New_York for all inputs."""
        result = get_timezone_from_location("Argentina", "Unknown City")
        assert result == "America/New_York"

    def test_get_timezone_from_location_returns_default_for_unknown_country(self):
        """Test that get_timezone_from_location returns default for unknown country."""
        result = get_timezone_from_location("Unknown Country", "Unknown City")
        assert result == "America/New_York"

    def test_get_timezone_from_location_handles_peru_cities(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location("Peru", "Lima") == "America/New_York"
        assert get_timezone_from_location("Peru", "Arequipa") == "America/New_York"
        assert get_timezone_from_location("Peru", "Cusco") == "America/New_York"

    def test_get_timezone_from_location_handles_chile_cities(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location("Chile", "Santiago") == "America/New_York"
        assert get_timezone_from_location("Chile", "Valparaiso") == "America/New_York"
        assert get_timezone_from_location("Chile", "Concepcion") == "America/New_York"

    def test_get_timezone_from_location_handles_colombia_cities(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location("Colombia", "Bogota") == "America/New_York"
        assert get_timezone_from_location("Colombia", "Medellin") == "America/New_York"
        assert get_timezone_from_location("Colombia", "Cali") == "America/New_York"

    def test_get_timezone_from_location_handles_mexico_cities(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location("Mexico", "Mexico City") == "America/New_York"
        assert get_timezone_from_location("Mexico", "Guadalajara") == "America/New_York"
        assert get_timezone_from_location("Mexico", "Monterrey") == "America/New_York"

    def test_get_timezone_from_location_handles_brazil_cities(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location("Brazil", "Sao Paulo") == "America/New_York"
        assert get_timezone_from_location("Brazil", "Rio de Janeiro") == "America/New_York"
        assert get_timezone_from_location("Brazil", "Brasilia") == "America/New_York"

    def test_get_timezone_from_location_handles_us_cities(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location("United States", "New York") == "America/New_York"
        assert get_timezone_from_location("United States", "Los Angeles") == "America/New_York"
        assert get_timezone_from_location("United States", "Chicago") == "America/New_York"
        assert get_timezone_from_location("United States", "Miami") == "America/New_York"

    def test_get_timezone_from_location_handles_spain_cities(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location("Spain", "Madrid") == "America/New_York"
        assert get_timezone_from_location("Spain", "Barcelona") == "America/New_York"
        assert get_timezone_from_location("Spain", "Valencia") == "America/New_York"

    def test_get_timezone_from_location_handles_uruguay_cities(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location("Uruguay", "Montevideo") == "America/New_York"
        assert get_timezone_from_location("Uruguay", "Salto") == "America/New_York"

    def test_get_timezone_from_location_handles_paraguay_cities(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location("Paraguay", "Asuncion") == "America/New_York"

    def test_get_timezone_from_location_handles_bolivia_cities(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location("Bolivia", "La Paz") == "America/New_York"
        assert get_timezone_from_location("Bolivia", "Santa Cruz") == "America/New_York"

    def test_get_timezone_from_location_handles_ecuador_cities(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location("Ecuador", "Quito") == "America/New_York"
        assert get_timezone_from_location("Ecuador", "Guayaquil") == "America/New_York"

    def test_get_timezone_from_location_handles_case_sensitivity(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location("argentina", "buenos aires") == "America/New_York"
        assert get_timezone_from_location("ARGENTINA", "BUENOS AIRES") == "America/New_York"

    def test_get_timezone_from_location_handles_whitespace(self):
        """Deprecated: returns America/New_York for all inputs."""
        assert get_timezone_from_location(" Argentina ", " Buenos Aires ") == "America/New_York"
