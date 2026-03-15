# config/settings.py
import os
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
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
    # B2C app base URL (e.g. http://localhost:8081). Used for password reset, signup verification, etc.
    FRONTEND_URL: str = ""

    # Payment provider: "mock" (Stripe mock for dev) or "stripe" (live Stripe). Default mock for dev.
    PAYMENT_PROVIDER: str = "mock"
    # Supplier (institution) payout: "mock" or "stripe". Used after settlement → bill for restaurant payouts.
    SUPPLIER_PAYOUT_PROVIDER: str = "mock"

    # Stripe (required when PAYMENT_PROVIDER=stripe; use test keys sk_test_/pk_test_ for sandbox)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""  # Optional; for client-side Stripe Elements

    # Google API Keys per environment (read from .env only - never commit)
    # local and dev use GOOGLE_API_KEY_DEV; staging uses _STAGING; prod uses _PROD
    GOOGLE_API_KEY_DEV: str = ""
    GOOGLE_API_KEY_STAGING: str = ""
    GOOGLE_API_KEY_PROD: str = ""

    # Fixed institution IDs (must match seed.sql). Override via env if seed uses different UUIDs.
    VIANDA_CUSTOMERS_INSTITUTION_ID: str = "22222222-2222-2222-2222-222222222222"
    VIANDA_ENTERPRISES_INSTITUTION_ID: str = "11111111-1111-1111-1111-111111111111"

    # Archival Configuration - Days to retain records before archiving
    RETENTION_PERIODS: dict = {
        "orders": 30,              # Customer service window
        "transactions": 90,        # Financial dispute resolution
        "subscriptions": 365,      # Annual billing cycles
        "user_data": 2555,         # Legal compliance (7 years)
        "payments": 180,           # Payment processing disputes
        "restaurant_data": 90,     # Restaurant operational data
        # Financial tables (HIGH PRIORITY)
        "client_bills": 365,       # Financial records - 1 year
        "client_transactions": 90, # Client payments - 90 days
        # Operational tables (MEDIUM PRIORITY)
        "plate_selections": 60,    # Order history - 60 days
        "payment_methods": 365,    # Payment methods - 1 year
        "plans": 730,             # Service plans - 2 years
        "qr_codes": 180,          # QR codes - 180 days
        "products": 365,          # Product catalog - 1 year
    }

    # Grace period before archival eligibility (days)
    ARCHIVAL_GRACE_PERIOD: int = 7

    # Enable/disable automatic archival
    AUTO_ARCHIVAL_ENABLED: bool = True

settings = Settings()


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


def get_settings() -> Settings:
    """
    Get application settings singleton.
    
    Returns:
        Settings instance
    """
    return settings
