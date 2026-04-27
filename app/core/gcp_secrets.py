# app/core/gcp_secrets.py
"""
GCP Secret Manager client with in-memory TTL cache.

Uses Application Default Credentials (ADC):
- Local: gcloud auth application-default login
- Cloud Run: automatic via attached service account

Shared by all ad platform gateways (Google Ads, Meta Ads) and any future
service needing runtime secrets from GCP.
"""

import logging
import os
import time

logger = logging.getLogger(__name__)

_client = None
_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL = 3600  # 1 hour


def _get_client():
    global _client
    if _client is None:
        from google.cloud import secretmanager

        _client = secretmanager.SecretManagerServiceClient()
    return _client


def get_secret(secret_id: str, version: str = "latest", project_id: str | None = None) -> str:
    """
    Fetch a secret from GCP Secret Manager. Results are cached in memory for CACHE_TTL seconds.

    Args:
        secret_id: The secret name (e.g., "google-ads-developer-token").
        version: Secret version (default "latest").
        project_id: GCP project ID. Falls back to GCP_PROJECT_ID env var.

    Returns:
        The secret value as a string.

    Raises:
        ValueError: If project_id is not provided and GCP_PROJECT_ID env var is not set.
        google.api_core.exceptions.NotFound: If the secret does not exist.
    """
    if project_id is None:
        project_id = os.getenv("GCP_PROJECT_ID", "").strip()
    if not project_id:
        raise ValueError("GCP project ID required. Set GCP_PROJECT_ID env var or pass project_id.")

    cache_key = f"{project_id}/{secret_id}/{version}"
    if cache_key in _cache:
        value, ts = _cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            return value

    client = _get_client()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    value = response.payload.data.decode("UTF-8")
    _cache[cache_key] = (value, time.time())
    # Logs the secret NAME only (e.g. "STRIPE_SECRET_KEY"), never the value.
    # `value` is returned to the caller but is not present in this log call.
    logger.info(
        "gcp_secret_fetched", extra={"secret_id": secret_id}
    )  # codeql[py/clear-text-logging-sensitive-data]  # pragma: no cover
    return value


def clear_cache() -> None:
    """Clear the secret cache. Useful for testing or forced refresh."""
    _cache.clear()
