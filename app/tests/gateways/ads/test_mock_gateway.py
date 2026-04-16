"""
Unit tests for mock ads gateway (app/gateways/ads/mock_gateway.py).

Verifies mock handles all event types and strategies correctly,
batch uploads, and campaign CRUD stubs.
"""

from datetime import UTC, datetime

from app.gateways.ads.mock_gateway import MockCampaignGateway, MockConversionGateway
from app.services.ads.models import (
    AdsPlatform,
    CampaignStrategy,
    ConversionEvent,
    ConversionEventType,
)


def _make_event(**overrides):
    defaults = dict(
        platform=AdsPlatform.META,
        event_type=ConversionEventType.SUBSCRIBE,
        strategy=CampaignStrategy.B2C_SUBSCRIBER,
        entity_id="sub-test-001",
        user_email="user@example.com",
        user_phone=None,
        conversion_value=29.99,
        currency_code="USD",
        event_time=datetime.now(UTC),
    )
    defaults.update(overrides)
    return ConversionEvent(**defaults)


class TestMockConversionGateway:
    def test_upload_returns_success(self):
        gw = MockConversionGateway("meta")
        result = gw.upload_conversion(_make_event())
        assert result.success
        assert result.entity_id == "sub-test-001"
        assert result.platform == AdsPlatform.META

    def test_upload_preserves_entity_id(self):
        gw = MockConversionGateway("google")
        event = _make_event(entity_id="lead-xyz", platform=AdsPlatform.GOOGLE)
        result = gw.upload_conversion(event)
        assert result.entity_id == "lead-xyz"

    def test_batch_upload(self):
        gw = MockConversionGateway("meta")
        events = [_make_event(entity_id=f"sub-{i}") for i in range(5)]
        results = gw.upload_conversions_batch(events)
        assert len(results) == 5
        assert all(r.success for r in results)

    def test_batch_empty(self):
        gw = MockConversionGateway("meta")
        results = gw.upload_conversions_batch([])
        assert results == []

    def test_all_event_types(self):
        gw = MockConversionGateway("meta")
        for event_type in ConversionEventType:
            event = _make_event(event_type=event_type)
            result = gw.upload_conversion(event)
            assert result.success

    def test_all_strategies(self):
        gw = MockConversionGateway("google")
        for strategy in CampaignStrategy:
            event = _make_event(strategy=strategy)
            result = gw.upload_conversion(event)
            assert result.success


class TestMockCampaignGateway:
    def test_create_campaign(self):
        gw = MockCampaignGateway("meta")
        cid = gw.create_campaign({"name": "test", "budget": 5000})
        assert cid.startswith("mock-meta-campaign-")

    def test_create_increments_counter(self):
        gw = MockCampaignGateway("google")
        c1 = gw.create_campaign({})
        c2 = gw.create_campaign({})
        assert c1 != c2

    def test_get_campaign(self):
        gw = MockCampaignGateway("meta")
        info = gw.get_campaign("mock-meta-campaign-1")
        assert info["status"] == "active"
        assert info["platform"] == "meta"

    def test_pause_campaign_no_error(self):
        gw = MockCampaignGateway("google")
        gw.pause_campaign("mock-google-campaign-1")

    def test_update_campaign_no_error(self):
        gw = MockCampaignGateway("meta")
        gw.update_campaign("mock-meta-campaign-1", {"daily_budget": 10000})

    def test_get_insights(self):
        gw = MockCampaignGateway("meta")
        insights = gw.get_campaign_insights("mock-meta-campaign-1", {"start": "2026-04-01", "end": "2026-04-09"})
        assert insights["impressions"] == 0
