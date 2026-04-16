# app/routes/crud_routes.py
"""
Admin/System CRUD Routes

This module consolidates all standard CRUD routes using the route factory pattern.
These are operations that do NOT require user context - they are performed by administrators
or system processes and don't need user_id extraction from authenticated users.

Entities consolidated (Admin/System operations):
- Role, Product, Plan, Restaurant, CreditCurrency, Address, Geolocation
- QRCode, Institution, InstitutionEntity, InstitutionBankAccount
- PaymentMethod, Plate, Employer

NOTE: User-dependent routes (like Subscription, ClientBill, etc.) are in crud_routes_user.py
These routes require user_id extraction from the authenticated user context.

Benefits:
- Clear separation between admin/system vs user operations
- Consistent API patterns for admin operations
- Centralized route logic
- Automatic error handling
"""

from fastapi import APIRouter

from app.services.route_factory import (
    create_credit_currency_routes,
    create_geolocation_routes,
    create_institution_entity_routes,
    create_institution_routes,
    create_plan_routes,
    create_plate_routes,
    create_product_routes,
    create_restaurant_routes,
)

# Create consolidated router
crud_router = APIRouter()

# Add all CRUD routes
# create_role_routes removed - role_info table deprecated
crud_router.include_router(create_product_routes())
crud_router.include_router(create_plan_routes())
crud_router.include_router(create_restaurant_routes())
crud_router.include_router(create_credit_currency_routes())
# Note: qr_code_routes moved to custom router in application.py
# Note: subscription_router moved to crud_routes_user.py
crud_router.include_router(create_institution_routes())
# Note: payment_method_routes moved to crud_routes_user.py
crud_router.include_router(create_plate_routes())
crud_router.include_router(create_geolocation_routes())
crud_router.include_router(create_institution_entity_routes())


# Export the consolidated router
__all__ = ["crud_router"]
