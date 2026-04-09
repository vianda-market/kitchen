"""
Unit tests for ads gateway factory (app/gateways/ads/factory.py).

Verifies factory routes to mock in DEV_MODE and resolves live gateways
when configured. Uses unittest.mock to avoid needing real credentials.
"""
from unittest.mock import patch

import pytest

from app.gateways.ads.factory import get_campaign_gateway, get_conversion_gateway
from app.gateways.ads.mock_gateway import MockCampaignGateway, MockConversionGateway
from app.services.ads.models import AdsPlatform


class TestConversionGatewayFactory:
    def test_google_returns_mock_in_dev_mode(self):
        with patch("app.gateways.ads.factory.settings") as mock_settings:
            mock_settings.DEV_MODE = True
            mock_settings.GOOGLE_ADS_PROVIDER = "live"
            gw = get_conversion_gateway(AdsPlatform.GOOGLE)
            assert isinstance(gw, MockConversionGateway)
            assert gw.platform_name == "google"

    def test_meta_returns_mock_in_dev_mode(self):
        with patch("app.gateways.ads.factory.settings") as mock_settings:
            mock_settings.DEV_MODE = True
            mock_settings.META_ADS_PROVIDER = "live"
            gw = get_conversion_gateway(AdsPlatform.META)
            assert isinstance(gw, MockConversionGateway)
            assert gw.platform_name == "meta"

    def test_google_returns_mock_when_provider_mock(self):
        with patch("app.gateways.ads.factory.settings") as mock_settings:
            mock_settings.DEV_MODE = False
            mock_settings.GOOGLE_ADS_PROVIDER = "mock"
            gw = get_conversion_gateway(AdsPlatform.GOOGLE)
            assert isinstance(gw, MockConversionGateway)

    def test_meta_returns_mock_when_provider_mock(self):
        with patch("app.gateways.ads.factory.settings") as mock_settings:
            mock_settings.DEV_MODE = False
            mock_settings.META_ADS_PROVIDER = "mock"
            gw = get_conversion_gateway(AdsPlatform.META)
            assert isinstance(gw, MockConversionGateway)

    def test_google_returns_live_when_configured(self):
        with patch("app.gateways.ads.factory.settings") as mock_settings:
            mock_settings.DEV_MODE = False
            mock_settings.GOOGLE_ADS_PROVIDER = "live"
            gw = get_conversion_gateway(AdsPlatform.GOOGLE)
            from app.gateways.ads.google.conversion_gateway import GoogleAdsConversionGateway
            assert isinstance(gw, GoogleAdsConversionGateway)

    def test_meta_returns_live_when_configured(self):
        with patch("app.gateways.ads.factory.settings") as mock_settings:
            mock_settings.DEV_MODE = False
            mock_settings.META_ADS_PROVIDER = "live"
            gw = get_conversion_gateway(AdsPlatform.META)
            from app.gateways.ads.meta.conversion_gateway import MetaConversionGateway
            assert isinstance(gw, MetaConversionGateway)

    def test_invalid_platform_raises(self):
        with pytest.raises(ValueError, match="Unknown ads platform"):
            get_conversion_gateway("invalid")


class TestCampaignGatewayFactory:
    def test_google_returns_mock_in_dev_mode(self):
        with patch("app.gateways.ads.factory.settings") as mock_settings:
            mock_settings.DEV_MODE = True
            mock_settings.GOOGLE_ADS_PROVIDER = "live"
            gw = get_campaign_gateway(AdsPlatform.GOOGLE)
            assert isinstance(gw, MockCampaignGateway)

    def test_meta_returns_mock_in_dev_mode(self):
        with patch("app.gateways.ads.factory.settings") as mock_settings:
            mock_settings.DEV_MODE = True
            mock_settings.META_ADS_PROVIDER = "live"
            gw = get_campaign_gateway(AdsPlatform.META)
            assert isinstance(gw, MockCampaignGateway)
