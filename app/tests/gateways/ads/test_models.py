"""
Unit tests for ads models (app/services/ads/models.py).

Verifies enum values, ConversionEvent serialization round-trip,
and ConversionResult construction.
"""

from datetime import UTC, datetime

from app.services.ads.models import (
    AdsPlatform,
    CampaignStrategy,
    ConversionEvent,
    ConversionEventType,
    ConversionResult,
)


class TestEnums:
    def test_ads_platform_values(self):
        assert AdsPlatform.GOOGLE.value == "google"
        assert AdsPlatform.META.value == "meta"

    def test_campaign_strategy_values(self):
        assert CampaignStrategy.B2C_SUBSCRIBER.value == "b2c_subscriber"
        assert CampaignStrategy.B2B_EMPLOYER.value == "b2b_employer"
        assert CampaignStrategy.B2B_RESTAURANT.value == "b2b_restaurant"

    def test_standard_event_types(self):
        assert ConversionEventType.SUBSCRIBE.value == "Subscribe"
        assert ConversionEventType.PURCHASE.value == "Purchase"
        assert ConversionEventType.LEAD.value == "Lead"
        assert ConversionEventType.COMPLETE_REGISTRATION.value == "CompleteRegistration"

    def test_custom_event_types(self):
        assert ConversionEventType.CANCEL.value == "Cancel"
        assert ConversionEventType.APPROVED_PARTNER.value == "ApprovedPartner"


class TestConversionEventSerialization:
    def _make_event(self, **overrides):
        defaults = dict(
            platform=AdsPlatform.META,
            event_type=ConversionEventType.LEAD,
            strategy=CampaignStrategy.B2B_RESTAURANT,
            entity_id="lead-123",
            user_email="test@example.com",
            user_phone="+5491155550001",
            conversion_value=10.0,
            currency_code="ARS",
            event_time=datetime(2026, 4, 9, 12, 0, 0, tzinfo=UTC),
            gclid=None,
            fbc="fb.1.1234.abcd",
            fbp="fb.1.1234.9876",
            event_id="conv-lead-123",
            custom_data={"lead_type": "restaurant"},
        )
        defaults.update(overrides)
        return ConversionEvent(**defaults)

    def test_to_dict_serializes_enums(self):
        event = self._make_event()
        d = event.to_dict()
        assert d["platform"] == "meta"
        assert d["event_type"] == "Lead"
        assert d["strategy"] == "b2b_restaurant"
        assert isinstance(d["event_time"], str)

    def test_from_dict_deserializes_enums(self):
        event = self._make_event()
        d = event.to_dict()
        restored = ConversionEvent.from_dict(d)
        assert restored.platform == AdsPlatform.META
        assert restored.event_type == ConversionEventType.LEAD
        assert restored.strategy == CampaignStrategy.B2B_RESTAURANT

    def test_round_trip_preserves_all_fields(self):
        event = self._make_event()
        d = event.to_dict()
        restored = ConversionEvent.from_dict(d)
        assert restored.entity_id == "lead-123"
        assert restored.user_email == "test@example.com"
        assert restored.user_phone == "+5491155550001"
        assert restored.conversion_value == 10.0
        assert restored.currency_code == "ARS"
        assert restored.fbc == "fb.1.1234.abcd"
        assert restored.fbp == "fb.1.1234.9876"
        assert restored.event_id == "conv-lead-123"
        assert restored.custom_data == {"lead_type": "restaurant"}

    def test_optional_fields_default_none(self):
        event = self._make_event(gclid=None, wbraid=None, gbraid=None, fbc=None, fbp=None)
        d = event.to_dict()
        restored = ConversionEvent.from_dict(d)
        assert restored.gclid is None
        assert restored.wbraid is None
        assert restored.fbc is None

    def test_google_platform_event(self):
        event = self._make_event(
            platform=AdsPlatform.GOOGLE,
            event_type=ConversionEventType.SUBSCRIBE,
            strategy=CampaignStrategy.B2C_SUBSCRIBER,
            gclid="CjwKCAtest",
            fbc=None,
            fbp=None,
        )
        d = event.to_dict()
        assert d["platform"] == "google"
        assert d["gclid"] == "CjwKCAtest"


class TestConversionResult:
    def test_success_result(self):
        result = ConversionResult(success=True, platform=AdsPlatform.META, entity_id="sub-123")
        assert result.success
        assert result.error_message is None

    def test_failure_result(self):
        result = ConversionResult(
            success=False,
            platform=AdsPlatform.GOOGLE,
            entity_id="sub-456",
            error_message="Rate limited",
            error_category="rate_limited",
        )
        assert not result.success
        assert result.error_category == "rate_limited"
