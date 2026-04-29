"""
Public country-list endpoints for the marketing site (vianda-home).

Carved out of ``app/routes/leads.py`` so the main leads router stays compact and
keeps a healthy maintainability index. These two endpoints are the only
``/leads/*`` routes that intentionally skip reCAPTCHA — they back the navbar
country selector, which loads on every page render and therefore cannot sit
behind a challenge.

**Cache-Control: private, no-store**

The response envelope now includes ``suggested_country_code``, derived from the
visitor's IP via the ``cf-ipcountry`` header (Cloudflare).  Because this value
varies per-visitor, responses MUST NOT be served from shared caches (CDN /
reverse proxy).  ``private, no-store`` prevents any intermediate cache from
holding and re-serving a visitor's suggestion to a different visitor.

An in-process, locale-keyed cache (10-minute TTL) fronts the DB read for the
countries list itself — only the suggestion varies.  Admin status flips reach
all workers within the TTL window.

**Geo source: Cloudflare cf-ipcountry header**

Cloudflare forwards the visitor's country as the ``cf-ipcountry`` HTTP request
header.  When this header is absent (Cloudflare not in the deploy chain, local
dev, or an unresolvable IP), ``suggested_country_code`` is ``null``.

NOTE: Cloudflare is not currently in the kitchen deploy chain (Cloud Run
direct).  This field will return ``null`` for all requests until CF is placed
in front of Cloud Run.  The implementation is forward-compatible: once CF is
added, the header is forwarded automatically and no further backend changes are
needed.

Full contract: ``docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md``.
"""

import time

import psycopg2.extensions
from fastapi import APIRouter, Depends, Header, Query, Request, Response

from app.config.settings import settings
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.i18n.locale_names import localize_country_name
from app.schemas.consolidated_schemas import LeadsCountriesResponseSchema, LeadsCountrySchema
from app.services.leads_public_service import (
    get_public_countries,
    get_public_supplier_countries,
)
from app.utils.locale import resolve_locale_from_header
from app.utils.rate_limit import limiter

# Sibling router at the same /leads prefix, *without* the router-level
# Depends(verify_recaptcha) used by ``app.routes.leads.router``.
public_router = APIRouter(prefix="/leads", tags=["Leads"])

_COUNTRIES_CACHE_TTL_SECONDS = 600  # 10 minutes
# locale -> (serialized rows, expiry)
_countries_cache: dict[str, tuple[list[dict], float]] = {}
_supplier_countries_cache: dict[str, tuple[list[dict], float]] = {}

# Cache-Control: private, no-store because the envelope includes a per-visitor
# suggested_country_code.  No shared CDN/proxy caching permitted.
_CACHE_CONTROL = "private, no-store"


def _resolve_leads_locale(request: Request, language: str | None) -> str:
    """Common locale resolution for leads endpoints: query param → Accept-Language → 422."""
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise envelope_exception(
            ErrorCode.LOCALE_UNSUPPORTED,
            status=422,
            locale="en",
            lang=locale,
            supported=", ".join(settings.SUPPORTED_LOCALES),
        )
    return locale


def _to_country_payload(rows: list[dict], locale: str) -> list[dict]:
    """Localize country names and drop DB-only fields before serialization."""
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


def _resolve_suggested_country(cf_ipcountry: str | None, country_codes: set[str]) -> str | None:
    """Resolve the visitor's suggested country from the Cloudflare cf-ipcountry header.

    Returns the ISO 3166-1 alpha-2 code only when:
    - The header is present and non-empty.
    - The resolved code is present in ``country_codes`` (the returned countries list).

    Returns ``None`` when the header is absent, invalid, or the resolved country
    is not a launched/configured market.

    Cloudflare uses ``"XX"`` for IPs it cannot resolve — treated as absent.
    """
    if not cf_ipcountry:
        return None
    code = cf_ipcountry.strip().upper()
    # Cloudflare sets "XX" for unknown/unresolvable IPs — treat as absent.
    if not code or code == "XX" or len(code) != 2:
        return None
    return code if code in country_codes else None


