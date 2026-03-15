from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from app.services.crud_service import plate_pickup_live_service
from app.services.plate_pickup_service import plate_pickup_service
from app.services.entity_service import get_enriched_plate_pickups
from app.schemas.consolidated_schemas import PlatePickupEnrichedResponseSchema
from app.auth.dependencies import get_current_user, oauth2_scheme
from app.dependencies.database import get_db
from app.utils.log import log_info, log_warning
from app.services.error_handling import handle_business_operation
import psycopg2.extensions

router = APIRouter(
    prefix="/plate-pickup", 
    tags=["Plate Pickup"],
    dependencies=[Depends(oauth2_scheme)]
)

# Request schemas
class ScanQRRequest(BaseModel):
    qr_code_payload: str  # Customer scans QR code and gets the payload string

# Response schemas for pending orders
class PlateOrderSummary(BaseModel):
    plate_name: str
    order_count: str  # "x1", "x2", "x3" - quantity for this person
    delivery_time_minutes: int
    plate_pickup_id: Optional[UUID] = Field(None, description="Use for POST /plate-pickup/{id}/complete")

class PickupTimeWindow(BaseModel):
    """Informational only - shows when pickup is planned"""
    start_time: datetime
    end_time: datetime
    window_minutes: int = 15

class PendingOrdersResponse(BaseModel):
    restaurant_id: UUID
    restaurant_name: str
    qr_code_id: UUID
    total_orders: int  # Total count of all plates
    total_plate_count: Optional[int] = Field(None, description="Same as total_orders; plates the assigned user picks up")
    plate_pickup_ids: Optional[List[UUID]] = Field(None, description="IDs for POST /plate-pickup/{id}/complete")
    orders: List[PlateOrderSummary]
    pickup_window: PickupTimeWindow  # Informational only
    status: str  # "Pending" or "Arrived"
    created_date: datetime

class ScanQRResponse(BaseModel):
    status: str
    message: str
    confirmation_code: Optional[str] = None
    expected_ready_time: Optional[datetime] = None
    delivery_time_minutes: Optional[int] = None

@router.get("/pending", response_model=Optional[PendingOrdersResponse])
def get_pending_order(
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get user's pending orders with company matching, order_count, and pickup window"""
    def _get_pending_order():
        result = plate_pickup_service.get_pending_orders_with_company_matching(
            current_user["user_id"], db
        )
        
        if not result:
            return None
        
        # Convert orders to response format
        orders = [
            PlateOrderSummary(
                plate_name=order['plate_name'],
                order_count=order['order_count'],
                delivery_time_minutes=order['delivery_time_minutes'],
                plate_pickup_id=order.get('plate_pickup_id'),
            )
            for order in result['orders']
        ]
        
        return PendingOrdersResponse(
            restaurant_id=result['restaurant_id'],
            restaurant_name=result['restaurant_name'],
            qr_code_id=result['qr_code_id'],
            total_orders=result['total_orders'],
            total_plate_count=result.get('total_plate_count', result['total_orders']),
            plate_pickup_ids=result.get('plate_pickup_ids'),
            orders=orders,
            pickup_window=PickupTimeWindow(**result['pickup_window']),
            status=result['status'],
            created_date=result['created_date']
        )
    
    return handle_business_operation(_get_pending_order, "pending order retrieval")

@router.get("/enriched", response_model=List[PlatePickupEnrichedResponseSchema])
def get_enriched_plate_pickups_endpoint(
    completed_only: bool = Query(False, description="When true (Customers only), filter to pickups with was_collected=true for order history page"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all plate pickups with enriched data (restaurant name, address details, product name, credit).
    Returns an array of enriched plate pickup records.
    
    Use completed_only=true for the customer order history page (pickups they have collected).
    
    Scoping:
    - Employees: See all plate pickups
    - Suppliers: See plate pickups for restaurants in their institution
    - Customers: See only their own plate pickups"""
    from app.security.entity_scoping import EntityScopingService, ENTITY_PLATE_PICKUP_LIVE
    
    def _get_enriched_pickups():
        scope = EntityScopingService.get_scope_for_entity(ENTITY_PLATE_PICKUP_LIVE, current_user)
        user_id = None
        
        # For Customers, apply user-level filtering
        if current_user.get("role_type") == "Customer":
            try:
                user_id_value = current_user["user_id"]
                # Check if it's already a UUID object, otherwise convert from string
                if isinstance(user_id_value, UUID):
                    user_id = user_id_value
                else:
                    user_id = UUID(user_id_value)
            except (ValueError, KeyError, TypeError) as e:
                log_warning(f"Invalid user_id in current_user: {current_user.get('user_id')}. Error: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid user ID format: {e}")
        
        return get_enriched_plate_pickups(
            db,
            scope=scope,
            user_id=user_id,
            include_archived=False,
            completed_only=completed_only if user_id else False
        )
    
    return handle_business_operation(_get_enriched_pickups, "enriched plate pickup retrieval")

@router.post("/scan-qr", response_model=ScanQRResponse)
def scan_qr_code(
    request: ScanQRRequest,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Scan QR code to mark customer as arrived - no pickup_id needed"""
    from app.utils.log import log_error
    import traceback
    
    def _scan_qr_code():
        try:
            result = plate_pickup_service.scan_qr_code_simplified(
                request.qr_code_payload, current_user, db
            )
            return ScanQRResponse(**result)
        except Exception as e:
            error_msg = f"Error in QR scan: {str(e)}\nTraceback: {traceback.format_exc()}"
            log_error(error_msg)
            # Also write to file for debugging
            with open("/tmp/qr_scan_error.log", "w") as f:
                f.write(error_msg)
            raise
    
    return handle_business_operation(_scan_qr_code, "QR code scan processing")

@router.post("/{pickup_id}/complete")
def complete_order(
    pickup_id: UUID, 
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Mark order as complete (DEPRECATED - Use POST /institution-bills/generate-daily-bills instead)
    
    This endpoint is deprecated and will be removed in a future version.
    For testing, use the billing endpoint which automatically completes orders as part of bill generation.
    In production, orders are automatically completed by the cron job when kitchen days close.
    """
    def _complete_order():
        return plate_pickup_service.complete_order(pickup_id, current_user, db)
    
    return handle_business_operation(_complete_order, "order completion")

# DELETE /plate-pickup/{pickup_id} – Delete (soft-delete) a plate pickup record
@router.delete("/{pickup_id}", response_model=dict)
def delete_plate_pickup(
    pickup_id: UUID, 
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Delete (soft-delete) a plate pickup record"""
    def _delete_plate_pickup():
        return plate_pickup_service.delete_pickup_record(pickup_id, current_user, db)
    
    return handle_business_operation(_delete_plate_pickup, "plate pickup deletion") 