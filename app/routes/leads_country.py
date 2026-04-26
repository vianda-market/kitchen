"""
Public country-list endpoints for the marketing site (vianda-home).

Carved out of `app/routes/leads.py` so the main leads router stays compact and
keeps a healthy maintainability index. These two endpoints are the only
`/leads/*` routes that intentionally skip reCAPTCHA — they back the navbar
country selector, which loads on every page render and therefore cannot sit
behind a challenge.

Both responses are heavily cached:
- `Cache-Control: public, max-age=86400, stale-while-revalidate=3600`
- Strong `ETag` (option c: hash over response fields + per-row modified_date + locale)
- `If-None-Match` → 304

A locale-keyed in-process cache fronts the DB read; admin status flips reach
all workers within `_COUNTRIES_CACHE_TTL_SECONDS + 24h browser cache`, which is
acceptable at the change frequency of this data.

Full contract: `docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md`.
"""

import hashlib
import time

import psycopg2.extensions
from fastapi import APIRouter, Depends, Header, Query, Request, Response

from app.config.settings import settings
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.i18n.locale_names import localize_country_name
from app.schemas.consolidated_schemas import LeadsCountrySchema
from app.services.leads_public_service import (
    get_public_countries,
    get_public_supplier_countries,
)
from app.utils.locale import resolve_locale_from_header
from app.utils.rate_limit import limiter

# Sibling router at the same /leads prefix, *without* the router-level
# Depends(verify_recaptcha) used by `app.routes.leads.router`.
public_router = APIRouter(prefix="/leads", tags=["Leads"])

_COUNTRIES_CACHE_TTL_SECONDS = 600  # 10 minutes
_countries_cache: dict[str, tuple[list[dict], str, float]] = {}  # locale -> (rows, etag, expiry)
_supplier_countries_cache: dict[str, tuple[list[dict], str, float]] = {}

_CACHE_CONTROL = "public, max-age=86400, stale-while-revalidate=3600"


def _resolve_leads_locale(request: Request, language: str | None) -> str:
    """Common locale resolution for leads endpoints: query param → Accept-Language → 422."""
    locale = language or resolve_locale_from_header(request.headers.get("Accept-Language"))
    if locale not in settings.SUPPORTED_LOCALES:
        raise envelope_exception(
            ErrorCode.LOCALE_UNSUPPORTED, status=422, locale="en",
            lang=locale, supported=", ".join(settings.SUPPORTED_LOCALES),
        )
    return locale


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


def _serve_countries(
    *,
    response: Response,
    locale: str,
    if_none_match: str | None,
    supplier_audience: bool,
    db: psycopg2.extensions.connection,
) -> list[LeadsCountrySchema] | Response:
    """Shared serve path for /leads/countries (supplier_audience=False) and
    /leads/supplier-countries (True). Cache lookup → DB fallback → ETag/Cache-Control.
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

    response.headers["Cache-Control"] = _CACHE_CONTROL
    response.headers["ETag"] = etag

    if if_none_match and if_none_match.strip() == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": _CACHE_CONTROL})

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
) -> list[LeadsCountrySchema] | Response:
    """
    Public (no auth, no reCAPTCHA) country selector source for the marketing-site navbar.

    Returns markets with `status='active'` (currently serving customers). Response shape:
    `[{code, name, currency, phone_prefix, default_locale}]`.

    **Empty array contract:** `[]` means no markets currently serve customers. The frontend
    hides the navbar country selector and every country-scoped section. The supplier
    application form is unaffected (it reads `/leads/supplier-countries`).
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
) -> list[LeadsCountrySchema] | Response:
    """
    Public (no auth, no reCAPTCHA) country list for the supplier application form.

    Superset of `/leads/countries`: includes markets with `status IN ('active', 'inactive')`.
    Inactive markets are configured in `market_info` but not yet serving customers — suppliers
    can still apply so we capture interest ahead of launch.

    **Empty array contract:** `[]` means no markets are configured at all. Frontend renders
    the supplier form without the country dropdown and promotes
    `mailto:partners@vianda.market` as the primary CTA.
    """
    locale = _resolve_leads_locale(request, language)
    return _serve_countries(
        response=response,
        locale=locale,
        if_none_match=if_none_match,
        supplier_audience=True,
        db=db,
    )
