from datetime import datetime
from typing import Optional
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import PlatePickupEnrichedResponseSchema
from app.services.entity_service import get_enriched_plate_pickups
from app.services.error_handling import handle_business_operation
from app.services.plate_pickup_service import plate_pickup_service
from app.utils.filter_builder import build_filter_conditions
from app.utils.log import log_warning

router = APIRouter(prefix="/plate-pickup", tags=["Plate Pickup"], dependencies=[Depends(oauth2_scheme)])


# Request schemas
class ScanQRRequest(BaseModel):
    qr_code_id: UUID = Field(..., description="QR code UUID from the signed URL")
    sig: str = Field(
        ...,
        min_length=16,
        max_length=16,
        pattern=r"^[0-9a-f]{16}$",
        description="HMAC-SHA256 signature (first 16 hex chars)",
    )


class CompleteOrderRequest(BaseModel):
    completion_type: str | None = Field(
        "user_confirmed",
        pattern=r"^(user_confirmed|user_disputed|timer_expired|confirmation_timeout|kitchen_day_close)$",
        description="How the pickup was completed: user_confirmed, user_disputed, timer_expired, confirmation_timeout, kitchen_day_close",
    )


# Response schemas for scan-qr
class PlateDetail(BaseModel):
    plate_name: str
    plate_id: str | None = None
    description: str | None = None


# Response schemas for pending orders
class PlateOrderSummary(BaseModel):
    plate_name: str
    order_count: str  # "x1", "x2", "x3" - quantity for this person
    delivery_time_minutes: int
    plate_pickup_id: UUID | None = Field(None, description="Use for POST /plate-pickup/{id}/complete")


class PickupTimeWindow(BaseModel):
    """Informational only - shows when pickup is planned"""

    start_time: datetime
    end_time: datetime
    window_minutes: int = 15


class PendingOrdersResponse(BaseModel):
    restaurant_id: UUID
    restaurant_name: str
    qr_code_id: UUID
    qr_code_sig: str = Field(..., description="HMAC signature for scan-qr endpoint")
    total_orders: int  # Total count of all plates
    total_plate_count: int | None = Field(None, description="Same as total_orders; plates the assigned user picks up")
    plate_pickup_ids: list[UUID] | None = Field(None, description="IDs for POST /plate-pickup/{id}/complete")
    orders: list[PlateOrderSummary]
    pickup_window: PickupTimeWindow  # Informational only
    status: str  # "pending" or "arrived"
    created_date: datetime


class ScanQRResponse(BaseModel):
    status: str
    message: str
    confirmation_code: str | None = None
    expected_ready_time: datetime | None = None
    delivery_time_minutes: int | None = None


