"""
Restaurant Staff Routes - Endpoints for restaurant staff operations

This module provides endpoints for restaurant staff to view and manage
daily orders, including privacy-safe customer information.
"""

from datetime import date as date_type
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import (
    DailyOrdersResponseSchema,
    VerifyAndHandoffRequest,
    VerifyAndHandoffResponse,
)
from app.services.crud_service import restaurant_service
from app.services.error_handling import handle_business_operation
from app.services.restaurant_staff_service import get_daily_orders, verify_and_handoff
from app.utils.db import db_read
from app.utils.log import log_info

router = APIRouter(prefix="/restaurant-staff", tags=["Restaurant Staff"])


@router.get("/daily-orders", response_model=DailyOrdersResponseSchema)
def get_restaurant_daily_orders(
    restaurant_id: UUID | None = Query(None, description="Filter to specific restaurant"),
    order_date: date_type | None = Query(None, description="Date to query (defaults to today)"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Get today's orders for restaurant staff.

    **Authorization**:
    - Supplier: Can access all restaurants within their institution_entity_id
    - Internal: Can access all restaurants across all institutions

    **Privacy**: Customer names displayed as "First L." format

    **Filtering**:
    - Omit restaurant_id: Returns all restaurants in institution_entity
    - Include restaurant_id: Returns only that restaurant (with auth check)

    **Query Parameters**:
    - restaurant_id (optional): UUID of specific restaurant to filter
    - order_date (optional): Date in YYYY-MM-DD format (defaults to today)

    **Response**:
    Returns orders grouped by restaurant with summary statistics.
    Each order includes customer name (privacy-safe), plate name,
    confirmation code, status, and pickup time information.
    """

    def _get_daily_orders():
        # 1. Determine institution_entity_id based on role
        institution_entity_id = None

        if current_user["role_type"] == "supplier":
            # Get user's institution, then institution_entity_id
            user_institution_query = """
                SELECT i.institution_id, ie.institution_entity_id
                FROM institution_info i
                INNER JOIN institution_entity_info ie ON i.institution_id = ie.institution_id
                WHERE i.institution_id = %s
                  AND i.is_archived = FALSE
                  AND ie.is_archived = FALSE
                LIMIT 1
            """

            result = db_read(user_institution_query, [str(current_user["institution_id"])], db)

            if not result:
                raise HTTPException(status_code=404, detail="Institution entity not found for user's institution")

            institution_entity_id = result[0]["institution_entity_id"]

            # If restaurant_id provided, verify it belongs to this institution_entity
            if restaurant_id:
                restaurant = restaurant_service.get_by_id(restaurant_id, db)
                if not restaurant:
                    raise HTTPException(status_code=404, detail="Restaurant not found")

                if restaurant.institution_entity_id != institution_entity_id:
                    raise HTTPException(status_code=403, detail="Access denied to this restaurant")

        elif current_user["role_type"] == "internal":
            # Internal users can access any restaurant
            # If restaurant_id provided, get its institution_entity_id
            if restaurant_id:
                restaurant = restaurant_service.get_by_id(restaurant_id, db)
                if not restaurant:
                    raise HTTPException(status_code=404, detail="Restaurant not found")
                institution_entity_id = restaurant.institution_entity_id
            else:
                # For employees without restaurant_id, require it
                # (Alternative: could return all restaurants across all entities,
                #  but that could be a very large result set)
                raise HTTPException(status_code=400, detail="Internal role must specify restaurant_id parameter")
        else:
            raise HTTPException(status_code=403, detail="Access denied: Must be Supplier or Internal role")

        # 2. Default date to today if not provided
        query_date = order_date or date_type.today()

        # 3. Call service
        result = get_daily_orders(institution_entity_id, query_date, restaurant_id, db)

        log_info(
            f"Retrieved daily orders for {len(result['restaurants'])} restaurant(s), "
            f"user_id={current_user['user_id']}, role={current_user['role_type']}"
        )

        return result

    return handle_business_operation(_get_daily_orders, "daily orders retrieval")


@router.post("/verify-and-handoff", response_model=VerifyAndHandoffResponse)
def verify_and_handoff_endpoint(
    request: VerifyAndHandoffRequest,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Verify confirmation code and transition order to Handed Out (Layer 2 kiosk verification).

    Auth: Supplier (any role, scoped to institution) or Internal.
    """

    def _verify():
        # Validate restaurant belongs to user's institution (same pattern as daily-orders)
        if current_user["role_type"] == "supplier":
            restaurant = restaurant_service.get_by_id(request.restaurant_id, db)
            if not restaurant:
                raise HTTPException(status_code=404, detail="Restaurant not found")

            user_institution_query = """
                SELECT ie.institution_entity_id
                FROM institution_info i
                INNER JOIN institution_entity_info ie ON i.institution_id = ie.institution_id
                WHERE i.institution_id = %s AND i.is_archived = FALSE AND ie.is_archived = FALSE
                LIMIT 1
            """
            result = db_read(user_institution_query, [str(current_user["institution_id"])], db)
            if not result:
                raise HTTPException(status_code=404, detail="Institution entity not found")
            if restaurant.institution_entity_id != result[0]["institution_entity_id"]:
                raise HTTPException(status_code=403, detail="Access denied to this restaurant")

        elif current_user["role_type"] != "internal":
            raise HTTPException(status_code=403, detail="Access restricted to restaurant staff")

        return verify_and_handoff(request.confirmation_code, request.restaurant_id, current_user["user_id"], db)

    return handle_business_operation(_verify, "code verification and handoff")
