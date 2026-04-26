"""
National Holiday Source Enumeration

Defines the valid source values for national holidays.
  - manual: created directly by an admin (via POST /national-holidays)
  - nager_date: imported from the Nager.Date provider (via /sync-from-provider cron)
"""

from enum import Enum


class NationalHolidaySource(str, Enum):
    """Valid source values for national holidays — fixed at compile time."""

    MANUAL = "manual"
    NAGER_DATE = "nager_date"
