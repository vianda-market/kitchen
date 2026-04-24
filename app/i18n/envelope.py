"""
Hybrid error-envelope factory.

Wire shape (scalar):
    {"detail": {"code": "stable.key", "message": "<localized>", "params": {...}}}

Usage:
    raise envelope_exception(ErrorCode.AUTH_INVALID_TOKEN, status=401, locale=locale)
    raise envelope_exception("auth.invalid_token", status=401, locale=locale)

The `code` argument accepts either an ErrorCode enum member or a plain string;
both are normalised via str() before lookup. This lets the factory be called
during the incremental K6..KN sweep before every site imports ErrorCode.

See docs/api/i18n.md and (once K3 lands) docs/api/error-envelope.md for full
contract, locale-resolution rules, and the legacy-transition path.
"""

from typing import Any, TypedDict

from fastapi import HTTPException

from app.i18n.messages import get_message


class ErrorEnvelope(TypedDict):
    code: str
    message: str
    params: dict[str, Any]


def build_envelope(code: str, locale: str, **params: Any) -> ErrorEnvelope:
    """
    Build the wire dict for a single error.

    Looks up the localized message via get_message; substitutes params.
    Falls back to the raw code string if no message entry exists (loud failure,
    per the catalog discipline rule in docs/api/i18n.md).
    """
    normalized = str(code)
    message = get_message(normalized, locale, **params)
    return ErrorEnvelope(code=normalized, message=message, params=dict(params))


def envelope_exception(code: str, status: int, locale: str, **params: Any) -> HTTPException:
    """
    Build and return an HTTPException whose detail is a single ErrorEnvelope.

    Callers raise the returned exception; they do not raise inside this function
    so that stack traces point to the actual raise site.

        raise envelope_exception(ErrorCode.AUTH_INVALID_TOKEN, status=401, locale=locale)
    """
    return HTTPException(status_code=status, detail=build_envelope(code, locale, **params))
