"""
reCAPTCHA v3 verification for public endpoints.

- verify_recaptcha: FastAPI dependency (always-on, used by leads router).
- verify_recaptcha_token: Reusable core that validates a token string,
  optionally checking the reCAPTCHA action value.

Disabled when RECAPTCHA_SECRET_KEY is empty (local dev convenience).
Exempt for B2C mobile apps (x-client-type: b2c-mobile).
Fails open if Google's verify API is unreachable.
"""

import logging

import requests
from fastapi import HTTPException, Request

from app.config.settings import settings

logger = logging.getLogger("my_app")

VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


async def verify_recaptcha_token(token: str, action: str | None = None) -> None:
    """Verify a reCAPTCHA v3 token against Google's API.

    Raises HTTPException(403) on failure. Fails open on network error.
    If `action` is provided, validates that the token was generated for
    that specific action (prevents cross-action token reuse).
    """
    try:
        resp = requests.post(
            VERIFY_URL,
            data={"secret": settings.RECAPTCHA_SECRET_KEY, "response": token},
            timeout=5,
        )
        data = resp.json()
    except Exception:
        logger.warning("reCAPTCHA verify API unreachable — failing open")
        return

    if not data.get("success"):
        raise HTTPException(status_code=403, detail="reCAPTCHA verification failed")

    if action and data.get("action") != action:
        raise HTTPException(status_code=403, detail="reCAPTCHA action mismatch")

    score = data.get("score", 0.0)
    if score < settings.RECAPTCHA_SCORE_THRESHOLD:
        raise HTTPException(status_code=403, detail="reCAPTCHA score too low")


async def verify_recaptcha(request: Request) -> None:
    """FastAPI dependency: validate reCAPTCHA v3 token (always-on, leads endpoints)."""
    if not settings.RECAPTCHA_SECRET_KEY:
        return

    client_type = request.headers.get("x-client-type", "").strip().lower()
    if client_type == "b2c-mobile":
        return

    token = request.headers.get("x-recaptcha-token", "").strip()
    if not token:
        raise HTTPException(status_code=403, detail="Missing reCAPTCHA token")

    await verify_recaptcha_token(token)
