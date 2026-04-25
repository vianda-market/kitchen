# application.py
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (explicit path so it works regardless of cwd)
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.auth.middleware.permission_cache import PermissionCacheMiddleware
from app.auth.routes import router as auth_router
from app.routes.address import router as address_router

# Admin routes
from app.routes.admin.archival import router as archival_admin_router
from app.routes.admin.archival_config import router as archival_config_admin_router
from app.routes.admin.cuisines import router as admin_cuisines_router
from app.routes.admin.markets import router as markets_admin_router

# Billing routes
from app.routes.billing.client_bill import router as client_bill_router
from app.routes.billing.institution_bill import router as institution_bill_router
from app.routes.billing.supplier_invoice import router as supplier_invoice_router
from app.routes.billing.supplier_w9 import router as supplier_w9_router
from app.routes.cities import router as cities_router
from app.routes.countries import router as countries_router

# Consolidated CRUD routes
from app.routes.crud_routes import crud_router
from app.routes.crud_routes_user import crud_router_user
from app.routes.cuisines import router as cuisines_router
from app.routes.currencies import router as currencies_router

# Customer payment methods and providers (B2C, mock for UI dev)
from app.routes.customer.payment_methods import router as customer_payment_methods_router
from app.routes.customer.payment_providers import router as customer_payment_providers_router

# from app.routes.employer import router as employer_router  # REMOVED — employer identity is institution + entity
from app.routes.employer_program import router as employer_program_router
from app.routes.favorite import router as favorite_router
from app.routes.institution_entity import router as institution_entity_router

# Leads (unauthenticated, rate-limited)
from app.routes.leads import router as leads_router
from app.routes.leads_country import public_router as leads_public_router
from app.routes.main import router as main_router
from app.routes.national_holidays import router as national_holidays_router
from app.routes.notification_banner import router as notification_banner_router

# Onboarding status (supplier/employer onboarding checklist)
from app.routes.onboarding import router as onboarding_router

# Payment method routes
from app.routes.payment_methods.mercado_pago import router as mercado_pago_router

# Phone pre-validation (unauthenticated, real-time form feedback)
from app.routes.phone import router as phone_router
from app.routes.plate_kitchen_days import router as plate_kitchen_days_router
from app.routes.plate_pickup import router as plate_pickup_router
from app.routes.plate_review import router as plate_review_router

# Complex routes (business logic)
from app.routes.plate_selection import router as plate_selection_router
from app.routes.provinces import router as provinces_router
from app.routes.qr_code import router as qr_code_router
from app.routes.restaurant import router as restaurant_router
from app.routes.restaurant_balance import router as restaurant_balance_router
from app.routes.restaurant_holidays import router as restaurant_holidays_router
from app.routes.restaurant_staff import router as restaurant_staff_router
from app.routes.restaurant_transaction import router as restaurant_transaction_router
from app.routes.supplier_terms import router as supplier_terms_router
from app.routes.user import router as user_router
from app.routes.user_onboarding import router as user_onboarding_router
from app.routes.user_public import auth_router as password_recovery_router
from app.routes.user_public import router as user_public_router
from app.routes.workplace_group import admin_router as workplace_group_admin_router
from app.routes.workplace_group import router as workplace_group_router
from app.utils.db_pool import get_db_pool

# Configure logging - using the custom logger from app.utils.log
from app.utils.log import logger
from app.utils.rate_limit import limiter


