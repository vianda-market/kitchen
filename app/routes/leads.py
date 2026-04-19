"""
Leads routes (unauthenticated, rate-limited).

Used for the lead/signup flow: city metrics (and zipcode metrics) to show coverage.
City-first so coverage grows faster; zipcode refinement can be added later.
"""

import hashlib
import time

import psycopg2.extensions
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response

from app.auth.recaptcha import verify_recaptcha
from app.config import Status
from app.config.settings import settings
from app.dependencies.database import get_db
from app.i18n.locale_names import (
    localize_country_name,
)
from app.schemas.consolidated_schemas import (
    CityMetricsResponseSchema,
    EmailRegisteredResponseSchema,
    EmployeeCountRangeSchema,
    LeadInterestCreateSchema,
    LeadInterestResponseSchema,
    LeadsCitiesResponseSchema,
    LeadsCountrySchema,
    LeadsCuisineSchema,
    LeadsFeaturedRestaurantSchema,
    LeadsPlanSchema,
    LeadsRestaurantSchema,
    MarketPublicMinimalSchema,
    RestaurantLeadCreateSchema,
    RestaurantLeadResponseSchema,
    ZipcodeMetricsResponseSchema,
)
from app.services.city_metrics_service import (
    get_cities_with_coverage,
    get_city_metrics,
)
from app.services.entity_service import get_user_by_email
from app.services.leads_public_service import (
    create_lead_interest,
    create_restaurant_lead,
    get_employee_count_ranges,
    get_leads_cuisines,
    get_public_countries,
    get_public_plans,
    get_public_restaurants,
    get_public_supplier_countries,
)
from app.services.market_service import get_markets_with_coverage, is_global_market, market_service
from app.services.zipcode_metrics_service import get_zipcode_metrics
from app.utils.country import normalize_country_code
from app.utils.db import db_read
from app.utils.locale import resolve_locale_from_header
from app.utils.rate_limit import limiter

router = APIRouter(prefix="/leads", tags=["Leads"], dependencies=[Depends(verify_recaptcha)])

# Sibling router at the same /leads prefix *without* reCAPTCHA. Hosts the two country-list
# endpoints that the marketing navbar loads on every page render — they cannot sit behind a
# challenge. All other leads routes keep the router-level Depends(verify_recaptcha).
public_router = APIRouter(prefix="/leads", tags=["Leads"])


def _require_country_code(country_code: str | None) -> str:
    """Normalize + validate the required country_code query param.

    Missing/empty → 400 (business-rule violation). Downstream endpoints treat
    "valid but unsupported country" as an empty response, 200, cacheable.
    """
    normalized = normalize_country_code(country_code, default=None) if country_code else None
    if not normalized:
        raise HTTPException(status_code=400, detail="country_code is required")
    return normalized


def _compute_countries_etag(rows: list[dict], locale: str) -> str:
    """ETag over response-field values + per-row market/currency modified_date + locale.

    Option (c) from the plan: no cross-table triggers, no materialization — the hash
    input is explicit and lives entirely at the query/response boundary.
    """
    h = hashlib.sha256()
    h.update(locale.encode("utf-8"))
    for r in rows:
        parts = [
            r.get("code") or "",
            r.get("currency") or "",
            r.get("phone_prefix") or "",
            r.get("default_locale") or "",
            str(r.get("market_modified_date") or ""),
            str(r.get("currency_modified_date") or ""),
        ]
        h.update("\x1f".join(parts).encode("utf-8"))
        h.update(b"\x1e")
    return f'"{h.hexdigest()[:32]}"'


def _to_country_payload(rows: list[dict], locale: str) -> list[dict]:
    """Localize country names and drop ETag-only fields before serialization."""
    return [
        {
            "code": r["code"],
            "name": localize_country_name(r["code"], locale),
            "currency": r["currency"],
            "phone_prefix": r.get("phone_prefix"),
            "default_locale": r["default_locale"],
        }
        for r in rows
    ]


# Locale-keyed process-local caches for the two public country endpoints.
# TTL mirrors _markets_cache / _cities_cache. Per-worker visibility — documented
# in the API doc. Admin status flips reach all workers within TTL + 24h browser
# cache, which is acceptable at the change frequency of this data.
_COUNTRIES_CACHE_TTL_SECONDS = 600  # 10 minutes
_countries_cache: dict[str, tuple[list[dict], str, float]] = {}  # locale -> (rows, etag, expiry)
_supplier_countries_cache: dict[str, tuple[list[dict], str, float]] = {}

