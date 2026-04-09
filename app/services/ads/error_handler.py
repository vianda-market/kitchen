# app/services/ads/error_handler.py
"""
Unified error taxonomy for ad platform operations.

Maps platform-specific error codes to shared categories so the worker
and conversion service can make retry/alert decisions without knowing
platform internals.
"""
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class AdsErrorCategory(Enum):
    RATE_LIMITED = "rate_limited"        # Retry with exponential backoff
    PARTIAL_FAILURE = "partial_failure"  # Some events succeeded, retry failed ones
    AUTH_EXPIRED = "auth_expired"        # Alert ops, do not retry
    INVALID_DATA = "invalid_data"       # Bad PII, missing click ID. Log and skip.
    TRANSIENT = "transient"             # Network/timeout. Retry immediately.
    PERMANENT = "permanent"             # Unrecoverable. Log and dead-letter.


def categorize_google_error(error) -> AdsErrorCategory:
    """
    Map a Google Ads API error to a shared category.

    Args:
        error: A google.ads.googleads error object or error code string.

    Returns:
        AdsErrorCategory for retry/alert decision.
    """
    error_str = str(getattr(error, "error_code", error))

    if "RESOURCE_EXHAUSTED" in error_str:
        return AdsErrorCategory.RATE_LIMITED
    if "AUTHENTICATION" in error_str or "AUTHORIZATION" in error_str:
        return AdsErrorCategory.AUTH_EXPIRED
    if "INVALID" in error_str or "REQUIRED_FIELD_MISSING" in error_str:
        return AdsErrorCategory.INVALID_DATA
    if "INTERNAL" in error_str or "TRANSIENT" in error_str:
        return AdsErrorCategory.TRANSIENT

    logger.warning("google_ads_unknown_error", extra={"error": error_str})
    return AdsErrorCategory.PERMANENT


def categorize_meta_error(error_code: int, error_message: str = "") -> AdsErrorCategory:
    """
    Map a Meta Marketing API error code to a shared category.

    Meta error codes: https://developers.facebook.com/docs/marketing-api/error-reference

    Args:
        error_code: Numeric Meta API error code.
        error_message: Optional error message for logging.

    Returns:
        AdsErrorCategory for retry/alert decision.
    """
    if error_code == 17:  # User request limit reached
        return AdsErrorCategory.RATE_LIMITED
    if error_code == 4:   # Application request limit reached
        return AdsErrorCategory.RATE_LIMITED
    if error_code == 32:  # Temporarily unavailable
        return AdsErrorCategory.TRANSIENT
    if error_code == 190:  # Invalid/expired access token
        return AdsErrorCategory.AUTH_EXPIRED
    if error_code == 100:  # Invalid parameter
        return AdsErrorCategory.INVALID_DATA
    if error_code == 200:  # Permission error
        return AdsErrorCategory.AUTH_EXPIRED
    if error_code == 1:    # Unknown error
        return AdsErrorCategory.TRANSIENT
    if error_code == 2:    # Temporary service error
        return AdsErrorCategory.TRANSIENT

    logger.warning(
        "meta_ads_unknown_error",
        extra={"error_code": error_code, "message": error_message},
    )
    return AdsErrorCategory.PERMANENT


def should_retry(category: AdsErrorCategory) -> bool:
    """Return True if the error category is retryable."""
    return category in (
        AdsErrorCategory.RATE_LIMITED,
        AdsErrorCategory.TRANSIENT,
        AdsErrorCategory.PARTIAL_FAILURE,
    )
