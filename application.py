# application.py
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.auth.middleware.permission_cache import PermissionCacheMiddleware
from app.utils.db_pool import get_db_pool
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
from app.routes.employer import router as employer_router
from app.routes.address import router as address_router
from app.routes.location_info import router as location_info_router
from app.routes.institution_bank_account import router as institution_bank_account_router
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
from app.routes.payment_methods.fintech_link_assignment import router as fintech_link_assignment_router
from app.routes.payment_methods.fintech_link import router as fintech_link_router
from app.routes.payment_methods.client_payment_attempt import router as client_payment_attempt_router
from app.routes.payment_methods.institution_payment_attempt import router as institution_payment_attempt_router

# Billing routes
from app.routes.billing.client_bill import router as client_bill_router
from app.routes.billing.institution_bill import router as institution_bill_router

# Admin routes
from app.routes.admin.archival import router as archival_admin_router
from app.routes.admin.archival_config import router as archival_config_admin_router

# Configure logging - using the custom logger from app.utils.log
from app.utils.log import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("App startup: Initialize resources.")
    # Initialize connection pool
    app.state.db_pool = get_db_pool()
    yield
    # Shutdown
    logger.info("App shutdown: Cleanup resources.")
    # Close connection pool
    if hasattr(app.state, 'db_pool') and app.state.db_pool:
        app.state.db_pool.close_pool()

def create_app() -> FastAPI:
    app = FastAPI(title="Kitchen API", lifespan=lifespan)

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
    
    @app.get("/")
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
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint for load balancers and monitoring tools"""
        return {"status": "healthy"}
    
    @app.get("/api/")
    async def api_root():
        """Redirect to current API version"""
        return RedirectResponse(url="/api/v1/", status_code=307)
    
    # Admin/infrastructure routes (non-versioned)
    # main_router includes: admin_discretionary_router, super_admin_discretionary_router, and /pool-stats
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
    
    v1_employer_router = create_versioned_router("api", ["Employers"], APIVersion.V1)
    v1_employer_router.include_router(employer_router)
    app.include_router(v1_employer_router)
    
    v1_address_router = create_versioned_router("api", ["Addresses"], APIVersion.V1)
    v1_address_router.include_router(address_router)
    app.include_router(v1_address_router)
    
    v1_location_info_router = create_versioned_router("api", ["Location Info"], APIVersion.V1)
    v1_location_info_router.include_router(location_info_router)
    app.include_router(v1_location_info_router)
    
    v1_institution_bank_account_router = create_versioned_router("api", ["Institution Bank Accounts"], APIVersion.V1)
    v1_institution_bank_account_router.include_router(institution_bank_account_router)
    app.include_router(v1_institution_bank_account_router)
    
    v1_qr_code_router = create_versioned_router("api", ["QR Codes"], APIVersion.V1)
    v1_qr_code_router.include_router(qr_code_router)
    app.include_router(v1_qr_code_router)
    
    v1_institution_entity_router = create_versioned_router("api", ["Institution Entities"], APIVersion.V1)
    v1_institution_entity_router.include_router(institution_entity_router)
    app.include_router(v1_institution_entity_router)
    
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
    
    # Payment method routes (non-versioned routes without versioned equivalents)
    app.include_router(mercado_pago_router)
    
    # Versioned payment method routes (v1)
    v1_fintech_link_assignment_router = create_versioned_router("api", ["Fintech Link Assignment"], APIVersion.V1)
    v1_fintech_link_assignment_router.include_router(fintech_link_assignment_router)
    app.include_router(v1_fintech_link_assignment_router)
    
    v1_fintech_link_router = create_versioned_router("api", ["Fintech Link"], APIVersion.V1)
    v1_fintech_link_router.include_router(fintech_link_router)
    app.include_router(v1_fintech_link_router)
    
    v1_client_payment_attempt_router = create_versioned_router("api", ["Client Payment Attempts"], APIVersion.V1)
    v1_client_payment_attempt_router.include_router(client_payment_attempt_router)
    app.include_router(v1_client_payment_attempt_router)
    
    v1_institution_payment_attempt_router = create_versioned_router("api", ["Institution Payment Attempts"], APIVersion.V1)
    v1_institution_payment_attempt_router.include_router(institution_payment_attempt_router)
    app.include_router(v1_institution_payment_attempt_router)
    
    # Billing routes (non-versioned routes without versioned equivalents)
    # Note: client_bill_router is now versioned - moved to versioned section below
    
    # Versioned billing routes (v1)
    v1_client_bill_router = create_versioned_router("api", ["Client Bills"], APIVersion.V1)
    v1_client_bill_router.include_router(client_bill_router)
    app.include_router(v1_client_bill_router)
    
    v1_institution_bill_router = create_versioned_router("api", ["Institution Bills"], APIVersion.V1)
    v1_institution_bill_router.include_router(institution_bill_router)
    app.include_router(v1_institution_bill_router)
    
    # Admin routes
    app.include_router(archival_admin_router)
    app.include_router(archival_config_admin_router)

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 