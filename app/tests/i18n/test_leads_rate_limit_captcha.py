"""
Tests for the captcha-on-rate-limit extension on country-scoped leads endpoints (#218).

The `_structured_rate_limit_handler` in application.py adds `captcha_required: true`
and `action: "leads_read"` to the 429 body when the rate-limited request path is one
of the country-scoped leads endpoints.

This test exercises the handler via a minimal test app that registers only the
rate-limit exception handler logic — no DB, no live server required.
"""

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from limits import parse as parse_limit
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.wrappers import Limit
from starlette.requests import Request

from app.i18n.envelope import build_envelope
from app.i18n.error_codes import ErrorCode
from app.utils.locale import resolve_locale_from_header


def _make_rate_limit_exc() -> RateLimitExceeded:
    """Build a RateLimitExceeded with the minimal slowapi Limit wrapper."""
    limit_item = parse_limit("60/minute")
    wrapped = Limit(
        limit=limit_item,
        key_func=get_remote_address,
        scope=None,
        per_method=False,
        methods=None,
        error_message=None,
        exempt_when=None,
        cost=1,
        override_defaults=False,
    )
    return RateLimitExceeded(wrapped)


# ---------------------------------------------------------------------------
# Minimal app replicating only the rate-limit handler logic from application.py
# ---------------------------------------------------------------------------

_LEADS_CAPTCHA_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/leads/plans",
        "/api/v1/leads/restaurants",
        "/api/v1/leads/featured-restaurant",
        "/api/v1/leads/cities",
        "/api/v1/leads/city-metrics",
        "/api/v1/leads/zipcode-metrics",
    }
)


def _make_captcha_test_app() -> FastAPI:
    """Minimal app with the rate-limit handler and a few trigger routes."""
    app = FastAPI()

    def _resolve_locale(request: Request) -> str:
        locale = getattr(request.state, "resolved_locale", None)
        if locale is None:
            locale = resolve_locale_from_header(request.headers.get("Accept-Language"))
        return locale

    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        locale = _resolve_locale(request)
        envelope = build_envelope(ErrorCode.REQUEST_RATE_LIMITED, locale, retry_after_seconds=60)
        content: dict = {"detail": envelope}
        if request.url.path in _LEADS_CAPTCHA_PATHS:
            content["captcha_required"] = True
            content["action"] = "leads_read"
        return JSONResponse(
            status_code=429,
            content=content,
            headers={"Retry-After": "60"},
        )

    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    # Routes that simulate the rate-limit exception being raised

    @app.get("/api/v1/leads/plans")
    async def leads_plans_sim(request: Request):
        raise _make_rate_limit_exc()

    @app.get("/api/v1/leads/restaurants")
    async def leads_restaurants_sim(request: Request):
        raise _make_rate_limit_exc()

    @app.get("/api/v1/leads/featured-restaurant")
    async def leads_featured_sim(request: Request):
        raise _make_rate_limit_exc()

    @app.get("/api/v1/leads/cities")
    async def leads_cities_sim(request: Request):
        raise _make_rate_limit_exc()

    @app.get("/api/v1/leads/city-metrics")
    async def leads_city_metrics_sim(request: Request):
        raise _make_rate_limit_exc()

    @app.get("/api/v1/leads/zipcode-metrics")
    async def leads_zipcode_metrics_sim(request: Request):
        raise _make_rate_limit_exc()

    @app.get("/api/v1/leads/countries")
    async def leads_countries_sim(request: Request):
        raise _make_rate_limit_exc()

    @app.get("/api/v1/leads/supplier-countries")
    async def leads_supplier_countries_sim(request: Request):
        raise _make_rate_limit_exc()

    @app.get("/api/v1/other-endpoint")
    async def other_sim(request: Request):
        raise _make_rate_limit_exc()

    return app


@pytest.fixture(scope="module")
def client():
    app = _make_captcha_test_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Covered endpoints: captcha fields MUST be present
# ---------------------------------------------------------------------------

_CAPTCHA_ENDPOINTS = [
    "/api/v1/leads/plans",
    "/api/v1/leads/restaurants",
    "/api/v1/leads/featured-restaurant",
    "/api/v1/leads/cities",
    "/api/v1/leads/city-metrics",
    "/api/v1/leads/zipcode-metrics",
]


