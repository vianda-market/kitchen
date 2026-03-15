"""
Unit tests for country code resolution and normalization (alpha-2 to country name; normalize at API boundary).
"""

import pytest
from fastapi import HTTPException

from app.utils.country import resolve_country_name, normalize_country_code


class TestResolveCountryName:
    """Tests for resolve_country_name (pycountry-based alpha-2 to name)."""

    def test_valid_alpha2_returns_official_name(self):
        """Valid ISO 3166-1 alpha-2 code returns official country name."""
        assert resolve_country_name("AR") == "Argentina"
        assert resolve_country_name("ar") == "Argentina"
        assert resolve_country_name("  DE  ") == "Germany"
        assert resolve_country_name("GB") == "United Kingdom"
        assert resolve_country_name("US") == "United States"

    def test_invalid_alpha2_raises_400(self):
        """Invalid or unknown alpha-2 code raises HTTP 400."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_country_name("XX")
        assert exc_info.value.status_code == 400
        assert "Invalid country_code" in (exc_info.value.detail or "")

        with pytest.raises(HTTPException) as exc_info:
            resolve_country_name("ZZ")  # invalid alpha-2
        assert exc_info.value.status_code == 400

    def test_alpha3_accepted_and_resolved(self):
        """Alpha-3 code (e.g. ARG) is accepted; normalized to alpha-2 and resolved to country name."""
        assert resolve_country_name("ARG") == "Argentina"
        assert resolve_country_name("USA") == "United States"
        assert resolve_country_name("  bra  ") == "Brazil"

    def test_empty_or_none_raises_400(self):
        """Empty string raises 400."""
        with pytest.raises(HTTPException) as exc_info:
            resolve_country_name("")
        assert exc_info.value.status_code == 400

        with pytest.raises(HTTPException) as exc_info:
            resolve_country_name("  ")
        assert exc_info.value.status_code == 400


class TestNormalizeCountryCode:
    """Tests for normalize_country_code (API boundary normalizer)."""

    def test_none_returns_default(self):
        """None returns default when provided."""
        assert normalize_country_code(None, default="US") == "US"
        assert normalize_country_code(None, default="AR") == "AR"

    def test_none_no_default_returns_empty(self):
        """None with no default returns empty string."""
        assert normalize_country_code(None) == ""
        assert normalize_country_code(None, default=None) == ""

    def test_blank_returns_default(self):
        """Blank string returns default."""
        assert normalize_country_code("", default="US") == "US"
        assert normalize_country_code("  ", default="US") == "US"

    def test_strips_and_uppercase(self):
        """Value is stripped and uppercased; at most 2 chars."""
        assert normalize_country_code(" us ") == "US"
        assert normalize_country_code("ar") == "AR"
        assert normalize_country_code("AR") == "AR"
        assert normalize_country_code("  ar  ") == "AR"

    def test_alpha3_converted_to_alpha2(self):
        """Alpha-3 is converted to alpha-2 via ISO lookup (not truncation)."""
        assert normalize_country_code("ARG") == "AR"
        assert normalize_country_code("usa") == "US"
        assert normalize_country_code("DEU") == "DE"
        assert normalize_country_code("GBR") == "GB"

    def test_invalid_alpha3_returned_as_is(self):
        """Invalid 3-char code is returned as-is so downstream validation can reject."""
        assert normalize_country_code("XXX") == "XXX"
        assert normalize_country_code("ZZZ") == "ZZZ"
