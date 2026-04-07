"""
Mobile number validation and E.164 normalization using the phonenumbers library (offline).
"""

# Note: phonenumbers.number_type() can distinguish mobile vs landline
# but returns FIXED_LINE_OR_MOBILE for most US/AR/PE numbers.
# Mobile-type enforcement is deferred to SMS verification (Twilio Verify)
# which rejects landlines at send time. See MOBILE_VERIFICATION_ROADMAP.md.

from typing import Optional

import phonenumbers
from phonenumbers import PhoneNumberFormat
from fastapi import HTTPException

from app.utils.country import normalize_country_code


def _normalize_mobile_or_raise_value_error(
    raw: Optional[str],
    country_hint: Optional[str] = None,
) -> Optional[str]:
    """
    Parse and return E.164, or None for empty input.
    Raises ValueError with a stable message for invalid numbers (Pydantic → 422).
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("Mobile number must be a string")
    s = raw.strip()
    if not s:
        return None

    region: Optional[str] = None
    if country_hint:
        cc = normalize_country_code(country_hint) or ""
        if len(cc) == 2:
            region = cc

    try:
        parsed = phonenumbers.parse(s, region)
    except phonenumbers.NumberParseException as exc:
        raise ValueError(
            "Invalid phone number. Expected E.164 format (e.g. +5491112345678) "
            "or a local number with a country hint."
        ) from exc

    if not phonenumbers.is_valid_number(parsed):
        raise ValueError(
            "Phone number is not valid for any country. "
            "Verify the number and try again."
        )

    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)


def validate_and_normalize_mobile(
    raw: Optional[str],
    country_hint: Optional[str] = None,
) -> Optional[str]:
    """
    Parse and return E.164, or None for empty input.
    Raises HTTPException 422 if the number is invalid.
    """
    try:
        return _normalize_mobile_or_raise_value_error(raw, country_hint)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def normalize_mobile_for_schema(
    raw: Optional[str],
    country_hint: Optional[str] = None,
) -> Optional[str]:
    """Alias for Pydantic validators: ValueError → 422 via FastAPI."""
    return _normalize_mobile_or_raise_value_error(raw, country_hint)


def format_mobile_for_display(e164: Optional[str]) -> Optional[str]:
    """
    Return an internationally formatted display string for a stored E.164 number.
    Example: '+5491112345678' → '+54 9 11 2345-6789'
    Returns None for empty/None input; returns the raw value on any parse failure.
    """
    if not e164 or not isinstance(e164, str):
        return None
    s = e164.strip()
    if not s:
        return None
    try:
        parsed = phonenumbers.parse(s, None)
        if not phonenumbers.is_valid_number(parsed):
            return s
        return phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
    except phonenumbers.NumberParseException:
        return s


def get_mobile_region(e164: str) -> Optional[str]:
    """Return ISO alpha-2 region for an E.164 number, or None if not parseable/valid."""
    if not e164 or not isinstance(e164, str):
        return None
    try:
        parsed = phonenumbers.parse(e164.strip(), None)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.region_code_for_number(parsed)
