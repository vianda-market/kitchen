# app/services/ads/models.py
"""
Canonical models for the ads platform. Platform-specific gateways translate
these to wire format (Google protobuf, Meta CAPI JSON).
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional


class AdsPlatform(Enum):
    GOOGLE = "google"
    META = "meta"


class CampaignStrategy(Enum):
    B2C_SUBSCRIBER = "b2c_subscriber"
    B2B_EMPLOYER = "b2b_employer"
    B2B_RESTAURANT = "b2b_restaurant"


class ConversionEventType(Enum):
    """
    Wire event names sent to ad platforms. Uses standard Meta event names
    for maximum optimization weight. Strategy is distinguished via custom_data
    parameters, not separate event names.

    Only ApprovedPartner is custom (no standard equivalent for post-human-vetting).
    """
    # Standard events (used across strategies)
    SUBSCRIBE = "Subscribe"
    PURCHASE = "Purchase"
    START_TRIAL = "StartTrial"
    LEAD = "Lead"
    COMPLETE_REGISTRATION = "CompleteRegistration"
    # Custom events
    CANCEL = "Cancel"
    APPROVED_PARTNER = "ApprovedPartner"


@dataclass
class ConversionEvent:
    """
    Canonical conversion event. One model for all platforms.
    Each gateway adapter translates this to platform wire format.
    """
    platform: AdsPlatform
    event_type: ConversionEventType
    strategy: CampaignStrategy
    # Idempotency key: subscription_id for B2C, lead_id for B2B
    entity_id: str
    # PII (raw here; hashed at dispatch time, never persisted raw in Redis/DB)
    user_email: str
    user_phone: Optional[str]
    # Value
    conversion_value: float
    currency_code: str  # ISO 4217
    event_time: datetime  # Timezone-aware
    # Click identifiers (platform-specific, at most one set populated)
    gclid: Optional[str] = None
    wbraid: Optional[str] = None
    gbraid: Optional[str] = None
    fbclid: Optional[str] = None
    fbc: Optional[str] = None  # Meta _fbc cookie
    fbp: Optional[str] = None  # Meta _fbp cookie
    # LTV signals
    predicted_ltv: Optional[float] = None
    subscription_months: Optional[int] = None
    # Event dedup (client-generated, shared across Pixel/SDK/CAPI)
    event_id: Optional[str] = None
    # Strategy-specific custom_data (sent as params alongside standard event name)
    custom_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize for ARQ job payload. Enums converted to values."""
        d = asdict(self)
        d["platform"] = self.platform.value
        d["event_type"] = self.event_type.value
        d["strategy"] = self.strategy.value
        d["event_time"] = self.event_time.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ConversionEvent":
        """Deserialize from ARQ job payload."""
        d = dict(d)
        d["platform"] = AdsPlatform(d["platform"])
        d["event_type"] = ConversionEventType(d["event_type"])
        d["strategy"] = CampaignStrategy(d["strategy"])
        d["event_time"] = datetime.fromisoformat(d["event_time"])
        return cls(**d)


@dataclass
class ConversionResult:
    """Result from a gateway upload attempt."""
    success: bool
    platform: AdsPlatform
    entity_id: str
    error_message: Optional[str] = None
    error_category: Optional[str] = None  # From AdsErrorCategory
    platform_response: Optional[dict] = None
