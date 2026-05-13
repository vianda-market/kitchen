# config/settings.py
import os
from typing import Literal
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict

# Only load .env for local development. Cloud Run environments (dev/staging/prod) read
# exclusively from the process environment injected by Cloud Run, never from a file.
# This prevents any .env that accidentally leaks into the image from silently overriding
# Cloud Run env vars (closes the root cause of issue #189).
_ENVIRONMENT = (os.getenv("ENVIRONMENT") or "local").lower()
_ENV_FILE = ".env" if _ENVIRONMENT == "local" else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")
    # Auth fields: required in every deployed environment (Cloud Run injects real values
    # from Secret Manager).  Defaulted to sentinel strings so that DB/maintenance scripts
    # (scripts/backfill_mapbox_geocoding.py, scripts/load_demo_data.sh) that transitively
    # import this module — but never exercise auth code paths — can complete without
    # ValidationError in CI runners that do not carry auth-specific env vars.
    #
    # Pattern A — sentinel default + use-site guard: any call to create_access_token,
    # verify_token, or get_current_user with the sentinel value raises RuntimeError before
    # a single byte is signed, so a misconfigured deployment fails loudly rather than
    # silently issuing tokens with a known-bad key.  Prod/dev/staging are unaffected:
    # Cloud Run's env block always supplies real values and the sentinel is never reached.
    SECRET_KEY: str = "__UNSET_NOT_FOR_AUTH__"
    ALGORITHM: str = "__UNSET_NOT_FOR_AUTH__"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 0
    DEV_OVERRIDE_DAY: str = ""  # Override current day for testing (e.g., "Monday")
    DEV_MODE: bool = True  # Enable to bypass external API calls and use mock responses
    # Set to True (or env DEBUG_PASSWORD_RECOVERY=1) to enable terminal debug logs for password/username recovery
    DEBUG_PASSWORD_RECOVERY: bool = False
    # Set to True (or env LOG_EMAIL_TRACKING=1) to log email send/tracking (SMTP connect, success, failures). Off in production; turn on when debugging email.
    LOG_EMAIL_TRACKING: bool = False
    # Set to 1/true/yes to log PUT /users/me/employer (employer assignment) for debugging. Off in production.
    LOG_EMPLOYER_ASSIGN: str = "0"

    # B2B invite: URL template for set-password link. Use {code} placeholder. E.g. "https://b2b.example.com/set-password?code={code}"
    # If empty, falls back to B2B_FRONTEND_URL + /set-password?code={code}
    B2B_INVITE_SET_PASSWORD_URL: str = ""
    # B2B app base URL (e.g. http://localhost:5173). Used for invite set-password links when B2B_INVITE_SET_PASSWORD_URL not set.
    B2B_FRONTEND_URL: str = ""

    # Payment provider: "mock" (Stripe mock for dev) or "stripe" (live Stripe). Default mock for dev.
    PAYMENT_PROVIDER: str = "mock"
    # Supplier (institution) payout: "mock" or "stripe". Used after settlement → bill for restaurant payouts.
    SUPPLIER_PAYOUT_PROVIDER: str = "mock"

    # Email provider: "smtp" (Gmail SMTP, default for dev) or "sendgrid" (production).
    EMAIL_PROVIDER: str = "smtp"
    SENDGRID_API_KEY: str = ""
    EMAIL_FROM_ADDRESS: str = ""  # e.g. hello@vianda.market (falls back to FROM_EMAIL env var)
    EMAIL_FROM_NAME: str = ""  # e.g. Vianda (falls back to FROM_NAME env var)
    EMAIL_REPLY_TO: str = ""  # e.g. support@vianda.market

    # Stripe (required when PAYMENT_PROVIDER=stripe; use test keys sk_test_/pk_test_ for sandbox)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""  # Optional; for client-side Stripe Elements
    # B2C Checkout Session (mode=setup): default success_url when POST body omits success_url
    STRIPE_CUSTOMER_SETUP_SUCCESS_URL: str = ""
    # Stripe Connect (supplier outbound payouts). SUPPLIER_PAYOUT_PROVIDER=stripe to activate.
    STRIPE_CONNECT_WEBHOOK_SECRET: str = ""  # whsec_… from sandbox/live Connect webhook endpoint
    STRIPE_PLATFORM_ACCOUNT_ID: str = ""  # acct_… of the Vianda platform account (optional; for logging)

    # App store URLs for benefit employee invite emails (placeholder until apps are published)
    APP_STORE_URL: str = "https://apps.apple.com/app/vianda/id_placeholder"
    PLAY_STORE_URL: str = "https://play.google.com/store/apps/details?id=com.vianda.placeholder"
    # B2C app password-set URL template for benefit employees (use {code} placeholder). Falls back to B2B URL if empty.
    BENEFIT_INVITE_SET_PASSWORD_URL: str = ""
    # B2C app deep link scheme for engagement emails (e.g. "vianda://plans"). Empty = use App Store/Play Store links only.
    APP_DEEP_LINK_BASE: str = ""

    # Google API Keys per environment (read from .env only - never commit)
    # local and dev use GOOGLE_API_KEY_DEV; staging uses _STAGING; prod uses _PROD
    GOOGLE_API_KEY_DEV: str = ""
    GOOGLE_API_KEY_STAGING: str = ""
    GOOGLE_API_KEY_PROD: str = ""

    # Mapbox Access Tokens per environment (read from .env only - never commit)
    MAPBOX_ACCESS_TOKEN_DEV: str = ""
    MAPBOX_ACCESS_TOKEN_STAGING: str = ""
    MAPBOX_ACCESS_TOKEN_PROD: str = ""

    # Persistent-storage Mapbox tokens (sk.*). Used by callsites that write lat/lng to DB.
    # DEV's MAPBOX_CACHE_MODE defaults to replay_only, so the persistent token is only
    # billed when a dev manually flips MAPBOX_CACHE_MODE to "record".
    MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT: str | None = None
    MAPBOX_ACCESS_TOKEN_STAGING_PERSISTENT: str | None = None
    MAPBOX_ACCESS_TOKEN_PROD_PERSISTENT: str | None = None

    # Address/geocoding provider: "mapbox" (default) or "google" (fallback)
    ADDRESS_PROVIDER: str = "mapbox"

    # Autocomplete provider for the /suggest endpoint.
    # "geocoding" (default) — uses Mapbox Geocoding API v6 forward search with autocomplete=true
    #   against the places-permanent dataset. One paid call per address. TOS-clean.
    # "search_box" — uses Mapbox Search Box (ephemeral session) for richer partial/typo UX.
    #   Two paid calls per address (suggest + final places-permanent resolve). Q2 rule still enforced.
    # Flip at runtime via ADDRESS_AUTOCOMPLETE_PROVIDER env var; no redeploy required.
    ADDRESS_AUTOCOMPLETE_PROVIDER: Literal["geocoding", "search_box"] = "geocoding"

    # Mapbox geocoding cache mode: "replay_only" (default — cache miss raises, never calls Mapbox),
    # "record" (cache miss calls Mapbox and writes entry), "bypass" (prod — always live, no cache).
    MAPBOX_CACHE_MODE: str = "replay_only"

    # Mapbox Static Images — style IDs and pin appearance
    MAPBOX_STYLE_LIGHT: str = "mapbox/light-v11"
    MAPBOX_STYLE_DARK: str = "mapbox/dark-v11"
    MAPBOX_PIN_COLOR: str = "4a7c59"
    MAPBOX_SNAPSHOT_MAX_PINS: int = 30
    MAPBOX_SNAPSHOT_CACHE_SECONDS: int = 86400
    MAPBOX_SNAPSHOT_ZOOM: int = 14

    # GCS Configuration (empty = use local storage)
    GCS_INTERNAL_BUCKET: str = ""
    GCS_SUPPLIER_BUCKET: str = ""
    GCS_CUSTOMER_BUCKET: str = ""
    GCS_EMPLOYER_BUCKET: str = ""
    GCS_SIGNED_URL_EXPIRATION_SECONDS: int = 3600
    GCS_QR_SIGNED_URL_EXPIRATION_SECONDS: int = 86400
    GCS_SIGNING_SA_EMAIL: str = ""  # Cloud Run: set to run_sa email; local: empty = default creds

    # Image pipeline: SafeSearch moderation rejection threshold.
    # One of UNKNOWN, VERY_UNLIKELY, UNLIKELY, POSSIBLE, LIKELY, VERY_LIKELY.
    # Any of adult/violence/racy at or above this level causes rejection.
    MODERATION_REJECT_LIKELIHOOD: str = "LIKELY"

    # Product image upload: max file size in bytes (default 5 MB)
    MAX_PRODUCT_IMAGE_BYTES: int = 5 * 1024 * 1024

    # Supplier invoice document upload: max file size in bytes (default 10 MB)
    MAX_INVOICE_DOCUMENT_BYTES: int = 10 * 1024 * 1024

    # Fixed institution IDs (must match seed.sql). Override via env if seed uses different UUIDs.
    VIANDA_CUSTOMERS_INSTITUTION_ID: str = "22222222-2222-2222-2222-222222222222"
    VIANDA_ENTERPRISES_INSTITUTION_ID: str = "11111111-1111-1111-1111-111111111111"

    # Archival Configuration - Days to retain records before archiving
    RETENTION_PERIODS: dict = {
        "orders": 30,  # Customer service window
        "transactions": 90,  # Financial dispute resolution
        "subscriptions": 365,  # Annual billing cycles
        "user_data": 2555,  # Legal compliance (7 years)
        "payments": 180,  # Payment processing disputes
        "restaurant_data": 90,  # Restaurant operational data
        # Financial tables (HIGH PRIORITY)
        "client_bills": 365,  # Financial records - 1 year
        "client_transactions": 90,  # Client payments - 90 days
        # Operational tables (MEDIUM PRIORITY)
        "vianda_selections": 60,  # Order history - 60 days
        "payment_methods": 365,  # Payment methods - 1 year
        "plans": 730,  # Service plans - 2 years
        "qr_codes": 180,  # QR codes - 180 days
        "products": 365,  # Product catalog - 1 year
    }

    # Grace period before archival eligibility (days)
    ARCHIVAL_GRACE_PERIOD: int = 7

    # Enable/disable automatic archival
    AUTO_ARCHIVAL_ENABLED: bool = True

    # i18n: supported API/UI locales (ISO 639-1 short codes)
    DEFAULT_LOCALE: str = "en"
    SUPPORTED_LOCALES: list[str] = ["en", "es", "pt"]

    # Open Food Facts (OFF) — real-time ingredient autocomplete
    OFF_ENABLED: bool = True  # kill switch for OFF real-time calls
    OFF_LOCAL_MIN_VERIFIED_RESULTS: int = 5  # min verified local results before calling OFF

    # Ingredient enrichment cron — image phase (Wikidata, CC licensed, permanent storage)
    WIKIDATA_ENRICHMENT_ENABLED: bool = False  # kill switch for Wikidata image cron
    ENRICHMENT_BATCH_SIZE: int = 50  # rows per cron run (shared by all enrichment phases)

    # Ingredient enrichment cron — nutrition phase (USDA FoodData Central, Phase 7)
    USDA_ENRICHMENT_ENABLED: bool = False  # kill switch for USDA nutrition cron

    # QR code HMAC signing (HMAC-SHA256 secret for signed QR code URLs)
    QR_HMAC_SECRET: str = ""

    # Pickup timer configuration (B2C app reads these from scan-qr response)
    PICKUP_COUNTDOWN_SECONDS: int = 300  # Timer duration in seconds (default 5 min)
    PICKUP_MAX_EXTENSIONS: int = 3  # Max timer extensions allowed

    # Handoff confirmation timeout (seconds after clerk marks Delivered before auto-completing)
    HANDOFF_CONFIRMATION_TIMEOUT_SECONDS: int = 300

    # Dispute auto-escalation (flags restaurants for Layer 2 code verification)
    DISPUTE_AUTO_ESCALATION_RATE: float = 0.03  # 3% dispute rate threshold
    DISPUTE_ESCALATION_MIN_ORDERS: int = 20  # Minimum orders before escalation applies
    DISPUTE_ESCALATION_LOOKBACK_DAYS: int = 30  # Rolling window for rate calculation

    # Portion complaint flag rate (size-1 + complaint, not size-1 alone)
    PORTION_COMPLAINT_FLAG_RATE: float = 0.05  # 5% triggers restaurant SLA review

    # Authenticated user rate limiting (middleware). Off by default for safe rollout.
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_MAX_TRACKED_USERS: int = 10_000  # eviction threshold for in-memory buckets
    RATE_LIMIT_EVICTION_AGE_SECONDS: int = 120  # stale bucket age before eviction

    # Firebase Cloud Messaging (push notifications)
    FIREBASE_CREDENTIALS_PATH: str = ""  # Path to Firebase service account JSON. Empty = push disabled.

    # Spoonacular — future partnership only; data served transiently, never stored
    # SPOONACULAR_API_KEY injected by GCP Secret Manager at runtime
    SPOONACULAR_ENABLED: bool = False
    SPOONACULAR_API_KEY: str = ""

    # CORS: comma-separated allowed origins. Empty = allow all (local dev convenience).
    CORS_ALLOWED_ORIGINS: str = ""
    # CORS regex: optional Python regex matched against the request Origin header.
    # Used to allow patterns the exact-match CORS_ALLOWED_ORIGINS list can't express
    # (e.g. Firebase preview channels like https://vianda-home-dev--pr-<N>-<hash>.web.app).
    # Empty = no regex matching (only the exact-match list applies).
    CORS_ALLOWED_ORIGIN_REGEX: str = ""

    # reCAPTCHA v3: bot protection for public /leads/* endpoints. Empty = disabled (local dev).
    RECAPTCHA_SECRET_KEY: str = ""
    RECAPTCHA_SCORE_THRESHOLD: float = 0.3  # Minimum score (0.0 = bot, 1.0 = human)

    # Conditional reCAPTCHA: per-endpoint thresholds and windows (0 = disabled for that endpoint)
    LOGIN_CAPTCHA_THRESHOLD: int = 5
    LOGIN_CAPTCHA_WINDOW_SECONDS: int = 900
    SIGNUP_VERIFY_CAPTCHA_THRESHOLD: int = 3
    SIGNUP_VERIFY_CAPTCHA_WINDOW_SECONDS: int = 900
    FORGOT_PASSWORD_CAPTCHA_THRESHOLD: int = 3
    FORGOT_PASSWORD_CAPTCHA_WINDOW_SECONDS: int = 900
    FORGOT_USERNAME_CAPTCHA_THRESHOLD: int = 3
    FORGOT_USERNAME_CAPTCHA_WINDOW_SECONDS: int = 900
    RESET_PASSWORD_CAPTCHA_THRESHOLD: int = 3
    RESET_PASSWORD_CAPTCHA_WINDOW_SECONDS: int = 900
    CAPTCHA_MAX_TRACKED_IPS: int = 10_000
    CAPTCHA_EVICTION_AGE_SECONDS: int = 1800

    # --- Ads Platform: Shared Infrastructure ---
    ADS_ENABLED_PLATFORMS: str = ""  # Comma-separated: "google,meta" or "" (disabled)
    ADS_DRY_RUN: bool = False  # Log payloads without uploading (all platforms)

    # --- Ads Platform: Redis / ARQ ---
    REDIS_URL: str = "redis://localhost:6379"
    ARQ_MAX_JOBS: int = 100
    ARQ_JOB_TIMEOUT: int = 300  # Seconds per job
    ARQ_MAX_RETRIES: int = 3

    # --- Ads Platform: Google Ads ---
    GOOGLE_ADS_PROVIDER: str = "mock"  # "mock" | "live"
    GOOGLE_ADS_CUSTOMER_ID: str = ""
    GOOGLE_ADS_CONVERSION_ACTION_ID: str = ""
    GOOGLE_ADS_DEVELOPER_TOKEN: str = ""  # Local dev only; prod uses Secret Manager
    GOOGLE_ADS_UPLOAD_DELAY_HOURS: int = 24

    # --- Ads Platform: Meta Ads ---
    META_ADS_PROVIDER: str = "mock"  # "mock" | "live"
    META_ADS_PIXEL_ID: str = ""
    META_ADS_AD_ACCOUNT_ID: str = ""
    META_ADS_SYSTEM_USER_TOKEN: str = ""  # Local dev only; prod uses Secret Manager
    META_ADS_APP_SECRET: str = ""  # Local dev only
    META_ADS_UPLOAD_DELAY_MINUTES: int = 5
    META_ADS_API_VERSION: str = "v25.0"

    # --- Ads Platform: Geographic Zones ---
    ZONE_MIN_RADIUS_KM: float = 1.5
    ZONE_DEFAULT_RADIUS_KM: float = 2.0
    ZONE_MIN_ESTIMATED_MAU: int = 40_000
    ZONE_BUDGET_FLOOR_SMALL_RADIUS: int = 5000  # Cents/day for radius < 2km
    ZONE_BUDGET_FLOOR_LARGE_RADIUS: int = 3000  # Cents/day for radius >= 2km
    ZONE_DBSCAN_MIN_LEADS: int = 40
    ZONE_DBSCAN_EPSILON_KM: float = 2.0
    ZONE_MAU_CACHE_TTL_HOURS: int = 24

    # --- Ads Platform: Marketing Collateral ---
    GCS_MARKETING_BUCKET: str = ""
    CREATIVE_SYNC_INTERVAL_HOURS: int = 24
    CREATIVE_CRITIQUE_MIN_IMPRESSIONS: int = 5000
    CREATIVE_AUTO_PUBLISH_MIN_SCORE: int = 7

    # --- Ads Platform: Gemini Advisor ---
    GEMINI_MODEL_ANALYSIS: str = "gemini-2.5-flash"
    GEMINI_MODEL_CREATIVE: str = "gemini-2.5-pro"
    GEMINI_ADVISOR_INTERVAL_HOURS: int = 1
    GEMINI_BUDGET_CHANGE_LIMIT_PCT: float = 0.20
    GEMINI_STRATEGY_SHIFT_LIMIT_PCT: float = 0.10


