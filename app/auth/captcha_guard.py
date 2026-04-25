"""
Conditional reCAPTCHA dependency factories for auth endpoints.

- require_captcha_after_threshold: activates CAPTCHA after N attempts per IP.
- always_require_captcha_for_web: requires CAPTCHA on every web request.

Both exempt B2C mobile clients and are disabled when RECAPTCHA_SECRET_KEY is empty.
"""

from collections.abc import Callable

from fastapi import Request

from app.auth.ip_attempt_tracker import ip_tracker
from app.auth.recaptcha import verify_recaptcha_token
from app.config.settings import settings
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode


def require_captcha_after_threshold(
    action: str,
    threshold: int,
    window_seconds: int,
    *,
    track_all_requests: bool = False,
) -> Callable:
    """Return a FastAPI dependency that requires CAPTCHA after threshold attempts.

    Args:
        action: reCAPTCHA action value (e.g. "login", "forgot_password").
        threshold: number of attempts before CAPTCHA is required.
        window_seconds: sliding window duration.
        track_all_requests: if True, every call increments the counter
            (for endpoints like forgot-password where every request counts).
            If False, the caller must call ip_tracker.increment manually on failure.
    """

    async def _guard(request: Request) -> None:
        if not settings.RECAPTCHA_SECRET_KEY:
            return

        if threshold == 0:
            return

        client_type = request.headers.get("x-client-type", "").strip().lower()
        if client_type == "b2c-mobile":
            return

        ip = request.client.host

        if track_all_requests:
            ip_tracker.increment(ip, action)

        count = ip_tracker.get_count(ip, action, window_seconds)
        if count < threshold:
            return

        token = request.headers.get("x-recaptcha-token", "").strip()
        if not token:
            # locale not available pre-auth; default to "en" (decision C)
            raise envelope_exception(ErrorCode.AUTH_CAPTCHA_REQUIRED, status=429, locale="en")

        await verify_recaptcha_token(token, action=action)

    return _guard


def always_require_captcha_for_web(action: str) -> Callable:
    """Return a FastAPI dependency that always requires CAPTCHA from web clients.

    Mobile clients (x-client-type: b2c-mobile) are exempt.
    """

    async def _guard(request: Request) -> None:
        if not settings.RECAPTCHA_SECRET_KEY:
            return

        client_type = request.headers.get("x-client-type", "").strip().lower()
        if client_type == "b2c-mobile":
            return

        token = request.headers.get("x-recaptcha-token", "").strip()
        if not token:
            # locale not available pre-auth; default to "en" (decision C)
            raise envelope_exception(ErrorCode.AUTH_CAPTCHA_REQUIRED, status=403, locale="en")

        await verify_recaptcha_token(token, action=action)

    return _guard
