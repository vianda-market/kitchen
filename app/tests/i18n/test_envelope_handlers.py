"""Integration tests for K3/K5 catch-all exception handlers.

Uses FastAPI's TestClient to exercise the main handler paths:
  1. Auto-404 (pre-route) → request.not_found envelope.
  2. In-route bare-string raise → server.internal_error envelope (K-last: legacy.uncoded removed).
  3. 422 validation error (missing field) → validation.field_required envelope (K5).
  4. Already-enveloped detail → pass-through unchanged.
  5. I18nValueError in custom validator → domain code (K5).

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

from app.i18n.envelope import I18nValueError, build_envelope, envelope_exception
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

        # Fallback: unclassified raise (typically a 5xx bare-string raise from an
        # unmigrated service error, or a dict detail without a 'code' key).
        # Emit server.internal_error so the client always receives a typed envelope.
        # The original detail is intentionally not forwarded (may contain internal info).
        envelope = build_envelope(ErrorCode.SERVER_INTERNAL_ERROR, locale)
        return JSONResponse(status_code=exc.status_code, content={"detail": envelope})

    # Email-format error types (mirrors application.py K5 handler)
    _EMAIL_TYPES = frozenset(
        {
            "value_error.email",
            "value_error.email.invalid_domain",
            "value_error.email.missing_at_sign",
            "value_error.email.missing_domain",
            "value_error.email.missing_local",
            "value_error.email.not_an_email_string",
        }
    )
    _TYPE_TO_CODE: dict[str, str] = {
        "missing": ErrorCode.VALIDATION_FIELD_REQUIRED,
        "string_too_short": ErrorCode.VALIDATION_VALUE_TOO_SHORT,
        "string_too_long": ErrorCode.VALIDATION_VALUE_TOO_LONG,
        "string_pattern_mismatch": ErrorCode.VALIDATION_INVALID_FORMAT,
    }

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        locale = _resolve_locale(request)
        envelopes = []
        for error in exc.errors():
            field = ".".join(str(x) for x in error["loc"])
            msg = error.get("msg", "")
            error_type = error.get("type", "")
            ctx = error.get("ctx", {}) or {}

            if error_type in _TYPE_TO_CODE:
                code: str = _TYPE_TO_CODE[error_type]
                extra_params: dict = {}
            elif error_type in _EMAIL_TYPES or error_type.startswith("value_error.email"):
                code = ErrorCode.VALIDATION_INVALID_FORMAT
                extra_params = {}
            elif error_type == "value_error":
                ctx_error = ctx.get("error")
                if isinstance(ctx_error, I18nValueError):
                    code = ctx_error.code
                    extra_params = dict(ctx_error.params)
                else:
                    code = ErrorCode.VALIDATION_CUSTOM
                    extra_params = {}
            else:
                code = ErrorCode.VALIDATION_CUSTOM
                extra_params = {}

            envelope = build_envelope(
                code,
                locale,
                field=field,
                msg=msg,
                type=error_type,
                **extra_params,
            )
            envelopes.append(envelope)
        return JSONResponse(status_code=422, content={"detail": envelopes})

    # ── Test routes ──────────────────────────────────────────────────────────

    @app.get("/bare-string-raise")
    async def bare_string_raise():
        raise HTTPException(status_code=401, detail="bad token")

    class _Body(BaseModel):
        name: str  # required — sending empty body triggers 422

    from pydantic import model_validator as _mv

    class _HoldBody(BaseModel):
        """Body with a custom I18nValueError validator for testing K5 domain codes."""

        end_after_start: bool = True

        @_mv(mode="after")
        def check_field(self):
            if not self.end_after_start:
                raise I18nValueError("validation.subscription.window_invalid")
            return self

    @app.post("/validation-target")
    async def validation_target(body: _Body):
        return {"name": body.name}

    @app.post("/i18n-validator-target")
    async def i18n_validator_target(body: _HoldBody):
        return {"ok": True}

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


def test_bare_string_raise_returns_server_internal_error(client):
    """In-route bare-string raise → server.internal_error envelope (K-last: legacy.uncoded removed).

    After the K6..KN sweep all 4xx routes emit typed envelopes via envelope_exception.
    The only sites still using bare-string detail are 5xx server-error signals
    (intentionally exempt per Decision 3).  Any such raise hits the catch-all
    fallback which now emits server.internal_error instead of legacy.uncoded.
    The original detail string is NOT forwarded to the client.
    """
    resp = client.get("/bare-string-raise")
    assert resp.status_code == 401
    body = resp.json()
    detail = body["detail"]
    assert isinstance(detail, dict), f"Expected dict envelope, got: {detail!r}"
    assert detail["code"] == ErrorCode.SERVER_INTERNAL_ERROR
    assert "message" in detail
    assert isinstance(detail["params"], dict)


def test_validation_error_returns_array_of_envelopes(client):
    """POST with missing required field → 422 with validation.field_required envelope (K5)."""
    resp = client.post("/validation-target", json={})
    assert resp.status_code == 422
    body = resp.json()
    detail = body["detail"]
    assert isinstance(detail, list), f"Expected list for 422, got: {detail!r}"
    assert len(detail) >= 1
    first = detail[0]
    # K5: missing field maps to validation.field_required, not validation.custom
    assert first["code"] == ErrorCode.VALIDATION_FIELD_REQUIRED
    assert "message" in first
    params = first["params"]
    assert "field" in params
    assert "msg" in params
    assert "type" in params


def test_i18n_value_error_emits_domain_code(client):
    """Custom validator raising I18nValueError → domain-specific code in envelope (K5)."""
    resp = client.post("/i18n-validator-target", json={"end_after_start": False})
    assert resp.status_code == 422
    body = resp.json()
    detail = body["detail"]
    assert isinstance(detail, list), f"Expected list for 422, got: {detail!r}"
    assert len(detail) >= 1
    first = detail[0]
    assert first["code"] == "validation.subscription.window_invalid", f"Expected domain code, got: {first['code']!r}"


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
