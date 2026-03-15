# application.py
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (explicit path so it works regardless of cwd)
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.auth.middleware.permission_cache import PermissionCacheMiddleware
from app.utils.db_pool import get_db_pool
from app.utils.rate_limit import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager

from app.routes.main import router as main_router
from app.routes.user import router as user_router
from app.routes.user_public import router as user_public_router, auth_router as password_recovery_router
from app.auth.routes import router as auth_router

# Consolidated CRUD routes
from app.routes.crud_routes import crud_router
from app.routes.crud_routes_user import crud_router_user

# Complex routes (business logic)
from app.routes.plate_selection import router as plate_selection_router
from app.routes.plate_pickup import router as plate_pickup_router
from app.routes.plate_review import router as plate_review_router
from app.routes.favorite import router as favorite_router
from app.routes.employer import router as employer_router
from app.routes.address import router as address_router
from app.routes.qr_code import router as qr_code_router
from app.routes.institution_entity import router as institution_entity_router
from app.routes.restaurant import router as restaurant_router
from app.routes.restaurant_balance import router as restaurant_balance_router
from app.routes.restaurant_transaction import router as restaurant_transaction_router
from app.routes.restaurant_staff import router as restaurant_staff_router
from app.routes.plate_kitchen_days import router as plate_kitchen_days_router
from app.routes.national_holidays import router as national_holidays_router
from app.routes.restaurant_holidays import router as restaurant_holidays_router

# Payment method routes
from app.routes.payment_methods.mercado_pago import router as mercado_pago_router

# Billing routes
from app.routes.billing.client_bill import router as client_bill_router
from app.routes.billing.institution_bill import router as institution_bill_router

# Admin routes
from app.routes.admin.archival import router as archival_admin_router
from app.routes.admin.archival_config import router as archival_config_admin_router
from app.routes.admin.markets import router as markets_admin_router
from app.routes.countries import router as countries_router
from app.routes.currencies import router as currencies_router
from app.routes.cities import router as cities_router
from app.routes.provinces import router as provinces_router
from app.routes.cuisines import router as cuisines_router

# Leads (unauthenticated, rate-limited)
from app.routes.leads import router as leads_router

# Customer payment methods (B2C, mock for UI dev)
from app.routes.customer.payment_methods import router as customer_payment_methods_router

# Configure logging - using the custom logger from app.utils.log
from app.utils.log import logger

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
    logger.info(f"[EmployerAssign] LOG_EMPLOYER_ASSIGN: os.environ={repr(_env_val)} config={_cfg_val} -> debug={'ON' if _on else 'OFF'}")
    # Initialize connection pool
    app.state.db_pool = get_db_pool()
    yield
    # Shutdown
    logger.info("App shutdown: Cleanup resources.")
    # Close connection pool
    if hasattr(app.state, 'db_pool') and app.state.db_pool:
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
    {"name": "Addresses", "description": "Address management"},
    {"name": "QR Codes", "description": "QR code generation and lookup"},
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
    {"name": "Leads", "description": "Lead capture (unauthenticated)"},
    {"name": "Webhooks", "description": "Webhook handlers (e.g. Stripe)"},
    {"name": "Customer", "description": "B2C customer payment methods"},
    {"name": "Enums", "description": "Enum reference values"},
    {"name": "Admin Discretionary", "description": "Admin discretionary credit management"},
    {"name": "Super-Admin Discretionary", "description": "Super-admin discretionary credits"},
    {"name": "Admin Archival", "description": "Archival statistics and operations"},
    {"name": "Admin Archival Config", "description": "Archival configuration"},
]


def create_app() -> FastAPI:
    app = FastAPI(title="Kitchen API", lifespan=lifespan, openapi_tags=OPENAPI_TAGS, redirect_slashes=False)

    # Rate limiting (slowapi) - must be set before routes that use @limiter.limit()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
    )

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
            "health": "/health"
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
    
    from app.core.versioning import create_versioned_router, APIVersion
    
    # Create versioned auth router
    v1_auth_router = create_versioned_router("api", ["Auth"], APIVersion.V1)
    v1_auth_router.include_router(auth_router)
    app.include_router(v1_auth_router)

    # Institution entities: register enriched-only router BEFORE crud so /enriched matches before /{entity_id}
    v1_institution_entity_router = create_versioned_router("api", ["Institution Entities"], APIVersion.V1)
    v1_institution_entity_router.include_router(institution_entity_router)
    app.include_router(v1_institution_entity_router)
    
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

    v1_favorite_router = create_versioned_router("api", ["Favorites"], APIVersion.V1)
    v1_favorite_router.include_router(favorite_router)
    app.include_router(v1_favorite_router)
    
    v1_employer_router = create_versioned_router("api", ["Employers"], APIVersion.V1)
    v1_employer_router.include_router(employer_router)
    app.include_router(v1_employer_router)
    
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
    
    # Leads router (versioned; no auth, rate-limited)
    v1_leads_router = create_versioned_router("api", ["Leads"], APIVersion.V1)
    v1_leads_router.include_router(leads_router)
    app.include_router(v1_leads_router)

    # Webhooks (Stripe payment_intent.succeeded; no auth, verified via Stripe-Signature)
    from app.routes.webhooks import router as webhooks_router
    v1_webhooks_router = create_versioned_router("api", ["Webhooks"], APIVersion.V1)
    v1_webhooks_router.include_router(webhooks_router)
    app.include_router(v1_webhooks_router)

    # Customer router (B2C payment method management; mock endpoints for UI dev)
    from fastapi import APIRouter
    customer_router = APIRouter(prefix="/customer", tags=["Customer"])
    customer_router.include_router(customer_payment_methods_router)
    v1_customer_router = create_versioned_router("api", ["Customer"], APIVersion.V1)
    v1_customer_router.include_router(customer_router)
    app.include_router(v1_customer_router)
    
    # Enum Service router (versioned)
    from app.routes.enums import router as enums_router
    v1_enums_router = create_versioned_router("api", ["Enums"], APIVersion.V1)
    v1_enums_router.include_router(enums_router)
    app.include_router(v1_enums_router)
    
    # Admin Discretionary router (versioned)
    from app.routes.admin.discretionary import router as admin_discretionary_router
    v1_admin_discretionary_router = create_versioned_router("api", ["Admin Discretionary"], APIVersion.V1)
    v1_admin_discretionary_router.include_router(admin_discretionary_router)
    app.include_router(v1_admin_discretionary_router)
    
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

    # Static files (product images, placeholders, QR codes)
    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 