settings = Settings()

_AUTH_SENTINEL = "__UNSET_NOT_FOR_AUTH__"


def _require_auth_settings() -> None:
    """Raise RuntimeError if auth settings are still at their sentinel defaults.

    Call this at the top of every function that reads SECRET_KEY, ALGORITHM, or
    ACCESS_TOKEN_EXPIRE_MINUTES.  The guard ensures a misconfigured environment
    fails loudly with a clear message rather than silently signing tokens with a
    known-bad key or with a 0-minute expiry.

    In prod/dev/staging, Cloud Run injects real values from Secret Manager before
    any request is handled, so this guard never fires there.
    """
    if settings.SECRET_KEY == _AUTH_SENTINEL or settings.ALGORITHM == _AUTH_SENTINEL:
        raise RuntimeError(
            "SECRET_KEY and ALGORITHM must be set via environment variables before "
            "any auth operation is performed.  In Cloud Run these come from Secret "
            "Manager.  If you are running a local script that does not need auth, "
            "this import is transitive — the script is safe, but you must not call "
            "any auth function without the env vars present."
        )
    if settings.ACCESS_TOKEN_EXPIRE_MINUTES == 0:
        raise RuntimeError(
            "ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer set via "
            "environment variables before any auth operation is performed."
        )


# Common email providers that cannot be registered as employer domains
EMPLOYER_DOMAIN_BLACKLIST = {
    "gmail.com",
    "googlemail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.com",
    "yahoo.co.uk",
    "yahoo.co.jp",
    "live.com",
    "msn.com",
    "aol.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "protonmail.com",
    "proton.me",
    "mail.com",
    "zoho.com",
    "yandex.com",
    "yandex.ru",
    "tutanota.com",
    "gmx.com",
    "gmx.net",
    "fastmail.com",
    "hey.com",
}


