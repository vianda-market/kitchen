"""
Tests for location_validation_service.

Validates country-province-city combinations (e.g. Florida+Seattle invalid, Washington+Seattle valid).
"""

from app.services.location_validation_service import (
    get_validation_error_detail,
    validate_country_province_city,
)


class TestValidateCountryProvinceCity:
    """validate_country_province_city() rejects invalid combinations."""

    def test_florida_seattle_invalid(self):
        """Florida + Seattle is invalid (Seattle is in Washington)."""
        assert validate_country_province_city("US", "Florida", "Seattle") is False
        assert validate_country_province_city("US", "FL", "Seattle") is False

    def test_washington_seattle_valid(self):
        """Washington + Seattle is valid."""
        assert validate_country_province_city("US", "Washington", "Seattle") is True
        assert validate_country_province_city("US", "WA", "Seattle") is True

    def test_florida_miami_valid(self):
        """Florida + Miami is valid."""
        assert validate_country_province_city("US", "Florida", "Miami") is True
        assert validate_country_province_city("US", "FL", "Miami") is True

    def test_empty_inputs_return_false(self):
        """Empty country, province, or city returns False."""
        assert validate_country_province_city("", "WA", "Seattle") is False
        assert validate_country_province_city("US", "", "Seattle") is False
        assert validate_country_province_city("US", "WA", "") is False

    def test_argentina_buenos_aires_valid(self):
        """Buenos Aires city is in CABA."""
        assert validate_country_province_city("AR", "CABA", "Buenos Aires") is True
        assert validate_country_province_city("AR", "Ciudad Autónoma de Buenos Aires", "Buenos Aires") is True


class TestGetValidationErrorDetail:
    """get_validation_error_detail() returns user-facing messages."""

    def test_florida_seattle_returns_helpful_message(self):
        """Florida + Seattle returns message about Seattle being in Washington."""
        detail = get_validation_error_detail("US", "Florida", "Seattle")
        assert detail is not None
        assert "Seattle" in detail
        assert "Washington" in detail
        assert "Florida" in detail

    def test_valid_combination_returns_none(self):
        """Valid combination returns None."""
        assert get_validation_error_detail("US", "WA", "Seattle") is None
        assert get_validation_error_detail("US", "Florida", "Miami") is None
