"""
Unit tests for app/utils/currency.py.

Introduced with kitchen issue #128: convert_currency is a new utility used
by the Stripe USD-minimum pre-flight check in live.py.
"""

from unittest.mock import MagicMock, patch

import pytest


def test_convert_currency_returns_converted_amount() -> None:
    """convert_currency multiplies amount by the rate for the target currency."""
    from app.utils.currency import convert_currency

    mock_response = MagicMock()
    mock_response.json.return_value = {"rates": {"USD": 0.001}}
    mock_response.raise_for_status = MagicMock()

    with patch("app.utils.currency.requests.get", return_value=mock_response) as mock_get:
        result = convert_currency(10000, "ARS", "USD")

    mock_get.assert_called_once_with("https://api.exchangerate-api.com/v4/latest/ARS")
    assert result == 10  # int(10000 * 0.001)


def test_convert_currency_same_currency_no_rounding_loss() -> None:
    """When from == to and rate is 1.0, amount is returned unchanged."""
    from app.utils.currency import convert_currency

    mock_response = MagicMock()
    mock_response.json.return_value = {"rates": {"USD": 1.0}}
    mock_response.raise_for_status = MagicMock()

    with patch("app.utils.currency.requests.get", return_value=mock_response):
        result = convert_currency(5000, "USD", "USD")

    assert result == 5000


def test_convert_currency_raises_on_http_error() -> None:
    """convert_currency propagates HTTP errors from raise_for_status."""
    from app.utils.currency import convert_currency

    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("HTTP error")

    with patch("app.utils.currency.requests.get", return_value=mock_response):
        with pytest.raises(Exception, match="HTTP error"):
            convert_currency(100, "ARS", "USD")