@router.get("/pending", response_model=Optional[PendingOrdersResponse])
def get_pending_order(
    current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get user's pending orders with company matching, order_count, and pickup window"""

    def _get_pending_order():
        result = plate_pickup_service.get_pending_orders_with_company_matching(current_user["user_id"], db)

        if not result:
            return None

        # Convert orders to response format
        orders = [
            PlateOrderSummary(
                plate_name=order["plate_name"],
                order_count=order["order_count"],
                delivery_time_minutes=order["delivery_time_minutes"],
                plate_pickup_id=order.get("plate_pickup_id"),
            )
            for order in result["orders"]
        ]

        return PendingOrdersResponse(
            restaurant_id=result["restaurant_id"],
            restaurant_name=result["restaurant_name"],
            qr_code_id=result["qr_code_id"],
            qr_code_sig=result["qr_code_sig"],
            total_orders=result["total_orders"],
            total_plate_count=result.get("total_plate_count", result["total_orders"]),
            plate_pickup_ids=result.get("plate_pickup_ids"),
            orders=orders,
            pickup_window=PickupTimeWindow(**result["pickup_window"]),
            status=result["status"],
            created_date=result["created_date"],
        )

    return handle_business_operation(_get_pending_order, "pending order retrieval")


@router.get("/enriched", response_model=list[PlatePickupEnrichedResponseSchema])
def get_enriched_plate_pickups_endpoint(
    completed_only: bool = Query(
        False,
        description="When true (Customers only), filter to pickups with was_collected=true for order history page",
    ),
    status: str | None = Query(None, description="Filter by pickup status (e.g. pending, arrived, completed, cancelled)"),
    market_id: UUID | None = Query(None, description="Filter by market ID"),
    window_from: str | None = Query(None, description="Filter pickups with expected_completion_time on or after this timestamp (ISO 8601)"),
    window_to: str | None = Query(None, description="Filter pickups with expected_completion_time on or before this timestamp (ISO 8601)"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get all plate pickups with enriched data (restaurant name, address details, product name, credit).
    Returns an array of enriched plate pickup records.

    Optional filters: status, market_id, window_from, window_to (filter by expected_completion_time).
    Use completed_only=true for the customer order history page (pickups they have collected).

    Scoping:
    - Internal: See all plate pickups
    - Suppliers: See plate pickups for restaurants in their institution
    - Customers: See only their own plate pickups"""
    from app.security.entity_scoping import ENTITY_PLATE_PICKUP_LIVE, EntityScopingService

    def _get_enriched_pickups():
        scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE_PICKUP_LIVE, current_user)
        user_id = None

        # For Customers, apply user-level filtering
        if current_user.get("role_type") == "customer":
            try:
                user_id_value = current_user["user_id"]
                # Check if it's already a UUID object, otherwise convert from string
                if isinstance(user_id_value, UUID):
                    user_id = user_id_value
                else:
                    user_id = UUID(user_id_value)
            except (ValueError, KeyError, TypeError) as e:
                log_warning(f"Invalid user_id in current_user: {current_user.get('user_id')}. Error: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid user ID format: {e}") from None

        try:
            filter_conditions = build_filter_conditions(
                "pickups",
                {
                    "status": status,
                    "market_id": market_id,
                    "window_from": window_from,
                    "window_to": window_to,
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return get_enriched_plate_pickups(
            db,
            scope=scope,
            user_id=user_id,
            include_archived=False,
            completed_only=completed_only if user_id else False,
            additional_conditions=filter_conditions,
        )

    return handle_business_operation(_get_enriched_pickups, "enriched plate pickup retrieval")


@router.post("/scan-qr", response_model=ScanQRResponse)
def scan_qr_code(
    request: ScanQRRequest,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Scan signed QR code to mark customer as arrived. Returns pickup confirmation details."""

    def _scan_qr_code():
        result = plate_pickup_service.scan_qr_code_by_id(request.qr_code_id, request.sig, current_user, db)
        return ScanQRResponse(**result)

    return handle_business_operation(_scan_qr_code, "QR code scan processing")


@router.post("/{pickup_id}/hand-out")
def hand_out_order(
    pickup_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Mark order as Handed Out (restaurant gave the plate to customer). One-tap kiosk action.

    Transitions: Arrived → Handed Out. Auth: Supplier (any role) or Internal.
    """
    from app.services.restaurant_staff_service import hand_out_pickup

    def _hand_out():
        # Validate user is Supplier or Internal
        if current_user["role_type"] not in ("supplier", "internal"):
            raise HTTPException(status_code=403, detail="Access restricted to restaurant staff")
        return hand_out_pickup(pickup_id, current_user["user_id"], db)

    return handle_business_operation(_hand_out, "order hand-out")


@router.post("/{pickup_id}/complete")
def complete_order(
    pickup_id: UUID,
    request: CompleteOrderRequest | None = None,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Mark order as complete. Accepts optional completion_type for analytics.

    completion_type values:
    - user_confirmed: User tapped "I received my plate" (default)
    - user_disputed: User tapped "I didn't receive this" — flags for support review
    - timer_expired: Countdown timer ran out after all extensions exhausted
    - confirmation_timeout: 5-min timeout after Handed Out with no customer response
    - kitchen_day_close: Auto-completed by billing cron at end of kitchen day
    """

    def _complete_order():
        completion_type = (request.completion_type if request else "user_confirmed") or "user_confirmed"
        return plate_pickup_service.complete_order(pickup_id, current_user, db, completion_type=completion_type)

    return handle_business_operation(_complete_order, "order completion")


# DELETE /plate-pickup/{pickup_id} – Delete (soft-delete) a plate pickup record
@router.delete("/{pickup_id}", response_model=dict)
def delete_plate_pickup(
    pickup_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Delete (soft-delete) a plate pickup record"""

    def _delete_plate_pickup():
        return plate_pickup_service.delete_pickup_record(pickup_id, current_user, db)

    return handle_business_operation(_delete_plate_pickup, "plate pickup deletion")


# POST /plate-pickup/run-promotion – Manual trigger for kitchen-start promotion cron
@router.post("/run-promotion", response_model=dict, status_code=200)
def run_kitchen_start_promotion_manual(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Manually trigger the kitchen-start promotion: promote active plate_selection_info
    rows to plate_pickup_live (creates pickup records + restaurant transactions).

    Normally triggered by cron at kitchen-open time. This endpoint allows manual/test
    runs — essential for Postman E2E collections and dev testing.

    **Authorization**: Internal only (employee).
    """
    from app.services.cron.kitchen_start_promotion import run_kitchen_start_promotion

    result = run_kitchen_start_promotion()
    return result
