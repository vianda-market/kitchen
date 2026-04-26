"""Checksum utilities for file integrity validation.

Layer 1 (Client → Backend): verify_checksum before upload.
Layer 2 (Backend → GCS): pass MD5 to GCS for server-side verification.
"""

import hashlib

from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest of data."""
    return hashlib.sha256(data).hexdigest()


def compute_md5(data: bytes) -> str:
    """Compute MD5 hex digest of data."""
    return hashlib.md5(data).hexdigest()


def verify_checksum(
    data: bytes,
    expected_checksum: str,
    algorithm: str = "sha256",
) -> None:
    """
    Verify file integrity. Raises 400 if checksum does not match.
    Call this before uploading to GCS or local storage.
    """
    if algorithm == "sha256":
        actual = compute_sha256(data)
    elif algorithm == "md5":
        actual = compute_md5(data)
    else:
        raise envelope_exception(ErrorCode.CHECKSUM_UNSUPPORTED_ALGORITHM, status=400, locale="en", algorithm=algorithm)

    if actual.lower() != expected_checksum.strip().lower():
        raise envelope_exception(ErrorCode.CHECKSUM_MISMATCH, status=400, locale="en")
