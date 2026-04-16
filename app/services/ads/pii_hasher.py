# app/services/ads/pii_hasher.py
"""
PII hashing for ad platform conversion uploads.

Both Google Enhanced Conversions and Meta CAPI require identical
normalize-lowercase-SHA256 hashing for email and phone. This module
provides the shared implementation.

SECURITY: Raw PII must never be logged, stored in Redis, or persisted
beyond the initial event capture. Hash before enqueuing to ARQ.
"""

import hashlib


def normalize_and_hash(value: str) -> str:
    """
    Normalize (lowercase, strip whitespace) and SHA256-hash a PII value.

    Both Google and Meta require this exact procedure:
    1. Strip leading/trailing whitespace
    2. Lowercase
    3. UTF-8 encode
    4. SHA256 hex digest
    """
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def build_hashed_user_data(
    email: str,
    phone: str | None = None,
    user_id: str | None = None,
) -> dict:
    """
    Build hashed user data dict usable by both platform adapters.

    Args:
        email: User email (required). Will be normalized and hashed.
        phone: User phone in E.164 format (optional). Will be normalized and hashed.
        user_id: Internal user ID (optional). Hashed as external_id for Meta EMQ.

    Returns:
        Dict with hashed_email, and optionally hashed_phone and hashed_external_id.
    """
    data = {"hashed_email": normalize_and_hash(email)}
    if phone:
        data["hashed_phone"] = normalize_and_hash(phone)
    if user_id:
        data["hashed_external_id"] = normalize_and_hash(user_id)
    return data
