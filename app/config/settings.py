# config/settings.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    DEV_OVERRIDE_DAY: str = ""  # Override current day for testing (e.g., "Monday")
    DEV_MODE: bool = True  # Enable to bypass external API calls and use mock responses
    
    # External API Keys
    GOOGLE_MAPS_API_KEY: str = ""  # Required for geolocation services

    class Config:
        env_file = ".env"

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
        "fintech_transactions": 180, # Payment processing - 180 days
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

def get_settings() -> Settings:
    """
    Get application settings singleton.
    
    Returns:
        Settings instance
    """
    return settings
