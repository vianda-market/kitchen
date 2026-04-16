# app/gateways/ads/meta/auth.py
"""
Meta Ads API client initialization.

Meta uses a system user long-lived token (no OAuth2 refresh dance).
The token is created in Business Manager UI and stored in Secret Manager.

appsecret_proof is computed per request by the SDK when app_secret is provided,
preventing token hijacking.
"""

import logging
import os

from facebook_business.api import FacebookAdsApi

from app.config.settings import settings

logger = logging.getLogger(__name__)

_initialized = False


def _load_credentials() -> dict:
    """
    Load Meta Ads API credentials from settings (local) or Secret Manager (prod).
    """
    env = (os.getenv("ENVIRONMENT") or "local").lower()

    if env in ("local", "dev"):
        return {
            "access_token": settings.META_ADS_SYSTEM_USER_TOKEN,
            "app_secret": settings.META_ADS_APP_SECRET,
            "pixel_id": settings.META_ADS_PIXEL_ID,
            "ad_account_id": settings.META_ADS_AD_ACCOUNT_ID,
            "api_version": settings.META_ADS_API_VERSION,
        }

    from app.core.gcp_secrets import get_secret

    return {
        "access_token": get_secret("meta-ads-system-user-token"),
        "app_secret": get_secret("meta-ads-app-secret"),
        "pixel_id": get_secret("meta-ads-pixel-id"),
        "ad_account_id": get_secret("meta-ads-ad-account-id"),
        "api_version": settings.META_ADS_API_VERSION,
    }


def init_meta_ads_client() -> None:
    """
    Initialize the global FacebookAdsApi singleton.

    Safe to call multiple times; only initializes once.
    The SDK uses a global singleton pattern, so this sets the default API instance.

    Raises ValueError if access_token is missing.
    """
    global _initialized
    if _initialized:
        return

    credentials = _load_credentials()

    if not credentials.get("access_token"):
        raise ValueError(
            "Meta Ads system user token is required. "
            "Set META_ADS_SYSTEM_USER_TOKEN in .env (local) or create the secret in GCP (prod)."
        )

    FacebookAdsApi.init(
        app_id=None,  # Not needed for system user auth
        app_secret=credentials["app_secret"] or None,
        access_token=credentials["access_token"],
        api_version=credentials["api_version"],
    )

    _initialized = True
    logger.info("meta_ads_client_initialized")


def get_pixel_id() -> str:
    """Get the Meta Pixel ID for CAPI events."""
    env = (os.getenv("ENVIRONMENT") or "local").lower()
    if env in ("local", "dev"):
        return settings.META_ADS_PIXEL_ID

    from app.core.gcp_secrets import get_secret

    return get_secret("meta-ads-pixel-id")


def get_ad_account_id() -> str:
    """Get the Meta ad account ID (act_XXXXXXXXX format)."""
    env = (os.getenv("ENVIRONMENT") or "local").lower()
    if env in ("local", "dev"):
        return settings.META_ADS_AD_ACCOUNT_ID

    from app.core.gcp_secrets import get_secret

    return get_secret("meta-ads-ad-account-id")


def clear_client_cache() -> None:
    """Reset initialization flag. For testing or credential rotation."""
    global _initialized
    _initialized = False
