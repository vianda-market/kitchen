# app/workers/conversion_worker.py
"""
ARQ task: upload a conversion event to the target ad platform.

Single task handles both Google and Meta. The platform is determined by
the job payload. Gateway resolution is deferred to the factory (Chunk 2).
"""

import logging
from datetime import timedelta

from arq import Retry

from app.services.ads.models import AdsPlatform, ConversionEvent

logger = logging.getLogger(__name__)


async def upload_conversion(ctx: dict, platform: str, event_data: dict) -> None:
    """
    Upload a single conversion event to the specified ad platform.

    Args:
        ctx: ARQ worker context (includes job_try count).
        platform: "google" or "meta".
        event_data: Serialized ConversionEvent (from ConversionEvent.to_dict()).
    """
    ads_platform = AdsPlatform(platform)
    event = ConversionEvent.from_dict(event_data)

    logger.info(
        "conversion_upload_start",
        extra={
            "platform": platform,
            "strategy": event.strategy.value,
            "event_type": event.event_type.value,
            "entity_id": event.entity_id,
        },
    )

    # Gateway resolution will be added in Chunk 2 (factory.get_conversion_gateway).
    # For now, import inline so the worker module loads even without gateways.
    try:
        from app.gateways.ads.factory import get_conversion_gateway

        gateway = get_conversion_gateway(ads_platform)
        result = gateway.upload_conversion(event)

        if result.success:
            logger.info(
                "conversion_upload_success",
                extra={"platform": platform, "entity_id": event.entity_id},
            )
        else:
            logger.warning(
                "conversion_upload_failed",
                extra={
                    "platform": platform,
                    "entity_id": event.entity_id,
                    "error": result.error_message,
                    "category": result.error_category,
                },
            )
            # Retryable errors get exponential backoff
            if result.error_category in ("rate_limited", "transient"):
                job_try = ctx.get("job_try", 1)
                raise Retry(defer=timedelta(minutes=job_try * 15))

    except ImportError:
        # Gateway not yet implemented (Chunk 2). Log and skip.
        logger.info(
            "conversion_upload_skipped_no_gateway",
            extra={"platform": platform, "entity_id": event.entity_id},
        )
    except Retry:
        raise  # Let ARQ handle retry
    except Exception:
        logger.exception(
            "conversion_upload_error",
            extra={"platform": platform, "entity_id": event.entity_id},
        )
        job_try = ctx.get("job_try", 1)
        raise Retry(defer=timedelta(minutes=job_try * 15)) from None