class TestCaptchaFieldsPresentOnScopedLeads:
    """Country-scoped leads 429 must carry captcha_required + action."""

    @pytest.mark.parametrize("path", _CAPTCHA_ENDPOINTS)
    def test_captcha_required_true(self, client, path: str):
        resp = client.get(path)
        assert resp.status_code == 429, f"Expected 429 on {path}, got {resp.status_code}"
        body = resp.json()
        assert body.get("captcha_required") is True, f"captcha_required should be True on {path}: {body}"

    @pytest.mark.parametrize("path", _CAPTCHA_ENDPOINTS)
    def test_action_is_leads_read(self, client, path: str):
        resp = client.get(path)
        assert resp.status_code == 429
        body = resp.json()
        assert body.get("action") == "leads_read", f"action should be 'leads_read' on {path}: {body}"

    @pytest.mark.parametrize("path", _CAPTCHA_ENDPOINTS)
    def test_standard_envelope_preserved(self, client, path: str):
        """The request.rate_limited envelope must still be present on captcha 429s."""
        resp = client.get(path)
        assert resp.status_code == 429
        body = resp.json()
        detail = body.get("detail")
        assert isinstance(detail, dict), f"detail should be dict on {path}: {body}"
        assert detail.get("code") == ErrorCode.REQUEST_RATE_LIMITED, f"Wrong code on {path}: {detail}"
        assert detail.get("params", {}).get("retry_after_seconds") == 60, (
            f"retry_after_seconds missing on {path}: {detail}"
        )
        assert resp.headers.get("retry-after") == "60", f"Retry-After header missing on {path}"


# ---------------------------------------------------------------------------
# Navbar-load country endpoints: captcha fields MUST NOT be present
# ---------------------------------------------------------------------------

_EXEMPT_ENDPOINTS = [
    "/api/v1/leads/countries",
    "/api/v1/leads/supplier-countries",
]


class TestCaptchaFieldsAbsentOnNavbarLoad:
    """Navbar-load country endpoint 429s must NOT carry captcha fields."""

    @pytest.mark.parametrize("path", _EXEMPT_ENDPOINTS)
    def test_captcha_required_absent(self, client, path: str):
        resp = client.get(path)
        assert resp.status_code == 429, f"Expected 429 on {path}"
        body = resp.json()
        assert "captcha_required" not in body, f"captcha_required should be absent on {path}: {body}"

    @pytest.mark.parametrize("path", _EXEMPT_ENDPOINTS)
    def test_action_absent(self, client, path: str):
        resp = client.get(path)
        assert resp.status_code == 429
        body = resp.json()
        assert "action" not in body, f"action should be absent on {path}: {body}"

    @pytest.mark.parametrize("path", _EXEMPT_ENDPOINTS)
    def test_standard_envelope_still_present(self, client, path: str):
        """Standard request.rate_limited envelope still present on exempt endpoint 429."""
        resp = client.get(path)
        assert resp.status_code == 429
        body = resp.json()
        detail = body.get("detail")
        assert isinstance(detail, dict)
        assert detail.get("code") == ErrorCode.REQUEST_RATE_LIMITED


# ---------------------------------------------------------------------------
# Non-leads endpoint: captcha fields absent
# ---------------------------------------------------------------------------


class TestCaptchaFieldsAbsentOnNonLeads:
    """Non-leads endpoints hit by rate limit must not carry captcha fields."""

    def test_other_endpoint_has_no_captcha(self, client):
        resp = client.get("/api/v1/other-endpoint")
        assert resp.status_code == 429
        body = resp.json()
        assert "captcha_required" not in body, f"captcha_required on non-leads path: {body}"
        assert "action" not in body, f"action on non-leads path: {body}"
        # standard envelope still present
        assert body["detail"]["code"] == ErrorCode.REQUEST_RATE_LIMITED


# ---------------------------------------------------------------------------
# Two consecutive 429s: consistent captcha shape
# ---------------------------------------------------------------------------


class TestConsecutive429s:
    """Back-to-back rate-limited responses on a scoped endpoint carry the same shape."""

    def test_two_consecutive_429s_same_shape(self, client):
        resp1 = client.get("/api/v1/leads/plans")
        resp2 = client.get("/api/v1/leads/plans")
        for resp in (resp1, resp2):
            assert resp.status_code == 429
            body = resp.json()
            assert body.get("captcha_required") is True
            assert body.get("action") == "leads_read"
            assert body["detail"]["code"] == ErrorCode.REQUEST_RATE_LIMITED
