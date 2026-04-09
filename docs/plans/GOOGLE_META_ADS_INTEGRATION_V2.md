# Unified Ads Platform -- Google Ads + Meta Ads

**Status:** Design
**Goal:** Multi-platform ad management backend. Server-side conversion uploads (Google Enhanced Conversions + Meta CAPI), campaign management (Performance Max + Advantage+ Sales), and full-funnel tracking across web, mobile native, and server.
**Scope:** Backend implementation + cross-repo requirements for B2C app, marketing site, and infrastructure.

---

## Table of Contents

1. [Reuse Analysis](#1-reuse-analysis)
2. [Architecture: Shared Core + AdsProvider Layer](#2-architecture-shared-core--adsprovider-layer)
3. [Data Flow Diagram (Unified)](#3-data-flow-diagram-unified)
4. [Concept Mapping: Google vs Meta](#4-concept-mapping-google-ads-vs-meta-ads)
5. [GCP Integration (Shared Infrastructure)](#5-gcp-integration-shared-infrastructure)
6. [Settings Additions](#6-settings-additions)
7. [Shared Logic: PII Hashing](#7-shared-logic-pii-hashing)
8. [Platform-Specific: Google Ads](#8-platform-specific-google-ads)
9. [Platform-Specific: Meta Ads](#9-platform-specific-meta-ads)
10. [Meta Advantage+ Best Practices](#10-meta-advantage-best-practices)
11. [Campaign Management Module](#11-campaign-management-module)
12. [Gemini Advisor Layer](#12-gemini-advisor-layer)
13. [Marketing Collateral Service](#13-marketing-collateral-service)
14. [Geographic Flywheel Engine](#14-geographic-flywheel-engine)
15. [Ad Zone Database](#15-ad-zone-database)
16. [Pre-Flight Validation and Scaling Signals](#16-pre-flight-validation-and-scaling-signals)
17. [Full-Funnel Tracking Architecture](#17-full-funnel-tracking-architecture)
18. [Shared: Conversion Job Queue (ARQ)](#18-shared-conversion-job-queue-arq)
19. [Shared: Error Taxonomy](#19-shared-error-taxonomy)
20. [Click Identifier Capture -- Database](#20-click-identifier-capture----database)
21. [Rate Limiting Strategy](#21-rate-limiting-strategy)
22. [Payment Provider Agnosticism](#22-payment-provider-agnosticism)
23. [B2B Restaurant Acquisition Track](#23-b2b-restaurant-acquisition-track)
24. [Local Development vs. Production](#24-local-development-vs-production)
25. [Infrastructure Requirements for Pulumi Agent](#25-infrastructure-requirements-for-pulumi-agent)
26. [Security Checklist](#26-security-checklist)
27. [Dependencies (New Packages)](#27-dependencies-new-packages)
28. [Implementation Phases](#28-implementation-phases)
29. [Cross-Repo Impact](#29-cross-repo-impact)
30. [Manual Operations (UI)](#30-manual-operations-ui)
31. [Reference Links](#31-reference-links)
32. [Feedback for B2C App Agent](#32-feedback-for-b2c-app-agent)
33. [Feedback for Infra Agent](#33-feedback-for-infra-agent)
34. [Open Questions](#34-open-questions)

---

## 1. Reuse Analysis

What can be shared 1:1, what needs a thin abstraction, and what is platform-specific.

| Component | Reuse Level | Notes |
|-----------|-------------|-------|
| PII hashing (SHA256) | **Shared 1:1** | Both platforms require identical normalize-lowercase-SHA256 for email/phone |
| ARQ job queue + Redis | **Shared 1:1** | Same worker infra, same deferred job pattern |
| GCP Secret Manager client | **Shared 1:1** | `gcp_secrets.py` fetches secrets for both providers |
| `ad_click_tracking` DB table | **Shared 1:1** | Stores click IDs from both platforms (gclid, fbclid, fbc, fbp) |
| Conversion event schema | **Light abstraction** | Same business event (Subscribe, Renew, Cancel), different wire formats |
| Rate limit / backoff | **Light abstraction** | Both need exponential backoff, but different limits and error codes |
| Auth / token management | **Light abstraction** | Google: OAuth2 refresh token. Meta: system user long-lived token. Both via Secret Manager. |
| Error taxonomy | **Light abstraction** | Map platform errors to shared categories (rate_limit, partial_failure, auth_expired, invalid_data) |
| Idempotency | **Light abstraction** | Google: `order_id`. Meta: `event_id`. Both keyed on `subscription_id`. |
| Upload delay buffer | **Light abstraction** | Google: 24h recommended. Meta: near-realtime preferred (but same ARQ defer pattern works). |
| Conversion payload builder | **Platform-specific** | Google: protobuf ClickConversion. Meta: CAPI JSON with `event_name`, `custom_data`. |
| Campaign CRUD | **Platform-specific** | Google Ads API vs Marketing API. Different object models, different automation levers. |
| Click identifier logic | **Platform-specific** | Google: gclid/wbraid/gbraid. Meta: fbclid/fbc/fbp + event_id dedup with Pixel/SDK. |
| SDK initialization | **Platform-specific** | `GoogleAdsClient` vs `facebook_business.FacebookAdsApi` |

---

## 2. Architecture: Shared Core + AdsProvider Layer

### 2.1 High-Level Design

```
                    +-----------------------------------------+
                    |         Shared Core Layer                |
                    |                                          |
                    |  ConversionEvent (canonical model)       |
                    |  PII Hasher (SHA256)                     |
                    |  ARQ Job Queue (Redis)                   |
                    |  GCP Secret Manager                     |
                    |  Rate Limit Backoff (generic)            |
                    |  ad_click_tracking (DB)                  |
                    |  Error Taxonomy (shared categories)      |
                    +----------+-----------+-------------------+
                               |           |
                    +----------v--+  +-----v--------------+
                    | GoogleAds   |  | MetaAds            |
                    | Provider    |  | Provider           |
                    |             |  |                    |
                    | gateway.py  |  | gateway.py         |
                    | adapter.py  |  | adapter.py         |
                    | campaign.py |  | campaign.py        |
                    +-------------+  +--------------------+
```

### 2.2 Folder Structure

```
app/
+-- gateways/
|   +-- ads/
|       +-- __init__.py
|       +-- base.py                      # AdsConversionGateway ABC, AdsCampaignGateway ABC
|       +-- mock_gateway.py              # Shared mock (logs payloads, returns success)
|       +-- factory.py                   # get_conversion_gateway(provider), get_campaign_gateway(provider)
|       +-- google/
|       |   +-- __init__.py
|       |   +-- conversion_gateway.py    # GoogleAdsClient -> upload_click_conversions
|       |   +-- campaign_gateway.py      # Campaign/ad group CRUD via Google Ads API
|       |   +-- auth.py                  # OAuth2 refresh token client init
|       +-- meta/
|       |   +-- __init__.py
|       |   +-- conversion_gateway.py    # CAPI -> POST /events
|       |   +-- campaign_gateway.py      # Marketing API campaign/adset/ad CRUD
|       |   +-- creative_sync_gateway.py # Download creatives from Meta CDN to GCS
|       |   +-- creative_gen_gateway.py  # Generate new variants via Meta API
|       |   +-- auth.py                  # System user token init
|       +-- gemini/
|           +-- __init__.py
|           +-- critique_gateway.py      # Send creative + metrics to Gemini for critique/scoring
|           +-- copy_gateway.py          # Generate ad copy variations via Gemini
|           +-- advisor_gateway.py       # Cross-platform performance analysis + recommendations
+-- services/
|   +-- ads/
|       +-- __init__.py
|       +-- conversion_service.py        # Shared: build ConversionEvent, hash PII, dispatch to provider(s)
|       +-- campaign_service.py          # Shared: campaign state machine, budget pacing
|       +-- collateral_service.py        # Creative lifecycle: sync, score, flag, enhance, publish
|       +-- collateral_models.py         # CreativeAsset, CreativeScore, CritiqueResult
|       +-- pii_hasher.py               # normalize_and_hash(), build_user_identifiers()
|       +-- error_handler.py            # Map platform errors to shared taxonomy, decide retry
|       +-- models.py                   # ConversionEvent, CampaignState, AdsPlatform, CampaignStrategy
+-- workers/
|   +-- __init__.py
|   +-- arq_settings.py                 # ARQ WorkerSettings (shared Redis, registers all ad tasks)
|   +-- conversion_worker.py            # ARQ task: upload_conversion(platform, event_data)
|   +-- creative_sync_worker.py         # ARQ task: sync Meta creatives to GCS
|   +-- creative_critique_worker.py     # ARQ task: daily Gemini critique + enhancement loop
|   +-- advisor_worker.py               # ARQ task: cross-platform Gemini analysis (hourly/daily)
+-- core/
|   +-- gcp_secrets.py                  # GCP Secret Manager (shared, unchanged)
+-- config/
    +-- settings.py                      # + ads settings (see section 6)
```

### 2.3 AdsProvider Interface

```python
# app/gateways/ads/base.py
from abc import ABC, abstractmethod
from app.services.ads.models import ConversionEvent, ConversionResult

class AdsConversionGateway(ABC):
    """Upload offline/server-side conversions to an ad platform."""

    @abstractmethod
    def upload_conversion(self, event: ConversionEvent) -> ConversionResult:
        """Upload a single conversion. Returns success/failure with platform error details."""
        ...

    @abstractmethod
    def upload_conversions_batch(self, events: list[ConversionEvent]) -> list[ConversionResult]:
        """Upload a batch. Handles partial failures internally."""
        ...

class AdsCampaignGateway(ABC):
    """Manage campaigns on an ad platform."""

    @abstractmethod
    def create_campaign(self, config: dict) -> str:
        """Returns platform campaign ID."""
        ...

    @abstractmethod
    def update_campaign(self, campaign_id: str, updates: dict) -> None: ...

    @abstractmethod
    def get_campaign(self, campaign_id: str) -> dict: ...

    @abstractmethod
    def pause_campaign(self, campaign_id: str) -> None: ...
```

### 2.4 Canonical Conversion Event

One model for all platforms. Each gateway adapter translates it to platform wire format.

```python
# app/services/ads/models.py
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class AdsPlatform(Enum):
    GOOGLE = "google"
    META = "meta"

class CampaignStrategy(Enum):
    B2C_SUBSCRIBER = "b2c_subscriber"      # Individual consumer subscription acquisition
    B2B_EMPLOYER = "b2b_employer"          # Employer benefits program acquisition
    B2B_RESTAURANT = "b2b_restaurant"      # Restaurant/supplier acquisition

class ConversionEventType(Enum):
    # Standard Meta events (used across strategies with custom_data params for routing)
    SUBSCRIBE = "Subscribe"                    # B2C new subscription + B2B employer first enrollment
    PURCHASE = "Purchase"                      # B2C renewal, first purchase
    START_TRIAL = "StartTrial"                 # B2C trial activation
    LEAD = "Lead"                              # B2B restaurant lead + B2B employer lead
    COMPLETE_REGISTRATION = "CompleteRegistration"  # B2B restaurant vetting + B2B employer onboarded
    # Custom events (no standard equivalent)
    CANCEL = "Cancel"                          # B2C negative signal
    APPROVED_PARTNER = "ApprovedPartner"       # B2B restaurant approved (custom, post-human-vetting)

# Strategy-specific parameters sent with standard events (not separate event types):
#
# | Internal Name           | Wire Event            | custom_data params                                    |
# |-------------------------|-----------------------|-------------------------------------------------------|
# | B2C Subscribe           | Subscribe             | subscription_type: "b2c_individual"                   |
# | B2C Renewal             | Purchase              | purchase_type: "renewal", subscription_months: N      |
# | B2C First Purchase      | Purchase              | purchase_type: "first", is_first_purchase: true       |
# | B2C StartTrial          | StartTrial            | subscription_type: "b2c_individual"                   |
# | B2C Cancel              | Cancel (custom)       | subscription_type: "b2c_individual"                   |
# | Restaurant Lead         | Lead                  | lead_type: "restaurant", value: 10                    |
# | Restaurant Registration | CompleteRegistration   | registration_type: "restaurant", value: 50            |
# | Restaurant Approved     | ApprovedPartner (cust) | partner_type: "restaurant", value: 500               |
# | Employer Lead           | Lead                  | lead_type: "employer", company_size: N, value: 10     |
# | Employer Onboarded      | CompleteRegistration   | registration_type: "employer_program", value: 200     |
# | Employer First Enroll   | Subscribe             | subscription_type: "b2b_employer", seats: N, value: 2000 |

@dataclass
class ConversionEvent:
    platform: AdsPlatform
    event_type: ConversionEventType
    strategy: CampaignStrategy  # B2C_SUBSCRIBER, B2B_EMPLOYER, or B2B_RESTAURANT
    subscription_id: str       # Idempotency key (subscription_id for B2C, lead_id for B2B)
    user_email: str            # Raw; hashed at dispatch time, never persisted raw
    user_phone: str | None
    conversion_value: float
    currency_code: str         # ISO 4217
    event_time: datetime       # Timezone-aware
    # Click identifiers (platform-specific, at most one set populated)
    gclid: str | None = None
    wbraid: str | None = None
    gbraid: str | None = None
    fbclid: str | None = None
    fbc: str | None = None     # Meta click cookie (_fbc)
    fbp: str | None = None     # Meta browser cookie (_fbp)
    # LTV signals
    predicted_ltv: float | None = None
    subscription_months: int | None = None
    # Event dedup (generated client-side, passed through for CAPI+Pixel/SDK dedup)
    event_id: str | None = None
```

---

## 3. Data Flow Diagram (Unified)

```
Payment Webhook (Stripe, MercadoPago, or future provider)
    |
    v
app/routes/webhooks.py (provider-specific webhook handler)
    |
    v
ads/conversion_service.py
    |-- build ConversionEvent (canonical)
    |-- hash PII (pii_hasher.py)
    |-- determine which platforms to notify (ADS_ENABLED_PLATFORMS)
    |
    +-- enqueue ARQ job: platform=google, defer_by=24h
    |       job_id = "gads-conv-{subscription_id}"
    |
    +-- enqueue ARQ job: platform=meta, defer_by=5min
            job_id = "meta-conv-{subscription_id}"
    |
    v (after defer period)
workers/conversion_worker.py
    |-- resolve gateway via factory.get_conversion_gateway(platform)
    |-- call gateway.upload_conversion(event)
    |-- on success: update ad_click_tracking.upload_status
    |-- on failure: error_handler categorizes, ARQ retries with backoff
    |
    +-- GoogleAdsConversionGateway.upload_conversion()
    |       -> Google Ads API ConversionUploadService v17
    |
    +-- MetaConversionGateway.upload_conversion()
            -> Meta CAPI POST /{pixel_id}/events
```

**Key difference:** Google recommends 24h delay. Meta prefers near-realtime (within minutes). The same ARQ `_defer_by` mechanism handles both with different delay values per platform.

---

## 4. Concept Mapping: Google Ads vs Meta Ads

### 4.1 Attribution and Conversion Concepts

| Concept | Google Ads | Meta Ads |
|---------|-----------|----------|
| Click identifier | `gclid` (web), `wbraid`/`gbraid` (iOS) | `fbclid` (URL param) -> `_fbc` cookie |
| Browser identifier | N/A | `_fbp` cookie (first-party, set by Pixel) |
| Server conversion API | Enhanced Conversions (Offline) | Conversions API (CAPI) |
| Conversion dedup | `order_id` field | `event_id` field (dedup with Pixel + SDK) |
| User matching | SHA256 email/phone in `UserIdentifier` | SHA256 email/phone in `user_data` |
| Conversion action | `ConversionAction` resource | Standard Event (`Purchase`, `Subscribe`) |
| Revenue signal | `conversion_value` + `currency_code` | `value` + `currency` in `custom_data` |
| LTV signal | `conversion_value` on renewal events | `predicted_ltv` in `custom_data` |
| Upload timing | 24h delay recommended | Near-realtime preferred |
| Batch limit | 2,000 per request | 1,000 per request |
| Rate limit | 15,000 req/day (basic access) | 200 calls/hr per ad account (BM-level pooling available) |

### 4.2 Campaign Management Concepts

| Concept | Google Ads | Meta Ads (v25.0+) |
|---------|-----------|-------------------|
| Campaign type | Performance Max | Sales campaign with Advantage+ automation |
| "Smart" toggle | `campaign.performance_max` type | Advantage+ is a **state**, not a type. Set via 3 automation levers (see section 10) |
| Budget | `campaign.campaign_budget` | `campaign.daily_budget` or `lifetime_budget` |
| Targeting | Asset groups + audience signals | `adset.targeting` (Advantage+ broadens automatically) |
| Creative unit | Asset group (text + images + video) | `ad.creative` (single creative per ad) |
| Ad group equivalent | Asset Group | Ad Set |
| Bidding | `maximize_conversions` / `target_roas` | `bid_strategy` (`LOWEST_COST_WITHOUT_CAP`, `COST_CAP`) |
| Conversion tracking | Conversion Action linked to campaign | Pixel + CAPI events linked to ad account |

### 4.3 Conversion Events to Send

**B2C Subscriber Events:**

| Event | Google Event | Meta Standard Event | When Fired | Params |
|-------|-------------|-------------------|------------|--------|
| New subscription | `conversion_action: subscribe` | `Subscribe` | Payment captured | value, currency, subscription_id |
| Trial start | `conversion_action: start_trial` | `StartTrial` | Trial activated | value=0, predicted_ltv |
| Renewal | `conversion_action: purchase` | `Purchase` | Renewal payment captured | value, currency, subscription_id, subscription_months |
| Cancellation | N/A (negative signal via audience) | `Cancel` (custom event) | Subscription cancelled | subscription_id |
| First purchase | `conversion_action: purchase` | `Purchase` | First non-trial payment | value, currency, is_first_purchase=true |

**B2B Employer Program Events (standard names + params):**

| Internal Name | Meta Wire Event | Google Conversion Action | When Fired | custom_data |
|--------------|----------------|-------------------------|------------|-------------|
| Employer Lead | `Lead` | `conversion_action: employer_lead` | Employer submits interest | lead_type: "employer", company_size, value: 10 |
| Employer Onboarded | `CompleteRegistration` | `conversion_action: employer_onboarded` | Program setup complete | registration_type: "employer_program", value: 200 |
| First Enrollment | `Subscribe` | `conversion_action: employer_first_enrollment` | First employee enrolled | subscription_type: "b2b_employer", seats: N, value: 2000 |

**B2B Restaurant Events (standard names + params):**

| Internal Name | Meta Wire Event | Google Conversion Action | When Fired | custom_data |
|--------------|----------------|-------------------------|------------|-------------|
| Restaurant Lead | `Lead` | `conversion_action: restaurant_lead` | Interest form submitted | lead_type: "restaurant", value: 10 |
| Full Application | `CompleteRegistration` | `conversion_action: restaurant_registration` | Vetting form completed | registration_type: "restaurant", value: 50 |
| Approved Partner | `ApprovedPartner` (custom) | `conversion_action: approved_partner` (offline) | Admin approves restaurant | partner_type: "restaurant", value: 500 |

**Why standard events?** Meta gives more optimization weight to standard events (`Lead`, `CompleteRegistration`, `Subscribe`, `Purchase`) than custom ones. Only `ApprovedPartner` stays custom because there is no standard equivalent for "human approved B2B lead."

**Micro-conversion funnel pattern (both B2B tracks):**
- **Optimize to:** `Lead` (micro-conversion, low value $10). This is the event campaigns bid on.
- **Send as learning signal:** `CompleteRegistration` ($50-200 value) and deep events ($500-2000 value). Platforms use these for learning even when not optimizing to them.
- **Switch optimization to deep event** only when volume exceeds 50/week total across all zones.
- **Enable value-based optimization (VBO)** when 15+ deep events/week. Platforms then shift budget to zones/audiences that produce high-value events, not just cheap leads.

**Critical:** Use the same `event_name` everywhere (Pixel JS, Meta SDK, CAPI). Differentiate strategies via `custom_data` parameters, not event names.

---

## 5. GCP Integration (Shared Infrastructure)

### 5.1 Secret Manager Client

```python
# app/core/gcp_secrets.py -- serves both providers
from google.cloud import secretmanager

_client = secretmanager.SecretManagerServiceClient()
_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL = 3600  # 1 hour

def get_secret(project_id: str, secret_id: str, version: str = "latest") -> str:
    cache_key = f"{project_id}/{secret_id}/{version}"
    if cache_key in _cache:
        value, ts = _cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            return value
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"
    response = _client.access_secret_version(request={"name": name})
    value = response.payload.data.decode("UTF-8")
    _cache[cache_key] = (value, time.time())
    return value
```

### 5.2 Application Default Credentials (ADC)

- **Local:** `gcloud auth application-default login` or `GOOGLE_APPLICATION_CREDENTIALS` env var
- **Cloud Run:** Automatic via attached service account

### 5.3 Secrets to Create in GCP Secret Manager

**Google Ads (7 secrets):**

| Secret ID | Contents |
|-----------|----------|
| `google-ads-developer-token` | Google Ads API developer token |
| `google-ads-oauth-client-id` | OAuth2 client ID |
| `google-ads-oauth-client-secret` | OAuth2 client secret |
| `google-ads-oauth-refresh-token` | OAuth2 refresh token |
| `google-ads-customer-id` | Google Ads customer/account ID |
| `google-ads-login-customer-id` | MCC (manager) account ID |
| `google-ads-conversion-action-id` | Performance Max conversion action ID |

**Meta Ads (4 secrets):**

| Secret ID | Contents |
|-----------|----------|
| `meta-ads-system-user-token` | System user long-lived access token |
| `meta-ads-app-secret` | Facebook App secret (for appsecret_proof) |
| `meta-ads-pixel-id` | Meta Pixel ID for CAPI events |
| `meta-ads-ad-account-id` | Ad account ID (act_XXXXXXXXX) |

### 5.4 Required IAM Roles (for Pulumi)

Single service account for both providers:

| IAM Role | Resource | Purpose |
|----------|----------|---------|
| `roles/secretmanager.secretAccessor` | Secret Manager secrets | Read all ad platform credentials |
| `roles/redis.editor` | Cloud Memorystore instance | ARQ job queue read/write |
| `roles/logging.logWriter` | Cloud Logging | Structured log export |
| `roles/monitoring.metricWriter` | Cloud Monitoring | Custom metrics (per-platform success/fail) |

---

## 6. Settings Additions

```python
# In app/config/settings.py

# --- Shared Ads Infrastructure ---
ADS_ENABLED_PLATFORMS: str = ""              # Comma-separated: "google,meta" or "google" or ""
ADS_DRY_RUN: bool = False                   # Log payloads without uploading (all platforms)

# --- Redis / ARQ (shared) ---
REDIS_URL: str = "redis://localhost:6379"    # Local Redis; prod = Cloud Memorystore URL
ARQ_MAX_JOBS: int = 100
ARQ_JOB_TIMEOUT: int = 300
ARQ_MAX_RETRIES: int = 3

# --- Google Ads ---
GOOGLE_ADS_PROVIDER: str = "mock"            # "mock" | "live"
GOOGLE_ADS_CUSTOMER_ID: str = ""
GOOGLE_ADS_CONVERSION_ACTION_ID: str = ""
GOOGLE_ADS_DEVELOPER_TOKEN: str = ""         # Local dev only; prod uses Secret Manager
GOOGLE_ADS_UPLOAD_DELAY_HOURS: int = 24

# --- Meta Ads ---
META_ADS_PROVIDER: str = "mock"              # "mock" | "live"
META_ADS_PIXEL_ID: str = ""
META_ADS_AD_ACCOUNT_ID: str = ""
META_ADS_SYSTEM_USER_TOKEN: str = ""         # Local dev only; prod uses Secret Manager
META_ADS_APP_SECRET: str = ""                # Local dev only
META_ADS_UPLOAD_DELAY_MINUTES: int = 5       # Near-realtime, small buffer for batching
META_ADS_API_VERSION: str = "v25.0"

# --- Marketing Collateral ---
GCS_MARKETING_BUCKET: str = ""               # GCS bucket for creative assets (Pulumi-managed)
CREATIVE_SYNC_INTERVAL_HOURS: int = 24       # How often to sync creatives from Meta
CREATIVE_CRITIQUE_MIN_IMPRESSIONS: int = 5000 # Min impressions before evaluating a creative
CREATIVE_AUTO_PUBLISH_MIN_SCORE: int = 7     # Min Gemini score for auto-publish (1-10)

# --- Gemini Advisor ---
GEMINI_MODEL_ANALYSIS: str = "gemini-2.5-flash"  # For data analysis, daily audits
GEMINI_MODEL_CREATIVE: str = "gemini-2.5-pro"    # For creative critique, copy generation
GEMINI_ADVISOR_INTERVAL_HOURS: int = 1            # How often to run cross-platform analysis
GEMINI_BUDGET_CHANGE_LIMIT_PCT: float = 0.20      # Max auto budget change without approval
GEMINI_STRATEGY_SHIFT_LIMIT_PCT: float = 0.10     # Max cross-strategy reallocation without approval

# --- Geographic Zones ---
ZONE_MIN_RADIUS_KM: float = 1.5                    # Minimum zone radius (technical min = 1km)
ZONE_DEFAULT_RADIUS_KM: float = 2.0                # Default for new zones
ZONE_MIN_ESTIMATED_MAU: int = 40000                 # Min Meta MAU for zone to be viable
ZONE_BUDGET_FLOOR_SMALL_RADIUS: int = 5000          # Min daily budget (cents) for radius < 2km
ZONE_BUDGET_FLOOR_LARGE_RADIUS: int = 3000          # Min daily budget (cents) for radius >= 2km
ZONE_DBSCAN_MIN_LEADS: int = 40                     # Min notify-me leads for auto-zone proposal
ZONE_DBSCAN_EPSILON_KM: float = 2.0                 # DBSCAN clustering epsilon
ZONE_MAU_CACHE_TTL_HOURS: int = 24                  # Cache delivery_estimate results
```

---

## 7. Shared Logic: PII Hashing

Both Google and Meta require identical SHA256 hashing. One implementation, shared.

```python
# app/services/ads/pii_hasher.py
import hashlib

def normalize_and_hash(value: str) -> str:
    """Normalize (lowercase, strip whitespace) and SHA256-hash a PII value.
    Both Google Enhanced Conversions and Meta CAPI require this exact procedure."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()

def build_hashed_user_data(email: str, phone: str | None = None) -> dict:
    """Returns hashed user data dict usable by both platform adapters."""
    data = {"hashed_email": normalize_and_hash(email)}
    if phone:
        # Both platforms expect E.164 format before hashing
        data["hashed_phone"] = normalize_and_hash(phone)
    return data
```

---

## 8. Platform-Specific: Google Ads

### 8.1 Client Initialization

```python
# app/gateways/ads/google/auth.py
from google.ads.googleads.client import GoogleAdsClient

_cached_client: GoogleAdsClient | None = None

def init_google_ads_client() -> GoogleAdsClient:
    global _cached_client
    if _cached_client:
        return _cached_client
    credentials = {
        "developer_token": get_secret(..., "google-ads-developer-token"),
        "client_id": get_secret(..., "google-ads-oauth-client-id"),
        "client_secret": get_secret(..., "google-ads-oauth-client-secret"),
        "refresh_token": get_secret(..., "google-ads-oauth-refresh-token"),
        "login_customer_id": get_secret(..., "google-ads-login-customer-id"),
        "use_proto_plus": True,
    }
    _cached_client = GoogleAdsClient.load_from_dict(credentials)
    return _cached_client
```

### 8.2 Conversion Upload

```python
# app/gateways/ads/google/conversion_gateway.py
class GoogleAdsConversionGateway(AdsConversionGateway):

    def upload_conversion(self, event: ConversionEvent) -> ConversionResult:
        client = init_google_ads_client()
        service = client.get_service("ConversionUploadService")

        click_conversion = client.get_type("ClickConversion")
        click_conversion.conversion_action = (
            f"customers/{self.customer_id}/conversionActions/{self.conversion_action_id}"
        )
        click_conversion.order_id = event.subscription_id  # Idempotency
        click_conversion.conversion_value = event.conversion_value
        click_conversion.currency_code = event.currency_code
        click_conversion.conversion_date_time = event.event_time.strftime("%Y-%m-%d %H:%M:%S%z")

        # Click identifier: gclid > wbraid > gbraid
        if event.gclid:
            click_conversion.gclid = event.gclid
        elif event.wbraid:
            click_conversion.wbraid = event.wbraid
        elif event.gbraid:
            click_conversion.gbraid = event.gbraid

        # Enhanced conversions: hashed PII
        user_id = client.get_type("UserIdentifier")
        user_id.hashed_email = normalize_and_hash(event.user_email)
        click_conversion.user_identifiers.append(user_id)

        response = service.upload_click_conversions(
            customer_id=self.customer_id,
            conversions=[click_conversion],
            partial_failure=True,
        )
        # ... handle partial_failure_error ...
```

### 8.3 GCLID vs WBRAID/GBRAID

| Identifier | Source | When Used |
|------------|--------|-----------|
| `gclid` | Google Click ID | Standard web clicks (Chrome, Android) |
| `wbraid` | Web-to-app bridge ID | iOS Safari to web conversions (post-ATT) |
| `gbraid` | App campaign bridge ID | iOS app campaign conversions |

At least one must be present for Google. Meta events do not use these.

---

## 9. Platform-Specific: Meta Ads

### 9.1 Client Initialization

Meta uses a system user token (long-lived, no OAuth refresh dance).

```python
# app/gateways/ads/meta/auth.py
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.serverside import (
    EventRequest, Event, UserData, CustomData
)

_initialized = False

def init_meta_ads_client():
    global _initialized
    if _initialized:
        return
    token = get_secret(..., "meta-ads-system-user-token")
    app_secret = get_secret(..., "meta-ads-app-secret")
    FacebookAdsApi.init(
        app_id=None,        # Not needed for system user
        app_secret=app_secret,
        access_token=token,
        api_version=settings.META_ADS_API_VERSION,
    )
    _initialized = True
```

### 9.2 CAPI Conversion Upload

```python
# app/gateways/ads/meta/conversion_gateway.py
class MetaConversionGateway(AdsConversionGateway):

    def upload_conversion(self, event: ConversionEvent) -> ConversionResult:
        init_meta_ads_client()

        user_data = UserData(
            email=normalize_and_hash(event.user_email),  # SDK accepts pre-hashed
            phone=normalize_and_hash(event.user_phone) if event.user_phone else None,
            fbc=event.fbc,    # _fbc cookie value (contains fbclid)
            fbp=event.fbp,    # _fbp browser ID cookie
            client_ip_address=None,    # Not available server-side
            client_user_agent=None,    # Not available server-side
        )

        custom_data = CustomData(
            value=event.conversion_value,
            currency=event.currency_code,
            order_id=event.subscription_id,  # Dedup with Pixel
            content_type="subscription",
            predicted_ltv=event.predicted_ltv,
        )

        server_event = Event(
            event_name=event.event_type.value,  # "Subscribe", "Purchase", etc.
            event_time=int(event.event_time.timestamp()),
            event_id=event.event_id or f"conv-{event.subscription_id}",
            event_source_url=None,
            user_data=user_data,
            custom_data=custom_data,
            action_source="website",  # or "app" for mobile
        )

        request = EventRequest(
            pixel_id=self.pixel_id,
            events=[server_event],
        )
        response = request.execute()
        # ... handle response.events_received vs errors ...
```

### 9.3 CAPI + Pixel/SDK Deduplication

Meta deduplicates using `event_id` across three sources:

- **Pixel JS** fires `fbq('track', 'Subscribe', {value: 29.99}, {eventID: 'conv-{subscription_id}'})` on web
- **Meta SDK** fires `AppEventsLogger.logEvent('Subscribe', 29.00, {event_id: 'conv-{subscription_id}'})` on native
- **CAPI** sends the same event with `event_id='conv-{subscription_id}'` from FastAPI

Meta keeps the highest-quality signal and deduplicates the rest. The `event_id` must be generated client-side (when user taps subscribe) and passed to the backend through the subscription API.

### 9.4 Meta Click Identifiers

| Identifier | Source | Lifetime | How Captured |
|------------|--------|----------|-------------|
| `fbclid` | URL query param | One-time click | Frontend extracts from URL on landing |
| `_fbc` | First-party cookie | 90 days | Set by Meta Pixel JS; format: `fb.1.{timestamp}.{fbclid}` |
| `_fbp` | First-party cookie | 90 days | Set by Meta Pixel JS; browser fingerprint |

**Logic:** Send `_fbc` (contains fbclid) and `_fbp` when available. Unlike Google, Meta can still attribute via `_fbp` alone (probabilistic matching). No hard requirement for click ID.

### 9.5 Event Match Quality (EMQ)

Meta scores each CAPI event on how well it can be matched to a user. Higher EMQ = better attribution = better campaign optimization.

**Maximize EMQ by sending:**
- Hashed email (required)
- Hashed phone (strongly recommended)
- `_fbc` cookie (strongly recommended)
- `_fbp` cookie (recommended)
- `external_id` = hashed `user_id` (recommended)

---

## 10. Meta Advantage+ Best Practices

### 10.1 Advantage+ Sales (v25.0+)

As of Marketing API v25.0, Advantage+ is a **state on a Sales campaign**, not a separate campaign type. The legacy `smart_promotion_type` field is deprecated.

**Three automation levers that activate Advantage+ state:**

1. **Advantage+ Audience** (`targeting_optimization`): Set `optimization_goal=OFFSITE_CONVERSIONS` on the ad set. Let Meta expand beyond your seed audience.
2. **Advantage+ Placements** (`automatic_placements`): Do not specify placement list. Meta distributes across Feed, Stories, Reels, Audience Network automatically.
3. **Advantage+ Creative** (`creative_optimization`): Enable in ad creative. Meta tests variations of your creative assets.

When all three are enabled, the campaign operates in full Advantage+ mode.

### 10.2 Data Foundation Requirements

- **50+ conversions before scaling:** Meta needs ~50 conversion events per week per ad set before its ML can optimize effectively. Start with a single ad set, consolidate events.
- **CAPI + Pixel/SDK redundancy:** Always fire from both client and server. Meta uses the higher-quality signal and deduplicates.
- **7-day click attribution window:** Default for Advantage+. Send conversions within 7 days of click for attribution.
- **Value optimization:** Send `value` + `currency` on every conversion to enable ROAS bidding.

### 10.3 Campaign Management API Endpoints

| Operation | Meta Marketing API Endpoint | Method |
|-----------|---------------------------|--------|
| Create campaign | `POST /act_{ad_account_id}/campaigns` | Campaign with `objective=OUTCOME_SALES` |
| Create ad set | `POST /act_{ad_account_id}/adsets` | Budget, targeting, optimization_goal |
| Create ad | `POST /act_{ad_account_id}/ads` | Links creative to ad set |
| Create creative | `POST /act_{ad_account_id}/adcreatives` | Image/video + copy |
| Update campaign | `POST /{campaign_id}` | Status, budget, name |
| Get insights | `GET /{campaign_id}/insights` | Performance metrics |
| Get delivery | `GET /{adset_id}/delivery_estimate` | Reach/frequency estimate |
| CAPI events | `POST /{pixel_id}/events` | Server-side conversions |

**Batch API:** Meta supports `POST /` with up to 50 API calls in one HTTP request (reduces rate limit consumption).

---

## 11. Campaign Management Module

**Status:** Scoped, not designed in detail yet. Implementation depends on Data Foundation layer (section 12) being fully operational.

This module covers **both** Google Ads (Performance Max) and Meta (Advantage+ Sales) campaign management. It supports **three strategy types** representing the three core business entities. The business revolves around acquiring and retaining these three audiences; the ads platform must support independent budgeting, creative, and optimization for each.

### 11.1 Strategy Types

| Strategy | Code | Objective | Target Audience | Key Events |
|----------|------|-----------|----------------|------------|
| **B2C Individual Comensal** | `B2C_SUBSCRIBER` | Maximize subscriptions / ROAS | Consumers in covered cities | Subscribe, StartTrial, Renewal, Purchase |
| **B2B Employer Program** | `B2B_EMPLOYER` | Acquire employers who subsidize employee meals | HR directors, benefits managers, office managers at mid-to-large companies | EmployerLead, EmployerOnboarded, EmployerFirstEnrollment |
| **B2B Restaurant** | `B2B_RESTAURANT` | Acquire quality restaurant partners (supply side) | Restaurant owners/operators | Lead, CompleteRegistration, ApprovedPartner |

Each strategy uses separate campaigns, budgets, creatives, and conversion actions on both platforms. The `CampaignStrategy` enum (section 2.4) drives routing.

### 11.1.1 Budget Allocation Framework

Budget allocation operates at **two levels**: per-zone (driven by flywheel state) and cross-zone (driven by Gemini advisor or operator).

**Model A: Zone-State-Based (launch, simple)**

Each zone's flywheel state (section 14) determines its strategy mix. The operator sets total daily budget per zone. The state determines the split.

| Flywheel State | B2B Restaurant | B2C Individual | B2B Employer | Min Budget |
|---------------|---------------|---------------|-------------|------------|
| Supply Acquisition | 100% | 0% | 0% | $50/day |
| Demand Activation | 30% | 60% | 10% | $150/day |
| Growth | 20% | 50% | 30% | $250/day |
| Mature | Gemini advisor | Gemini advisor | Gemini advisor | Variable |

The operator can override these percentages per zone at any time. Starting a brand new market with zero restaurants = set zone to Supply Acquisition = 100% restaurant ads. Starting in a market where restaurants already exist = set zone to Demand Activation = mostly B2C.

**Model B: Bottleneck-Based (mature, AI-driven)**

When the Gemini advisor is live, it replaces fixed percentages with goal-based allocation:

"We need 10 new restaurants in Zone X at max $200 CAC. Spend what is needed to hit that, then allocate remaining to B2C subscribers in that zone."

The advisor treats supply as the bottleneck and demand as the variable. It factors in:
- Cross-strategy performance (CPA per strategy per zone)
- Supply/demand balance per zone (restaurants vs subscribers)
- Flywheel speed score per zone
- Cross-zone priority ranking (shift incremental budget to fastest zones)
- Halo effects (employer ads in a zone may lower B2C CAC in the same zone)

Both models coexist. Start with Model A, graduate to Model B when advisor is live and has data. Model A percentages remain as defaults and fallbacks.

**CBO (Campaign Budget Optimization) structure:**

Budget allocation is implemented via CBO with per-zone ad set minimum budgets, not by splitting into separate campaigns:

```
Campaign: B2B_RESTAURANT  CBO total = sum(zone restaurant budgets)
  Ad Set: Zone_Palermo  min $60/day
  Ad Set: Zone_Recoleta min $50/day
  Ad Set: Longtail      min $40/day  [3-5 small zones grouped]

Campaign: B2C_SUBSCRIBER  CBO total = sum(zone B2C budgets)
  Ad Set: Zone_Palermo  min $100/day  (only if zone is in Demand Activation+)
```

CBO distributes budget to ad sets with cheapest conversions while min budgets prevent starvation of new zones.

### 11.2 Objectives

Build a hands-off campaign operation system where the backend manages campaigns end-to-end on both Google and Meta. Human input is limited to high-level strategy; platform ML handles the rest.

**Gemini integration confirmed:** Google Gemini will serve as the AI advisor layer for campaign management. It handles cross-platform budget optimization, creative critique, fatigue detection, and B2B buyer journey logic that neither Google Ads nor Meta automate natively. See section 12 for architecture. See section 13 for the creative enhancement loop that uses both Gemini (critique) and Meta (generation).

### 11.3 Inputs (from operator/admin)

| Input | Description |
|-------|-------------|
| Strategy type | `B2C_SUBSCRIBER`, `B2B_EMPLOYER`, or `B2B_RESTAURANT` |
| Strategy/objective | e.g., "maximize subscriptions", "maximize ROAS", "maximize qualified leads" |
| Budget | Daily or lifetime budget in target currency |
| Geo targeting | Countries/regions/cities (seed audience) |
| Creative assets | Images, video, ad copy, headlines |
| Logo | Brand logo for Advantage+ / Performance Max creative variations |
| Guardrails | Max CPA, min ROAS, spending limits, excluded audiences |

### 11.4 Outputs (from the system)

| Output | Description |
|--------|-------------|
| Campaign performance | Impressions, clicks, conversions, CPA, ROAS (via platform Insights APIs) |
| Creative fatigue alerts | Detect declining CTR/engagement per creative over time |
| Budget pacing reports | Actual vs planned spend, projected end-of-period spend |
| Automated actions | Pause underperforming creatives, reallocate budget (TBD) |

### 11.5 B2B Restaurant Campaign Specifics

B2B restaurant acquisition requires different targeting and optimization than B2C:

**Audience controls:** Advantage+ audience expansion is too broad for B2B restaurant targeting. B2B campaigns must use `audience_controls` to constrain targeting:
- Interest-based: "restaurant owner", "food service", "catering business"
- Behavioral: "small business owners", "food industry professionals"
- Geo: cities where Vianda has or is expanding coverage
- Exclusions: existing Vianda restaurant partners (via Custom Audience)

**Conversion optimization:** Campaigns should optimize for `ApprovedPartner` (the highest-quality signal), not `Lead`. This requires accumulating enough approval events first (~50/week). During ramp-up, optimize for `Lead` then switch.

**Lead-gen vs self-serve:** The system supports both paths:
- **Lead-gen (initial launch):** Ad drives to marketing site form. Conversion = form submission.
- **Self-serve (future):** Ad drives to B2B portal registration. Conversion = account creation.

See `docs/plans/RESTAURANT_VETTING_SYSTEM.md` for the full vetting pipeline design.

### 11.6 B2B Employer Program Campaign Specifics

Employer program acquisition targets HR decision-makers at companies, not individual consumers. This is a higher-LTV, lower-volume channel.

**Audience controls:**
- Job title targeting: "HR Director", "Benefits Manager", "Office Manager", "People Operations"
- Company size: mid-to-large (50+ employees) where meal benefits are a meaningful perk
- Industry: tech, finance, consulting, professional services (companies that value employee perks)
- Geo: cities where Vianda has active restaurant supply
- Exclusions: existing Vianda employer partners (Custom Audience)

**Conversion optimization:**
- Optimize for `EmployerOnboarded` (program setup complete) as the primary value signal
- During ramp-up, optimize for `EmployerLead` then switch when volume allows (~50 onboardings/month)
- `EmployerFirstEnrollment` is the ultimate activation signal (employer actually using the program) but may be too delayed for campaign optimization

**Landing pages:**
- Marketing site: `/for-employers` landing page (employer benefits value proposition)
- B2B portal: self-serve signup for employer program (future)

**Creative approach:**
- Focus on employee satisfaction, retention, and tax advantages of meal benefit programs
- Different messaging than B2C (ROI-focused, not food-focused)
- Case studies and testimonials from existing employer partners

**Relationship to B2C:**
- Employer programs drive bulk B2C subscriptions (enrolled employees become individual subscribers)
- A successful employer campaign indirectly boosts B2C subscriber numbers without B2C ad spend
- The Gemini advisor should factor this multiplier effect when recommending budget allocation

### 11.7 Key Dependencies

```
Data Foundation (MUST be complete before campaign management)
  +-- Meta Pixel JS on vianda-home (marketing site) -- all 3 strategy landing pages
  +-- Meta Pixel JS on vianda-app web build -- B2C only
  +-- Meta SDK in vianda-app iOS/Android native -- B2C only
  +-- CAPI from FastAPI (this repo) -- all 3 strategies
  +-- 50+ weekly conversions flowing before scaling campaigns (per strategy type)

B2B Restaurant Track (additional dependencies)
  +-- Restaurant interest form on marketing site (docs/plans/RESTAURANT_VETTING_SYSTEM.md)
  +-- CAPI Lead + ApprovedPartner events wired
  +-- Admin review dashboard for restaurant leads

B2B Employer Track (additional dependencies)
  +-- /for-employers landing page on marketing site
  +-- Employer interest form (enhanced from existing employer lead interest)
  +-- CAPI EmployerLead + EmployerOnboarded + EmployerFirstEnrollment events wired
  +-- Existing employer program onboarding flow (already built, see CLAUDE_ARCHITECTURE.md)
```

Campaign management without the data foundation will result in platforms having no signal to optimize on. Start with conversion tracking, accumulate data, then activate campaigns.

### 11.8 Architecture Placement

The campaign management module fits into the existing `AdsCampaignGateway` abstraction:

- `app/gateways/ads/google/campaign_gateway.py` implements `AdsCampaignGateway` for Performance Max
- `app/gateways/ads/meta/campaign_gateway.py` implements `AdsCampaignGateway` for Advantage+ Sales
- `app/services/ads/campaign_service.py` provides shared campaign state machine logic
- `CampaignStrategy` enum routes to the correct conversion actions and audience configs per strategy
- Automated monitoring (creative fatigue, budget pacing) runs as ARQ scheduled tasks alongside conversion upload tasks

### 11.9 Where It Fits in Phases

Campaign management is Phases 9-10 in the implementation plan. It depends on:
- Phase 6 (Meta CAPI gateway) for conversion data flowing
- Phase 12 (frontend tracking) for full-funnel Pixel + SDK data
- Sufficient data volume (50+ weekly conversions per strategy) before scaling
- For B2B: restaurant vetting system (Phase 15) must be live to generate `ApprovedPartner` events

Detailed design will be produced when strategy inputs are provided by the operator.

---

## 12. Gemini Advisor Layer

**Status:** Confirmed viable. Integration architecture defined, implementation deferred until campaign management module (Phases 9-10) begins.

Google Gemini serves as a cross-platform AI advisor for campaign management. It fills gaps that neither Google Ads Performance Max nor Meta Advantage+ address: cross-platform budget optimization, creative critique, and B2B-specific reasoning.

### 12.1 What Gemini Adds Beyond Native Platform Automation

| Gap | Why Platforms Cannot Fill It | Gemini Capability |
|-----|----------------------------|-------------------|
| Cross-platform budget allocation | Google optimizes for Google only; Meta for Meta only. Neither knows the other's CPA. Neither optimizes across strategies. | Analyze combined metrics from both platforms AND all 3 strategies, output rebalancing recommendations (platform x strategy matrix). |
| Creative critique with brand context | Platforms optimize delivery but do not assess brand consistency or explain *why* a creative underperforms. | Multimodal analysis of images/video against brand guidelines and historical top performers. |
| B2B buyer journey logic | Performance Max and Advantage+ are optimized for B2C purchase funnels. Restaurant acquisition has a different qualification pipeline. | Gemini can filter performance data through B2B-specific logic (lead quality scoring, approval rate correlation). |
| Contextual reasoning | Platforms do not consider business context (seasonal menus, market expansion, PR events). | Gemini can adjust strategy recommendations given internal context documents. |
| Copy generation with constraints | Platform tools generate generic copy. | Gemini produces variations that follow brand voice, character limits, and multi-language requirements. |

### 12.2 Architecture: Advisor/Executor Pattern

```
ARQ Scheduled Job (hourly or daily)
    |
    v
Campaign Metrics Collector
    |-- Pull Google Ads insights (Insights API)
    |-- Pull Meta insights (GET /{campaign_id}/insights)
    |-- Merge into unified performance dataset
    |
    v
Gemini Advisor (google-genai SDK)
    |-- System prompt: campaign strategy, guardrails, brand guidelines
    |-- Input: merged metrics JSON (both platforms)
    |-- Output: structured JSON recommendations
    |       {
    |         "actions": [
    |           {"platform": "meta", "action": "adjust_budget", "ad_set_id": "...", "change_pct": 0.2},
    |           {"platform": "google", "action": "pause_creative", "asset_group_id": "...", "reason": "CTR < 0.5% after 5k impressions"},
    |           {"platform": "meta", "action": "flag_fatigue", "creative_id": "...", "metric": "ctr_14d_decline_pct": 35}
    |         ]
    |       }
    |
    v
Action Executor (campaign_service.py)
    |-- Routes each action to the correct AdsCampaignGateway
    |-- Auto-executes minor actions (budget tweak, creative pause)
    |-- Queues major actions for admin approval (new campaign, strategy change)
    |
    v
Audit Log (DB)
    |-- All recommendations + executions logged for review
```

### 12.3 Execution Modes

| Mode | Trigger | Use Case |
|------|---------|----------|
| **Async scheduled** (recommended) | ARQ cron job, hourly or daily | Routine optimization: budget pacing, fatigue detection, performance reports |
| **On-demand** | Admin dashboard button | Manual audit: "analyze this campaign and tell me what to change" |
| **Function calling** | Gemini outputs function calls | Advanced: Gemini directly invokes `AdsCampaignGateway` methods (pause_ad_set, adjust_budget). Backend validates before executing. |

### 12.4 Model Selection

| Task | Recommended Model | Reason |
|------|-------------------|--------|
| Data analysis, daily audit | Gemini 2.5 Flash | Fastest, lowest cost for structured data processing (~$0.01/1M input tokens) |
| Creative copy generation | Gemini 2.5 Pro | Superior reasoning for brand guidelines and creative nuance |
| Creative image/video scoring | Gemini 2.5 Pro | Better spatial and aesthetic reasoning for complex visuals |
| Batch daily reports | Gemini Batch API | 50% cost reduction for non-urgent analysis |

### 12.5 GCP Integration

- **SDK:** `google-genai` (Google GenAI SDK for Python)
- **Auth:** Application Default Credentials (ADC) on Cloud Run. Reuse existing service account.
- **IAM:** Add `roles/aiplatform.user` (Vertex AI User) to the Cloud Run service account.
- **Cost:** ~$0.01/1M input tokens (Flash). 10 campaigns x 2 platforms x hourly = viable at minimal cost.
- **Latency:** 2-10 seconds per analysis call. Acceptable for async ARQ jobs.

### 12.6 Guardrails

- Gemini recommendations are **suggestions**, not direct actions (except for minor tweaks below a configurable threshold).
- All actions logged to audit table before execution.
- Budget changes capped at +/- 20% per cycle without admin approval.
- Creative pausing allowed automatically; creative creation requires approval.
- B2B campaigns (restaurant + employer) always require admin approval for strategy changes (higher-value, lower-volume).
- Cross-strategy budget reallocation recommendations capped at +/- 10% shift per cycle without admin approval.
- Gemini must consider supply/demand balance: shifting budget away from B2B_RESTAURANT when restaurant supply is thin would harm B2C subscriber experience.

---

## 13. Marketing Collateral Service

**Status:** Scoped, not designed in detail yet. Depends on campaign management module (Phases 9-10) and Gemini advisor layer (section 12).

This service manages the lifecycle of ad creative assets: storage, performance tracking, critique, enhancement, and reuse across platforms and the marketing site.

### 13.1 Overview

The creative pipeline uses a **seed-concept-then-analyze** pattern. Advantage+ generates creative variants dynamically at impression time, so intercepting and re-scoring individual variants in real-time is not practical. Instead, we control which *concepts* (seed creatives) enter the system, let Meta optimize delivery of variants, then analyze performance at the concept level weekly.

```
Week 1: Seed
    |-- Human + Gemini generate 3-5 high-quality seed creatives per strategy
    |-- Upload to Meta as ad creatives in asset_feed_spec
    |-- Let Advantage+ Creative make minor variations (crops, text overlays, backgrounds)
    |
    v
Daily: Sync + Ingest
    |-- Creative sync job downloads active creatives from Meta CDN to GCS (within 24h)
    |-- Performance ingest job pulls insights per creative: impressions, clicks, CPA, CTR
    |-- Read Meta's native recommendations: GET /{ad_id}?fields=recommendations
    |
    v
Weekly: Analyze + Decide
    |-- Gemini analyzes which CONCEPT is winning (not individual variants)
    |-- Input: performance data per concept + Meta native recommendations
    |-- Output: "Concept A (food close-up) outperforms Concept B (lifestyle) by 40% CTR.
    |            Recommend: double down on food close-up, generate 2 new seeds in that direction."
    |
    v
Weekly: Refresh
    |-- Generate new seed creatives in the winning concept direction
    |-- Gemini generates ad copy variations. Human or Gemini-assisted image/video for visuals.
    |-- Upload new seeds. Pause losing concepts (create new ad, pause old ad).
    |-- Tag with parent_creative_id for lineage tracking.
    |
    v
Repeat weekly
```

**Why this pattern?** Advantage+ generates variants dynamically at the impression level. We cannot intercept those. What we control is which seed assets enter the system and which get paused. Concept-level analysis (not variant-level) aligns with how Advantage+ actually works.

**Human-in-loop gate:** New seed creatives require operator approval before upload. Concept pausing is auto-allowed. Strategy changes require approval.

### 13.2 Folder Structure

```
app/
+-- services/
|   +-- ads/
|       +-- collateral_service.py          # Creative lifecycle: sync, score, flag, publish
|       +-- collateral_models.py           # CreativeAsset, CreativeScore, CritiqueResult
+-- gateways/
|   +-- ads/
|       +-- meta/
|       |   +-- creative_sync_gateway.py   # Download creatives from Meta CDN to GCS
|       |   +-- creative_gen_gateway.py    # Generate new variants via Meta API
|       +-- gemini/
|           +-- critique_gateway.py        # Send creative + metrics to Gemini for critique
|           +-- copy_gateway.py            # Generate ad copy variations via Gemini
+-- workers/
    +-- creative_sync_worker.py            # ARQ task: sync Meta creatives to GCS
    +-- creative_critique_worker.py        # ARQ task: daily critique + enhancement loop
```

### 13.3 Database: marketing_collateral Tables

```sql
-- Creative assets (synced from ad platforms + human uploads)
CREATE TABLE public.marketing_collateral (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Source
    platform VARCHAR(20) NOT NULL,                -- 'meta', 'google', 'manual'
    platform_ad_id VARCHAR(100),                   -- Meta ad_id or Google asset_group_id
    platform_creative_id VARCHAR(100),             -- Meta creative_id
    strategy_type VARCHAR(30) NOT NULL,            -- 'b2c_subscriber', 'b2b_restaurant'
    -- Asset
    asset_type VARCHAR(20) NOT NULL,               -- 'image', 'video', 'copy'
    gcs_url TEXT NOT NULL,                         -- GCS path in marketing bucket
    original_url TEXT,                             -- Platform CDN URL (temporary)
    headline TEXT,
    body_text TEXT,
    -- Lineage
    parent_collateral_id UUID REFERENCES public.marketing_collateral(id),
    generation_method VARCHAR(50),                 -- 'manual', 'meta_advantage_plus', 'meta_generative', 'gemini_copy'
    -- Status
    status VARCHAR(30) NOT NULL DEFAULT 'active',  -- 'active', 'paused', 'archived', 'pending_approval'
    approved_by UUID REFERENCES public.users(id),
    approved_at TIMESTAMPTZ,
    -- Timestamps
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modified_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Performance data per creative (updated daily)
CREATE TABLE public.collateral_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collateral_id UUID NOT NULL REFERENCES public.marketing_collateral(id),
    date DATE NOT NULL,
    platform VARCHAR(20) NOT NULL,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_cents INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    cpa_cents INTEGER,
    ctr_pct NUMERIC(5,3),
    video_3sec_view_rate NUMERIC(5,3),
    UNIQUE(collateral_id, date, platform)
);

-- Gemini critique results
CREATE TABLE public.collateral_critique (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collateral_id UUID NOT NULL REFERENCES public.marketing_collateral(id),
    critique_text TEXT NOT NULL,
    score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 10),
    issues JSONB DEFAULT '[]',          -- ["low_contrast", "text_too_small", "off_brand"]
    recommendations JSONB DEFAULT '[]', -- ["increase_contrast", "use_brand_font"]
    model_used VARCHAR(50) NOT NULL,    -- 'gemini-2.5-flash', 'gemini-2.5-pro'
    created_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 13.4 Creative Sync from Meta

The sync job pulls active creatives from Meta Marketing API and downloads them to GCS before the temporary CDN URLs expire (24h).

**API fields to pull:**
```
GET /act_{ad_account_id}/ads?fields=
    id,name,effective_status,issues_info,
    creative{
        effective_object_story_id,
        image_url,video_id,
        asset_feed_spec,
        object_story_spec,
        degrees_of_freedom_spec
    }
```

**Filtering:** Only sync creatives where `effective_status=ACTIVE` and no disapproval in `issues_info`.

**From Advantage+ Creative variants:**
- `asset_feed_spec.images` -- all image variants
- `asset_feed_spec.videos` -- all video variants
- `asset_feed_spec.bodies` -- all copy variants
- `asset_feed_spec.titles` -- all headline variants

**GCS bucket:** `GCS_MARKETING_BUCKET` (new, Pulumi-managed). Path: `collateral/{strategy_type}/{platform}/{creative_id}/{asset_type}`.

**Marketing site reuse:** The marketing site reads the `marketing_collateral` table (via API) to render an "As seen on Instagram" gallery or use high-performing creative assets on landing pages.

### 13.5 Underperformer Detection Criteria

| Metric | Threshold | Window |
|--------|-----------|--------|
| CPA | > 150% of guardrail | After $50+ spend |
| CTR | < 0.5% | After 5,000 impressions |
| Video 3-sec view rate | < 15% | After 5,000 impressions |
| CTR 14-day trend | Declining > 25% | Rolling 14-day window |
| Frequency | > 3.0 per user | Rolling 7-day window |

### 13.6 Meta Native Suggestions

Before generating our own critique, the system should read Meta's native recommendations:

```
GET /{ad_id}?fields=recommendations
```

Meta provides actionable suggestions (e.g., "increase budget", "broaden audience"). These are consumed first and passed to Gemini as additional context.

### 13.7 Enhancement: Create New, Do Not Edit In Place

Meta API does not allow editing a creative in place. Enhancement always means:
1. Create new ad with new `creative_hash` under the same ad set
2. Pause the underperforming original ad
3. Tag the new ad with `parent_creative_id` for lineage tracking

### 13.8 Human-in-Loop Gate

| Change Type | Auto-Publish? | Rationale |
|-------------|---------------|-----------|
| New headline | Yes | Low risk, easily reversible |
| Image crop/resize | Yes | Minor visual change |
| Background change | Yes | Non-brand element |
| New body copy | Yes, if Gemini score >= 7 | Copy quality verified |
| Logo modification | **No, require approval** | Brand identity |
| New image/video asset | **No, require approval** | High visual impact |
| Strategy change | **No, require approval** | Business decision |

### 13.9 Key Dependencies

- Campaign management module (section 11) must be live (creatives must exist in campaigns)
- Gemini advisor layer (section 12) for critique
- GCS marketing bucket (Pulumi)
- Cloud Scheduler for daily sync + critique jobs
- Marketing site API for collateral gallery (cross-repo)

---

## 14. Geographic Flywheel Engine

**Status:** Designed based on feedback from both Google Gemini and Meta AI. This is the core market expansion mechanism.

The marketplace has a cold-start problem per geography: consumers subscribe where restaurants deliver, restaurants join where consumers exist. The ads platform must sequence spend geographically to spin up this flywheel.

### 14.1 Zone Creation: Two Paths

**Path 1: Operator Cold Start (always available)**

At launch and in new markets, there are no notify-me leads or internal signals. The operator creates zones manually based on business judgment: market research, population density, local partnerships, competitor gaps.

The operator can create a zone and set it to any flywheel state directly. No data thresholds required. This is how every new market starts.

**Path 2: Data-Proposed Zones (after traction)**

Once the platform has organic traction, notify-me leads accumulate. The Gemini advisor runs DBSCAN clustering on lead coordinates and proposes new zones:

- Input: lat/lon of notify-me leads
- Algorithm: DBSCAN (min 40 leads, 2km epsilon)
- Output: "Zone Alpha: centered at [-34.603, -58.381], radius 2km. 42 leads detected. Estimated MAU: 85k. Recommend: 14-day restaurant acquisition sprint at $50/day."
- Operator reviews and approves or rejects the proposal

Both paths produce the same `ad_zone` record. The system is advisory, not gatekeeping. The operator can override any automated threshold or state transition at any time.

### 14.2 Flywheel State Machine

Each zone progresses through states independently. Transitions can be triggered automatically (when thresholds are met) or manually (operator override).

| State | Auto Entry Condition | Operator Can Force? | Ad Strategy | Min Budget |
|-------|---------------------|-------------------|-------------|------------|
| **Monitoring** | Notify-me leads accumulating, below thresholds | Yes, skip to any state | No ads. Organic + email only. | $0 |
| **Supply Acquisition** | 40+ notify-me leads in 2km cluster, MAU > 40k | Yes, no data required (cold start) | 100% B2B_RESTAURANT | $50/day |
| **Demand Activation** | 5+ diverse restaurants in zone, 70% area coverage | Yes | 60% B2C / 30% restaurant / 10% employer | $150/day total |
| **Growth** | 10%+ notify-me-to-subscriber conversion within 30 days, CPA stable 7 days | Yes | 50% B2C / 20% restaurant / 30% employer | $250/day |
| **Mature** | Frequency < 2.5, CPA flat, flywheel self-sustaining | Yes | Gemini advisor optimizes dynamically | Variable |

**Auto thresholds are defaults, not gates.** The operator can:
- Create a zone directly in `Supply Acquisition` with zero notify-me leads (cold start)
- Force a zone from `Supply Acquisition` to `Demand Activation` before hitting 5 restaurants (business judgment)
- Override any budget allocation percentage per zone
- Pause or deactivate any zone at any time

### 14.3 Geographic Unit: Coordinate-Based Zones

The flywheel operates on **zones** (lat/lon center + radius), not neighborhoods or zipcodes.

**Why not zipcodes?** In cities like Buenos Aires, a single zipcode can span 10km2 with multiple distinct neighborhoods. Too coarse for hyper-local supply/demand matching.

**Why not neighborhoods alone?** People live in one neighborhood and work in another. A restaurant 500m away in the next neighborhood is more relevant than one 3km away in the same neighborhood.

**Why coordinates + radius?** Flexible, automatable, can be positioned around restaurant clusters or office districts rather than administrative boundaries. Both Google Ads and Meta fully support lat/lon + radius targeting via API.

**Neighborhood as display label:** Store neighborhood on address records for human-readable reporting and landing page personalization. The flywheel engine thinks in coordinates; the admin dashboard shows neighborhood names on the map overlay.

### 14.4 Zone Targeting on Ad Platforms

**Meta API field:**

```json
"targeting": {
  "geo_locations": {
    "custom_locations": [
      {
        "latitude": -34.6037,
        "longitude": -58.3816,
        "radius": 2,
        "distance_unit": "kilometer"
      }
    ],
    "location_types": ["home", "recent"]
  }
}
```

- `location_types: ["home", "recent"]` for B2B restaurant (catch owners at work or home)
- `location_types: ["home"]` for B2C (avoid tourists, less impacted by iOS 14.5)
- Multiple non-contiguous circles allowed in one ad set (for longtail zone consolidation)

**Google Ads:** Proximity targets via LocationView service (lat, lon, radius, distance_unit).

**Audience estimation (Meta):** `GET /act_{id}/delivery_estimate` with targeting spec. Returns `estimate_dau` and `estimate_mau`. Cache results for 24h.

### 14.5 Campaign Structure Per Zone

One campaign per strategy, one ad set per zone, CBO (Campaign Budget Optimization) with per-zone min/max budgets.

```
Campaign: B2B_RESTAURANT_LATAM  (CBO $300/day)
  Ad Set: BA_Palermo_2km        min $60/day  custom_locations: 1 circle
  Ad Set: BA_Recoleta_2km       min $50/day  custom_locations: 1 circle
  Ad Set: Lima_Miraflores_2.5km min $50/day  custom_locations: 1 circle
  Ad Set: Longtail_Zones        min $40/day  custom_locations: [3-5 circles]

Campaign: B2C_SUB_LATAM  (CBO $500/day)
  Ad Set: BA_Palermo_2km        min $100/day + LAL notify-me
  (activated only when zone reaches Demand Activation state)

Campaign: B2B_EMP_LATAM  (CBO $200/day)
  Ad Set: BA_Palermo_2km        min $50/day
  (activated only when zone reaches Growth state)
```

**Key rules:**
- New zone = add ad set to existing campaign (inherits campaign learning). Never create new campaigns per zone.
- CBO distributes budget across ad sets. Min budgets prevent starvation of small zones.
- Without min budgets, CBO dumps 90% into the cheapest zone. Always set mins.
- Keep radius similar across ad sets in same campaign (+/- 0.5km). If one is 1km and another is 5km, CBO always favors the 5km (cheaper CPM).

**Hybrid tier structure at scale:**
- `B2B_RESTAURANT_TIER1`: major metros with $100+/day each (own ad sets)
- `B2B_RESTAURANT_LONGTAIL`: CBO across small zones at $20-30/day each (grouped in one ad set with multiple circles)

### 14.6 Notify-Me Leads as Audience Seeds

| List Size (matched) | Use For |
|---------------------|---------|
| < 100 | Exclusion only (don't re-advertise). "We're live!" retargeting email when zone activates. |
| 100-300 | Above + seed in `audience_controls` as hint for Advantage+ |
| 300+ | Above + 1% Lookalike Audience for B2C demand activation |

Best combo for B2C activation in a zone: `custom_locations: 2km radius` + `audience_controls: LAL_1%_notify_me`. This tells Meta "people like my leads, who are in this 2km zone."

Hash uploads with `em`, `ph`, `ct` (city), `st` (state), `zip` for best match rate. Zip is critical for city-level matching. Custom Audiences do not accept lat/lon; use lat/lon for targeting, not matching.

### 14.7 Audience Exclusions Per Zone

Per-zone exclusions prevent internal bidding competition and wasted spend:

- `Subscribers_ZoneX` excluded from `B2B_RESTAURANT` ZoneX ad set
- `Restaurant_Partners_ZoneX` excluded from `B2C_SUBSCRIBER` ZoneX ad set
- `Employer_Partners_ZoneX` excluded from other B2B campaigns targeting ZoneX

Nightly job updates per-zone Custom Audiences via API. Account-level exclusion is insufficient because a subscriber in Zone A should not be excluded from B2B campaigns in Zone B.

### 14.8 Sequential Launch Strategy

Activation of strategies per zone is sequential, not parallel. This prevents all three campaigns from being in learning phase simultaneously.

**Per-zone activation sequence:**

| Month | Action | Budget |
|-------|--------|--------|
| 1 | B2C only (or first market cold start with restaurants). Hit 50+ Subscribe/week. | $100-200/day |
| 2 | Creative sync + enhancement loop for B2C. Prove ROAS. | Same |
| 3 | Add B2B Employer lead-gen in zones with stable B2C. | +$50/day per zone |
| 4 | Add B2B Restaurant lead-gen if Employer CPA < 2x B2C CPA. | +$50/day per zone |
| 6+ | Switch B2B optimization to deep events if volume > 50/week. | Scale based on signals |

**Cold start exception:** When entering a brand new market with zero restaurants, the operator forces the zone directly to `Supply Acquisition` and runs B2B_RESTAURANT first. The sequential order above applies to markets where supply already exists.

**Minimum viable zone launch budget:** $50/day restaurant + $100/day B2C = $150/day. Below that, don't run ads; use email and organic.

---

## 15. Ad Zone Database

### 15.1 ad_zone Table

```sql
CREATE TABLE public.ad_zone (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Identity
    name VARCHAR(100) NOT NULL,            -- Human-readable, e.g., "BA-Palermo"
    country_code VARCHAR(2) NOT NULL,
    city_name VARCHAR(100) NOT NULL,
    neighborhood VARCHAR(100),             -- Display label (optional)
    -- Geometry
    latitude NUMERIC(10,7) NOT NULL,
    longitude NUMERIC(10,7) NOT NULL,
    radius_km NUMERIC(4,2) NOT NULL DEFAULT 2.0,
    -- Flywheel state
    flywheel_state VARCHAR(30) NOT NULL DEFAULT 'monitoring',
    state_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    state_changed_by UUID REFERENCES public.users(id),  -- Operator who changed state
    -- Metrics (updated by cron/advisor)
    notify_me_lead_count INTEGER DEFAULT 0,
    active_restaurant_count INTEGER DEFAULT 0,
    active_subscriber_count INTEGER DEFAULT 0,
    estimated_mau INTEGER,                 -- Cached from Meta delivery_estimate
    mau_estimated_at TIMESTAMPTZ,
    -- Budget
    budget_allocation JSONB DEFAULT '{"b2c_subscriber": 0, "b2b_employer": 0, "b2b_restaurant": 100}',
    daily_budget_cents INTEGER,            -- Total daily budget for this zone (all strategies)
    -- Ad platform references
    meta_ad_set_ids JSONB DEFAULT '{}',    -- {"b2c_subscriber": "adset_123", "b2b_restaurant": "adset_456"}
    google_campaign_ids JSONB DEFAULT '{}',
    -- Creation
    created_by VARCHAR(30) NOT NULL DEFAULT 'operator',  -- 'operator' | 'advisor_proposed'
    approved_by UUID REFERENCES public.users(id),
    -- Timestamps
    created_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modified_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ad_zone_state ON public.ad_zone(flywheel_state);
CREATE INDEX idx_ad_zone_country ON public.ad_zone(country_code);
```

### 15.2 Flywheel State Enum

```sql
CREATE TYPE flywheel_state_enum AS ENUM (
    'monitoring',
    'supply_acquisition',
    'demand_activation',
    'growth',
    'mature',
    'paused'
);
```

### 15.3 Zone Overlap Check

Before creating a zone, validate that its circle does not overlap with existing zones in the same country:

```python
def check_zone_overlap(new_lat, new_lon, new_radius_km, existing_zones):
    """Flag overlapping zones. Distance between centers must exceed sum of radii."""
    from math import radians, sin, cos, sqrt, atan2
    overlaps = []
    for zone in existing_zones:
        # Haversine distance
        d = haversine(new_lat, new_lon, zone.latitude, zone.longitude)
        if d < (new_radius_km + zone.radius_km):
            overlaps.append(zone)
    return overlaps
```

Overlaps are flagged as warnings, not hard blocks. Operator can accept overlap (CBO arbitrates) or adjust radii.

### 15.4 Address Model Dependency

This plan requires adding `neighborhood` to `address_info`:

- Add `neighborhood VARCHAR(100)` column to `address_info` table
- Mapbox geocoding already returns neighborhood data (verify field mapping)
- lat/lon already stored from geocoding (verify)
- Follow DB schema change protocol: `schema.sql` -> `trigger.sql` -> `seed.sql` -> `dto/models.py` -> `consolidated_schemas.py`

This is a separate schema change, not part of the ads platform implementation, but is a dependency for human-readable zone reporting.

---

## 16. Pre-Flight Validation and Scaling Signals

### 16.1 Pre-Flight Checks (Before Creating Ad Set for a Zone)

| Check | Validation | Action on Failure |
|-------|-----------|-------------------|
| Audience size | Call Meta `delivery_estimate`. MAU must be > 40k. | Warn operator. Suggest widening radius. Block auto-creation. |
| Overlap | Haversine distance to all existing zones. Distance must exceed sum of radii. | Warn operator. Options: widen gap, merge zones, or accept. |
| Budget floor | Radius < 2km requires $50/day min. Radius >= 2km requires $30/day min. | Warn operator. Block if below $20/day (guaranteed waste). |
| Location types | B2C: `home` only. B2B: `home` + `recent`. | Auto-set based on strategy. |
| Creative count | Minimum 2 creatives per ad set (Advantage+ needs variation). | Block until creatives uploaded. |

### 16.2 Scaling Signals (When to Increase Budget Per Zone)

| Signal | Threshold | What It Means |
|--------|-----------|---------------|
| CPA stable 7 days | Variance < 20% day-over-day | Safe to scale |
| Frequency | < 2.5 | Audience not saturated |
| Delivery status | "Active" not "Learning Limited" | Budget increase will help |
| Approval rate (restaurants) | > 15% of leads approved within 14 days | Targeting/creative is working |
| Notify-me conversion (B2C) | > 10% convert to subscriber within 30 days | Market is activating |

**Scaling rule:** Increase budget 20% every 3 days if CPA < target * 0.8 AND frequency < 3. Roll back if CPA rises > 20% after increase. Never increase if delivery status is "Learning Limited by Audience Size" (more budget will not help; need to widen zone or improve creative).

### 16.3 Flywheel Health Metrics (Gemini Advisor Input)

The Gemini advisor uses these per-zone metrics to rank zones and recommend budget allocation:

**Flywheel speed score:** `(notify_me_density * 0.4) + (restaurant_onboard_rate * 0.3) + (subscriber_conversion_rate * 0.3)`

**Zone priority ranking:** Advisor ranks all active zones by flywheel speed and recommends shifting incremental budget to the fastest zones. Zones stuck in `Supply Acquisition` with low restaurant onboard rate get flagged for creative refresh or strategy change, not more budget.

---

## 17. Full-Funnel Tracking Architecture

Complete tracking requires the right tool on each surface. Pixel JS is for web only. Native apps require Meta SDK. CAPI covers all surfaces server-side.

### 17.1 Tracking Matrix

**B2C Surfaces:**

| Surface | Tool | Key Events | Dedup With |
|---------|------|------------|------------|
| Marketing site (vianda-home) | Meta Pixel JS | `ViewContent`, `Lead`, `CompleteRegistration` | CAPI via `event_id` |
| B2C app - web build | Meta Pixel JS | `StartTrial`, `Subscribe` | CAPI via `event_id` |
| B2C app - iOS/Android native | Meta SDK (`react-native-fbsdk-next`) | `fb_mobile_activate_app`, `StartTrial`, `Subscribe`, `Cancel` | CAPI via `event_id` |
| FastAPI backend | CAPI | All B2C events + hashed email/phone for EMQ | Dedup key owner |

**B2B Restaurant Surfaces:**

| Surface | Tool | Key Events | Dedup With |
|---------|------|------------|------------|
| Marketing site /for-restaurants | Meta Pixel JS | `ViewContent`, `Lead` | CAPI via `event_id` |
| FastAPI backend | CAPI | `Lead`, `CompleteRegistration`, `ApprovedPartner` + hashed email | Dedup key owner |

**B2B Employer Surfaces:**

| Surface | Tool | Key Events | Dedup With |
|---------|------|------------|------------|
| Marketing site /for-employers | Meta Pixel JS | `ViewContent`, `EmployerLead` | CAPI via `event_id` |
| B2B portal (vianda-platform) | Meta Pixel JS | `EmployerOnboarded` | CAPI via `event_id` |
| FastAPI backend | CAPI | `EmployerLead`, `EmployerOnboarded`, `EmployerFirstEnrollment` + hashed email | Dedup key owner |

### 17.2 Why Full-Funnel Matters

- **Advantage+ needs full-funnel data:** If you only track the marketing site, Meta cannot optimize for what happens after signup. App events like `StartTrial`, `Subscribe`, `Renewal` are what it actually bids on.
- **Attribution breaks without it:** Click on ad -> install app -> subscribe. If you only have Pixel on the site, Meta never sees the subscription and thinks the ad failed.
- **Audience building:** SDK lets you build audiences of "people who opened app but didn't subscribe" for retargeting.

### 17.3 Event ID Flow (Deduplication)

```
User taps "Subscribe" in B2C app
    |
    +-- App generates event_id = "conv-{subscription_id}"
    |
    +-- Meta SDK fires: AppEventsLogger.logEvent('Subscribe', 29.00, {event_id})
    |   OR Pixel JS fires: fbq('track', 'Subscribe', {value: 29.00}, {eventID: event_id})
    |
    +-- App calls POST /api/v1/subscriptions/with-payment
    |   Body includes: { ..., event_id: "conv-{subscription_id}" }
    |
    +-- Payment webhook fires -> webhooks.py -> conversion_service
    |   Reads event_id from subscription record (provider-agnostic)
    |
    +-- CAPI sends to Meta with same event_id
    |
    +-- Meta deduplicates: keeps CAPI (higher quality), drops SDK/Pixel duplicate
```

### 17.4 Advanced Matching / EMQ Maximization

| Surface | How to Maximize EMQ |
|---------|-------------------|
| Web (Pixel) | Enable Pixel Advanced Matching in Meta Events Manager |
| Native (SDK) | Call `AppEventsLogger.setUserData({ em: email, ph: phone })` |
| Server (CAPI) | Send hashed `em`, `ph`, `external_id`, `fbc`, `fbp` |

---

## 18. Shared: Conversion Job Queue (ARQ)

### 18.1 Worker Configuration

```python
# app/workers/arq_settings.py
from app.workers.conversion_worker import upload_conversion

class WorkerSettings:
    functions = [upload_conversion]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_tries = 3
    retry_jobs = True
    job_timeout = 300
    health_check_interval = 30
```

### 18.2 Unified Conversion Worker

```python
# app/workers/conversion_worker.py
async def upload_conversion(ctx, platform: str, event_data: dict):
    """Single ARQ task handles both platforms."""
    ads_platform = AdsPlatform(platform)
    event = ConversionEvent(**event_data)
    gateway = get_conversion_gateway(ads_platform)

    try:
        result = gateway.upload_conversion(event)
        if result.success:
            update_tracking_status(event.subscription_id, ads_platform, "uploaded")
        else:
            update_tracking_status(event.subscription_id, ads_platform, "failed")
            raise RetryableError(result.error_message)
    except RateLimitError:
        # Re-enqueue with exponential backoff
        raise Retry(defer=timedelta(minutes=ctx["job_try"] * 15))
```

### 18.3 Enqueue Pattern (called from subscription confirmation)

```python
# app/services/ads/conversion_service.py
async def enqueue_conversion_for_all_platforms(redis, event: ConversionEvent):
    """Fan out to all enabled platforms."""
    platforms = settings.ADS_ENABLED_PLATFORMS.split(",")

    for platform_name in platforms:
        platform_name = platform_name.strip()
        if not platform_name:
            continue

        if platform_name == "google":
            delay = timedelta(hours=settings.GOOGLE_ADS_UPLOAD_DELAY_HOURS)
        elif platform_name == "meta":
            delay = timedelta(minutes=settings.META_ADS_UPLOAD_DELAY_MINUTES)
        else:
            continue

        await redis.enqueue_job(
            "upload_conversion",
            platform=platform_name,
            event_data=event.to_dict(),
            _defer_by=delay,
            _job_id=f"{platform_name}-conv-{event.subscription_id}",
        )
```

---

## 19. Shared: Error Taxonomy

Map platform-specific errors to shared categories for unified retry/alerting logic.

```python
# app/services/ads/error_handler.py
class AdsErrorCategory(Enum):
    RATE_LIMITED = "rate_limited"           # Retry with backoff
    PARTIAL_FAILURE = "partial_failure"     # Some succeeded, retry failed ones
    AUTH_EXPIRED = "auth_expired"           # Alert ops, do not retry
    INVALID_DATA = "invalid_data"          # Log and skip (bad PII, missing click ID)
    TRANSIENT = "transient"                # Retry immediately
    PERMANENT = "permanent"                # Log and dead-letter

def categorize_google_error(error) -> AdsErrorCategory:
    if error.error_code == "RESOURCE_EXHAUSTED":
        return AdsErrorCategory.RATE_LIMITED
    if "AUTHENTICATION" in str(error.error_code):
        return AdsErrorCategory.AUTH_EXPIRED
    # ...

def categorize_meta_error(error_code: int) -> AdsErrorCategory:
    if error_code == 17:    # User request limit reached
        return AdsErrorCategory.RATE_LIMITED
    if error_code == 190:   # Invalid/expired token
        return AdsErrorCategory.AUTH_EXPIRED
    if error_code == 100:   # Invalid parameter
        return AdsErrorCategory.INVALID_DATA
    # ...
```

---

## 20. Click Identifier Capture -- Database

### ad_click_tracking Table (Unified, Both Platforms)

```sql
CREATE TABLE public.ad_click_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id),
    subscription_id UUID REFERENCES public.subscriptions(id),
    -- Google identifiers
    gclid VARCHAR(255),
    wbraid VARCHAR(255),
    gbraid VARCHAR(255),
    -- Meta identifiers
    fbclid VARCHAR(255),
    fbc VARCHAR(500),          -- _fbc cookie (longer format: fb.1.timestamp.fbclid)
    fbp VARCHAR(255),          -- _fbp browser cookie
    -- Dedup
    event_id VARCHAR(255),     -- Client-generated, shared across Pixel/SDK/CAPI
    -- Shared
    landing_url TEXT,
    source_platform VARCHAR(20),   -- 'google' | 'meta' | 'organic'
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Per-platform upload status
    google_upload_status VARCHAR(50) DEFAULT 'pending',
    google_uploaded_at TIMESTAMPTZ,
    meta_upload_status VARCHAR(50) DEFAULT 'pending',
    meta_uploaded_at TIMESTAMPTZ
);

CREATE INDEX idx_ad_click_tracking_subscription ON public.ad_click_tracking(subscription_id);
CREATE INDEX idx_ad_click_tracking_pending ON public.ad_click_tracking(google_upload_status)
    WHERE google_upload_status = 'pending' OR meta_upload_status = 'pending';
```

Follow DB schema change protocol: `schema.sql` -> `trigger.sql` -> `seed.sql` -> `dto/models.py` -> `consolidated_schemas.py`.

---

## 21. Rate Limiting Strategy

| Platform | Limit | Strategy |
|----------|-------|----------|
| Google Ads | 15,000 req/day (basic), 2,000 conversions/batch | Single uploads at low volume. Batch at >1,000/day. Backoff on `RESOURCE_EXHAUSTED`. |
| Meta Ads | 200 calls/hr per ad account, 1,000 events/CAPI batch | Batch CAPI events (collect for 5min, flush). Use Batch API for campaign CRUD (50 calls/request). Backoff on error code 17. |

Both platforms: ARQ retry with exponential backoff (5min, 30min, 2h). Dead-letter after 3 failures.

---

## 22. Payment Provider Agnosticism

### 22.1 Problem

The ads conversion pipeline must fire events when payments are captured, regardless of which payment provider processed the transaction. Currently the codebase supports Stripe (live + mock). MercadoPago is planned for LATAM markets. Future providers may follow.

If the conversion pipeline is hardcoded to Stripe webhooks, every new payment provider requires refactoring the ads integration.

### 22.2 Design Principle

The ads conversion service must be **payment-provider-agnostic**. It should react to a canonical "payment captured" event, not to Stripe-specific webhook payloads.

### 22.3 Architecture

```
Payment Provider Webhooks (provider-specific)
    |
    +-- Stripe: POST /api/v1/webhooks/stripe
    +-- MercadoPago: POST /api/v1/webhooks/mercadopago (future)
    +-- Future provider: POST /api/v1/webhooks/{provider}
    |
    v
Each webhook handler normalizes to a shared internal event:
    PaymentCapturedEvent(
        subscription_id, amount, currency, user_id, provider_name
    )
    |
    v
ads/conversion_service.enqueue_conversion_for_all_platforms()
    (already provider-agnostic -- receives canonical ConversionEvent)
```

### 22.4 What Needs to Change

The current Stripe webhook handler in `app/routes/webhooks.py` directly calls subscription confirmation logic. The ads integration point should be inserted at the **subscription confirmation layer**, not the webhook layer:

1. **Webhook handlers** (Stripe, MercadoPago, etc.) call a shared `confirm_subscription_payment()` function
2. `confirm_subscription_payment()` updates subscription status AND calls `enqueue_conversion_for_all_platforms()`
3. The ads service never knows or cares which payment provider triggered the event

This follows the existing `payment_provider/` pattern where `__init__.py` dispatches to `stripe/live.py` or `stripe/mock.py` based on `PAYMENT_PROVIDER` setting.

### 22.5 MercadoPago Considerations

| Concern | Stripe | MercadoPago | Impact on Ads |
|---------|--------|-------------|---------------|
| Webhook event | `payment_intent.succeeded` | `payment` notification (IPN) | Both resolve to "payment captured" |
| Currency | Multi-currency | ARS, PEN, BRL, etc. | `currency_code` field on ConversionEvent handles this |
| Payment ID | `pi_xxx` | MP payment ID (numeric) | Stored in `external_payment_id`, not relevant to ads |
| Settlement delay | Immediate | 2-30 days (depends on plan) | No impact; conversion fires on payment capture, not settlement |

### 22.6 No Refactoring Needed for Ads

The ads conversion pipeline (`ConversionEvent`, `AdsConversionGateway`, ARQ worker) is already provider-agnostic. The only coupling point is **where** the conversion event is triggered. By inserting the ads hook at the subscription confirmation layer (not the webhook layer), adding a new payment provider only requires:

1. New webhook route for the provider
2. New payment provider adapter (following existing `payment_provider/` pattern)
3. Both call the same `confirm_subscription_payment()` which triggers ads events

No changes to the ads gateway, worker, or conversion service.

---

## 23. B2B Restaurant Acquisition Track

**Status:** Scoped as parallel track alongside B2C subscriber acquisition. Detailed form design and vetting questions TBD.

This section covers the ad campaign and conversion tracking side of B2B restaurant acquisition. For the full vetting pipeline (forms, external verification APIs, approval workflow), see `docs/plans/RESTAURANT_VETTING_SYSTEM.md`.

### 23.1 Overview

Vianda needs to acquire restaurant suppliers through paid ads, separate from B2C subscriber campaigns. Restaurants are the supply side of the B2B2C model.

Two phases:
1. **Phase 1 (launch):** Ads drive restaurants to a landing page on the marketing site. Interest form captures lead data. Manual review + vetting.
2. **Phase 2 (future):** Self-serve registration on the B2B portal with auto-vetting. Ads drive to B2B portal directly.

### 23.2 B2B Conversion Events

| Event | When Fired | Value Signal | Platforms |
|-------|-----------|-------------|-----------|
| `Lead` | Restaurant submits interest form | Low ($1) | Google + Meta CAPI |
| `CompleteRegistration` | Full vetting form completed | Medium ($10) | Google + Meta CAPI |
| `ApprovedPartner` | Admin approves restaurant after vetting | High ($100-500) | Meta CAPI (custom event) + Google offline conversion |

The `ApprovedPartner` event is the most valuable optimization signal. It tells ad platforms: "this type of lead actually converts to a paying partner." This is critical for campaign ML to find similar high-quality leads.

### 23.3 B2B Audience Targeting

Advantage+ audience expansion is too broad for B2B restaurant targeting. Campaigns must use `audience_controls`:

**Interest targeting:**
- Restaurant owner, food service professional, catering business
- Small business owner, entrepreneur

**Geo targeting:**
- Cities where Vianda has or is expanding coverage
- Metro areas with high restaurant density

**Exclusions:**
- Existing Vianda restaurant partners (Custom Audience upload)
- Non-business users (age, behavior filters)

### 23.4 Lead-Gen vs Self-Serve

| Acquisition Path | Ad Destination | Conversion Point | Dependencies |
|-----------------|---------------|-----------------|-------------|
| **Lead-gen (Phase 1)** | Marketing site `/for-restaurants` | Form submission = `Lead` event | Restaurant interest form + marketing site landing page |
| **Self-serve (Phase 2)** | B2B portal `/register` | Account creation = `CompleteRegistration` event | B2B portal registration + approval flow |

Initial launch uses lead-gen to validate demand, simplify vetting, and accumulate conversion data before investing in self-serve registration.

### 23.5 Data Flow (B2B Track)

```
Ad Click (Google/Meta B2B campaign)
    |
    v
Marketing Site: /for-restaurants
    |-- Pixel fires ViewContent (content_type: restaurant_landing)
    |
    v
Restaurant Interest Form submitted
    |-- POST /api/v1/leads/restaurant-interest
    |-- CAPI fires Lead event (both platforms)
    |-- Click IDs (gclid/fbclid/fbc/fbp) stored on restaurant_lead record
    |
    v
Internal Admin Review
    |-- Optional: external verification (AFIP, SUNAT, D&B)
    |
    v
Approved
    |-- Create Supplier institution
    |-- CAPI fires ApprovedPartner event (highest value signal)
    |-- Send onboarding invite email
    |
    v
Supplier Onboarding (existing flow)
```

### 23.6 Risks

| Risk | Mitigation |
|------|-----------|
| Low volume: <50 approvals/week prevents ML optimization | Start with `Lead` optimization, switch to `ApprovedPartner` when volume allows |
| Broad audience waste: ads shown to non-restaurant users | Use `audience_controls` (section 18.3) to constrain targeting |
| Lead quality: many form submissions, few approvals | Send `ApprovedPartner` event so platforms learn quality signals |
| Self-serve dependency: B2B portal registration not built | Phase 1 uses lead-gen only, no portal dependency |
| Vetting questions not finalized | `vetting_answers` JSONB field allows iteration without schema changes |

### 23.7 Dependencies

- **Ads Platform Phase 6:** Meta CAPI gateway must be live
- **Restaurant Vetting System:** `docs/plans/RESTAURANT_VETTING_SYSTEM.md` (form, review workflow, approval automation)
- **Marketing Site:** `/for-restaurants` landing page with Pixel tracking
- **B2B Portal (Phase 2 only):** Registration flow with approval queue

---

## 24. Local Development vs. Production

### docker-compose.yml

```yaml
version: "3.8"
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes

  arq-worker:
    build: .
    command: arq app.workers.arq_settings.WorkerSettings
    environment:
      - REDIS_URL=redis://redis:6379
      - ADS_ENABLED_PLATFORMS=google,meta
      - GOOGLE_ADS_PROVIDER=mock
      - META_ADS_PROVIDER=mock
      - DEV_MODE=true
    depends_on:
      - redis
    volumes:
      - .:/app

volumes:
  redis-data:
```

### Environment Separation

| Concern | Local | Production |
|---------|-------|------------|
| Redis | `docker-compose` container | GCP Cloud Memorystore (Pulumi) |
| Google Ads API | Mock gateway (logs) | Live gateway via `google-ads-python` |
| Meta Ads API | Mock gateway (logs) | Live gateway via `facebook-business` SDK |
| Secrets | `.env` file | GCP Secret Manager via ADC |
| Worker | `arq` CLI in Docker | Cloud Run Job or second Cloud Run service |
| Click identifiers | Hardcoded test values | Captured from real ad traffic |

---

## 25. Infrastructure Requirements for Pulumi Agent

### GCP Resources

| Resource | Type | New/Reused | Config |
|----------|------|------------|--------|
| Cloud Memorystore (Redis) | `gcp.redis.Instance` | **New** | See Tier recommendation in section 26 |
| VPC Connector | `gcp.vpcaccess.Connector` | **New** | Cloud Run to Memorystore |
| Google Ads secrets (x7) | `gcp.secretmanager.Secret` | **New** | See section 5.3 |
| Meta Ads secrets (x4) | `gcp.secretmanager.Secret` | **New** | See section 5.3 |
| Cloud Run service (worker) | `gcp.cloudrun.Service` | **New** | Same image, entrypoint: `arq app.workers.arq_settings.WorkerSettings` |
| IAM bindings | `gcp.projects.IAMMember` | **Reused SA** | Same Cloud Run SA, add secretAccessor for new secrets |
| Cloud Scheduler | `gcp.cloudscheduler.Job` | **New** (optional) | ARQ worker health check ping |
| Cloud Run (API) | `gcp.cloudrun.Service` | **Existing** | Add REDIS_URL, ADS_* env vars |

**Single service account** for both the API and worker Cloud Run services. No need for separate SAs per ad platform.

### Network

- Cloud Memorystore requires VPC access. Cloud Run must use Serverless VPC Access connector.
- No public IP needed for Memorystore.

---

## 26. Security Checklist

- [ ] PII (email, phone) is SHA256-hashed before leaving the service boundary (shared `pii_hasher.py`)
- [ ] Raw PII is **never** written to logs, Redis, or any persistent store
- [ ] ARQ job payloads contain hashed identifiers only (hash before enqueue)
- [ ] All ad platform credentials stored in GCP Secret Manager (prod)
- [ ] `GOOGLE_APPLICATION_CREDENTIALS` never committed to repo
- [ ] Meta `app_secret` used for `appsecret_proof` on every API call (prevents token hijacking)
- [ ] Meta system user token scoped to minimum permissions (`ads_management`, `ads_read`, `business_management`, `leads_retrieval`)
- [ ] Redis (Memorystore) accessible only via private VPC
- [ ] `ad_click_tracking` table stores click IDs (not PII) and upload status only
- [ ] Ad tracking consent collected before storing click IDs (see Terms of Service plan)

---

## 27. Dependencies (New Packages)

```
google-ads>=24.0.0              # Google Ads API client
facebook-business>=25.0.0       # Meta Marketing API + CAPI SDK
google-genai>=1.0.0             # Google Gemini API (GenAI SDK) -- advisor layer + creative critique
google-cloud-secret-manager     # GCP Secret Manager
arq>=0.26                       # Async Redis Queue
redis[hiredis]>=5.0             # Redis client with C parser
```

---

## 28. Implementation Phases

**Launch activation sequence:** B2C first (month 1), B2B employer (month 3), B2B restaurant (month 4). Build all infrastructure in parallel, but activate ad spend sequentially. See section 14.8 for rationale.

| Phase | Scope | Depends On | Target Month |
|-------|-------|------------|-------------|
| **Phase 1** | Shared infra: `gcp_secrets.py`, settings, Redis docker-compose, `pii_hasher.py`, `models.py` | Nothing | M1 |
| **Phase 2** | AdsProvider ABC, mock gateway, gateway factory | Phase 1 | M1 |
| **Phase 3** | ARQ worker setup: `arq_settings.py`, `conversion_worker.py` (unified) | Phase 1 | M1 |
| **Phase 4** | `ad_click_tracking` + `ad_zone` tables, DTOs, schemas (DB layer) | Nothing | M1 |
| **Phase 5** | Google Ads gateway (conversion upload) | Phases 2, 3 | M1 |
| **Phase 6** | Meta Ads gateway (CAPI conversion upload) | Phases 2, 3 | M1 |
| **Phase 7** | Wire subscription confirmation to `enqueue_conversion_for_all_platforms` (payment-provider-agnostic hook) | Phases 4, 5, 6 | M1 |
| **Phase 8** | Error taxonomy + retry logic (`error_handler.py`) | Phase 7 | M1 |
| **Phase 9** | Pulumi infra (Memorystore, secrets, VPC connector, worker, marketing GCS bucket) | Phases 1-8 | M1 |
| **Phase 10** | Frontend tracking: Pixel JS (vianda-home, vianda-app web), Meta SDK (vianda-app native) | Phase 4 | M1 |
| **Phase 11** | E2E testing: Google Ads sandbox + Meta test events tool | Phases 7, 9 | M1 |
| **Phase 12** | **B2C LAUNCH:** Activate B2C_SUBSCRIBER campaigns. Hit 50+ Subscribe/week. Operator creates initial zones. | Phases 7-11 | M1 |
| **Phase 13** | Terms of Service: ad tracking consent flow (`docs/plans/TERMS_OF_SERVICE.md`) | Phase 4 | M1 |
| **Phase 14** | Google Ads + Meta campaign management gateways | Phases 5, 6 | M2 |
| **Phase 15** | Marketing collateral service: `marketing_collateral` tables, creative sync (Meta to GCS), performance ingest | Phase 14 | M2 |
| **Phase 16** | Creative concept analysis: weekly Gemini analysis of concept performance + seed refresh | Phase 15 | M2 |
| **Phase 17** | B2B employer track: employer interest form enhancement, CAPI Lead/CompleteRegistration/Subscribe events (standard names), /for-employers landing page | Phases 6, 7 | M2 |
| **Phase 18** | **B2B EMPLOYER LAUNCH:** Activate B2B_EMPLOYER campaigns in zones with stable B2C CPA | Phases 14, 17 | M3 |
| **Phase 19** | B2B restaurant acquisition: `restaurant_lead` table, `POST /leads/restaurant-interest`, CAPI Lead/CompleteRegistration/ApprovedPartner events (`docs/plans/RESTAURANT_VETTING_SYSTEM.md`) | Phases 6, 7 | M3 |
| **Phase 20** | **B2B RESTAURANT LAUNCH:** Activate B2B_RESTAURANT campaigns. Micro-conversion funnel (optimize to Lead, send ApprovedPartner as value signal). | Phases 14, 19 | M4 |
| **Phase 21** | Zone automation: notify-me DBSCAN clustering, delivery_estimate caching, audience sync jobs, overlap validation | Phases 4, 12 | M4 |
| **Phase 22** | Gemini advisor layer: `google-genai` SDK, cross-platform + cross-strategy analysis, budget recommendations | Phase 14 | M5 |
| **Phase 23** | Cross-platform Gemini optimizer: 3-strategy budget allocation, zone flywheel speed ranking, bottleneck-based spending | Phase 22 | M6 |
| **Phase 24** | MercadoPago webhook integration (payment-provider-agnostic ads hook already in place from Phase 7) | Phase 7 | When needed |
| **Phase 25** | Retention/win-back strategy: Custom Audience sync of churned subscribers + inactive restaurants (future) | Phase 22 | Future |

---

## 29. Cross-Repo Impact

| Repo | What It Needs | Reference |
|------|---------------|-----------|
| **infra-kitchen-gcp** | Pulumi: Memorystore (STANDARD tier), VPC connector, 11 secrets, worker Cloud Run, marketing GCS bucket, IAM (incl. `aiplatform.user` for Gemini) | Section 33 |
| **vianda-app** (B2C) | Pixel JS (web), Meta SDK (native), click ID capture, event_id generation, user data for EMQ | Section 32 |
| **vianda-home** (marketing) | Meta Pixel JS, click ID capture, `/for-restaurants` + `/for-employers` landing pages with forms | Section 32, `docs/plans/RESTAURANT_VETTING_SYSTEM.md` section 12 |
| **vianda-platform** (B2B) | Restaurant lead review dashboard, Pixel JS on B2B portal for employer onboarding events, zone management admin UI | `docs/plans/RESTAURANT_VETTING_SYSTEM.md` section 11 |
| **kitchen** (this repo) | All backend implementation (Phases 1-25) | This document |

---

## 30. Manual Operations (UI)

These steps must be completed manually before backend integration can function. Organized by platform.

### 30.1 Google Ads (Google Ads UI)

| Step | Where | What to Do | Output Needed |
|------|-------|-----------|---------------|
| 1. Create MCC account | Google Ads UI | Create a Manager (MCC) account if not already exists | `login_customer_id` |
| 2. Create customer account | Google Ads UI | Create an ad account under MCC | `customer_id` |
| 3. Create B2C conversion actions | Google Ads UI > Tools > Conversions | Create conversion actions: "Subscription" (Subscribe category), "Trial Start", "Renewal" (Purchase category). Enable Enhanced Conversions on each. | `conversion_action_id` per action |
| 4. Create B2B conversion actions | Google Ads UI > Tools > Conversions | Create conversion actions: "Restaurant Lead" (Lead category), "Restaurant Registration" (Submit Form), "Approved Partner" (Other). | `conversion_action_id` per action |
| 5. Create Performance Max campaign (B2C) | Google Ads UI | Set up campaign with goals, budget, geo targeting, asset groups (images, headlines, descriptions, logo) | Campaign ID (for validation) |
| 6. Create Performance Max campaign (B2B) | Google Ads UI | Separate campaign for restaurant acquisition. Different budget, geo, and creative. | Campaign ID (for validation) |
| 7. Apply for API access | Google Ads API Center | Submit for Basic Access (or Standard for >15k req/day). Provide developer token use case. | `developer_token` approved |
| 8. Create OAuth2 credentials | Google Cloud Console > APIs & Credentials | Create OAuth2 client ID (Desktop app type). Generate refresh token using `google-ads-python` auth helper. | `client_id`, `client_secret`, `refresh_token` |

### 30.2 Meta Ads (Meta Business Manager)

| Step | Where | What to Do | Output Needed |
|------|-------|-----------|---------------|
| 1. Create Business Manager | business.facebook.com | Create BM if not exists. Add ad account. | BM ID |
| 2. Create system user | Business Manager > Settings > Users > System Users | Create a system user with `admin` role. Generate a long-lived token with permissions: `ads_management`, `ads_read`, `business_management`. | `system_user_token` |
| 3. Create Meta App | Meta Developers | Create a Business-type app. Link to BM. Get app secret. | `app_id`, `app_secret` |
| 4. Create Pixel | Business Manager > Events Manager | Create a Meta Pixel. Note the Pixel ID. | `pixel_id` |
| 5. Configure Pixel events | Events Manager > Custom Conversions | Verify that `Subscribe`, `StartTrial`, `Purchase` standard events are recognized. No custom conversions needed if using standard event names. | Validation |
| 6. Create ad account | Business Manager > Ad Accounts | Create or claim an ad account. Note the `act_` ID. | `ad_account_id` |
| 7. Set up Advantage+ Sales campaign | Ads Manager UI | Create a Sales campaign. Enable all 3 Advantage+ levers (audience, placements, creative). Set budget, geo, upload creative assets. | Campaign ID (for validation) |
| 8. Verify domain | Business Manager > Brand Safety > Domains | Add and verify vianda.market domain (DNS TXT record or meta tag). Required for Aggregated Event Measurement. | Domain verified |

### 30.3 Store Secrets After Manual Setup

After completing UI setup for both platforms, store all credentials in GCP Secret Manager:

```bash
# Google Ads (run once after manual setup)
echo -n "YOUR_DEVELOPER_TOKEN" | gcloud secrets create google-ads-developer-token --data-file=-
echo -n "YOUR_CLIENT_ID" | gcloud secrets create google-ads-oauth-client-id --data-file=-
# ... repeat for all 7 Google secrets (section 5.3)

# Meta Ads (run once after manual setup)
echo -n "YOUR_SYSTEM_USER_TOKEN" | gcloud secrets create meta-ads-system-user-token --data-file=-
# ... repeat for all 4 Meta secrets (section 5.3)
```

Or better: let the Pulumi agent create empty secrets, then populate values via GCP Console UI.

---

## 31. Reference Links

**Meta:**
- Marketing API overview: https://developers.facebook.com/docs/marketing-apis
- Advantage+ Sales campaigns: https://developers.facebook.com/docs/marketing-api/audiences/advantage-plus-audience
- Conversions API (CAPI): https://developers.facebook.com/docs/marketing-api/conversions-api
- CAPI best practices: https://developers.facebook.com/docs/marketing-api/conversions-api/best-practices
- System user tokens: https://developers.facebook.com/docs/marketing-api/system-users
- Rate limits: https://developers.facebook.com/docs/marketing-api/overview/rate-limiting
- Batch API: https://developers.facebook.com/docs/marketing-api/batch-requests
- Event Match Quality: https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/server-event
- React Native SDK: https://developers.facebook.com/docs/app-events/getting-started-app-events-react-native

**Google Ads:**
- API overview: https://developers.google.com/google-ads/api/docs/start
- Enhanced Conversions: https://developers.google.com/google-ads/api/docs/conversions/upload-clicks
- Performance Max: https://developers.google.com/google-ads/api/docs/performance-max/overview
- Rate limits: https://developers.google.com/google-ads/api/docs/best-practices/rate-limits

---

## 32. Feedback for B2C App Agent

> **Audience:** vianda-app agent (B2C React Native app). Read this section for implementation requirements related to the Ads Platform integration.

### 32.1 Meta Pixel JS (Web Build Only)

**Requirement:** Install Meta Pixel JS base code in the web build of the React Native app (`react-native-web`).

- Add the Pixel base code snippet to `index.html` (web entry point)
- Pixel ID will be provided as an environment variable: `META_PIXEL_ID`
- Only load Pixel JS when `Platform.OS === 'web'`
- Do NOT load Pixel JS on native (iOS/Android). It will not work in native code.

**Events to fire from web:**

```javascript
// On subscription completion (thank-you page / confirmation screen)
fbq('track', 'Subscribe', {
  value: 29.99,
  currency: 'USD',
  subscription_id: 'sub_uuid_here'
}, { eventID: 'conv-sub_uuid_here' });

// On trial activation
fbq('track', 'StartTrial', {
  value: 0,
  currency: 'USD',
  subscription_id: 'sub_uuid_here'
}, { eventID: 'conv-sub_uuid_here' });
```

**Enable Advanced Matching** in Meta Events Manager (UI step, not code) for better EMQ on web.

### 32.2 Meta SDK (Native iOS/Android)

**Requirement:** Install `react-native-fbsdk-next` for native event tracking.

```bash
npm install react-native-fbsdk-next
```

**Platform setup:**
- iOS: Add Facebook App ID to `Info.plist`
- Android: Add Facebook App ID to `AndroidManifest.xml`
- Follow Meta docs: https://developers.facebook.com/docs/app-events/getting-started-app-events-react-native

**Events to fire from native:**

```javascript
import { AppEventsLogger } from 'react-native-fbsdk-next';

// On subscription completion
AppEventsLogger.logEvent('Subscribe', 29.00, {
  currency: 'USD',
  subscription_id: 'sub_uuid_here',
  event_id: 'conv-sub_uuid_here'  // MUST match CAPI event_id
});

// Set user data for EMQ (after login, hashed by SDK internally)
AppEventsLogger.setUserData({
  email: 'user@example.com',  // SDK hashes automatically
  phone: '+1234567890'
});
```

**Platform detection pattern:**

```javascript
import { Platform } from 'react-native';

function trackSubscription(subscriptionId, value, currency) {
  const eventId = `conv-${subscriptionId}`;
  if (Platform.OS === 'web') {
    fbq('track', 'Subscribe', { value, currency, subscription_id: subscriptionId }, { eventID: eventId });
  } else {
    AppEventsLogger.logEvent('Subscribe', value, { currency, subscription_id: subscriptionId, event_id: eventId });
  }
}
```

### 32.3 Click Identifier Capture

**Requirement:** Capture ad click identifiers from URL parameters on app launch / deep link entry and persist them through the subscription flow.

**What to capture:**

| URL Param | Storage Key | Platform |
|-----------|------------|----------|
| `gclid` | `ad_gclid` | Google |
| `wbraid` | `ad_wbraid` | Google (iOS) |
| `gbraid` | `ad_gbraid` | Google (iOS) |
| `fbclid` | `ad_fbclid` | Meta |

Additionally, read these cookies on web:
- `_fbc` (Meta click cookie, set by Pixel JS)
- `_fbp` (Meta browser cookie, set by Pixel JS)

**Where to store:** AsyncStorage or equivalent session storage. These values must survive navigation through the signup/subscription flow.

**When to send:** Include all captured click identifiers in the `POST /api/v1/subscriptions/with-payment` request body. New fields will be added to the subscription creation schema:

```json
{
  "plan_id": "...",
  "payment_method_id": "...",
  "gclid": "...",
  "wbraid": null,
  "gbraid": null,
  "fbclid": "...",
  "fbc": "fb.1.1234567890.abcdef",
  "fbp": "fb.1.1234567890.987654321",
  "event_id": "conv-{subscription_id}"
}
```

### 32.4 Event ID Generation

**Requirement:** Generate a stable `event_id` at the moment the user initiates a subscription action (taps Subscribe button). This ID must be:

1. Passed to Meta SDK / Pixel JS when firing the client-side event
2. Included in the `POST /subscriptions/with-payment` request body
3. Used by the backend CAPI call for deduplication

**Format:** `conv-{subscription_id}` (the subscription UUID will be known after the API call returns, so generate a temporary UUID client-side, then use the server-returned subscription_id for the CAPI call).

**Alternative:** Generate `event_id` server-side and return it in the subscription creation response. The app then fires the SDK/Pixel event with that ID. This avoids the timing issue but means the client event fires slightly after the server event.

### 32.5 Open Questions for B2C Team

1. How does the B2C app currently handle URL query parameters on deep links? Specifically, do params like `?gclid=xxx` survive through the app install flow (ad click -> app store -> install -> first open)?
2. Does the RN web build use a separate domain from the marketing site? If same domain, only one Pixel base code is needed.
3. What is the current deep link handling library? Need to ensure click ID extraction works with it.
4. Is there an existing analytics/tracking abstraction in the app? If so, the Meta SDK events should integrate with it rather than being called directly.

---

## 33. Feedback for Infra Agent

> **Audience:** infra-kitchen-gcp agent (Pulumi Python stack). Read this section for infrastructure requirements related to the Ads Platform integration.

### 33.1 Cloud Memorystore (Redis) -- Tier Recommendation

**Recommendation: STANDARD tier**, not BASIC.

**Why:** The ARQ job queue holds conversion upload jobs deferred by up to 24 hours. BASIC tier has no replication. If the single Redis node fails:
- All deferred jobs are lost
- Conversions are never uploaded to Google/Meta
- Revenue attribution data is permanently lost
- No way to reconstruct which conversions were pending

STANDARD tier provides:
- Automatic failover to replica (99.9% SLA)
- Cross-zone replication
- Zero data loss on node failure

**Cost impact:** STANDARD is ~2x BASIC for the same memory. At 1GB, this is minimal.

**Config:**

| Setting | Value |
|---------|-------|
| Tier | `STANDARD_HA` |
| Memory | 1 GB (sufficient for ~100k pending jobs) |
| Version | Redis 7.x |
| Region | Same as Cloud Run services |
| VPC | Same VPC as Cloud Run |
| Auth | `AUTH` enabled, password in Secret Manager |
| Maintenance window | Off-peak hours (e.g., Sunday 02:00 UTC) |

If cost is a hard constraint, BASIC is acceptable with a mitigation: implement a DB-backed fallback that polls `ad_click_tracking` rows with `pending` status and re-enqueues missing jobs on worker startup.

### 33.2 GCP Resources to Provision

| Resource | Pulumi Type | Config |
|----------|------------|--------|
| Cloud Memorystore | `gcp.redis.Instance` | STANDARD_HA, 1GB, same VPC, AUTH enabled |
| VPC Connector | `gcp.vpcaccess.Connector` | Connect Cloud Run to Memorystore private network |
| Google Ads secrets (x7) | `gcp.secretmanager.Secret` | See section 5.3 for secret IDs |
| Meta Ads secrets (x4) | `gcp.secretmanager.Secret` | See section 5.3 for secret IDs |
| Cloud Run service (ARQ worker) | `gcp.cloudrun.Service` | Same container image as API, different entrypoint (see below) |
| GCS marketing bucket | `gcp.storage.Bucket` | `GCS_MARKETING_BUCKET` for creative assets synced from Meta + human uploads |
| IAM: secretAccessor | `gcp.secretmanager.SecretIamMember` | Grant existing Cloud Run SA access to all 11 new secrets |
| IAM: redis.editor | `gcp.projects.IAMMember` | Grant existing Cloud Run SA Redis access |
| IAM: aiplatform.user | `gcp.projects.IAMMember` | Grant existing Cloud Run SA Vertex AI access (Gemini) |
| IAM: storage.objectAdmin | `gcp.storage.BucketIAMMember` | Grant Cloud Run SA write access to marketing bucket |
| Cloud Scheduler (creative sync) | `gcp.cloudscheduler.Job` | Daily creative sync + critique job trigger |
| Cloud Scheduler (ARQ health) | `gcp.cloudscheduler.Job` | Periodic health check for ARQ worker |

### 33.3 Worker Cloud Run Service

The ARQ worker runs as a **separate Cloud Run service** using the same container image but a different entrypoint:

```
entrypoint: ["arq", "app.workers.arq_settings.WorkerSettings"]
```

| Setting | Value |
|---------|-------|
| Image | Same as API service (shared build) |
| Entrypoint | `arq app.workers.arq_settings.WorkerSettings` |
| Min instances | 1 (must stay warm for deferred jobs) |
| Max instances | 3 |
| Memory | 512 MB |
| CPU | 1 |
| VPC Connector | Same as API service (for Memorystore access) |
| Concurrency | 1 (ARQ handles its own concurrency) |

### 33.4 Environment Variables for Both Services

Add to both API and worker Cloud Run services:

```
REDIS_URL=redis://:${REDIS_AUTH_PASSWORD}@${MEMORYSTORE_HOST}:6379
ADS_ENABLED_PLATFORMS=google,meta
GOOGLE_ADS_PROVIDER=live
META_ADS_PROVIDER=live
GCP_PROJECT_ID=${PROJECT_ID}
```

Google/Meta-specific credentials should be fetched from Secret Manager at runtime (not env vars).

### 33.5 Per-Environment Ad Accounts

Each environment uses different ad platform accounts/tokens:

| Secret | Dev | Staging | Prod |
|--------|-----|---------|------|
| `google-ads-customer-id` | Test account | Test account | Live account |
| `meta-ads-pixel-id` | Test Pixel | Test Pixel | Live Pixel |
| `meta-ads-ad-account-id` | Sandbox act_ | Sandbox act_ | Live act_ |
| `meta-ads-system-user-token` | Test token | Test token | Live token |

Consider using Pulumi's `config.require_secret()` per stack (dev/staging/prod) for account IDs, and Secret Manager for tokens/credentials.

### 33.6 Network

- Cloud Memorystore requires private VPC. No public IP.
- Serverless VPC Access connector required for Cloud Run to reach Memorystore.
- No new firewall rules needed beyond the VPC connector default.

### 33.7 Monitoring

Add Cloud Monitoring alerts for:

| Metric | Threshold | Action |
|--------|-----------|--------|
| ARQ worker health check | No heartbeat for 5 min | Page on-call |
| Conversion upload failure rate | >10% over 1h | Alert to Slack |
| Redis memory usage | >80% | Scale up Memorystore |
| Secret Manager access errors | Any | Alert (indicates auth/IAM issue) |

---

## 34. Open Questions

1. ~~**Conversion action setup (Google):**~~ Will be done via UI (see section 30).
2. ~~**Meta Pixel setup:**~~ Not installed yet. Requirements in section 32 for B2C and marketing site agents.
3. ~~**Click ID passthrough:**~~ Open question for B2C team (see section 32).
4. ~~**Redis persistence tier:**~~ STANDARD recommended (see section 33).
5. **Consent/GDPR:** Ad tracking consent must be collected before storing click IDs or uploading hashed PII. See `docs/plans/TERMS_OF_SERVICE.md`. The subscription flow must include an explicit consent checkbox or banner.
6. ~~**Meta system user:**~~ Will be created via Business Manager UI (see section 30).
7. ~~**Campaign management scope:**~~ Full campaign management is in scope for all 3 strategies. Modules scoped in section 11.
8. **MercadoPago timeline:** When is MercadoPago integration expected? Ads pipeline is payment-provider-agnostic (section 22), but webhook handler needed for LATAM payment events.
9. **Restaurant vetting questions:** TBD. See `docs/plans/RESTAURANT_VETTING_SYSTEM.md`.
10. ~~**Gemini campaign automation:**~~ Confirmed viable. Architecture in section 12. Implementation in Phase 22.
11. **Address model: neighborhood field.** Adding `neighborhood` to `address_info` is a dependency for human-readable zone reporting (section 15.4). Verify that Mapbox geocoding returns neighborhood data and that lat/lon are already stored. Schema change follows DB protocol.
12. **Retention/win-back strategy.** Gemini recommends a fourth strategy for churned subscriber and inactive restaurant reactivation via Custom Audience sync. Noted as Phase 25 (future). The audience exclusion infrastructure (section 14.7) already supports the Custom Audience sync needed for this.
13. **Meta `effective_object_story_id`.** To get the final rendered post as users see it (for "as seen on Instagram" gallery), sync should pull `effective_object_story_id` via `GET /{id}?fields=attachments`. Note for Phase 15 implementation.
14. **First zone: where?** Operator must decide the first cold-start zone for B2C launch (Phase 12). This is a business decision, not a technical one. The system supports operator-created zones with no prior data.
