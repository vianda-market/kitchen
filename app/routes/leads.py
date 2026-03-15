"""
Leads routes (unauthenticated, rate-limited).

Used for the lead/signup flow: city metrics (and zipcode metrics) to show coverage.
City-first so coverage grows faster; zipcode refinement can be added later.
"""

import time
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
import psycopg2.extensions

from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import (
    CityMetricsResponseSchema,
    EmailRegisteredResponseSchema,
    LeadsCitiesResponseSchema,
    ZipcodeMetricsResponseSchema,
)
from app.services.city_metrics_service import (
    get_cities_with_coverage,
    get_city_metrics,
)
from app.services.zipcode_metrics_service import get_zipcode_metrics
from app.services.entity_service import get_user_by_email
from app.utils.country import normalize_country_code

router = APIRouter(prefix="/leads", tags=["Leads"])

# All lead endpoints: max 20 requests per IP per 60s; 21st request returns 429 until window expires
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW_SECONDS = 60
_rate_limit_timestamps: dict = defaultdict(list)


def _rate_limit_leads(request: Request) -> None:
    """Allow at most 20 requests per IP per 60 seconds. On 21st, 429 until window expires."""
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    # Prune old entries and evict stale keys to prevent unbounded growth
    for k, v in list(_rate_limit_timestamps.items()):
        pruned = [t for t in v if now - t < RATE_LIMIT_WINDOW_SECONDS]
        if pruned:
            _rate_limit_timestamps[k] = pruned
        else:
            del _rate_limit_timestamps[k]
    if len(_rate_limit_timestamps.get(ip, [])) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again in 60 seconds.",
        )
    _rate_limit_timestamps.setdefault(ip, []).append(now)


@router.get("/cities", response_model=LeadsCitiesResponseSchema)
async def get_leads_cities(
    request: Request,
    country_code: Optional[str] = "US",
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    List city names (from city_info) that have at least one restaurant in the given country.
    Single public API for lead flow, signup picker, and explore. No auth; rate-limited per IP.
    Use market's country_code (e.g. from GET /markets/available). Client sends selected city_name in signup.
    """
    _rate_limit_leads(request)
    country = normalize_country_code(country_code, default="US")
    cities = get_cities_with_coverage(country, db)
    return LeadsCitiesResponseSchema(cities=cities)


@router.get("/city-metrics", response_model=CityMetricsResponseSchema)
async def get_city_metrics_endpoint(
    request: Request,
    city: str,
    country_code: Optional[str] = "US",
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Return lead metrics for a city: restaurant count, has_coverage, matched_city, optional center.
    City-first so coverage grows faster at aggregate level; zipcode refinement can be added later.
    No auth; rate-limited to 20 requests per 60 seconds per IP.
    """
    _rate_limit_leads(request)
    country = normalize_country_code(country_code, default="US")
    data = get_city_metrics(city=city, country_code=country, db=db)
    return CityMetricsResponseSchema(**data)


@router.get(
    "/email-registered",
    response_model=EmailRegisteredResponseSchema,
    summary="Check if email is already registered (lead flow)",
    responses={
        200: {"description": "Returns whether the email is registered."},
        400: {"description": "Invalid or missing email."},
        429: {"description": "Rate limit exceeded."},
    },
)
async def get_email_registered(
    request: Request,
    email: Optional[str] = None,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Check if a user with the given email already exists (non-archived).
    For lead flow: after city/zipcode, frontend can route to login vs signup without asking for full form.
    No auth; rate-limited to 20 requests per 60 seconds per IP.
    """
    _rate_limit_leads(request)
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        raise HTTPException(status_code=400, detail="Valid email is required")
    user = get_user_by_email(normalized, db)
    return EmailRegisteredResponseSchema(registered=user is not None)


@router.get("/zipcode-metrics", response_model=ZipcodeMetricsResponseSchema)
async def get_zipcode_metrics_endpoint(
    request: Request,
    zip: str,
    country_code: Optional[str] = "US",
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Return lead metrics for a zipcode: restaurant count, has_coverage, matched_zipcode, optional center.
    No auth; rate-limited to 20 requests per 60 seconds per IP.
    Kept for backward compatibility; prefer city-metrics for new flows.
    """
    _rate_limit_leads(request)
    country = normalize_country_code(country_code, default="US")
    data = get_zipcode_metrics(zip_code=zip, country_code=country, db=db)
    return ZipcodeMetricsResponseSchema(**data)
