# app/gateways/ads/google/conversion_gateway.py
"""
Google Ads conversion upload gateway.

Uploads Enhanced Conversions via the ConversionUploadService. Handles:
- GCLID / WBRAID / GBRAID click identifier selection
- SHA256-hashed PII for user matching
- Partial failure handling
- order_id-based idempotency (Google deduplicates by order_id per conversion action)
"""
import logging

from app.gateways.ads.base import AdsConversionGateway
from app.gateways.ads.google.auth import (
    get_conversion_action_id,
    get_customer_id,
    get_google_ads_client,
)
from app.services.ads.error_handler import AdsErrorCategory, categorize_google_error
from app.services.ads.models import ConversionEvent, ConversionResult
from app.services.ads.pii_hasher import normalize_and_hash

logger = logging.getLogger(__name__)


class GoogleAdsConversionGateway(AdsConversionGateway):
    """Live Google Ads conversion upload gateway."""

    def __init__(self):
        self._customer_id: str | None = None
        self._conversion_action_id: str | None = None

    @property
    def customer_id(self) -> str:
        if self._customer_id is None:
            self._customer_id = get_customer_id()
        return self._customer_id

    @property
    def conversion_action_id(self) -> str:
        if self._conversion_action_id is None:
            self._conversion_action_id = get_conversion_action_id()
        return self._conversion_action_id

    def _build_click_conversion(self, event: ConversionEvent):
        """Build a ClickConversion protobuf from a canonical ConversionEvent."""
        client = get_google_ads_client()

        click_conversion = client.get_type("ClickConversion")

        # Conversion action resource name
        click_conversion.conversion_action = (
            f"customers/{self.customer_id}/conversionActions/{self.conversion_action_id}"
        )

        # Idempotency: order_id prevents duplicate reporting
        click_conversion.order_id = str(event.entity_id)

        # Value
        click_conversion.conversion_value = event.conversion_value
        click_conversion.currency_code = event.currency_code

        # Timestamp (Google expects "yyyy-mm-dd hh:mm:ss+/-hh:mm" format)
        click_conversion.conversion_date_time = event.event_time.strftime(
            "%Y-%m-%d %H:%M:%S%z"
        )

        # Click identifier: gclid > wbraid > gbraid
        if event.gclid:
            click_conversion.gclid = event.gclid
        elif event.wbraid:
            click_conversion.wbraid = event.wbraid
        elif event.gbraid:
            click_conversion.gbraid = event.gbraid
        # If none set, Enhanced Conversions can still match via user identifiers

        # Enhanced Conversions: hashed PII for user matching
        user_identifier = client.get_type("UserIdentifier")
        user_identifier.hashed_email = normalize_and_hash(event.user_email)
        click_conversion.user_identifiers.append(user_identifier)

        if event.user_phone:
            phone_identifier = client.get_type("UserIdentifier")
            phone_identifier.hashed_phone_number = normalize_and_hash(event.user_phone)
            click_conversion.user_identifiers.append(phone_identifier)

        return click_conversion

    def upload_conversion(self, event: ConversionEvent) -> ConversionResult:
        """Upload a single conversion to Google Ads."""
        try:
            client = get_google_ads_client()
            service = client.get_service("ConversionUploadService")
            click_conversion = self._build_click_conversion(event)

            response = service.upload_click_conversions(
                customer_id=self.customer_id,
                conversions=[click_conversion],
                partial_failure=True,
            )

            # Check for partial failures
            if response.partial_failure_error:
                errors = response.partial_failure_error.details
                error_msgs = []
                for error in errors:
                    error_str = str(error)
                    category = categorize_google_error(error)
                    error_msgs.append(error_str)
                    logger.error(
                        "google_ads_partial_failure",
                        extra={
                            "entity_id": event.entity_id,
                            "error": error_str,
                            "category": category.value,
                        },
                    )

                return ConversionResult(
                    success=False,
                    platform=event.platform,
                    entity_id=event.entity_id,
                    error_message="; ".join(error_msgs),
                    error_category=categorize_google_error(errors[0]).value if errors else "permanent",
                )

            logger.info(
                "google_ads_conversion_uploaded",
                extra={"entity_id": event.entity_id},
            )
            return ConversionResult(
                success=True,
                platform=event.platform,
                entity_id=event.entity_id,
            )

        except Exception as exc:
            category = categorize_google_error(exc)
            logger.exception(
                "google_ads_upload_error",
                extra={
                    "entity_id": event.entity_id,
                    "category": category.value,
                },
            )
            return ConversionResult(
                success=False,
                platform=event.platform,
                entity_id=event.entity_id,
                error_message=str(exc),
                error_category=category.value,
            )

    def upload_conversions_batch(
        self, events: list[ConversionEvent]
    ) -> list[ConversionResult]:
        """Upload a batch of conversions. Max 2,000 per request (Google limit)."""
        if not events:
            return []

        BATCH_SIZE = 2000
        results = []

        for i in range(0, len(events), BATCH_SIZE):
            batch = events[i : i + BATCH_SIZE]
            try:
                client = get_google_ads_client()
                service = client.get_service("ConversionUploadService")
                conversions = [self._build_click_conversion(e) for e in batch]

                response = service.upload_click_conversions(
                    customer_id=self.customer_id,
                    conversions=conversions,
                    partial_failure=True,
                )

                if response.partial_failure_error:
                    # Some failed -- mark individually
                    # For simplicity, mark all in this batch as partial failure
                    for event in batch:
                        results.append(
                            ConversionResult(
                                success=False,
                                platform=event.platform,
                                entity_id=event.entity_id,
                                error_message="Batch partial failure",
                                error_category=AdsErrorCategory.PARTIAL_FAILURE.value,
                            )
                        )
                else:
                    for event in batch:
                        results.append(
                            ConversionResult(
                                success=True,
                                platform=event.platform,
                                entity_id=event.entity_id,
                            )
                        )

            except Exception as exc:
                category = categorize_google_error(exc)
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
