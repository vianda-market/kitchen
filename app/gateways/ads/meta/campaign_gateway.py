# app/gateways/ads/meta/campaign_gateway.py
"""
Meta Ads campaign management gateway (stub).

Full implementation in Phase 10/14. This stub allows the factory to resolve
the live campaign gateway without errors while campaign management is not
yet built.
"""
from app.gateways.ads.base import AdsCampaignGateway


class MetaCampaignGateway(AdsCampaignGateway):
    """Meta Ads campaign management -- stub for Phase 10."""

    def create_campaign(self, config: dict) -> str:
        raise NotImplementedError(
            "Meta Ads campaign creation not yet implemented (Phase 10). "
            "Use mock gateway for development."
        )

    def update_campaign(self, campaign_id: str, updates: dict) -> None:
        raise NotImplementedError("Meta Ads campaign update not yet implemented (Phase 10).")

    def get_campaign(self, campaign_id: str) -> dict:
        raise NotImplementedError("Meta Ads campaign get not yet implemented (Phase 10).")

    def pause_campaign(self, campaign_id: str) -> None:
        raise NotImplementedError("Meta Ads campaign pause not yet implemented (Phase 10).")

    def get_campaign_insights(self, campaign_id: str, date_range: dict) -> dict:
        raise NotImplementedError("Meta Ads insights not yet implemented (Phase 10).")