# -----------------------------------------------------------------------------
# Public markets (no auth): rate limit and cache — country_code + country_name only
# -----------------------------------------------------------------------------
_markets_cache: dict[str, tuple[list[dict], float]] = {}  # key -> (data, expiry)
CACHE_TTL_SECONDS = 600  # 10 minutes


def _get_cached_markets(audience: str, db) -> list[MarketPublicMinimalSchema]:
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


@router.get("/markets", response_model=list[MarketPublicMinimalSchema])
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
    return [m.model_copy(update={"country_name": localize_country_name(m.country_code, locale)}) for m in markets]


@router.get("/featured-restaurant", response_model=LeadsFeaturedRestaurantSchema | None)
@limiter.limit("60/minute")
async def get_featured_restaurant(
    request: Request,
    language: str = Query(
        None,
        description="Locale for display names (en, es, pt). Falls back to Accept-Language header.",
    ),
    country_code: str | None = Query(
        None,
        description="Required ISO 3166-1 alpha-2 country code. Missing/empty → 400.",
    ),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Public (no auth) featured restaurant for marketing site spotlight, scoped to a country.

    Returns a single curated restaurant with localized tagline, spotlight label, and member perks.
    **Returns JSON `null` (HTTP 200) when no featured restaurant exists for the requested country**
    (either unsupported country or supported country with no match). The legacy 404 behavior has
    been retired — callers must handle a null body.
    """
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise HTTPException(status_code=422, detail=f"Unsupported language '{locale}'.")
    country = _require_country_code(country_code)
    row = db_read(
        """
        SELECT r.restaurant_id, r.name,
               COALESCE(cu.cuisine_name_i18n->>%s, cu.cuisine_name) AS cuisine_name,
               COALESCE(r.tagline_i18n->>%s, r.tagline) AS tagline,
               r.average_rating, r.review_count, r.cover_image_url,
               COALESCE(r.spotlight_label_i18n->>%s, r.spotlight_label) AS spotlight_label,
               r.verified_badge, r.member_perks, r.member_perks_i18n
        FROM ops.restaurant_info r
        LEFT JOIN ops.cuisine cu ON r.cuisine_id = cu.cuisine_id
        JOIN core.institution_info i ON i.institution_id = r.institution_id
        JOIN core.institution_market im ON im.institution_id = i.institution_id
        JOIN core.market_info m ON m.market_id = im.market_id
        WHERE r.is_featured = TRUE AND r.is_archived = FALSE AND r.status = 'active'
          AND m.country_code = %s AND m.status = 'active' AND m.is_archived = FALSE
        LIMIT 1
        """,
        (locale, locale, locale, country),
        connection=db,
        fetch_one=True,
    )
    if not row:
        return None
    result = dict(row)
    # Resolve member_perks from i18n if non-English
    if locale != "en":
        i18n = result.get("member_perks_i18n") or {}
        if locale in i18n:
            result["member_perks"] = i18n[locale]
    result.pop("member_perks_i18n", None)
    return LeadsFeaturedRestaurantSchema(**result)


# Cities cache — keyed by (country, audience), 600s TTL (same pattern as _markets_cache)
_cities_cache: dict[str, tuple[list[str], float]] = {}
CITIES_CACHE_TTL_SECONDS = 600  # 10 minutes


def _get_cached_cities(country: str, audience: str, db) -> list[str]:
    """Return cached city list for the (country, audience) pair."""
    global _cities_cache
    now = time.time()
    key = f"{country}:{audience}"
    entry = _cities_cache.get(key)
    if entry and now < entry[1]:
        return entry[0]

    if audience == "supplier":
        from app.services.city_metrics_service import get_supplier_cities_for_country

        cities = get_supplier_cities_for_country(country, db)
    else:
        cities = get_cities_with_coverage(country, db)

    if cities is not None:
        _cities_cache[key] = (cities, now + CITIES_CACHE_TTL_SECONDS)
    return cities or []


@router.get("/cities", response_model=LeadsCitiesResponseSchema)
@limiter.limit("20/minute")
async def get_leads_cities(
    request: Request,
    response: Response,
    country_code: str | None = "US",
    audience: str = Query(
        None,
        description=(
            "Optional. Pass 'supplier' for the broader lead-capture dropdown (includes all "
            "cities in markets that accept supplier interest, from GeoNames + curated + crowd-sourced). "
            "Default returns only served cities (active restaurants with plates + QR)."
        ),
    ),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    List city names for lead forms. No auth; rate-limited per IP.

    Default (no audience): cities with ≥1 active restaurant with plate_kitchen_days + QR.
    ?audience=supplier: all cities in supplier-audience countries (GeoNames ∪ city_metadata ∪ restaurant_lead).

    Client sends selected city_name in the lead/signup form body.
    """
    country = normalize_country_code(country_code, default="US")
    effective_audience = "supplier" if audience == "supplier" else "customer"
    cities = _get_cached_cities(country, effective_audience, db)
    response.headers["Cache-Control"] = "public, max-age=3600"
    return LeadsCitiesResponseSchema(cities=cities)


@router.get("/city-metrics", response_model=CityMetricsResponseSchema)
@limiter.limit("20/minute")
async def get_city_metrics_endpoint(
    request: Request,
    city: str,
    country_code: str | None = "US",
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
    email: str | None = None,
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
    country_code: str | None = "US",
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


@router.get("/restaurants", response_model=list[LeadsRestaurantSchema])
@limiter.limit("60/minute")
async def list_leads_restaurants(  # noqa: PLR0913 — declarative FastAPI Query params, not algorithmic args
    request: Request,
    language: str = Query(
        None,
        description="Locale for display names (en, es, pt). Falls back to Accept-Language header.",
    ),
    country_code: str | None = Query(
        None,
        description="Required ISO 3166-1 alpha-2 country code. Missing/empty → 400. Unsupported → [].",
    ),
    featured: bool = Query(False, description="Filter to featured restaurants only"),
    limit: int = Query(12, ge=1, le=50, description="Max results (1-50, default 12)"),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Public (no auth) list of restaurants for marketing site, scoped to a country.

    Limited projection of restaurant_info: name, cuisine, tagline, rating, cover image.
    Pass `?featured=true` to get only featured restaurants. Rate-limited per IP.
    """
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise HTTPException(status_code=422, detail=f"Unsupported language '{locale}'.")
    country = _require_country_code(country_code)
    rows = get_public_restaurants(locale, country, db, featured_only=featured, limit=limit)
    return [LeadsRestaurantSchema(**r) for r in rows]


@router.get("/plans", response_model=list[LeadsPlanSchema])
@limiter.limit("60/minute")
async def list_leads_plans(
    request: Request,
    language: str = Query(
        None,
        description="Locale for display names (en, es, pt). Falls back to Accept-Language header.",
    ),
    country_code: str | None = Query(
        None,
        description="Required ISO 3166-1 alpha-2 country code. Missing/empty → 400. Unsupported → [].",
    ),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Public (no auth) pricing table for marketing site, scoped to a country.

    Limited projection of plan_info with currency. All prices are monthly.
    Excludes Global Marketplace plans. Rate-limited per IP.
    """
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise HTTPException(status_code=422, detail=f"Unsupported language '{locale}'.")
    country = _require_country_code(country_code)
    rows = get_public_plans(locale, country, db)
    return [LeadsPlanSchema(**r) for r in rows]


@router.get("/cuisines", response_model=list[LeadsCuisineSchema])
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


@router.get("/employee-count-ranges", response_model=list[EmployeeCountRangeSchema])
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


@router.post("/restaurant-interest", response_model=RestaurantLeadResponseSchema, status_code=201)
@limiter.limit("5/minute")
async def submit_restaurant_interest(
    request: Request,
    data: RestaurantLeadCreateSchema,
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Public (no auth) restaurant supplier application.

    Enhanced interest form for the B2B restaurant acquisition pipeline.
    Captures contact info, business profile, cuisine selections, and ad tracking params.
    Rate-limited to 5 requests per minute per IP.
    """
    row = create_restaurant_lead(data.model_dump(), db)
    if not row:
        raise HTTPException(
            status_code=422,
            detail="Invalid restaurant lead data. Check referral_source and cuisine_ids.",
        )
    return RestaurantLeadResponseSchema(**row)


# -----------------------------------------------------------------------------
# Public country endpoints — no reCAPTCHA (navbar-load), ETag + long cache + SWR.
# Mounted on the sibling `public_router` which skips the router-level
# Depends(verify_recaptcha). Registered in application.py alongside `router`.
# -----------------------------------------------------------------------------


def _resolve_leads_locale(request: Request, language: str | None) -> str:
    """Common locale resolution for leads endpoints: query param → Accept-Language → 422."""
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise HTTPException(status_code=422, detail=f"Unsupported language '{locale}'.")
    return locale


def _serve_countries(
    *,
    response: Response,
    locale: str,
    if_none_match: str | None,
    supplier_audience: bool,
    db: psycopg2.extensions.connection,
) -> list[LeadsCountrySchema] | Response:
    """Shared serve path for /leads/countries (supplier_audience=False) and
    /leads/supplier-countries (True).

    Cache lookup → DB fallback → ETag + Cache-Control headers.
    Returns a 304 Response when If-None-Match matches, else the serialized list.
    """
    cache = _supplier_countries_cache if supplier_audience else _countries_cache
    fetch = get_public_supplier_countries if supplier_audience else get_public_countries

    now = time.time()
    entry = cache.get(locale)
    if entry and now < entry[2]:
        rows, etag = entry[0], entry[1]
    else:
        raw_rows = fetch(db)
        etag = _compute_countries_etag(raw_rows, locale)
        rows = _to_country_payload(raw_rows, locale)
        cache[locale] = (rows, etag, now + _COUNTRIES_CACHE_TTL_SECONDS)

    response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=3600"
    response.headers["ETag"] = etag

    if if_none_match and if_none_match.strip() == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": response.headers["Cache-Control"]})

    return [LeadsCountrySchema(**r) for r in rows]


@public_router.get("/countries", response_model=list[LeadsCountrySchema])
@limiter.limit("60/minute")
async def list_leads_countries(
    request: Request,
    response: Response,
    language: str | None = Query(
        None,
        description="Locale for country names (en, es, pt). Falls back to Accept-Language header.",
    ),
    if_none_match: str | None = Header(None, alias="If-None-Match"),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Public (no auth, no reCAPTCHA) country selector source for the marketing-site navbar.

    Returns markets with `status='active'` (currently serving customers). Response shape:
    `[{code, name, currency, phone_prefix, default_locale}]`. Country names are localized per
    `language`.

    **Empty array contract:** `[]` means no markets currently serve customers. The frontend
    hides the navbar country selector and every country-scoped section (plans, restaurants,
    featured-restaurant, coverage checker, metrics). Country-agnostic sections stay visible.
    The supplier application form is unaffected (it reads `/leads/supplier-countries`).

    Caching: `Cache-Control: public, max-age=86400, stale-while-revalidate=3600` + `ETag`.
    Send `If-None-Match` to get `304 Not Modified` when unchanged.
    """
    locale = _resolve_leads_locale(request, language)
    return _serve_countries(
        response=response,
        locale=locale,
        if_none_match=if_none_match,
        supplier_audience=False,
        db=db,
    )


@public_router.get("/supplier-countries", response_model=list[LeadsCountrySchema])
@limiter.limit("60/minute")
async def list_leads_supplier_countries(
    request: Request,
    response: Response,
    language: str | None = Query(
        None,
        description="Locale for country names (en, es, pt). Falls back to Accept-Language header.",
    ),
    if_none_match: str | None = Header(None, alias="If-None-Match"),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Public (no auth, no reCAPTCHA) country list for the `RestaurantApplicationForm`.

    Superset of `/leads/countries`: includes markets with `status IN ('active', 'inactive')`.
    "Inactive" markets are configured in market_info but not currently serving customers —
    suppliers can still apply there so we capture interest ahead of launch. Same response
    shape as `/leads/countries`.

    **Empty array contract:** `[]` means no markets are configured at all. Frontend renders
    `RestaurantApplicationForm` without the country dropdown and promotes
    `mailto:partners@vianda.market` as the primary CTA ("We'd still love to hear from you —
    email partners@vianda.market to tell us where you're cooking").

    Caching: same long-cache + ETag + SWR pattern as `/leads/countries`.
    """
    locale = _resolve_leads_locale(request, language)
    return _serve_countries(
        response=response,
        locale=locale,
        if_none_match=if_none_match,
        supplier_audience=True,
        db=db,
    )
