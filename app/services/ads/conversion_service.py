# app/services/ads/conversion_service.py
"""
Conversion event dispatch service. Builds canonical ConversionEvent instances
and fans out to all enabled ad platforms via ARQ deferred jobs.

This is the single entry point from business logic (subscription confirmation,
lead submission, employer onboarding) into the ads platform.
"""

import logging
from datetime import timedelta

from app.config.settings import settings
from app.services.ads.models import (
    ConversionEvent,
)

logger = logging.getLogger(__name__)


def get_enabled_platforms() -> list[str]:
    """Return list of enabled ad platform names from settings."""
    raw = (settings.ADS_ENABLED_PLATFORMS or "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _get_upload_delay(platform_name: str) -> timedelta:
    """Return the platform-specific upload delay."""
    if platform_name == "google":
        return timedelta(hours=settings.GOOGLE_ADS_UPLOAD_DELAY_HOURS)
    if platform_name == "meta":
        return timedelta(minutes=settings.META_ADS_UPLOAD_DELAY_MINUTES)
    return timedelta(minutes=5)  # Default


async def enqueue_conversion_for_all_platforms(
    redis,
    event: ConversionEvent,
) -> list[str]:
    """
    Fan out a conversion event to all enabled ad platforms.

    Each platform gets its own ARQ job with a platform-specific delay
    (Google: 24h, Meta: 5min). Job IDs are deterministic per platform +
    entity_id for idempotency.

    Args:
        redis: ArqRedis connection.
        event: The canonical conversion event.

    Returns:
        List of enqueued job IDs.
    """
    platforms = get_enabled_platforms()
    if not platforms:
        return []

    if settings.ADS_DRY_RUN:
        logger.info(
            "ads_dry_run_skip_enqueue",
            extra={
                "entity_id": event.entity_id,
                "strategy": event.strategy.value,
                "event_type": event.event_type.value,
                "platforms": platforms,
            },
        )
        return []

    job_ids = []
    event_data = event.to_dict()

    for platform_name in platforms:
        delay = _get_upload_delay(platform_name)
        job_id = f"{platform_name}-conv-{event.entity_id}"

        await redis.enqueue_job(
            "upload_conversion",
            platform=platform_name,
            event_data=event_data,
            _defer_by=delay,
            _job_id=job_id,
        )

        logger.info(
            "conversion_enqueued",
            extra={
                "platform": platform_name,
                "job_id": job_id,
                "entity_id": event.entity_id,
                "strategy": event.strategy.value,
                "event_type": event.event_type.value,
                "defer_seconds": int(delay.total_seconds()),
            },
        )
        job_ids.append(job_id)

    return job_ids
