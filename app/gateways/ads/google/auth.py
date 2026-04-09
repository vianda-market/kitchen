# app/gateways/ads/google/auth.py
"""
Google Ads client initialization.

The GoogleAdsClient is expensive to instantiate (OAuth2 token refresh,
HTTP session setup). This module creates it once and caches it.

Credentials come from:
- Local dev: settings (GOOGLE_ADS_DEVELOPER_TOKEN, etc.)
- Production: GCP Secret Manager via app/core/gcp_secrets.py
"""
import logging
import os

from google.ads.googleads.client import GoogleAdsClient

from app.config.settings import settings

logger = logging.getLogger(__name__)

_cached_client: GoogleAdsClient | None = None


def _load_credentials() -> dict:
    """
    Load Google Ads API credentials from settings (local) or Secret Manager (prod).

    Returns dict suitable for GoogleAdsClient.load_from_dict().
    """
    env = (os.getenv("ENVIRONMENT") or "local").lower()

    if env in ("local", "dev"):
        # Local dev: read from settings (.env file)
        return {
            "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
            "client_id": os.getenv("GOOGLE_ADS_OAUTH_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_ADS_OAUTH_CLIENT_SECRET", ""),
            "refresh_token": os.getenv("GOOGLE_ADS_OAUTH_REFRESH_TOKEN", ""),
            "login_customer_id": settings.GOOGLE_ADS_CUSTOMER_ID.replace("-", ""),
            "use_proto_plus": True,
        }

    # Staging/prod: fetch from GCP Secret Manager
    from app.core.gcp_secrets import get_secret

    return {
        "developer_token": get_secret("google-ads-developer-token"),
        "client_id": get_secret("google-ads-oauth-client-id"),
        "client_secret": get_secret("google-ads-oauth-client-secret"),
        "refresh_token": get_secret("google-ads-oauth-refresh-token"),
        "login_customer_id": get_secret("google-ads-login-customer-id"),
        "use_proto_plus": True,
    }


def get_google_ads_client() -> GoogleAdsClient:
    """
    Get or create the cached GoogleAdsClient singleton.

    Raises ValueError if credentials are missing or invalid.
    """
    global _cached_client
    if _cached_client is not None:
        return _cached_client

    credentials = _load_credentials()

    # Validate minimum required fields
    if not credentials.get("developer_token"):
        raise ValueError(
            "Google Ads developer_token is required. "
            "Set GOOGLE_ADS_DEVELOPER_TOKEN in .env (local) or create the secret in GCP (prod)."
        )
    if not credentials.get("refresh_token"):
        raise ValueError(
            "Google Ads OAuth2 refresh_token is required. "
            "Set GOOGLE_ADS_OAUTH_REFRESH_TOKEN in .env (local) or create the secret in GCP (prod)."
        )

    _cached_client = GoogleAdsClient.load_from_dict(credentials)
    logger.info("google_ads_client_initialized")
    return _cached_client


def get_customer_id() -> str:
    """
    Get the Google Ads customer ID (numeric, no dashes).

    Local: from settings. Prod: from Secret Manager.
    """
    env = (os.getenv("ENVIRONMENT") or "local").lower()
    if env in ("local", "dev"):
        return settings.GOOGLE_ADS_CUSTOMER_ID.replace("-", "")

    from app.core.gcp_secrets import get_secret
    return get_secret("google-ads-customer-id").replace("-", "")


def get_conversion_action_id() -> str:
    """
    Get the Google Ads conversion action ID.

    Local: from settings. Prod: from Secret Manager.
    """
    env = (os.getenv("ENVIRONMENT") or "local").lower()
    if env in ("local", "dev"):
        return settings.GOOGLE_ADS_CONVERSION_ACTION_ID

    from app.core.gcp_secrets import get_secret
    return get_secret("google-ads-conversion-action-id")


def clear_client_cache() -> None:
    """Clear the cached client. For testing or credential rotation."""
    global _cached_client
    _cached_client = None
