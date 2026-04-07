# app/config/market_config.py
from typing import Dict, Any, Optional, List
from datetime import time, datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field

# Address display: order of street components by market (USA: number, name, type; AR/PE: type, name, number)
DEFAULT_ADDRESS_STREET_ORDER = ["street_name", "building_number", "street_type"]

class MarketKitchenConfig(BaseModel):
    """Configuration for kitchen operations in a specific market"""
    
    # Market identification
    market_id: str = Field(..., description="Unique market identifier")
    market_name: str = Field(..., description="Human readable market name")
    country_code: str = Field(..., description="ISO country code (AR, PE, etc.)")
    timezone: str = Field(..., description="IANA timezone (America/Argentina/Buenos_Aires)")
    
    # Address display: order of street components for format_street_display
    address_street_order: List[str] = Field(
        default_factory=lambda: list(DEFAULT_ADDRESS_STREET_ORDER),
        description="Order of street_type, street_name, building_number for address display"
    )
    
    # Kitchen day configuration (in LOCAL time)
    kitchen_day_config: Dict[str, Dict[str, Any]] = Field(..., description="Kitchen day settings")
    
    # Business hours (in LOCAL time)
    business_hours: Dict[str, Dict[str, time]] = Field(..., description="Business hours per day")
    
    # Billing and reservation timing (in LOCAL time)
    billing_delay_minutes: int = Field(..., description="Minutes after kitchen close to run billing")
    reservation_opens_delay_minutes: int = Field(..., description="Minutes after kitchen close to open reservations")
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

