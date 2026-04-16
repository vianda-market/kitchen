"""Tests for app.utils.phone — E.164 normalization (phonenumbers, offline)."""

import pytest
from fastapi import HTTPException

from app.utils.phone import (
    format_mobile_for_display,
    get_mobile_region,
    normalize_mobile_for_schema,
    validate_and_normalize_mobile,
)


def test_normalize_none_and_empty_returns_none():
    assert normalize_mobile_for_schema(None) is None
    assert normalize_mobile_for_schema("") is None
    assert normalize_mobile_for_schema("   ") is None


def test_normalize_valid_e164_passthrough():
    assert normalize_mobile_for_schema("+14155552671") == "+14155552671"


def test_normalize_national_with_country_hint_us():
    assert normalize_mobile_for_schema("4155552671", "US") == "+14155552671"


def test_normalize_national_with_country_hint_ar():
    out = normalize_mobile_for_schema("91112345678", "AR")
    assert out == "+5491112345678"


def test_normalize_invalid_raises_value_error():
    with pytest.raises(ValueError, match="Invalid phone number"):
        normalize_mobile_for_schema("not-a-number", None)


def test_validate_and_normalize_mobile_raises_http_exception():
    with pytest.raises(HTTPException) as exc:
        validate_and_normalize_mobile("bogus", None)
    assert exc.value.status_code == 422
    assert "Invalid phone number" in str(exc.value.detail)


def test_get_mobile_region_us():
    assert get_mobile_region("+14155552671") == "US"


def test_get_mobile_region_invalid_returns_none():
    assert get_mobile_region("invalid") is None


# ---------------------------------------------------------------------------
# format_mobile_for_display
# ---------------------------------------------------------------------------


def test_format_display_none_and_empty_returns_none():
    assert format_mobile_for_display(None) is None
    assert format_mobile_for_display("") is None
    assert format_mobile_for_display("   ") is None


def test_format_display_us_number():
    result = format_mobile_for_display("+14155552671")
    assert result is not None
    # INTERNATIONAL format: "+1 415-555-2671" or similar — starts with "+1"
    assert result.startswith("+1")


def test_format_display_ar_number():
    result = format_mobile_for_display("+5491112345678")
    assert result is not None
    assert result.startswith("+54")


def test_format_display_invalid_e164_returns_raw():
    raw = "+9999999999999999"  # too long, invalid
    result = format_mobile_for_display(raw)
    # Falls back to returning raw value
    assert result == raw