def _serve_countries(
    *,
    response: Response,
    locale: str,
    cf_ipcountry: str | None,
    supplier_audience: bool,
    db: psycopg2.extensions.connection,
) -> LeadsCountriesResponseSchema:
    """Shared serve path for /leads/countries (supplier_audience=False) and
    /leads/supplier-countries (True). In-process cache → DB fallback → envelope.

    Response is always ``private, no-store`` because the envelope contains a
    per-visitor ``suggested_country_code``.
    """
    cache = _supplier_countries_cache if supplier_audience else _countries_cache
    fetch = get_public_supplier_countries if supplier_audience else get_public_countries

    now = time.time()
    entry = cache.get(locale)
    if entry and now < entry[1]:
        rows = entry[0]
    else:
        raw_rows = fetch(db)
        rows = _to_country_payload(raw_rows, locale)
        cache[locale] = (rows, now + _COUNTRIES_CACHE_TTL_SECONDS)

    response.headers["Cache-Control"] = _CACHE_CONTROL

    country_codes = {r["code"] for r in rows}
    suggested = _resolve_suggested_country(cf_ipcountry, country_codes)

    countries = [LeadsCountrySchema(**r) for r in rows]
    return LeadsCountriesResponseSchema(countries=countries, suggested_country_code=suggested)


@public_router.get("/countries", response_model=LeadsCountriesResponseSchema)
@limiter.limit("60/minute")
async def list_leads_countries(
    request: Request,
    response: Response,
    language: str | None = Query(
        None,
        description="Locale for country names (en, es, pt). Falls back to Accept-Language header.",
    ),
    cf_ipcountry: str | None = Header(None, alias="cf-ipcountry"),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> LeadsCountriesResponseSchema:
    """
    Public (no auth, no reCAPTCHA) country selector source for the marketing-site navbar.

    Returns markets with ``status='active'`` (currently serving customers). Response shape::

        {
          "countries": [{code, name, currency, phone_prefix, default_locale}, ...],
          "suggested_country_code": "AR" | null
        }

    ``suggested_country_code`` is the ISO 3166-1 alpha-2 of the visitor's country, inferred
    from the ``cf-ipcountry`` header forwarded by Cloudflare.  Returns ``null`` when CF is not
    in the deploy chain, when the header is absent, or when the resolved country is not a
    launched market.

    **Empty countries contract:** ``countries: []`` means no markets currently serve customers.
    The frontend hides the navbar country selector and every country-scoped section. The
    supplier application form is unaffected (it reads ``/leads/supplier-countries``).

    **Cache-Control: private, no-store** — the envelope contains a per-visitor suggestion;
    shared caches must not serve one visitor's response to another.
    """
    locale = _resolve_leads_locale(request, language)
    return _serve_countries(
        response=response,
        locale=locale,
        cf_ipcountry=cf_ipcountry,
        supplier_audience=False,
        db=db,
    )


@public_router.get("/supplier-countries", response_model=LeadsCountriesResponseSchema)
@limiter.limit("60/minute")
async def list_leads_supplier_countries(
    request: Request,
    response: Response,
    language: str | None = Query(
        None,
        description="Locale for country names (en, es, pt). Falls back to Accept-Language header.",
    ),
    cf_ipcountry: str | None = Header(None, alias="cf-ipcountry"),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> LeadsCountriesResponseSchema:
    """
    Public (no auth, no reCAPTCHA) country list for the supplier application form.

    Superset of ``/leads/countries``: includes markets with ``status IN ('active', 'inactive')``.
    Inactive markets are configured in ``market_info`` but not yet serving customers — suppliers
    can still apply so we capture interest ahead of launch.

    ``suggested_country_code`` is the ISO 3166-1 alpha-2 of the visitor's country, inferred
    from the ``cf-ipcountry`` header forwarded by Cloudflare.  Returns ``null`` when CF is not
    in the deploy chain, when the header is absent, or when the resolved country is not a
    configured market (active or inactive).

    **Empty countries contract:** ``countries: []`` means no markets are configured at all.
    Frontend renders the supplier form without the country dropdown and promotes
    ``mailto:partners@vianda.market`` as the primary CTA.

    **Cache-Control: private, no-store** — the envelope contains a per-visitor suggestion;
    shared caches must not serve one visitor's response to another.
    """
    locale = _resolve_leads_locale(request, language)
    return _serve_countries(
        response=response,
        locale=locale,
        cf_ipcountry=cf_ipcountry,
        supplier_audience=True,
        db=db,
    )
