"""
Leads routes (unauthenticated, rate-limited).

Used for the lead/signup flow: city metrics (and zipcode metrics) to show coverage.
City-first so coverage grows faster; zipcode refinement can be added later.
"""

import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
import psycopg2.extensions

from app.config import Status
from app.config.settings import settings
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import (
    CityMetricsResponseSchema,
    EmailRegisteredResponseSchema,
    EmployeeCountRangeSchema,
    LeadInterestCreateSchema,
    LeadInterestResponseSchema,
    LeadsCitiesResponseSchema,
    LeadsCuisineSchema,
    LeadsFeaturedRestaurantSchema,
    LeadsPlanSchema,
    LeadsRestaurantSchema,
    MarketPublicMinimalSchema,
    ZipcodeMetricsResponseSchema,
)
from app.services.city_metrics_service import (
    get_cities_with_coverage,
    get_city_metrics,
)
from app.services.zipcode_metrics_service import get_zipcode_metrics
from app.services.leads_public_service import (
    get_public_restaurants,
    get_public_plans,
    create_lead_interest,
    get_leads_cuisines,
    get_employee_count_ranges,
)
from app.services.entity_service import get_user_by_email
from app.services.market_service import market_service, is_global_market, get_markets_with_coverage
from app.i18n.locale_names import localize_country_name, resolve_i18n_field, resolve_i18n_list_field, resolve_i18n_field_dict
from app.utils.country import normalize_country_code
from app.utils.db import db_read
from app.utils.locale import resolve_locale_from_header
from app.utils.rate_limit import limiter
from app.auth.recaptcha import verify_recaptcha

router = APIRouter(prefix="/leads", tags=["Leads"], dependencies=[Depends(verify_recaptcha)])

# -----------------------------------------------------------------------------
# Public markets (no auth): rate limit and cache — country_code + country_name only
# -----------------------------------------------------------------------------
_markets_cache: dict[str, tuple[List[dict], float]] = {}  # key -> (data, expiry)
CACHE_TTL_SECONDS = 600  # 10 minutes


def _get_cached_markets(audience: str, db) -> List[MarketPublicMinimalSchema]:
    """Return cached markets for the given audience. Two cache entries: 'customer' and 'supplier'."""
    global _markets_cache
    now = time.time()
    entry = _markets_cache.get(audience)
    if entry and now < entry[1]:
        return [MarketPublicMinimalSchema(**m) for m in entry[0]]

    if audience == "supplier":
        raw = market_service.get_all(include_archived=False, status=Status.ACTIVE)
        slim = [
            {
                "country_code": m["country_code"],
                "country_name": m["country_name"],
                "language": m.get("language") or "en",
                "phone_dial_code": m.get("phone_dial_code"),
                "phone_local_digits": m.get("phone_local_digits"),
            }
            for m in raw
            if not is_global_market(m.get("market_id"))
        ]
    else:
        slim = [
            {
                "country_code": m["country_code"],
                "country_name": m["country_name"],
                "language": m.get("language") or "en",
                "phone_dial_code": m.get("phone_dial_code"),
                "phone_local_digits": m.get("phone_local_digits"),
            }
            for m in get_markets_with_coverage(db)
        ]

    if slim:
        _markets_cache[audience] = (slim, now + CACHE_TTL_SECONDS)
    return [MarketPublicMinimalSchema(**m) for m in slim]


