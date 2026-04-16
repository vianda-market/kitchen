# app/gateways/ads/google/campaign_gateway.py
"""
Google Ads campaign management gateway (stub).

Full implementation in Phase 9/14. This stub allows the factory to resolve
the live campaign gateway without errors while campaign management is not
yet built.
"""

from app.gateways.ads.base import AdsCampaignGateway


class GoogleAdsCampaignGateway(AdsCampaignGateway):
    """Google Ads campaign management -- stub for Phase 9."""

    def create_campaign(self, config: dict) -> str:
        raise NotImplementedError(
            "Google Ads campaign creation not yet implemented (Phase 9). Use mock gateway for development."
        )

    def update_campaign(self, campaign_id: str, updates: dict) -> None:
        raise NotImplementedError("Google Ads campaign update not yet implemented (Phase 9).")

    def get_campaign(self, campaign_id: str) -> dict:
        raise NotImplementedError("Google Ads campaign get not yet implemented (Phase 9).")

    def pause_campaign(self, campaign_id: str) -> None:
        raise NotImplementedError("Google Ads campaign pause not yet implemented (Phase 9).")

    def get_campaign_insights(self, campaign_id: str, date_range: dict) -> dict:
        raise NotImplementedError("Google Ads insights not yet implemented (Phase 9).")
