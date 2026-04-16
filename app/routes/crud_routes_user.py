# app/routes/crud_routes_user.py
"""
User-Dependent CRUD Routes

This module consolidates all CRUD routes that require user context (user_id extraction).
These are operations performed by end-users who log into the app and need their user_id
automatically set from the authenticated user context.

Entities requiring user context:
- Subscription (user_id from current_user)
- PaymentMethod (user_id from current_user)
- ClientBill (user_id from current_user)
- PlateSelection (user_id from current_user)
- Any other user-owned entities

Benefits:
- Clear separation between admin/system routes vs user routes
- Automatic user_id extraction from authenticated context
- Consistent user context handling
- Easier to maintain user-specific business logic
"""

from fastapi import APIRouter

from app.routes.subscription_payment import router as subscription_payment_router
from app.services.route_factory import create_payment_method_routes, create_subscription_routes

# Create consolidated router for user-dependent routes
crud_router_user = APIRouter()

# Subscription payment (with-payment, confirm-payment) must be registered before generic subscription CRUD so /with-payment is matched
crud_router_user.include_router(subscription_payment_router)
# Add all user-dependent CRUD routes using enhanced route factory
crud_router_user.include_router(create_subscription_routes())
crud_router_user.include_router(create_payment_method_routes())

# Note: Plate selection routes are handled by custom business logic service
# in app/routes/plate_selection.py instead of generic CRUD routes

# Add other user-dependent routes as they are identified
# crud_router_user.include_router(create_client_bill_routes())