class ContentLanguageMiddleware(BaseHTTPMiddleware):
    """Locale hint for clients via X-Content-Language header.
    Uses DB-resolved locale from get_resolved_locale (stored on request.state)
    when available; falls back to Accept-Language header parsing."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        locale = getattr(request.state, "resolved_locale", None)
        if not locale:
            accept_language = request.headers.get("Accept-Language", "") or ""
            locale = "en"
            for lang in accept_language.replace(" ", "").split(","):
                code = lang.split(";")[0].split("-")[0].lower()
                if code in {"en", "es", "pt"}:
                    locale = code
                    break
        response.headers["X-Content-Language"] = locale
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("App startup: Initialize resources.")
    # Diagnostic: always log what we read for LOG_EMPLOYER_ASSIGN (helps debug when logs don't appear)
    import os as _os

    _env_val = _os.environ.get("LOG_EMPLOYER_ASSIGN", "<not set>")
    try:
        from app.config.settings import get_settings

        _cfg_val = str(get_settings().LOG_EMPLOYER_ASSIGN)
    except Exception:
        _cfg_val = "<error>"
    _on = str(_env_val).strip().lower() in ("1", "true", "yes") or str(_cfg_val).strip().lower() in ("1", "true", "yes")
    logger.info(
        f"[EmployerAssign] LOG_EMPLOYER_ASSIGN: os.environ={repr(_env_val)} config={_cfg_val} -> debug={'ON' if _on else 'OFF'}"
    )
    # Initialize connection pool
    app.state.db_pool = get_db_pool()
    yield
    # Shutdown
    logger.info("App shutdown: Cleanup resources.")
    # Close connection pool
    if hasattr(app.state, "db_pool") and app.state.db_pool:
        app.state.db_pool.close_pool()


OPENAPI_TAGS = [
    {"name": "Auth", "description": "Authentication and session management"},
    {"name": "Users", "description": "User profile and management"},
    {"name": "User Public", "description": "Public user endpoints (signup, etc.)"},
    {"name": "Password Recovery", "description": "Password reset flow"},
    {"name": "CRUD", "description": "Generic CRUD operations"},
    {"name": "User CRUD", "description": "User-specific CRUD"},
    {"name": "Products", "description": "Product CRUD"},
    {"name": "Plans", "description": "Plan CRUD"},
    {"name": "Credit Currencies", "description": "Credit currency CRUD"},
    {"name": "Subscriptions", "description": "Subscription CRUD"},
    {"name": "Institutions", "description": "Institution CRUD"},
    {"name": "Payment Methods", "description": "Payment method CRUD"},
    {"name": "Plates", "description": "Plate CRUD"},
    {"name": "Geolocations", "description": "Geolocation CRUD"},
    {"name": "Plate Selections", "description": "Plate selection CRUD"},
    {"name": "Plate Selection", "description": "Plate selection flows"},
    {"name": "Plate Pickup", "description": "Plate pickup management"},
    {"name": "Plate Reviews", "description": "Plate review ratings"},
    {"name": "Favorites", "description": "User favorites"},
    {"name": "Employers", "description": "Employer entities"},
    {"name": "Employer Program", "description": "Employer Benefits Program — config, enrollment, billing"},
    {"name": "Addresses", "description": "Address management"},
    {"name": "QR Codes", "description": "QR code generation and lookup"},
    {"name": "Onboarding", "description": "Supplier/employer onboarding status tracking"},
    {"name": "User Onboarding", "description": "Customer onboarding status (user-level)"},
    {"name": "Institution Entities", "description": "Institutions and entities"},
    {"name": "Plate Kitchen Days", "description": "Kitchen day scheduling"},
    {"name": "Restaurants", "description": "Restaurant management"},
    {"name": "Restaurant Balances", "description": "Restaurant balance and credits"},
    {"name": "Restaurant Transactions", "description": "Restaurant transactions"},
    {"name": "Restaurant Staff", "description": "Restaurant staff management"},
    {"name": "Restaurant Holidays", "description": "Restaurant holiday schedules"},
    {"name": "National Holidays", "description": "National holiday reference data"},
    {"name": "Mercado Pago", "description": "Mercado Pago payment integration"},
    {"name": "Client Bills", "description": "Client billing"},
    {"name": "Institution Bills", "description": "Institution billing"},
    {"name": "Markets", "description": "Market and country-scope data"},
    {"name": "Countries", "description": "Supported countries"},
    {"name": "Currencies", "description": "Supported currencies"},
    {"name": "Cities", "description": "City reference data"},
    {"name": "Provinces", "description": "Province/state reference data"},
    {"name": "Cuisines", "description": "Cuisine types"},
    {"name": "Ingredients", "description": "Ingredient catalog search and product ingredient management"},
    {"name": "Leads", "description": "Lead capture (unauthenticated)"},
    {"name": "Webhooks", "description": "Webhook handlers (e.g. Stripe)"},
    {"name": "Customer", "description": "B2C customer payment methods"},
    {"name": "Enums", "description": "Enum reference values"},
    {"name": "Attribute Labels", "description": "DB column display labels per locale and schema"},
    {"name": "Admin Discretionary", "description": "Admin discretionary credit management"},
    {"name": "Super-Admin Discretionary", "description": "Super-admin discretionary credits"},
    {"name": "Admin Archival", "description": "Archival statistics and operations"},
    {"name": "Admin Archival Config", "description": "Archival configuration"},
    {"name": "Admin Cuisines", "description": "Admin cuisine management and suggestion review"},
    {"name": "Workplace Groups", "description": "B2C workplace group management for coworker pickup coordination"},
    {"name": "Admin Workplace Groups", "description": "Admin workplace group management"},
]


def create_app() -> FastAPI:
    app = FastAPI(title="Kitchen API", lifespan=lifespan, openapi_tags=OPENAPI_TAGS, redirect_slashes=False)

    # ── Exception handlers (K3) ──────────────────────────────────────────────
    # All handlers use a two-stage locale lookup (Q-S6 in design doc):
    #   1. request.state.resolved_locale — set by route DI for in-route raises.
    #   2. resolve_locale_from_header(Accept-Language) — for pre-route errors
    #      (auto-404/405/413, malformed JSON) where DI never ran.
    from app.i18n.envelope import build_envelope
    from app.i18n.error_codes import ErrorCode
    from app.utils.locale import resolve_locale_from_header

    def _resolve_handler_locale(request: Request) -> str:
        locale = getattr(request.state, "resolved_locale", None)
        if locale is None:
            locale = resolve_locale_from_header(request.headers.get("Accept-Language"))
        return locale

    # Status-code → ErrorCode map for known pre-route HTTP errors.
    _STATUS_CODE_MAP: dict[int, str] = {
        404: ErrorCode.REQUEST_NOT_FOUND,
        405: ErrorCode.REQUEST_METHOD_NOT_ALLOWED,
        413: ErrorCode.REQUEST_TOO_LARGE,
    }

    @app.exception_handler(StarletteHTTPException)
    async def _envelope_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """
        Catch-all handler for all HTTP exceptions.

        Dispatch order (Q-S1 in design doc):
        1. dict detail with 'code' key → already enveloped; pass through.
        2. status_code in {404, 405, 413} → emit request.* envelope.
           (Checked before bare-string branch: FastAPI auto-404/405/413 carries a
           plain string detail like "Not Found" that must be upgraded, not wrapped.)
        3. str detail → wrap as legacy.uncoded (transitional; removed in K-last).
        4. Fallback → wrap as legacy.uncoded with str(detail).
        """
        locale = _resolve_handler_locale(request)
        detail = exc.detail

        if isinstance(detail, dict) and "code" in detail:
            # Already a well-formed envelope — pass through unchanged.
            return JSONResponse(status_code=exc.status_code, content={"detail": detail})

        if exc.status_code in _STATUS_CODE_MAP:
            # Pre-route error generated by FastAPI (auto-404/405/413).
            # Emit the canonical request.* code regardless of what detail says.
            code = _STATUS_CODE_MAP[exc.status_code]
            envelope = build_envelope(code, locale)
            return JSONResponse(status_code=exc.status_code, content={"detail": envelope})

        if isinstance(detail, str):
            # Transitional wrapping branch. Applies to unmigrated bare-string
            # raises encountered before the K6..KN sweep completes.
            # REMOVE this branch in K-last once the sweep is done.
            envelope = build_envelope(ErrorCode.LEGACY_UNCODED, locale, message=detail)
            return JSONResponse(status_code=exc.status_code, content={"detail": envelope})

        # Fallback: wrap anything else as legacy.uncoded.
        # REMOVE this branch in K-last once the sweep is done.
        fallback_msg = str(detail) if detail else f"HTTP {exc.status_code}"
        envelope = build_envelope(ErrorCode.LEGACY_UNCODED, locale, message=fallback_msg)
        return JSONResponse(status_code=exc.status_code, content={"detail": envelope})

    from app.i18n.envelope import I18nValueError

    # Email-format error types (Pydantic v1 naming; kept for forward compat).
    # In Pydantic v2, EmailStr failures arrive as type="value_error" and are
    # handled by the value_error branch below.
    _EMAIL_TYPES: frozenset[str] = frozenset(
        {
            "value_error.email",
            "value_error.email.invalid_domain",
            "value_error.email.missing_at_sign",
            "value_error.email.missing_domain",
            "value_error.email.missing_local",
            "value_error.email.not_an_email_string",
        }
    )

    # Static type→code map — built once at app startup, not per-request.
    _TYPE_TO_CODE: dict[str, str] = {
        "missing": ErrorCode.VALIDATION_FIELD_REQUIRED,
        "string_too_short": ErrorCode.VALIDATION_VALUE_TOO_SHORT,
        "string_too_long": ErrorCode.VALIDATION_VALUE_TOO_LONG,
        "string_pattern_mismatch": ErrorCode.VALIDATION_INVALID_FORMAT,
    }

    @app.exception_handler(RequestValidationError)
    async def _envelope_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        """
        Catch-all handler for Pydantic RequestValidationError (422).

        Emits detail as a list of envelopes — one per Pydantic error (Q-S2).
        Detailed type→code mapping per K5 (kitchen#67).

        Type→code mapping:
          "missing"                    → validation.field_required
          "string_too_short"           → validation.value_too_short
          "string_too_long"            → validation.value_too_long
          "string_pattern_mismatch"    → validation.invalid_format
          "value_error.email" variants → validation.invalid_format
          "value_error" with I18nValueError ctx → domain code from the error
          anything else               → validation.custom

        Wire shape: {"detail": [{code, message, params}, ...]}
        """
        locale = _resolve_handler_locale(request)
        envelopes = []
        for error in exc.errors():
            field = ".".join(str(x) for x in error["loc"])
            msg = error.get("msg", "")
            error_type = error.get("type", "")
            ctx = error.get("ctx", {}) or {}

            # Determine code + extra params
            if error_type in _TYPE_TO_CODE:
                code: str = _TYPE_TO_CODE[error_type]
                extra_params: dict = {}
            elif error_type in _EMAIL_TYPES or error_type.startswith("value_error.email"):
                code = ErrorCode.VALIDATION_INVALID_FORMAT
                extra_params = {}
            elif error_type == "value_error":
                # Custom validator — check for I18nValueError in ctx
                ctx_error = ctx.get("error")
                if isinstance(ctx_error, I18nValueError):
                    code = ctx_error.code
                    extra_params = dict(ctx_error.params)
                else:
                    code = ErrorCode.VALIDATION_CUSTOM
                    extra_params = {}
            else:
                code = ErrorCode.VALIDATION_CUSTOM
                extra_params = {}

            # Build params dict, then remove any keys that would collide with
            # build_envelope's positional args. I18nValueError instances may
            # carry kwargs named "code" or "locale" (they're valid message
            # placeholders), so pop defensively before splatting.
            params = {"field": field, "msg": msg, "type": error_type, **extra_params}
            params.pop("code", None)
            params.pop("locale", None)
            envelope = build_envelope(code, locale, **params)
            envelopes.append(envelope)
        return JSONResponse(status_code=422, content={"detail": envelopes})

    # Rate limiting (slowapi) — emits request.rate_limited envelope (K3).
    # Replaces the previous plain {"detail": "rate_limited", "retry_after_seconds": 60}.

    async def _structured_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        locale = _resolve_handler_locale(request)
        envelope = build_envelope(ErrorCode.REQUEST_RATE_LIMITED, locale, retry_after_seconds=60)
        return JSONResponse(
            status_code=429,
            content={"detail": envelope},
            headers={"Retry-After": "60"},
        )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _structured_rate_limit_handler)

    # CORS: explicit allowlist from env, or allow all for local dev
    from app.config.settings import settings

    _raw_origins = settings.CORS_ALLOWED_ORIGINS.strip()
    _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()] if _raw_origins else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count"],
    )

    # Order: last registered runs first on the request.
    # Target: PermissionCache (outer) -> UserRateLimit -> ContentLanguage -> CORS -> app.
    app.add_middleware(ContentLanguageMiddleware)

    # Authenticated user rate limiting (per-user sliding window, tier-based)
    from app.auth.middleware.rate_limit_middleware import UserRateLimitMiddleware

    app.add_middleware(UserRateLimitMiddleware)

    # Add permission cache middleware
    app.add_middleware(PermissionCacheMiddleware)

    # =============================================================================
    # Infrastructure Endpoints (Non-Versioned)
    # These are infrastructure endpoints for monitoring, load balancers, etc.
    # They don't require versioning as they're not part of the business API.
    # =============================================================================

    @app.get("/", include_in_schema=False)
    async def root():
        """Root endpoint - API status and information"""
        return {
            "message": "Kitchen API is running",
            "status": "healthy",
            "current_version": "v1",
            "api_base": "/api/v1",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health", include_in_schema=False)
    async def health_check():
        """Health check endpoint for load balancers and monitoring tools"""
        return {"status": "healthy"}

    @app.get("/api", include_in_schema=False)
    async def api_root():
        """Redirect to current API version"""
        return RedirectResponse(url="/api/v1", status_code=307)

    # Infrastructure/monitoring routes (non-versioned)
    # main_router includes: /pool-stats (database connection pool monitoring)
    app.include_router(main_router)

    # =============================================================================
    # Versioned Business API Routes (v1)
    # All business endpoints require explicit versioning: /api/v1/...
    # =============================================================================

    from app.core.versioning import APIVersion, create_versioned_router

    # Create versioned auth router
    v1_auth_router = create_versioned_router("api", ["Auth"], APIVersion.V1)
    v1_auth_router.include_router(auth_router)
    app.include_router(v1_auth_router)

    # Institution entities: register enriched-only router BEFORE crud so /enriched matches before /{entity_id}
    v1_institution_entity_router = create_versioned_router("api", ["Institution Entities"], APIVersion.V1)
    v1_institution_entity_router.include_router(institution_entity_router)
    app.include_router(v1_institution_entity_router)

    # Onboarding status: register BEFORE CRUD so /institutions/onboarding-summary matches before /{institution_id}
    v1_onboarding_router = create_versioned_router("api", ["Onboarding"], APIVersion.V1)
    v1_onboarding_router.include_router(onboarding_router)
    app.include_router(v1_onboarding_router)

    # Customer onboarding (user-level): GET /users/me/onboarding-status
    v1_user_onboarding_router = create_versioned_router("api", ["User Onboarding"], APIVersion.V1)
    v1_user_onboarding_router.include_router(user_onboarding_router)
    app.include_router(v1_user_onboarding_router)

    # Create versioned CRUD router
    v1_crud_router = create_versioned_router("api", ["CRUD"], APIVersion.V1)
    v1_crud_router.include_router(crud_router)
    app.include_router(v1_crud_router)

    # Create versioned user CRUD router
    v1_crud_router_user = create_versioned_router("api", ["User CRUD"], APIVersion.V1)
    v1_crud_router_user.include_router(crud_router_user)
    app.include_router(v1_crud_router_user)

    # Create versioned user router
    v1_user_router = create_versioned_router("api", ["Users"], APIVersion.V1)
    v1_user_router.include_router(user_router)
    app.include_router(v1_user_router)

    # Create versioned user public router
    v1_user_public_router = create_versioned_router("api", ["User Public"], APIVersion.V1)
    v1_user_public_router.include_router(user_public_router)
    app.include_router(v1_user_public_router)

    # Create versioned password recovery router (public auth endpoints)
    v1_password_recovery_router = create_versioned_router("api", ["Password Recovery"], APIVersion.V1)
    v1_password_recovery_router.include_router(password_recovery_router)
    app.include_router(v1_password_recovery_router)

    # Versioned complex routes (v1)
    v1_plate_selection_router = create_versioned_router("api", ["Plate Selection"], APIVersion.V1)
    v1_plate_selection_router.include_router(plate_selection_router)
    app.include_router(v1_plate_selection_router)

    v1_plate_pickup_router = create_versioned_router("api", ["Plate Pickup"], APIVersion.V1)
    v1_plate_pickup_router.include_router(plate_pickup_router)
    app.include_router(v1_plate_pickup_router)

    v1_plate_review_router = create_versioned_router("api", ["Plate Reviews"], APIVersion.V1)
    v1_plate_review_router.include_router(plate_review_router)
    app.include_router(v1_plate_review_router)

    v1_notification_banner_router = create_versioned_router("api", ["Notification Banners"], APIVersion.V1)
    v1_notification_banner_router.include_router(notification_banner_router)
    app.include_router(v1_notification_banner_router)

    v1_favorite_router = create_versioned_router("api", ["Favorites"], APIVersion.V1)
    v1_favorite_router.include_router(favorite_router)
    app.include_router(v1_favorite_router)

    # v1_employer_router REMOVED — employer identity is institution + entity

    v1_employer_program_router = create_versioned_router("api", ["Employer Program"], APIVersion.V1)
    v1_employer_program_router.include_router(employer_program_router)
    app.include_router(v1_employer_program_router)

    v1_address_router = create_versioned_router("api", ["Addresses"], APIVersion.V1)
    v1_address_router.include_router(address_router)
    app.include_router(v1_address_router)

    v1_qr_code_router = create_versioned_router("api", ["QR Codes"], APIVersion.V1)
    v1_qr_code_router.include_router(qr_code_router)
    app.include_router(v1_qr_code_router)

    v1_plate_kitchen_days_router = create_versioned_router("api", ["Plate Kitchen Days"], APIVersion.V1)
    v1_plate_kitchen_days_router.include_router(plate_kitchen_days_router)
    app.include_router(v1_plate_kitchen_days_router)

    v1_restaurant_router = create_versioned_router("api", ["Restaurants"], APIVersion.V1)
    v1_restaurant_router.include_router(restaurant_router)
    app.include_router(v1_restaurant_router)

    v1_restaurant_balance_router = create_versioned_router("api", ["Restaurant Balances"], APIVersion.V1)
    v1_restaurant_balance_router.include_router(restaurant_balance_router)
    app.include_router(v1_restaurant_balance_router)

    v1_restaurant_transaction_router = create_versioned_router("api", ["Restaurant Transactions"], APIVersion.V1)
    v1_restaurant_transaction_router.include_router(restaurant_transaction_router)
    app.include_router(v1_restaurant_transaction_router)

    v1_restaurant_staff_router = create_versioned_router("api", ["Restaurant Staff"], APIVersion.V1)
    v1_restaurant_staff_router.include_router(restaurant_staff_router)
    app.include_router(v1_restaurant_staff_router)

    v1_restaurant_holidays_router = create_versioned_router("api", ["Restaurant Holidays"], APIVersion.V1)
    v1_restaurant_holidays_router.include_router(restaurant_holidays_router)
    app.include_router(v1_restaurant_holidays_router)

    v1_national_holidays_router = create_versioned_router("api", ["National Holidays"], APIVersion.V1)
    v1_national_holidays_router.include_router(national_holidays_router)
    app.include_router(v1_national_holidays_router)

    # Payment method routes (versioned)
    v1_mercado_pago_router = create_versioned_router("api", ["Mercado Pago"], APIVersion.V1)
    v1_mercado_pago_router.include_router(mercado_pago_router)
    app.include_router(v1_mercado_pago_router)

    # Billing routes (non-versioned routes without versioned equivalents)
    # Note: client_bill_router is now versioned - moved to versioned section below

    # Versioned billing routes (v1)
    v1_client_bill_router = create_versioned_router("api", ["Client Bills"], APIVersion.V1)
    v1_client_bill_router.include_router(client_bill_router)
    app.include_router(v1_client_bill_router)

    v1_institution_bill_router = create_versioned_router("api", ["Institution Bills"], APIVersion.V1)
    v1_institution_bill_router.include_router(institution_bill_router)
    app.include_router(v1_institution_bill_router)

    # Supplier invoice compliance routes (versioned)
    v1_supplier_invoice_router = create_versioned_router("api", ["Supplier Invoices"], APIVersion.V1)
    v1_supplier_invoice_router.include_router(supplier_invoice_router)
    app.include_router(v1_supplier_invoice_router)

    # Supplier W-9 routes (versioned — US tax compliance)
    v1_supplier_w9_router = create_versioned_router("api", ["Supplier W-9"], APIVersion.V1)
    v1_supplier_w9_router.include_router(supplier_w9_router)
    app.include_router(v1_supplier_w9_router)

    v1_supplier_terms_router = create_versioned_router("api", ["Supplier Terms"], APIVersion.V1)
    v1_supplier_terms_router.include_router(supplier_terms_router)
    app.include_router(v1_supplier_terms_router)

    # Payout enriched routes (versioned)
    from app.routes.billing.payout import router as payout_router

    v1_payout_router = create_versioned_router("api", ["Payouts"], APIVersion.V1)
    v1_payout_router.include_router(payout_router)
    app.include_router(v1_payout_router)

    # Markets router (versioned)
    v1_markets_router = create_versioned_router("api", ["Markets"], APIVersion.V1)
    v1_markets_router.include_router(markets_admin_router)
    app.include_router(v1_markets_router)

    # Countries router (versioned; supported countries for Create Market dropdown)
    v1_countries_router = create_versioned_router("api", ["Countries"], APIVersion.V1)
    v1_countries_router.include_router(countries_router)
    app.include_router(v1_countries_router)

    # Currencies router (versioned; supported currencies for Create Credit Currency dropdown)
    v1_currencies_router = create_versioned_router("api", ["Currencies"], APIVersion.V1)
    v1_currencies_router.include_router(currencies_router)
    app.include_router(v1_currencies_router)

    # Cities router (versioned; supported cities for user onboarding and employer address scoping)
    v1_cities_router = create_versioned_router("api", ["Cities"], APIVersion.V1)
    v1_cities_router.include_router(cities_router)
    app.include_router(v1_cities_router)

    # Provinces router (versioned; supported provinces for address forms and cascading dropdowns)
    v1_provinces_router = create_versioned_router("api", ["Provinces"], APIVersion.V1)
    v1_provinces_router.include_router(provinces_router)
    app.include_router(v1_provinces_router)

    # Cuisines router (versioned; supported cuisines for restaurant create/edit dropdown)
    v1_cuisines_router = create_versioned_router("api", ["Cuisines"], APIVersion.V1)
    v1_cuisines_router.include_router(cuisines_router)
    app.include_router(v1_cuisines_router)

    # Locales router (versioned; no auth, public locale discovery)
    from app.routes.locales import router as locales_router

    v1_locales_router = create_versioned_router("api", ["Locales"], APIVersion.V1)
    v1_locales_router.include_router(locales_router)
    app.include_router(v1_locales_router)

    # Leads router (versioned; no auth, rate-limited)
    # `leads_router` gates every route behind reCAPTCHA. `leads_public_router` carves out the
    # two navbar-load country endpoints (/countries, /supplier-countries) that the marketing
    # site fetches on every page render and therefore cannot sit behind a challenge.
    v1_leads_router = create_versioned_router("api", ["Leads"], APIVersion.V1)
    v1_leads_router.include_router(leads_router)
    v1_leads_router.include_router(leads_public_router)
    app.include_router(v1_leads_router)

    # Phone pre-validation (versioned; no auth, real-time form feedback)
    v1_phone_router = create_versioned_router("api", ["Phone"], APIVersion.V1)
    v1_phone_router.include_router(phone_router)
    app.include_router(v1_phone_router)

    # Webhooks (Stripe payment_intent.succeeded; no auth, verified via Stripe-Signature)
    from app.routes.webhooks import router as webhooks_router

    v1_webhooks_router = create_versioned_router("api", ["Webhooks"], APIVersion.V1)
    v1_webhooks_router.include_router(webhooks_router)
    app.include_router(v1_webhooks_router)

    # Customer router (B2C payment method and provider management; mock endpoints for UI dev)
    from fastapi import APIRouter

    customer_router = APIRouter(prefix="/customer", tags=["Customer"])
    customer_router.include_router(customer_payment_methods_router)
    customer_router.include_router(customer_payment_providers_router)
    v1_customer_router = create_versioned_router("api", ["Customer"], APIVersion.V1)
    v1_customer_router.include_router(customer_router)
    app.include_router(v1_customer_router)

    # Customer Referral router (versioned)
    from app.routes.customer.referral import router as customer_referral_router

    v1_customer_referral_router = create_versioned_router("api", ["Referrals"], APIVersion.V1)
    v1_customer_referral_router.include_router(customer_referral_router)
    app.include_router(v1_customer_referral_router)

    # Enum Service router (versioned)
    from app.routes.enums import router as enums_router

    v1_enums_router = create_versioned_router("api", ["Enums"], APIVersion.V1)
    v1_enums_router.include_router(enums_router)
    app.include_router(v1_enums_router)

    # Attribute Labels router (versioned; K-attr1)
    from app.routes.attribute_labels import router as attribute_labels_router

    v1_attribute_labels_router = create_versioned_router("api", ["Attribute Labels"], APIVersion.V1)
    v1_attribute_labels_router.include_router(attribute_labels_router)
    app.include_router(v1_attribute_labels_router)

    # Ingredients router (versioned; OFF-backed search + custom creation)
    from app.routes.ingredients import router as ingredients_router

    v1_ingredients_router = create_versioned_router("api", ["Ingredients"], APIVersion.V1)
    v1_ingredients_router.include_router(ingredients_router)
    app.include_router(v1_ingredients_router)

    # User payment summary (Internal only — employee portal for reviewing customer payment status)
    from app.routes.admin.user_payment_summary import router as user_payment_summary_router

    v1_user_payment_summary_router = create_versioned_router("api", ["User Payment Summary"], APIVersion.V1)
    v1_user_payment_summary_router.include_router(user_payment_summary_router)
    app.include_router(v1_user_payment_summary_router)

    # Admin Discretionary router (versioned)
    from app.routes.admin.discretionary import router as admin_discretionary_router

    v1_admin_discretionary_router = create_versioned_router("api", ["Admin Discretionary"], APIVersion.V1)
    v1_admin_discretionary_router.include_router(admin_discretionary_router)
    app.include_router(v1_admin_discretionary_router)

    # Admin Referral Config router (versioned)
    from app.routes.admin.referral_config import router as admin_referral_config_router

    v1_admin_referral_config_router = create_versioned_router("api", ["Admin Referral Config"], APIVersion.V1)
    v1_admin_referral_config_router.include_router(admin_referral_config_router)
    app.include_router(v1_admin_referral_config_router)

    # Super-Admin Discretionary router (versioned)
    from app.routes.super_admin.discretionary import router as super_admin_discretionary_router

    v1_super_admin_discretionary_router = create_versioned_router("api", ["Super-Admin Discretionary"], APIVersion.V1)
    v1_super_admin_discretionary_router.include_router(super_admin_discretionary_router)
    app.include_router(v1_super_admin_discretionary_router)

    # Admin archival routes (versioned)
    v1_archival_admin_router = create_versioned_router("api", ["Admin Archival"], APIVersion.V1)
    v1_archival_admin_router.include_router(archival_admin_router)
    app.include_router(v1_archival_admin_router)

    v1_archival_config_admin_router = create_versioned_router("api", ["Admin Archival Config"], APIVersion.V1)
    v1_archival_config_admin_router.include_router(archival_config_admin_router)
    app.include_router(v1_archival_config_admin_router)

    # Admin leads routes (versioned) — Internal-only lead interest dashboard
    from app.routes.admin.leads import router as admin_leads_router

    v1_admin_leads_router = create_versioned_router("api", ["Admin Leads"], APIVersion.V1)
    v1_admin_leads_router.include_router(admin_leads_router)
    app.include_router(v1_admin_leads_router)

    # Admin cuisine routes (versioned)
    v1_admin_cuisines_router = create_versioned_router("api", ["Admin Cuisines"], APIVersion.V1)
    v1_admin_cuisines_router.include_router(admin_cuisines_router)
    app.include_router(v1_admin_cuisines_router)

    # Workplace group routes (B2C coworker pickup coordination)
    v1_workplace_group_router = create_versioned_router("api", ["Workplace Groups"], APIVersion.V1)
    v1_workplace_group_router.include_router(workplace_group_router)
    app.include_router(v1_workplace_group_router)

    # Admin workplace group routes (Internal only)
    v1_workplace_group_admin_router = create_versioned_router("api", ["Admin Workplace Groups"], APIVersion.V1)
    v1_workplace_group_admin_router.include_router(workplace_group_admin_router)
    app.include_router(v1_workplace_group_admin_router)

    # Admin external data routes (GeoNames picker for city/country promotion UI)
    from app.routes.admin.external_data import router as admin_external_data_router

    v1_admin_external_data_router = create_versioned_router("api", ["Admin: External Data"], APIVersion.V1)
    v1_admin_external_data_router.include_router(admin_external_data_router)
    app.include_router(v1_admin_external_data_router)

    # Ad click tracking (user-facing, captures gclid/fbclid from frontend)
    from app.routes.ad_tracking import router as ad_tracking_router

    v1_ad_tracking_router = create_versioned_router("api", ["Ad Tracking"], APIVersion.V1)
    v1_ad_tracking_router.include_router(ad_tracking_router)
    app.include_router(v1_ad_tracking_router)

    # Admin ad zones (geographic flywheel management)
    from app.routes.admin.ad_zones import router as admin_ad_zones_router

    v1_admin_ad_zones_router = create_versioned_router("api", ["Admin Ad Zones"], APIVersion.V1)
    v1_admin_ad_zones_router.include_router(admin_ad_zones_router)
    app.include_router(v1_admin_ad_zones_router)

    # Maps (static map snapshots for B2C Explore)
    from app.routes.maps import router as maps_router

    v1_maps_router = create_versioned_router("api", ["Maps"], APIVersion.V1)
    v1_maps_router.include_router(maps_router)
    app.include_router(v1_maps_router)

    # Dev-only routes (guarded by DEV_MODE)
    from app.routes.dev import router as dev_router

    v1_dev_router = create_versioned_router("api", ["Dev"], APIVersion.V1)
    v1_dev_router.include_router(dev_router)
    app.include_router(v1_dev_router)

    # Static files (product images, placeholders, QR codes)
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