@router.get("/markets", response_model=List[MarketPublicMinimalSchema])
@limiter.limit("60/minute")
async def list_leads_markets(
    request: Request,
    language: str = Query(
        None,
        description="Locale for display names (en, es, pt). Falls back to Accept-Language header, then 'en'.",
    ),
    audience: str = Query(
        None,
        description="Optional. Pass 'supplier' to get all active markets (for interest forms). Default returns only markets with plate coverage.",
    ),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Public (no auth) list of active markets for UI dropdown.

    Default (no param): only markets with active plate coverage — for B2C app + customer flows.
    ?audience=supplier: all active non-global markets — for supplier/employer interest forms.

    Pass `?language=es` or send `Accept-Language: es` to get localized country names.
    For authenticated flows that need market_id, use GET /api/v1/markets/enriched/.
    """
    effective_audience = "supplier" if audience == "supplier" else "customer"
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise HTTPException(status_code=422, detail=f"Unsupported language '{locale}'.")
    markets = _get_cached_markets(effective_audience, db)
    if locale == "en":
        return markets
    return [
        m.model_copy(update={"country_name": localize_country_name(m.country_code, locale)})
        for m in markets
    ]


@router.get("/featured-restaurant", response_model=LeadsFeaturedRestaurantSchema)
@limiter.limit("60/minute")
async def get_featured_restaurant(
    request: Request,
    language: str = Query(
        None,
        description="Locale for display names (en, es, pt). Falls back to Accept-Language header.",
    ),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Public (no auth) featured restaurant for marketing site spotlight.

    Returns a single curated restaurant with localized tagline, spotlight label, and member perks.
    Returns 404 if no restaurant is currently featured.
    """
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise HTTPException(status_code=422, detail=f"Unsupported language '{locale}'.")
    row = db_read(
        """
        SELECT r.restaurant_id, r.name,
               COALESCE(cu.cuisine_name_i18n->>%s, cu.cuisine_name) AS cuisine_name,
               COALESCE(r.tagline_i18n->>%s, r.tagline) AS tagline,
               r.average_rating, r.review_count, r.cover_image_url,
               COALESCE(r.spotlight_label_i18n->>%s, r.spotlight_label) AS spotlight_label,
               r.verified_badge, r.member_perks, r.member_perks_i18n
        FROM restaurant_info r
        LEFT JOIN cuisine cu ON r.cuisine_id = cu.cuisine_id
        WHERE r.is_featured = TRUE AND r.is_archived = FALSE AND r.status = 'Active'
        LIMIT 1
        """,
        (locale, locale, locale),
        connection=db,
        fetch_one=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="No featured restaurant available")
    result = dict(row)
    # Resolve member_perks from i18n if non-English
    if locale != "en":
        i18n = result.get("member_perks_i18n") or {}
        if locale in i18n:
            result["member_perks"] = i18n[locale]
    result.pop("member_perks_i18n", None)
    return LeadsFeaturedRestaurantSchema(**result)


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
    Use market's country_code (e.g. from GET /api/v1/leads/markets). Client sends selected city_name in signup.
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


@router.get("/restaurants", response_model=List[LeadsRestaurantSchema])
@limiter.limit("60/minute")
async def list_leads_restaurants(
    request: Request,
    language: str = Query(
        None,
        description="Locale for display names (en, es, pt). Falls back to Accept-Language header.",
    ),
    featured: bool = Query(False, description="Filter to featured restaurants only"),
    limit: int = Query(12, ge=1, le=50, description="Max results (1-50, default 12)"),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Public (no auth) list of restaurants for marketing site.

    Limited projection of restaurant_info: name, cuisine, tagline, rating, cover image.
    Pass `?featured=true` to get only featured restaurants. Rate-limited per IP.
    """
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise HTTPException(status_code=422, detail=f"Unsupported language '{locale}'.")
    rows = get_public_restaurants(locale, db, featured_only=featured, limit=limit)
    return [LeadsRestaurantSchema(**r) for r in rows]


@router.get("/plans", response_model=List[LeadsPlanSchema])
@limiter.limit("60/minute")
async def list_leads_plans(
    request: Request,
    language: str = Query(
        None,
        description="Locale for display names (en, es, pt). Falls back to Accept-Language header.",
    ),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Public (no auth) pricing table for marketing site.

    Limited projection of plan_info with currency. All prices are monthly.
    Excludes Global Marketplace plans. Rate-limited per IP.
    """
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise HTTPException(status_code=422, detail=f"Unsupported language '{locale}'.")
    rows = get_public_plans(locale, db)
    return [LeadsPlanSchema(**r) for r in rows]


@router.get("/cuisines", response_model=List[LeadsCuisineSchema])
@limiter.limit("60/minute")
async def list_leads_cuisines(
    request: Request,
    language: str = Query(
        None,
        description="Locale for cuisine names (en, es, pt). Falls back to Accept-Language header.",
    ),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Public (no auth) cuisine list for interest form dropdowns.

    Same cuisines as the authenticated endpoint, limited to id + localized name.
    """
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise HTTPException(status_code=422, detail=f"Unsupported language '{locale}'.")
    rows = get_leads_cuisines(locale, db)
    return [LeadsCuisineSchema(**r) for r in rows]


@router.get("/employee-count-ranges", response_model=List[EmployeeCountRangeSchema])
@limiter.limit("60/minute")
async def list_employee_count_ranges(
    request: Request,
    language: str = Query(
        None,
        description="Locale for labels (en, es, pt). Falls back to Accept-Language header.",
    ),
):
    """
    Public (no auth) predefined company size ranges for employer interest form.

    Static data — no DB query. Labels localized per language.
    """
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise HTTPException(status_code=422, detail=f"Unsupported language '{locale}'.")
    ranges = get_employee_count_ranges(locale)
    return [EmployeeCountRangeSchema(**r) for r in ranges]


@router.post("/interest", response_model=LeadInterestResponseSchema, status_code=201)
@limiter.limit("5/minute")
async def submit_lead_interest(
    request: Request,
    data: LeadInterestCreateSchema,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Public (no auth) interest capture — "notify me" requests.

    Supports three interest types: customer (coverage alerts), employer (benefits program),
    supplier (join as restaurant). Source determined from x-client-type header.
    Rate-limited to 5 requests per minute per IP.
    """
    client_type = request.headers.get("x-client-type", "").strip().lower()
    source = "b2c_app" if client_type == "b2c-mobile" else "marketing_site"

    row = create_lead_interest(data.model_dump(), source, db)
    if not row:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid interest_type '{data.interest_type}'. Must be: customer, employer, or supplier.",
        )
    return LeadInterestResponseSchema(**row)
