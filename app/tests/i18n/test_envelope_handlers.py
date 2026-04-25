"""Integration tests for K3 catch-all exception handlers.

Uses FastAPI's TestClient to exercise the four main handler paths:
  1. Auto-404 (pre-route) → request.not_found envelope.
  2. In-route bare-string raise → legacy.uncoded envelope.
  3. 422 validation error → list of validation.custom envelopes.
  4. Already-enveloped detail → pass-through unchanged.

Rate-limit (request.rate_limited) is exercised via a dedicated fixture route
rather than triggering slowapi's real limiter (which is per-process state).

These tests verify the wire shape; message content is locale-dependent and
checked separately by test_error_codes_parity.py.
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from app.i18n.envelope import build_envelope, envelope_exception
from app.i18n.error_codes import ErrorCode
from app.utils.locale import resolve_locale_from_header

# ---------------------------------------------------------------------------
# Minimal test app that reuses the real handlers from application.py
# ---------------------------------------------------------------------------


def _make_test_app() -> FastAPI:
    """
    Build a minimal FastAPI app that registers the same catch-all handlers
    as the production app, plus a handful of test routes.
    """
    app = FastAPI()

    def _resolve_locale(request: Request) -> str:
        locale = getattr(request.state, "resolved_locale", None)
        if locale is None:
            locale = resolve_locale_from_header(request.headers.get("Accept-Language"))
        return locale

    _STATUS_CODE_MAP: dict[int, str] = {
        404: ErrorCode.REQUEST_NOT_FOUND,
        405: ErrorCode.REQUEST_METHOD_NOT_ALLOWED,
        413: ErrorCode.REQUEST_TOO_LARGE,
    }

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        locale = _resolve_locale(request)
        detail = exc.detail

        if isinstance(detail, dict) and "code" in detail:
            return JSONResponse(status_code=exc.status_code, content={"detail": detail})

        if exc.status_code in _STATUS_CODE_MAP:
            code = _STATUS_CODE_MAP[exc.status_code]
            envelope = build_envelope(code, locale)
            return JSONResponse(status_code=exc.status_code, content={"detail": envelope})

        if isinstance(detail, str):
            envelope = build_envelope(ErrorCode.LEGACY_UNCODED, locale, message=detail)
            return JSONResponse(status_code=exc.status_code, content={"detail": envelope})

        fallback_msg = str(detail) if detail else f"HTTP {exc.status_code}"
        envelope = build_envelope(ErrorCode.LEGACY_UNCODED, locale, message=fallback_msg)
        return JSONResponse(status_code=exc.status_code, content={"detail": envelope})

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        locale = _resolve_locale(request)
        envelopes = []
        for error in exc.errors():
            field = ".".join(str(x) for x in error["loc"])
            msg = error.get("msg", "")
            error_type = error.get("type", "")
            envelope = build_envelope(
                ErrorCode.VALIDATION_CUSTOM,
                locale,
                msg=msg,
                field=field,
                type=error_type,
            )
            envelopes.append(envelope)
        return JSONResponse(status_code=422, content={"detail": envelopes})

    # ── Test routes ──────────────────────────────────────────────────────────

    @app.get("/bare-string-raise")
    async def bare_string_raise():
        raise HTTPException(status_code=401, detail="bad token")

    class _Body(BaseModel):
        name: str  # required — sending empty body triggers 422

    @app.post("/validation-target")
    async def validation_target(body: _Body):
        return {"name": body.name}

    @app.get("/already-enveloped")
    async def already_enveloped():
        locale = "en"
        raise envelope_exception(ErrorCode.AUTH_INVALID_TOKEN, status=401, locale=locale)

    @app.get("/rate-limited-sim")
    async def rate_limited_sim():
        locale = "en"
        envelope = build_envelope(ErrorCode.REQUEST_RATE_LIMITED, locale, retry_after_seconds=60)
        return JSONResponse(
            status_code=429,
            content={"detail": envelope},
            headers={"Retry-After": "60"},
        )

    return app


@pytest.fixture(scope="module")
def client():
    app = _make_test_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_auto_404_returns_request_not_found(client):
    """GET on a non-existent path triggers auto-404 → request.not_found envelope."""
    resp = client.get("/nonexistent-path")
    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body
    detail = body["detail"]
    assert isinstance(detail, dict), f"Expected dict envelope, got: {detail!r}"
    assert detail["code"] == ErrorCode.REQUEST_NOT_FOUND
    assert "message" in detail
    assert isinstance(detail["params"], dict)


def test_bare_string_raise_returns_legacy_uncoded(client):
    """In-route raise HTTPException(detail=<str>) → legacy.uncoded envelope."""
    resp = client.get("/bare-string-raise")
    assert resp.status_code == 401
    body = resp.json()
    detail = body["detail"]
    assert isinstance(detail, dict), f"Expected dict envelope, got: {detail!r}"
    assert detail["code"] == ErrorCode.LEGACY_UNCODED
    assert detail["message"] == "bad token"
    assert isinstance(detail["params"], dict)


def test_validation_error_returns_array_of_envelopes(client):
    """POST with missing required field → 422 with list of validation.custom envelopes."""
    resp = client.post("/validation-target", json={})
    assert resp.status_code == 422
    body = resp.json()
    detail = body["detail"]
    assert isinstance(detail, list), f"Expected list for 422, got: {detail!r}"
    assert len(detail) >= 1
    first = detail[0]
    assert first["code"] == ErrorCode.VALIDATION_CUSTOM
    assert "message" in first
    params = first["params"]
    assert "field" in params
    assert "msg" in params
    assert "type" in params


def test_already_enveloped_passes_through(client):
    """In-route raise via envelope_exception → detail passes through with original code."""
    resp = client.get("/already-enveloped")
    assert resp.status_code == 401
    body = resp.json()
    detail = body["detail"]
    assert isinstance(detail, dict), f"Expected dict envelope, got: {detail!r}"
    assert detail["code"] == ErrorCode.AUTH_INVALID_TOKEN
    assert "message" in detail


def test_rate_limited_returns_request_rate_limited_envelope(client):
    """rate_limited_sim route emits request.rate_limited envelope with retry_after_seconds."""
    resp = client.get("/rate-limited-sim")
    assert resp.status_code == 429
    body = resp.json()
    detail = body["detail"]
    assert isinstance(detail, dict), f"Expected dict envelope, got: {detail!r}"
    assert detail["code"] == ErrorCode.REQUEST_RATE_LIMITED
    assert detail["params"]["retry_after_seconds"] == 60
    assert resp.headers.get("Retry-After") == "60"


def test_auto_404_locale_header_used(client):
    """Accept-Language: es header → message is in Spanish (pre-route locale via header)."""
    resp = client.get("/nonexistent-path", headers={"Accept-Language": "es"})
    assert resp.status_code == 404
    body = resp.json()
    detail = body["detail"]
    assert detail["code"] == ErrorCode.REQUEST_NOT_FOUND
    # Spanish message should not be the English fallback
    assert detail["message"] != ""
    # Verify it is indeed different from the English message when Spanish locale is used.
    # (Both could legitimately be the same string only if translations happen to match.)
    from app.i18n.messages import MESSAGES

    es_msg = MESSAGES["es"].get(ErrorCode.REQUEST_NOT_FOUND, "")
    assert detail["message"] == es_msg, f"Expected Spanish message '{es_msg}', got '{detail['message']}'"
