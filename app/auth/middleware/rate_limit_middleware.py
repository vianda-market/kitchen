"""
Authenticated-user rate limiting middleware (in-memory sliding window).

Tiers are resolved from JWT claims (role_type + onboarding_status).
Anonymous requests pass through — slowapi handles those separately.
"""

import time
from collections import deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.auth.security import verify_token
from app.config.rate_limit_config import (
    RateLimitRule,
    classify_tier,
    resolve_rule,
)
from app.config.settings import settings
from app.i18n.messages import get_message

# ── Module-level storage: bucket_key → deque of monotonic timestamps ────────
_buckets: dict[str, deque[float]] = {}


def _extract_bearer_token(request: Request) -> str | None:
    """Extract raw JWT from Authorization header. Returns None if absent."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 7:
        return auth[7:]
    return None


def _decode_claims(token: str) -> dict | None:
    """Decode JWT via verify_token. Returns payload dict or None."""
    return verify_token(token)


def _check_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int,
    now: float,
) -> tuple[bool, int]:
    """
    Sliding-window check. Returns (allowed, remaining).
    Appends timestamp only when allowed.
    """
    bucket = _buckets.get(key)
    if bucket is None:
        bucket = deque()
        _buckets[key] = bucket

    cutoff = now - window_seconds
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()

    remaining = max_requests - len(bucket)
    if remaining <= 0:
        return False, 0

    bucket.append(now)
    return True, remaining - 1


def _evict_stale_buckets(now: float) -> None:
    """Remove stale buckets when count exceeds threshold."""
    if len(_buckets) <= settings.RATE_LIMIT_MAX_TRACKED_USERS:
        return
    eviction_age = settings.RATE_LIMIT_EVICTION_AGE_SECONDS
    stale_keys = [k for k, dq in _buckets.items() if not dq or (now - dq[-1]) > eviction_age]
    for k in stale_keys:
        del _buckets[k]


def _set_rate_limit_headers(
    response: Response,
    rule: RateLimitRule,
    remaining: int,
) -> None:
    """Attach standard rate-limit headers."""
    response.headers["X-RateLimit-Limit"] = str(rule.max_requests)
    response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
    response.headers["X-RateLimit-Reset"] = str(int(time.time()) + rule.window_seconds)


def _resolve_locale(request: Request) -> str:
    """Parse Accept-Language for error message locale."""
    accept = request.headers.get("Accept-Language", "")
    for lang in accept.replace(" ", "").split(","):
        code = lang.split(";")[0].split("-")[0].lower()
        if code in ("en", "es", "pt"):
            return code
    return "en"


class UserRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-user rate limiting based on JWT onboarding_status tier."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        token = _extract_bearer_token(request)
        if token is None:
            return await call_next(request)

        claims = _decode_claims(token)
        if claims is None:
            return await call_next(request)

        role_type = claims.get("role_type", "")
        onboarding_status = claims.get("onboarding_status")
        user_id = str(claims.get("sub", ""))

        tier = classify_tier(role_type, onboarding_status)

        # Global rule (always checked for non-exempt tiers)
        global_rule = resolve_rule(tier, path="", method=request.method)
        if global_rule.exempt:
            return await call_next(request)

        # Endpoint-specific rule (may differ for Free tier GET overrides)
        endpoint_rule = resolve_rule(tier, request.url.path, request.method)
        has_endpoint_override = endpoint_rule.matched_prefix is not None

        now = time.monotonic()

        # Check global bucket
        global_allowed, global_remaining = _check_rate_limit(
            user_id,
            global_rule.max_requests,
            global_rule.window_seconds,
            now,
        )

        # Check endpoint bucket if override applies
        endpoint_allowed, endpoint_remaining = True, global_rule.max_requests
        if has_endpoint_override:
            ep_key = f"{user_id}:endpoint:{endpoint_rule.matched_prefix}"
            endpoint_allowed, endpoint_remaining = _check_rate_limit(
                ep_key,
                endpoint_rule.max_requests,
                endpoint_rule.window_seconds,
                now,
            )

        _evict_stale_buckets(now)

        allowed = global_allowed and endpoint_allowed
        # Use the more restrictive values for headers
        effective_rule = endpoint_rule if has_endpoint_override else global_rule
        effective_remaining = min(global_remaining, endpoint_remaining) if has_endpoint_override else global_remaining

        if not allowed:
            locale = _resolve_locale(request)
            detail = get_message("error.rate_limit_exceeded", locale)
            if detail == "error.rate_limit_exceeded":
                detail = "Too many requests. Please try again later."
            response = JSONResponse(
                status_code=429,
                content={"detail": detail},
            )
            _set_rate_limit_headers(response, effective_rule, 0)
            response.headers["Retry-After"] = str(effective_rule.window_seconds)
            return response

        response = await call_next(request)
        _set_rate_limit_headers(response, effective_rule, effective_remaining)
        return response
