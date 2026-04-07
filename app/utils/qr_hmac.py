"""HMAC-SHA256 signing and verification for QR code URLs."""

from __future__ import annotations

import hashlib
import hmac

from app.config.settings import settings


def sign_qr_code_id(qr_code_id: str) -> str:
    """HMAC-SHA256 over qr_code_id, truncated to first 16 hex characters."""
    secret = settings.QR_HMAC_SECRET
    if not secret:
        raise ValueError("QR_HMAC_SECRET not configured")
    mac = hmac.new(secret.encode(), qr_code_id.encode(), hashlib.sha256)
    return mac.hexdigest()[:16]


def verify_qr_signature(qr_code_id: str, sig: str) -> bool:
    """Verify HMAC signature with constant-time comparison."""
    expected = sign_qr_code_id(qr_code_id)
    return hmac.compare_digest(expected, sig)


def build_signed_qr_url(qr_code_id: str) -> str:
    """Build the full signed QR code URL for embedding in QR images."""
    sig = sign_qr_code_id(qr_code_id)
    return f"https://vianda.app/qr?id={qr_code_id}&sig={sig}"
