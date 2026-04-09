# app/gateways/ads/factory.py
"""
Gateway factory. Resolves the correct AdsConversionGateway or AdsCampaignGateway
implementation based on platform + settings (mock vs live).

Follows the same pattern as app/gateways/address_provider.py and
app/services/payment_provider/__init__.py.
"""
from app.config.settings import settings
from app.gateways.ads.base import AdsCampaignGateway, AdsConversionGateway
from app.gateways.ads.mock_gateway import MockCampaignGateway, MockConversionGateway
from app.services.ads.models import AdsPlatform


def get_conversion_gateway(platform: AdsPlatform) -> AdsConversionGateway:
    """
    Return the conversion gateway for the given platform.

    Mock is used when:
    - DEV_MODE is True, OR
    - The platform-specific provider setting is "mock"

    Live gateways are loaded lazily to avoid importing SDKs
    (google-ads, facebook-business) when not needed.
    """
    if platform == AdsPlatform.GOOGLE:
        provider = (settings.GOOGLE_ADS_PROVIDER or "mock").strip().lower()
        if settings.DEV_MODE or provider == "mock":
            return MockConversionGateway("google")
        # Lazy import: google-ads SDK only loaded when provider=live
        from app.gateways.ads.google.conversion_gateway import GoogleAdsConversionGateway
        return GoogleAdsConversionGateway()

    if platform == AdsPlatform.META:
        provider = (settings.META_ADS_PROVIDER or "mock").strip().lower()
        if settings.DEV_MODE or provider == "mock":
            return MockConversionGateway("meta")
        # Lazy import: facebook-business SDK only loaded when provider=live
        from app.gateways.ads.meta.conversion_gateway import MetaConversionGateway
        return MetaConversionGateway()

    raise ValueError(f"Unknown ads platform: {platform}")


def get_campaign_gateway(platform: AdsPlatform) -> AdsCampaignGateway:
    """
    Return the campaign management gateway for the given platform.

    Same mock/live logic as get_conversion_gateway.
    """
    if platform == AdsPlatform.GOOGLE:
        provider = (settings.GOOGLE_ADS_PROVIDER or "mock").strip().lower()
        if settings.DEV_MODE or provider == "mock":
            return MockCampaignGateway("google")
        from app.gateways.ads.google.campaign_gateway import GoogleAdsCampaignGateway
        return GoogleAdsCampaignGateway()

    if platform == AdsPlatform.META:
        provider = (settings.META_ADS_PROVIDER or "mock").strip().lower()
        if settings.DEV_MODE or provider == "mock":
            return MockCampaignGateway("meta")
        from app.gateways.ads.meta.campaign_gateway import MetaCampaignGateway
        return MetaCampaignGateway()

    raise ValueError(f"Unknown ads platform: {platform}")