class MarketConfiguration:
    """Centralized market configuration management"""
    
    # Market configurations
    MARKETS = {
        "AR": MarketKitchenConfig(
            market_id="AR",
            market_name="Argentina",
            country_code="AR",
            timezone="America/Argentina/Buenos_Aires",
            address_street_order=["street_type", "street_name", "building_number"],
            kitchen_day_config={
                "Monday": {
                    "kitchen_close": time(13, 30),      # 1:30 PM local (order cutoff)
                    "billing_run": time(15, 0),         # 3:00 PM local (90 min after kitchen close)
                    "reservations_open": time(16, 0),   # 4:00 PM local (2.5h after kitchen close)
                    "enabled": True
                },
                "Tuesday": {
                    "kitchen_close": time(13, 30),      # 1:30 PM local (order cutoff)
                    "billing_run": time(15, 0),         # 3:00 PM local (90 min after kitchen close)
                    "reservations_open": time(16, 0),   # 4:00 PM local (2.5h after kitchen close)
                    "enabled": True
                },
                "Wednesday": {
                    "kitchen_close": time(13, 30),      # 1:30 PM local (order cutoff)
                    "billing_run": time(15, 0),         # 3:00 PM local (90 min after kitchen close)
                    "reservations_open": time(16, 0),   # 4:00 PM local (2.5h after kitchen close)
                    "enabled": True
                },
                "Thursday": {
                    "kitchen_close": time(13, 30),      # 1:30 PM local (order cutoff)
                    "billing_run": time(15, 0),         # 3:00 PM local (90 min after kitchen close)
                    "reservations_open": time(16, 0),   # 4:00 PM local (2.5h after kitchen close)
                    "enabled": True
                },
                "Friday": {
                    "kitchen_close": time(13, 30),      # 1:30 PM local (order cutoff)
                    "billing_run": time(15, 0),         # 3:00 PM local (90 min after kitchen close)
                    "reservations_open": time(16, 0),   # 4:00 PM local (2.5h after kitchen close)
                    "enabled": True
                }
            },
            business_hours={
                "Monday": {"open": time(11, 30), "close": time(13, 30)},
                "Tuesday": {"open": time(11, 30), "close": time(13, 30)},
                "Wednesday": {"open": time(11, 30), "close": time(13, 30)},
                "Thursday": {"open": time(11, 30), "close": time(13, 30)},
                "Friday": {"open": time(11, 30), "close": time(13, 30)}
            },
            billing_delay_minutes=90,      # 1.5 hours after kitchen close
            reservation_opens_delay_minutes=150  # 2.5 hours after kitchen close
        ),
        "PE": MarketKitchenConfig(
            market_id="PE",
            market_name="Peru",
            country_code="PE",
            timezone="America/Lima",
            address_street_order=["street_type", "street_name", "building_number"],
            kitchen_day_config={
                "Monday": {
                    "kitchen_close": time(13, 30),      # 1:30 PM local (order cutoff)
                    "billing_run": time(15, 0),         # 3:00 PM local (90 min after kitchen close)
                    "reservations_open": time(16, 0),   # 4:00 PM local (2.5h after kitchen close)
                    "enabled": True
                },
                "Tuesday": {
                    "kitchen_close": time(13, 30),      # 1:30 PM local (order cutoff)
                    "billing_run": time(15, 0),         # 3:00 PM local (90 min after kitchen close)
                    "reservations_open": time(16, 0),   # 4:00 PM local (2.5h after kitchen close)
                    "enabled": True
                },
                "Wednesday": {
                    "kitchen_close": time(13, 30),      # 1:30 PM local (order cutoff)
                    "billing_run": time(15, 0),         # 3:00 PM local (90 min after kitchen close)
                    "reservations_open": time(16, 0),   # 4:00 PM local (2.5h after kitchen close)
                    "enabled": True
                },
                "Thursday": {
                    "kitchen_close": time(13, 30),      # 1:30 PM local (order cutoff)
                    "billing_run": time(15, 0),         # 3:00 PM local (90 min after kitchen close)
                    "reservations_open": time(16, 0),   # 4:00 PM local (2.5h after kitchen close)
                    "enabled": True
                },
                "Friday": {
                    "kitchen_close": time(13, 30),      # 1:30 PM local (order cutoff)
                    "billing_run": time(15, 0),         # 3:00 PM local (90 min after kitchen close)
                    "reservations_open": time(16, 0),   # 4:00 PM local (2.5h after kitchen close)
                    "enabled": True
                }
            },
            business_hours={
                "Monday": {"open": time(11, 30), "close": time(13, 30)},
                "Tuesday": {"open": time(11, 30), "close": time(13, 30)},
                "Wednesday": {"open": time(11, 30), "close": time(13, 30)},
                "Thursday": {"open": time(11, 30), "close": time(13, 30)},
                "Friday": {"open": time(11, 30), "close": time(13, 30)}
            },
            billing_delay_minutes=90,      # 1.5 hours after kitchen close
            reservation_opens_delay_minutes=150  # 2.5 hours after kitchen close
        ),
        "US": MarketKitchenConfig(
            market_id="US",
            market_name="United States",
            country_code="US",
            timezone="America/New_York",
            address_street_order=["building_number", "street_name", "street_type"],
            kitchen_day_config={
                "Monday": {
                    "kitchen_close": time(13, 30),
                    "billing_run": time(15, 0),
                    "reservations_open": time(16, 0),
                    "enabled": True
                },
                "Tuesday": {
                    "kitchen_close": time(13, 30),
                    "billing_run": time(15, 0),
                    "reservations_open": time(16, 0),
                    "enabled": True
                },
                "Wednesday": {
                    "kitchen_close": time(13, 30),
                    "billing_run": time(15, 0),
                    "reservations_open": time(16, 0),
                    "enabled": True
                },
                "Thursday": {
                    "kitchen_close": time(13, 30),
                    "billing_run": time(15, 0),
                    "reservations_open": time(16, 0),
                    "enabled": True
                },
                "Friday": {
                    "kitchen_close": time(13, 30),
                    "billing_run": time(15, 0),
                    "reservations_open": time(16, 0),
                    "enabled": True
                }
            },
            business_hours={
                "Monday": {"open": time(11, 30), "close": time(13, 30)},
                "Tuesday": {"open": time(11, 30), "close": time(13, 30)},
                "Wednesday": {"open": time(11, 30), "close": time(13, 30)},
                "Thursday": {"open": time(11, 30), "close": time(13, 30)},
                "Friday": {"open": time(11, 30), "close": time(13, 30)}
            },
            billing_delay_minutes=90,
            reservation_opens_delay_minutes=150
        )
    }
    
    @classmethod
    def get_market_config(cls, country_code: str) -> Optional[MarketKitchenConfig]:
        """Get market configuration for a specific country"""
        return cls.MARKETS.get(country_code.upper())
    
    @classmethod
    def get_all_markets(cls) -> Dict[str, MarketKitchenConfig]:
        """Get all market configurations"""
        return cls.MARKETS.copy()
    
    @classmethod
    def get_market_timezone(cls, country_code: str) -> Optional[str]:
        """Get timezone for a specific market"""
        config = cls.get_market_config(country_code)
        return config.timezone if config else None
    
    @classmethod
    def convert_local_to_utc(cls, country_code: str, local_time: time, target_date: datetime) -> datetime:
        """Convert local time to UTC for a specific market and date"""
        config = cls.get_market_config(country_code)
        if not config:
            raise ValueError(f"Market configuration not found for country: {country_code}")
        
        # Create datetime in local timezone
        local_dt = datetime.combine(target_date.date(), local_time)
        local_tz = ZoneInfo(config.timezone)
        local_dt = local_dt.replace(tzinfo=local_tz)
        
        # Convert to UTC
        utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
        return utc_dt
    
    @classmethod
    def convert_utc_to_local(cls, country_code: str, utc_time: datetime) -> datetime:
        """Convert UTC time to local time for a specific market"""
        config = cls.get_market_config(country_code)
        if not config:
            raise ValueError(f"Market configuration not found for country: {country_code}")
        
        # Convert UTC to local timezone
        local_tz = ZoneInfo(config.timezone)
        local_dt = utc_time.astimezone(local_tz)
        return local_dt
    
    @classmethod
    def get_kitchen_close_utc(cls, country_code: str, target_date: datetime, day_name: str) -> Optional[datetime]:
        """Get kitchen close time in UTC for a specific market and day"""
        config = cls.get_market_config(country_code)
        if not config:
            return None
        
        day_config = config.kitchen_day_config.get(day_name)
        if not day_config or not day_config.get("enabled", True):
            return None
        
        kitchen_close_local = day_config["kitchen_close"]
        return cls.convert_local_to_utc(country_code, kitchen_close_local, target_date)
    
    @classmethod
    def get_billing_run_utc(cls, country_code: str, target_date: datetime, day_name: str) -> Optional[datetime]:
        """Get billing run time in UTC for a specific market and day"""
        config = cls.get_market_config(country_code)
        if not config:
            return None
        
        day_config = config.kitchen_day_config.get(day_name)
        if not day_config or not day_config.get("enabled", True):
            return None
        
        billing_run_local = day_config["billing_run"]
        return cls.convert_local_to_utc(country_code, billing_run_local, target_date)

    @classmethod
    def get_billing_run_utc_for_timezone(
        cls, market: str, timezone_str: str, target_date: datetime, day_name: str
    ) -> Optional[datetime]:
        """Get billing run time in UTC using a specific timezone (for location-based billing, e.g. US-Pacific)."""
        config = cls.get_market_config(market)
        if not config:
            return None
        day_config = config.kitchen_day_config.get(day_name)
        if not day_config or not day_config.get("enabled", True):
            return None
        billing_run_local = day_config["billing_run"]
        d = target_date.date() if isinstance(target_date, datetime) else target_date
        local_dt = datetime.combine(d, billing_run_local)
        local_tz = ZoneInfo(timezone_str)
        local_dt = local_dt.replace(tzinfo=local_tz)
        return local_dt.astimezone(ZoneInfo("UTC"))
    
    @classmethod
    def get_reservation_opens_utc(cls, country_code: str, target_date: datetime, day_name: str) -> Optional[datetime]:
        """Get reservation opening time in UTC for a specific market and day"""
        config = cls.get_market_config(country_code)
        if not config:
            return None
        
        day_config = config.kitchen_day_config.get(day_name)
        if not day_config or not day_config.get("enabled", True):
            return None
        
        reservation_opens_local = day_config["reservations_open"]
        return cls.convert_local_to_utc(country_code, reservation_opens_local, target_date)
    
    @classmethod
    def is_kitchen_day_enabled(cls, country_code: str, day_name: str) -> bool:
        """Check if kitchen day is enabled for a specific market"""
        config = cls.get_market_config(country_code)
        if not config:
            return False
        
        day_config = config.kitchen_day_config.get(day_name)
        return day_config.get("enabled", False) if day_config else False 