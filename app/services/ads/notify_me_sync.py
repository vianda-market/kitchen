# app/services/ads/notify_me_sync.py
"""
Notify-me lead aggregation for ad zones.

Queries lead_interest records and aggregates them per zone for:
1. Zone metrics (notify_me_lead_count)
2. Custom Audience export (hashed email lists for Meta/Google upload)

Current limitation: lead_interest has city_name + zipcode but no lat/lon.
Matching is by city_name + country_code. Once leads are geocoded (future),
this can use radius-based matching like restaurant/subscriber counts.
"""
import logging
from uuid import UUID

import psycopg2.extensions

from app.services.ads.pii_hasher import normalize_and_hash
from app.utils.db import db_read

logger = logging.getLogger(__name__)


def count_notify_me_leads_for_zone(
    country_code: str,
    city_name: str,
    db: psycopg2.extensions.connection,
) -> int:
    """
    Count active notify-me leads matching a zone's city + country.

    This is a city-level approximation. When lead_interest gets
    lat/lon (via geocoding), this should switch to radius matching.
    """
    row = db_read(
        """
        SELECT COUNT(*) AS cnt
        FROM core.lead_interest
        WHERE country_code = %s
          AND LOWER(city_name) = LOWER(%s)
          AND status = 'active'
          AND is_archived = FALSE
        """,
        (country_code, city_name),
        connection=db,
        fetch_one=True,
    )
    return row["cnt"] if row else 0


def get_notify_me_emails_for_zone(
    country_code: str,
    city_name: str,
    db: psycopg2.extensions.connection,
) -> list[str]:
    """
    Get active notify-me lead emails for a zone (for Custom Audience upload).

    Returns raw emails. Caller must hash before upload.
    """
    rows = db_read(
        """
        SELECT DISTINCT email
        FROM core.lead_interest
        WHERE country_code = %s
          AND LOWER(city_name) = LOWER(%s)
          AND status = 'active'
          AND is_archived = FALSE
        """,
        (country_code, city_name),
        connection=db,
    )
    return [r["email"] for r in rows] if rows else []


def export_hashed_audience_for_zone(
    country_code: str,
    city_name: str,
    db: psycopg2.extensions.connection,
) -> list[dict]:
    """
    Export hashed email list for Custom Audience upload.

    Returns list of dicts with hashed_email (and hashed_phone if available).
    Format compatible with both Meta Custom Audience and Google Customer Match.
    """
    rows = db_read(
        """
        SELECT DISTINCT email
        FROM core.lead_interest
        WHERE country_code = %s
          AND LOWER(city_name) = LOWER(%s)
          AND status = 'active'
          AND is_archived = FALSE
        """,
        (country_code, city_name),
        connection=db,
    )
    if not rows:
        return []

    return [{"hashed_email": normalize_and_hash(r["email"])} for r in rows]
