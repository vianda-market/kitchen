# app/gateways/ads/mock_gateway.py
"""
Mock ad platform gateway. Logs payloads and returns success.

Used when GOOGLE_ADS_PROVIDER=mock / META_ADS_PROVIDER=mock / DEV_MODE=true.
Allows full end-to-end testing of the conversion pipeline without live
credentials or external API calls.
"""

import logging

from app.gateways.ads.base import AdsCampaignGateway, AdsConversionGateway
from app.services.ads.models import ConversionEvent, ConversionResult

logger = logging.getLogger(__name__)


class MockConversionGateway(AdsConversionGateway):
    """Logs conversion payloads, returns success. No external calls."""

    def __init__(self, platform_name: str):
        self.platform_name = platform_name

    def upload_conversion(self, event: ConversionEvent) -> ConversionResult:
        logger.info(
            "mock_conversion_upload",
            extra={
                "platform": self.platform_name,
                "event_type": event.event_type.value,
                "strategy": event.strategy.value,
                "entity_id": event.entity_id,
                "conversion_value": event.conversion_value,
                "currency_code": event.currency_code,
                "custom_data": event.custom_data,
            },
        )
        return ConversionResult(
            success=True,
            platform=event.platform,
            entity_id=event.entity_id,
        )

    def upload_conversions_batch(self, events: list[ConversionEvent]) -> list[ConversionResult]:
        return [self.upload_conversion(e) for e in events]


class MockCampaignGateway(AdsCampaignGateway):
    """Logs campaign operations, returns mock IDs. No external calls."""

    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self._counter = 0

    def create_campaign(self, config: dict) -> str:
        self._counter += 1
        campaign_id = f"mock-{self.platform_name}-campaign-{self._counter}"
        logger.info(
            "mock_campaign_create",
            extra={"platform": self.platform_name, "campaign_id": campaign_id, "config": config},
        )
        return campaign_id

    def update_campaign(self, campaign_id: str, updates: dict) -> None:
        logger.info(
            "mock_campaign_update",
            extra={"platform": self.platform_name, "campaign_id": campaign_id, "updates": updates},
        )

    def get_campaign(self, campaign_id: str) -> dict:
        return {
            "id": campaign_id,
            "platform": self.platform_name,
            "status": "active",
            "daily_budget": 10000,
        }

    def pause_campaign(self, campaign_id: str) -> None:
        logger.info(
            "mock_campaign_pause",
            extra={"platform": self.platform_name, "campaign_id": campaign_id},
        )

    def get_campaign_insights(self, campaign_id: str, date_range: dict) -> dict:
        return {
            "campaign_id": campaign_id,
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "spend_cents": 0,
        }
