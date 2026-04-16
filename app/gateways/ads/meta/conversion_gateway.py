# app/gateways/ads/meta/conversion_gateway.py
"""
Meta Conversions API (CAPI) gateway.

Uploads server-side conversion events to Meta for attribution and campaign
optimization. Handles:
- Standard event names with custom_data parameters (Lead, Subscribe, etc.)
- SHA256-hashed PII for Event Match Quality (EMQ)
- fbc/fbp cookie identifiers for click attribution
- event_id-based deduplication with Pixel JS and Meta SDK
- action_source selection (website vs app vs system_generated)
- Batch support (1,000 events per request, Meta limit)
"""

import logging

from facebook_business.adobjects.serverside.action_source import ActionSource
from facebook_business.adobjects.serverside.custom_data import CustomData
from facebook_business.adobjects.serverside.event import Event
from facebook_business.adobjects.serverside.event_request import EventRequest
from facebook_business.adobjects.serverside.user_data import UserData

from app.gateways.ads.base import AdsConversionGateway
from app.gateways.ads.meta.auth import get_pixel_id, init_meta_ads_client
from app.services.ads.error_handler import AdsErrorCategory, categorize_meta_error
from app.services.ads.models import ConversionEvent, ConversionResult
from app.services.ads.pii_hasher import normalize_and_hash

logger = logging.getLogger(__name__)


