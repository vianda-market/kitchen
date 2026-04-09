# app/gateways/ads/base.py
"""
Abstract base classes for ad platform gateways.

Each platform (Google, Meta) implements these ABCs. The factory
(factory.py) resolves the correct implementation based on settings.
"""
from abc import ABC, abstractmethod

from app.services.ads.models import ConversionEvent, ConversionResult


class AdsConversionGateway(ABC):
    """Upload offline/server-side conversions to an ad platform."""

    @abstractmethod
    def upload_conversion(self, event: ConversionEvent) -> ConversionResult:
        """
        Upload a single conversion event.

        Returns:
            ConversionResult with success/failure and platform error details.
        """
        ...

    @abstractmethod
    def upload_conversions_batch(
        self, events: list[ConversionEvent]
    ) -> list[ConversionResult]:
        """
        Upload a batch of conversion events. Handles partial failures internally.

        Returns:
            List of ConversionResult, one per input event.
        """
        ...


class AdsCampaignGateway(ABC):
    """Manage campaigns on an ad platform."""

    @abstractmethod
    def create_campaign(self, config: dict) -> str:
        """Create a campaign. Returns platform campaign ID."""
        ...

    @abstractmethod
    def update_campaign(self, campaign_id: str, updates: dict) -> None:
        """Update campaign settings (budget, status, targeting)."""
        ...

    @abstractmethod
    def get_campaign(self, campaign_id: str) -> dict:
        """Get campaign details and current status."""
        ...

    @abstractmethod
    def pause_campaign(self, campaign_id: str) -> None:
        """Pause a running campaign."""
        ...

    @abstractmethod
    def get_campaign_insights(self, campaign_id: str, date_range: dict) -> dict:
        """Get performance metrics for a campaign over a date range."""
        ...