def get_vianda_customers_institution_id() -> UUID:
    """Vianda Customers institution UUID. Customer Employer addresses and customer signup use this. Must match seed.sql."""
    return UUID(settings.VIANDA_CUSTOMERS_INSTITUTION_ID)


def get_vianda_enterprises_institution_id() -> UUID:
    """Vianda Enterprises institution UUID. Must match seed.sql."""
    return UUID(settings.VIANDA_ENTERPRISES_INSTITUTION_ID)


def get_google_api_key() -> str:
    """Return env-specific Google API key. local/dev -> DEV; staging -> STAGING; prod -> PROD."""
    env = (os.getenv("ENVIRONMENT") or "local").lower()
    if env in ("local", "dev"):
        key = settings.GOOGLE_API_KEY_DEV
    elif env == "staging":
        key = settings.GOOGLE_API_KEY_STAGING
    elif env == "prod":
        key = settings.GOOGLE_API_KEY_PROD
    else:
        key = settings.GOOGLE_API_KEY_DEV  # fallback for unknown
    return (key or "").strip()


def get_mapbox_access_token(permanent: bool = False) -> str:
    """Return env-specific Mapbox access token. local/dev -> DEV; staging -> STAGING; prod -> PROD.

    Args:
        permanent: When True, return the persistent-storage token (sk.*) for the active
            environment. The persistent token is required for callsites that write lat/lng
            to the DB — using the ephemeral token for persisted-storage data violates Mapbox
            TOS. Raises RuntimeError if the token is not configured. Defaults to False, which
            preserves the original behavior (ephemeral token).
    """
    env = (os.getenv("ENVIRONMENT") or "local").lower()
    if permanent:
        if env in ("local", "dev"):
            key = settings.MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT
        elif env == "staging":
            key = settings.MAPBOX_ACCESS_TOKEN_STAGING_PERSISTENT
        elif env == "prod":
            key = settings.MAPBOX_ACCESS_TOKEN_PROD_PERSISTENT
        else:
            key = settings.MAPBOX_ACCESS_TOKEN_DEV_PERSISTENT
        if not key or not key.strip():
            # DEV_MODE uses mock responses — no real Mapbox call is made, so the TOS
            # guardrail (persistent token required for DB writes) is a false positive.
            # Return a stub so gateway construction succeeds and mocks are served.
            # In production (DEV_MODE=False) the RuntimeError still guards the TOS rule.
            if settings.DEV_MODE:
                return "dev-mode-stub-token"
            raise RuntimeError(
                f"MAPBOX_ACCESS_TOKEN_{env.upper()}_PERSISTENT is not set. "
                "Callsites that write lat/lng to the DB must use the persistent-storage "
                "token (sk.*). Configure it in GCP Secret Manager "
                f"(vianda-{env}-mapbox-token-persistent) and expose it as the env var. "
                "Do NOT fall back to the ephemeral token — that would violate Mapbox TOS."
            )
        return key.strip()
    if env in ("local", "dev"):
        key = settings.MAPBOX_ACCESS_TOKEN_DEV
    elif env == "staging":
        key = settings.MAPBOX_ACCESS_TOKEN_STAGING
    elif env == "prod":
        key = settings.MAPBOX_ACCESS_TOKEN_PROD
    else:
        key = settings.MAPBOX_ACCESS_TOKEN_DEV
    return (key or "").strip()


def get_settings() -> Settings:
    """
    Get application settings singleton.

    Returns:
        Settings instance
    """
    return settings
