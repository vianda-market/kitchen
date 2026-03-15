"""
Unit tests for supported currencies config (list, sort, name→code lookup).
"""

import pytest

from app.config.supported_currencies import (
    get_supported_currencies_sorted_by_name,
    get_currency_code_by_name,
    SUPPORTED_CURRENCY_CODES,
    SUPPORTED_CURRENCIES,
)


class TestGetSupportedCurrenciesSortedByName:
    """Tests for get_supported_currencies_sorted_by_name()."""

    def test_returns_list_of_dicts_with_currency_name_and_code(self):
        """Returns list of { currency_name, currency_code }."""
        result = get_supported_currencies_sorted_by_name()
        assert isinstance(result, list)
        assert len(result) >= 1
        for item in result:
            assert "currency_name" in item
            assert "currency_code" in item
            assert isinstance(item["currency_name"], str)
            assert isinstance(item["currency_code"], str)

    def test_sorted_by_currency_name_case_insensitive(self):
        """List is sorted by currency_name (case-insensitive)."""
        result = get_supported_currencies_sorted_by_name()
        names = [x["currency_name"].lower() for x in result]
        assert names == sorted(names)

    def test_contains_expected_currencies(self):
        """Contains US Dollar and Argentine Peso."""
        result = get_supported_currencies_sorted_by_name()
        names = [x["currency_name"] for x in result]
        codes = [x["currency_code"] for x in result]
        assert "US Dollar" in names
        assert "Argentine Peso" in names
        assert "USD" in codes
        assert "ARS" in codes


class TestGetCurrencyCodeByName:
    """Tests for get_currency_code_by_name()."""

    def test_known_name_returns_code(self):
        """Known currency name returns ISO code."""
        assert get_currency_code_by_name("US Dollar") == "USD"
        assert get_currency_code_by_name("Argentine Peso") == "ARS"
        assert get_currency_code_by_name("Canadian Dollar") == "CAD"

    def test_stripped_name_returns_code(self):
        """Whitespace around name is stripped."""
        assert get_currency_code_by_name("  US Dollar  ") == "USD"

    def test_unknown_name_returns_none(self):
        """Unknown currency name returns None."""
        assert get_currency_code_by_name("Unknown Currency") is None
        assert get_currency_code_by_name("Euro") is None

    def test_empty_or_none_returns_none(self):
        """Empty string or None returns None."""
        assert get_currency_code_by_name("") is None
        assert get_currency_code_by_name("   ") is None
        assert get_currency_code_by_name(None) is None


class TestSupportedCurrencyCodes:
    """Tests for SUPPORTED_CURRENCY_CODES set."""

    def test_contains_expected_codes(self):
        """Set contains USD, ARS, etc."""
        assert "USD" in SUPPORTED_CURRENCY_CODES
        assert "ARS" in SUPPORTED_CURRENCY_CODES
        assert "CAD" in SUPPORTED_CURRENCY_CODES

    def test_matches_currencies_list(self):
        """Set is derived from SUPPORTED_CURRENCIES (same codes)."""
        expected = frozenset(code for _, code in SUPPORTED_CURRENCIES)
        assert SUPPORTED_CURRENCY_CODES == expected
