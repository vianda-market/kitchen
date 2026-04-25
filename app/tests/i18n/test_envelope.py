"""build_envelope and envelope_exception factory behavior."""

from fastapi import HTTPException

from app.i18n.envelope import ErrorEnvelope, build_envelope, envelope_exception
from app.i18n.error_codes import ErrorCode


def test_build_envelope_with_enum_member_returns_wire_dict():
    env = build_envelope(ErrorCode.AUTH_INVALID_TOKEN, "en")
    assert env["code"] == "auth.invalid_token"
    assert isinstance(env["message"], str) and env["message"]
    assert env["params"] == {}


def test_build_envelope_with_string_code_normalises_via_str():
    env = build_envelope("auth.invalid_token", "en")
    assert env["code"] == "auth.invalid_token"
    assert isinstance(env["message"], str)


def test_build_envelope_includes_params_in_wire_dict():
    env = build_envelope(ErrorCode.REQUEST_RATE_LIMITED, "en", retry_after_seconds=60)
    assert env["code"] == "request.rate_limited"
    assert env["params"] == {"retry_after_seconds": 60}


def test_build_envelope_resolves_message_per_locale():
    en = build_envelope(ErrorCode.AUTH_INVALID_TOKEN, "en")
    es = build_envelope(ErrorCode.AUTH_INVALID_TOKEN, "es")
    assert en["message"] != es["message"]


def test_envelope_exception_returns_httpexception_with_envelope_detail():
    exc = envelope_exception(ErrorCode.AUTH_INVALID_TOKEN, status=401, locale="en")
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 401
    assert isinstance(exc.detail, dict)
    assert exc.detail["code"] == "auth.invalid_token"
    assert exc.detail["params"] == {}


def test_envelope_exception_passes_params_through():
    exc = envelope_exception(ErrorCode.REQUEST_RATE_LIMITED, status=429, locale="en", retry_after_seconds=60)
    assert exc.status_code == 429
    assert isinstance(exc.detail, dict)
    assert exc.detail["params"] == {"retry_after_seconds": 60}


def test_error_envelope_typed_dict_shape():
    env: ErrorEnvelope = {"code": "x.y", "message": "m", "params": {}}
    assert env["code"] == "x.y"