class MetaConversionGateway(AdsConversionGateway):
    """Live Meta CAPI conversion upload gateway."""

    def __init__(self):
        self._pixel_id: str | None = None

    @property
    def pixel_id(self) -> str:
        if self._pixel_id is None:
            self._pixel_id = get_pixel_id()
        return self._pixel_id

    def _build_user_data(self, event: ConversionEvent) -> UserData:
        """Build Meta UserData with hashed PII for EMQ."""
        user_data = UserData()

        # Hashed email (required for EMQ)
        user_data.email = normalize_and_hash(event.user_email)

        # Hashed phone (strongly recommended)
        if event.user_phone:
            user_data.phone = normalize_and_hash(event.user_phone)

        # Meta click/browser cookies (from frontend capture)
        if event.fbc:
            user_data.fbc = event.fbc
        if event.fbp:
            user_data.fbp = event.fbp

        # Hashed external_id for cross-device matching
        if event.entity_id:
            user_data.external_id = normalize_and_hash(event.entity_id)

        return user_data

    def _build_custom_data(self, event: ConversionEvent) -> CustomData:
        """Build Meta CustomData with value, currency, and strategy-specific params."""
        custom_data = CustomData()

        custom_data.value = event.conversion_value
        custom_data.currency = event.currency_code

        # order_id for server-side dedup (Meta also uses event_id for Pixel/SDK dedup)
        custom_data.order_id = str(event.entity_id)

        custom_data.content_type = "subscription"

        # Predicted LTV for value optimization
        if event.predicted_ltv is not None:
            custom_data.predicted_ltv = event.predicted_ltv

        # Strategy-specific custom parameters are passed through
        # The SDK serializes unknown keys in CustomData via custom_properties
        if event.custom_data:
            custom_data.custom_properties = event.custom_data

        return custom_data

    def _determine_action_source(self, event: ConversionEvent) -> ActionSource:
        """
        Determine the action_source based on event context.

        - system_generated: for delayed offline events (B2B approvals, renewals)
        - website: for events originating from web actions
        - app: for events originating from mobile app actions
        """
        # B2B approval events are always system_generated (they happen after human review)
        if event.event_type.value in ("ApprovedPartner",):
            return ActionSource.SYSTEM_GENERATED

        # If the event was deferred significantly (>1h), treat as system_generated
        # This helps with attribution backfill for delayed B2B events
        if event.custom_data.get("action_source") == "system_generated":
            return ActionSource.SYSTEM_GENERATED

        if event.custom_data.get("action_source") == "app":
            return ActionSource.APP

        return ActionSource.WEBSITE

    def _build_event(self, event: ConversionEvent) -> Event:
        """Build a Meta server-side Event from a canonical ConversionEvent."""
        server_event = Event()

        # Standard event name (Lead, Subscribe, Purchase, CompleteRegistration, etc.)
        server_event.event_name = event.event_type.value

        # Unix timestamp
        server_event.event_time = int(event.event_time.timestamp())

        # event_id for dedup with Pixel JS and Meta SDK
        server_event.event_id = event.event_id or f"conv-{event.entity_id}"

        server_event.action_source = self._determine_action_source(event)
        server_event.user_data = self._build_user_data(event)
        server_event.custom_data = self._build_custom_data(event)

        return server_event

    def upload_conversion(self, event: ConversionEvent) -> ConversionResult:
        """Upload a single conversion to Meta CAPI."""
        try:
            init_meta_ads_client()

            server_event = self._build_event(event)

            request = EventRequest(
                pixel_id=self.pixel_id,
                events=[server_event],
            )
            response = request.execute()

            events_received = getattr(response, "events_received", 0)
            if events_received > 0:
                logger.info(
                    "meta_capi_conversion_uploaded",
                    extra={
                        "entity_id": event.entity_id,
                        "events_received": events_received,
                    },
                )
                return ConversionResult(
                    success=True,
                    platform=event.platform,
                    entity_id=event.entity_id,
                    platform_response={"events_received": events_received},
                )

            # Zero events received -- something went wrong
            logger.warning(
                "meta_capi_zero_events_received",
                extra={"entity_id": event.entity_id},
            )
            return ConversionResult(
                success=False,
                platform=event.platform,
                entity_id=event.entity_id,
                error_message="Zero events received by Meta",
                error_category=AdsErrorCategory.TRANSIENT.value,
            )

        except Exception as exc:
            # Extract Meta error code if available
            error_code = getattr(exc, "api_error_code", None) or 0
            error_message = str(exc)
            category = categorize_meta_error(int(error_code), error_message)

            logger.exception(
                "meta_capi_upload_error",
                extra={
                    "entity_id": event.entity_id,
                    "error_code": error_code,
                    "category": category.value,
                },
            )
            return ConversionResult(
                success=False,
                platform=event.platform,
                entity_id=event.entity_id,
                error_message=error_message,
                error_category=category.value,
            )

    def upload_conversions_batch(self, events: list[ConversionEvent]) -> list[ConversionResult]:
        """Upload a batch of conversions. Max 1,000 per request (Meta limit)."""
        if not events:
            return []

        BATCH_SIZE = 1000
        results = []

        for i in range(0, len(events), BATCH_SIZE):
            batch = events[i : i + BATCH_SIZE]
            try:
                init_meta_ads_client()

                server_events = [self._build_event(e) for e in batch]

                request = EventRequest(
                    pixel_id=self.pixel_id,
                    events=server_events,
                )
                response = request.execute()

                events_received = getattr(response, "events_received", 0)
                if events_received >= len(batch):
                    for event in batch:
                        results.append(
                            ConversionResult(
                                success=True,
                                platform=event.platform,
                                entity_id=event.entity_id,
                            )
                        )
                else:
                    # Partial -- can't determine which ones failed
                    for event in batch:
                        results.append(
                            ConversionResult(
                                success=False,
                                platform=event.platform,
                                entity_id=event.entity_id,
                                error_message=f"Batch partial: {events_received}/{len(batch)} received",
                                error_category=AdsErrorCategory.PARTIAL_FAILURE.value,
                            )
                        )

            except Exception as exc:
                error_code = getattr(exc, "api_error_code", None) or 0
                category = categorize_meta_error(int(error_code), str(exc))
                for event in batch:
                    results.append(
                        ConversionResult(
                            success=False,
                            platform=event.platform,
                            entity_id=event.entity_id,
                            error_message=str(exc),
                            error_category=category.value,
                        )
                    )

        return results
