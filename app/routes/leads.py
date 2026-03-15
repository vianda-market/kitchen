"""
Leads routes (unauthenticated, rate-limited).

Used for the lead/signup flow: city metrics (and zipcode metrics) to show coverage.
City-first so coverage grows faster; zipcode refinement can be added later.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
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
from app.utils.rate_limit import limiter

router = APIRouter(prefix="/leads", tags=["Leads"])


@router.get("/cities", response_model=LeadsCitiesResponseSchema)
@limiter.limit("20/minute")
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
    country = normalize_country_code(country_code, default="US")
    cities = get_cities_with_coverage(country, db)
    return LeadsCitiesResponseSchema(cities=cities)


@router.get("/city-metrics", response_model=CityMetricsResponseSchema)
@limiter.limit("20/minute")
async def get_city_metrics_endpoint(
    request: Request,
    city: str,
    country_code: Optional[str] = "US",
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Return lead metrics for a city: restaurant count, has_coverage, matched_city.
    City-first so coverage grows faster at aggregate level; zipcode refinement can be added later.
    No auth; rate-limited to 20 requests per minute per IP.
    """
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
@limiter.limit("10/minute")
async def get_email_registered(
    request: Request,
    email: Optional[str] = None,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Check if a user with the given email already exists (non-archived).
    For lead flow: after city/zipcode, frontend can route to login vs signup without asking for full form.
    No auth; rate-limited to 10 requests per minute per IP (stricter for enumeration protection).
    """
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        raise HTTPException(status_code=400, detail="Valid email is required")
    user = get_user_by_email(normalized, db)
    return EmailRegisteredResponseSchema(registered=user is not None)


@router.get("/zipcode-metrics", response_model=ZipcodeMetricsResponseSchema)
@limiter.limit("20/minute")
async def get_zipcode_metrics_endpoint(
    request: Request,
    zip: str,
    country_code: Optional[str] = "US",
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Return lead metrics for a zipcode: restaurant count, has_coverage, matched_zipcode.
    No auth; rate-limited to 20 requests per minute per IP.
    Kept for backward compatibility; prefer city-metrics for new flows.
    """
    country = normalize_country_code(country_code, default="US")
    data = get_zipcode_metrics(zip_code=zip, country_code=country, db=db)
    return ZipcodeMetricsResponseSchema(**data)
