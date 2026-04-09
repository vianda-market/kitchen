# app/services/ads/subscription_ads_hook.py
"""
Ads notification hooks for subscription lifecycle events.

These are called best-effort (try/except, non-blocking) from:
- Stripe webhook: payment_intent.succeeded -> notify_ads_subscription_activated
- Subscription renewal cron -> notify_ads_subscription_renewed

The hook queries subscription + user + plan data, builds a canonical
ConversionEvent, and enqueues to all enabled ad platforms via ARQ.

IMPORTANT: This module must never raise exceptions that bubble up to callers.
All errors are logged and swallowed. Ads tracking is never worth breaking
the payment flow.
"""
import logging
from datetime import datetime, timezone
from uuid import UUID

import psycopg2.extensions

from app.services.ads.conversion_service import (
    enqueue_conversion_for_all_platforms,
    get_enabled_platforms,
)
from app.services.ads.models import (
    AdsPlatform,
    CampaignStrategy,
    ConversionEvent,
    ConversionEventType,
)
from app.utils.db import db_read

logger = logging.getLogger(__name__)


def _get_subscription_ads_data(
    subscription_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict | None:
    """
    Query subscription + user + plan data needed for conversion events.

    Returns dict with: user_email, user_phone, plan_price, currency_code,
    subscription_months, user_id. Or None if not found.
    """
    row = db_read(
        """
        SELECT
            s.subscription_id,
            s.user_id,
            u.email,
            u.mobile_number,
            p.price AS plan_price,
            cc.currency_code
        FROM subscription_info s
        JOIN core.user_info u ON s.user_id = u.user_id
        JOIN plan_info p ON s.plan_id = p.plan_id
        JOIN core.credit_currency cc ON p.market_id = cc.market_id
        WHERE s.subscription_id = %s::uuid
        """,
        (str(subscription_id),),
        connection=db,
        fetch_one=True,
    )
    return row


def _get_click_tracking_data(
    subscription_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict | None:
    """
    Get ad click tracking data for this subscription (if captured by frontend).
    Returns dict with click identifiers, or None if no tracking data exists.
    """
    row = db_read(
        """
        SELECT gclid, wbraid, gbraid, fbclid, fbc, fbp, event_id, source_platform
        FROM core.ad_click_tracking
        WHERE subscription_id = %s::uuid
        ORDER BY captured_at DESC
        LIMIT 1
        """,
        (str(subscription_id),),
        connection=db,
        fetch_one=True,
    )
    return row


def _build_subscription_event(
    event_type: ConversionEventType,
    subscription_id: UUID,
    sub_data: dict,
    click_data: dict | None,
) -> ConversionEvent:
    """Build a ConversionEvent from subscription + click tracking data."""
    return ConversionEvent(
        # Platform is set per-enqueue (fan-out to all enabled platforms)
        platform=AdsPlatform.GOOGLE,  # Placeholder; overridden by fan-out
        event_type=event_type,
        strategy=CampaignStrategy.B2C_SUBSCRIBER,
        entity_id=str(subscription_id),
        user_email=sub_data["email"] or "",
        user_phone=sub_data.get("mobile_number"),
        conversion_value=float(sub_data.get("plan_price", 0)),
        currency_code=sub_data.get("currency_code", "USD"),
        event_time=datetime.now(timezone.utc),
        # Click identifiers (from frontend capture, may be None)
        gclid=(click_data or {}).get("gclid"),
        wbraid=(click_data or {}).get("wbraid"),
        gbraid=(click_data or {}).get("gbraid"),
        fbclid=(click_data or {}).get("fbclid"),
        fbc=(click_data or {}).get("fbc"),
        fbp=(click_data or {}).get("fbp"),
        event_id=(click_data or {}).get("event_id"),
        custom_data={"subscription_type": "b2c_individual"},
    )


async def notify_ads_subscription_activated(
    subscription_id: UUID,
    db: psycopg2.extensions.connection,
    redis=None,
) -> None:
    """
    Notify ad platforms that a subscription was activated (first payment succeeded).

    Called best-effort from Stripe webhook after db.commit().
    Never raises. All errors logged and swallowed.

    Args:
        subscription_id: The activated subscription UUID.
        db: DB connection (for querying subscription/user/plan data).
        redis: ArqRedis connection. If None, attempts to create one from settings.
    """
    try:
        platforms = get_enabled_platforms()
        if not platforms:
            return

        sub_data = _get_subscription_ads_data(subscription_id, db)
        if not sub_data or not sub_data.get("email"):
            logger.info(
                "ads_hook_skip_no_email",
                extra={"subscription_id": str(subscription_id)},
            )
            return

        click_data = _get_click_tracking_data(subscription_id, db)

        event = _build_subscription_event(
            ConversionEventType.SUBSCRIBE,
            subscription_id,
            sub_data,
            click_data,
        )

        if redis is None:
            redis = await _get_redis()

        await enqueue_conversion_for_all_platforms(redis, event)

        logger.info(
            "ads_hook_subscription_activated",
            extra={"subscription_id": str(subscription_id), "platforms": platforms},
        )

    except Exception:
        logger.exception(
            "ads_hook_subscription_activated_error",
            extra={"subscription_id": str(subscription_id)},
        )


async def notify_ads_subscription_renewed(
    subscription_id: UUID,
    db: psycopg2.extensions.connection,
    redis=None,
) -> None:
    """
    Notify ad platforms that a subscription was renewed.

    Called best-effort from renewal cron after successful renewal.
    Fires a Purchase event (standard Meta event for renewals).
    """
    try:
        platforms = get_enabled_platforms()
        if not platforms:
            return

        sub_data = _get_subscription_ads_data(subscription_id, db)
        if not sub_data or not sub_data.get("email"):
            return

        click_data = _get_click_tracking_data(subscription_id, db)

        event = _build_subscription_event(
            ConversionEventType.PURCHASE,
            subscription_id,
            sub_data,
            click_data,
        )
        event.custom_data = {
            "subscription_type": "b2c_individual",
            "purchase_type": "renewal",
        }

        if redis is None:
            redis = await _get_redis()

        await enqueue_conversion_for_all_platforms(redis, event)

    except Exception:
        logger.exception(
            "ads_hook_subscription_renewed_error",
            extra={"subscription_id": str(subscription_id)},
        )


async def _get_redis():
    """Get an ArqRedis connection from settings. Lazy import to avoid circular deps."""
    from arq import create_pool
    from arq.connections import RedisSettings

    from app.config.settings import settings

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    return await create_pool(redis_settings)
