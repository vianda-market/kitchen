# app/utils/currency.py
"""
Currency conversion utilities.
"""

import requests

from app.config.settings import settings


def convert_currency(amount_minor: int, from_currency: str, to_currency: str) -> int:
    """Convert the given amount from one currency to another."""
    api_url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
    response = requests.get(api_url)
    response.raise_for_status()
    data = response.json()
    rate = data["rates"][to_currency]
    return int(amount_minor * rate)