"""
Plate Pickup Business Logic Service

This service contains all business logic related to plate pickup operations,
including QR code scanning, order completion, and pickup management.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
from typing import Optional, Dict, Any
from fastapi import HTTPException
import psycopg2.extensions

from app.dto.models import (
    PlatePickupLiveDTO, QRCodeDTO, RestaurantDTO, PlateSelectionDTO, 
    PlateDTO, RestaurantTransactionDTO
)
from app.services.crud_service import (
    plate_pickup_live_service, qr_code_service, restaurant_service,
    plate_selection_service, plate_service, restaurant_transaction_service,
    update_balance_on_arrival, mark_collected_with_balance_update
)
from app.utils.log import log_info, log_warning, log_error
from app.utils.error_messages import pickup_record_not_found, plate_selection_not_found, plate_not_found
from app.config import Status


class PlatePickupService:
    """Service for handling plate pickup business logic"""
    
    def __init__(self):
        pass
    
    def scan_qr_code(
        self, 
        pickup_id: UUID, 
        qr_code_payload: str, 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> Dict[str, Any]:
        """
        Process QR code scan for customer arrival.
        
        Args:
            pickup_id: ID of the pickup record
            qr_code_payload: QR code payload string from scanned QR code
            current_user: Current user information
            db: Database connection
            
        Returns:
            Dictionary containing scan result with status and message
            
        Raises:
            HTTPException: For various validation and authorization errors
        """
        # 1. Get the pickup record and verify it belongs to the user
        pickup_record = self._get_and_validate_pickup_record(pickup_id, current_user, db)
        
        # 2. Validate QR code exists in our system
        qr_code = self._validate_qr_code_by_payload(qr_code_payload, db)
        
        # 3. Check if QR code belongs to the correct restaurant
        self._validate_restaurant_match(pickup_record, qr_code, db)
        
        # 4. Get plate delivery time for SLA calculation
        plate = self._get_plate_delivery_info(pickup_record, db)
        
        # 5. Calculate expected completion time
        arrival_time = datetime.now()
        expected_completion_time = arrival_time + timedelta(minutes=plate.delivery_time_minutes)
        
        try:
            # 6. Update plate_pickup_live record (commit=False for atomic transaction)
            self._update_pickup_record_arrival(pickup_id, arrival_time, expected_completion_time, current_user, db)
            
            # 7. Update corresponding restaurant_transaction and restaurant balance (commit=False for atomic transaction)
            self._update_restaurant_transaction_arrival(pickup_record, arrival_time, expected_completion_time, plate, current_user, db)
            
            # Commit all operations atomically
            db.commit()
            log_info(f"Customer {current_user['user_id']} arrived at restaurant for pickup {pickup_id} (atomic transaction)")
            
            return {
                "status": "arrived",
                "message": f"Welcome! Your order will be ready in {plate.delivery_time_minutes} minutes",
                "expected_ready_time": expected_completion_time,
                "delivery_time_minutes": plate.delivery_time_minutes
            }
        except HTTPException:
            # HTTPException already handled rollback, just re-raise
            raise
        except Exception as e:
            # Rollback on any unexpected error
            db.rollback()
            log_error(f"Error processing QR code scan: {e}")
            raise HTTPException(status_code=500, detail="Failed to process QR code scan")
    
    def complete_order(
        self, 
        pickup_id: UUID, 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> Dict[str, Any]:
        """
        Mark order as complete.
        
        All status updates are performed atomically - either all succeed or all are rolled back.
        
        Args:
            pickup_id: ID of the pickup record
            current_user: Current user information
            db: Database connection
            
        Returns:
            Dictionary containing completion result
            
        Raises:
            HTTPException: For various validation and authorization errors
        """
        try:
            # Get the pickup record
            pickup_record = self._get_and_validate_pickup_record(pickup_id, current_user, db)
            
            if pickup_record.status not in ['Arrived', 'Pending']:
                raise HTTPException(status_code=400, detail=f"Cannot complete order with status {pickup_record.status}")
            
            completion_time = datetime.now()
            
            # Update plate_pickup_live (do NOT archive immediately - keep for customer service)
            # All operations use commit=False for atomic transaction
            self._update_pickup_record_completion(pickup_id, completion_time, current_user, db)
            
            # Update restaurant_transaction with balance adjustment if needed
            self._update_restaurant_transaction_completion(pickup_record, completion_time, current_user, db)
            
            # Commit all operations atomically
            db.commit()
            log_info(f"Order {pickup_id} completed for user {current_user['user_id']} (atomic transaction)")
            
            return {"status": "completed", "message": "Order completed successfully"}
        except HTTPException:
            # HTTPException already handled rollback, just re-raise
            raise
        except Exception as e:
            # Rollback on any unexpected error
            db.rollback()
            log_error(f"Error completing order: {e}")
            raise HTTPException(status_code=500, detail="Failed to complete order")
    
    def delete_pickup_record(
        self, 
        pickup_id: UUID, 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> Dict[str, str]:
        """
        Delete (soft-delete) a plate pickup record.
        
        Args:
            pickup_id: ID of the pickup record
            current_user: Current user information
            db: Database connection
            
        Returns:
            Dictionary containing deletion result
            
        Raises:
            HTTPException: For various validation and authorization errors
        """
        # Get the pickup record to check authorization
        pickup_record = self._get_and_validate_pickup_record(pickup_id, current_user, db)
        
        # Only allow deletion if status is Pending (not arrived or completed)
        if pickup_record.status != Status.PENDING:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot delete pickup record with status {pickup_record.status}. Only pending orders can be deleted."
            )
        
        # Soft delete the pickup record
        deleted_count = plate_pickup_live_service.soft_delete(pickup_id, db)
        if deleted_count == 0:
            raise pickup_record_not_found(pickup_id)
        
        log_info(f"Deleted plate pickup record with ID: {pickup_id}")
        return {"detail": "Plate pickup record deleted successfully"}
    
    def _get_and_validate_pickup_record(
        self, 
        pickup_id: UUID, 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> PlatePickupLiveDTO:
        """Get pickup record and validate user authorization"""
        pickup_record_result = plate_pickup_live_service.get_by_id(pickup_id, db)
        if not pickup_record_result:
            raise pickup_record_not_found(pickup_id)
        
        pickup_record = pickup_record_result
        
        if pickup_record.user_id != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to access this pickup record")
        
        return pickup_record
    
    def _validate_qr_code(self, qr_code_id: UUID, db: psycopg2.extensions.connection) -> QRCodeDTO:
        """Validate QR code exists in system"""
        qr_code_result = qr_code_service.get_by_id(qr_code_id, db)
        if not qr_code_result:
            raise HTTPException(status_code=400, detail="This QR code is not recognized")
        
        return qr_code_result
    
    def _validate_qr_code_by_payload(self, qr_code_payload: str, db: psycopg2.extensions.connection) -> QRCodeDTO:
        """Validate QR code exists in system by payload"""
        from app.utils.db import db_read
        
        query = """
        SELECT qr_code_id, restaurant_id, qr_code_payload, is_archived, status, created_date, modified_by, modified_date
        FROM qr_code 
        WHERE qr_code_payload = %s 
        AND is_archived = FALSE 
        AND status = 'Active'
        LIMIT 1
        """
        result = db_read(query, (qr_code_payload,), connection=db, fetch_one=True)
        if not result:
            raise HTTPException(status_code=400, detail="This QR code is not recognized")
        
        return QRCodeDTO(**result)
    
    def _validate_restaurant_match(
        self, 
        pickup_record: PlatePickupLiveDTO, 
        qr_code: QRCodeDTO, 
        db: psycopg2.extensions.connection
    ) -> None:
        """Validate QR code belongs to correct restaurant"""
        if qr_code.restaurant_id != pickup_record.restaurant_id:
            # Get restaurant names for better error message
            scanned_restaurant = restaurant_service.get_by_id(qr_code.restaurant_id, db)
            ordered_restaurant = restaurant_service.get_by_id(pickup_record.restaurant_id, db)
            
            scanned_name = "Unknown Restaurant"
            ordered_name = "Unknown Restaurant"
            
            if scanned_restaurant:
                scanned_name = scanned_restaurant.name
                
            if ordered_restaurant:
                ordered_name = ordered_restaurant.name
            
            raise HTTPException(
                status_code=400,
                detail=f"You're at {scanned_name}, but your order is for {ordered_name}"
            )
    
    def _get_plate_delivery_info(
        self, 
        pickup_record: PlatePickupLiveDTO, 
        db: psycopg2.extensions.connection
    ) -> PlateDTO:
        """Get plate delivery information for SLA calculation"""
        # Get plate_id from the plate_selection since plate_pickup_live stores product_id, not plate_id
        selection_result = plate_selection_service.get_by_id(pickup_record.plate_selection_id, db)
        if not selection_result:
            raise plate_selection_not_found()
            
        selection = selection_result
        
        plate_result = plate_service.get_by_id(selection.plate_id, db)
        if not plate_result:
            raise plate_not_found()
            
        return plate_result
    
    def _update_pickup_record_arrival(
        self, 
        pickup_id: UUID, 
        arrival_time: datetime, 
        expected_completion_time: datetime, 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> None:
        """Update pickup record with arrival information (commit=False for atomic transaction)"""
        update_data = {
            "status": Status.ARRIVED,
            "arrival_time": arrival_time,
            "expected_completion_time": expected_completion_time,
            "modified_by": current_user["user_id"]
        }
        
        success = plate_pickup_live_service.update(pickup_id, update_data, db, commit=False)
        if not success:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to update pickup record")
    
    def _update_restaurant_transaction_arrival(
        self, 
        pickup_record: PlatePickupLiveDTO, 
        arrival_time: datetime, 
        expected_completion_time: datetime, 
        plate: PlateDTO, 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> None:
        """Update restaurant transaction and balance for arrival (commit=False for atomic transaction)"""
        restaurant_transaction = restaurant_transaction_service.get_by_plate_selection(pickup_record.plate_selection_id, db)
        if not restaurant_transaction:
            db.rollback()
            raise HTTPException(status_code=404, detail="Restaurant transaction not found")
        
        current_final_amount = restaurant_transaction.final_amount or Decimal("0")
        credit_amount = plate.credit if isinstance(plate.credit, Decimal) else Decimal(str(plate.credit))
        rt_update_data = {
            "status": Status.ARRIVED,
            "arrival_time": arrival_time,
            "expected_completion_time": expected_completion_time,
            "final_amount": credit_amount,
            "was_collected": True,
            "modified_by": current_user["user_id"]
        }
        
        success = restaurant_transaction_service.update(restaurant_transaction.transaction_id, rt_update_data, db, commit=False)
        if not success:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to update restaurant transaction")
        
        # Update restaurant balance - customer actually showed up!
        # This is when the restaurant gets paid the difference to reach full amount
        # Customer showed up, so restaurant gets the difference between full amount and discounted amount
        credit_difference = float(credit_amount - current_final_amount)
        balance_updated = update_balance_on_arrival(
            restaurant_transaction.restaurant_id,
            credit_difference,  # Add the difference to reach full amount
            db,
            commit=False  # Defer commit for atomic transaction
        )
        
        if not balance_updated:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to update restaurant balance for arrival")
        
        log_info(f"Restaurant balance updated for customer arrival - transaction {restaurant_transaction.transaction_id} (commit deferred)")
    
    def _update_pickup_record_completion(
        self, 
        pickup_id: UUID, 
        completion_time: datetime, 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> None:
        """Update pickup record with completion information (commit=False for atomic transaction)"""
        update_data = {
            "status": Status.COMPLETE,
            "is_archived": False,  # Keep active per retention policy (archived after 30 days)
            "completion_time": completion_time,
            "was_collected": True,
            "modified_by": current_user["user_id"]
        }
        
        success = plate_pickup_live_service.update(pickup_id, update_data, db, commit=False)
        if not success:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to update pickup record")
    
    def _update_restaurant_transaction_completion(
        self, 
        pickup_record: PlatePickupLiveDTO, 
        completion_time: datetime, 
        current_user: Dict[str, Any], 
        db: psycopg2.extensions.connection
    ) -> None:
        """Update restaurant transaction for completion (commit=False for atomic transaction)"""
        restaurant_transaction = restaurant_transaction_service.get_by_plate_selection(pickup_record.plate_selection_id, db)
        if not restaurant_transaction:
            db.rollback()
            raise HTTPException(status_code=404, detail="Restaurant transaction not found")
        
        # First update the transaction status and completion time
        rt_update_data = {
            "status": Status.COMPLETE,
            "completion_time": completion_time,
            "modified_by": current_user["user_id"]
        }
        success = restaurant_transaction_service.update(restaurant_transaction.transaction_id, rt_update_data, db, commit=False)
        if not success:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to update restaurant transaction")
        
        # Then mark as collected - no additional balance update needed
        # Since customer showed up, restaurant already got full credit amount on arrival
        # Just update the transaction status to mark as collected
        success = mark_collected_with_balance_update(
            restaurant_transaction.transaction_id,
            restaurant_transaction.restaurant_id,
            0.0,  # No additional balance update - already got full amount on arrival
            db,
            commit=False  # Defer commit for atomic transaction
        )
        if not success:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to mark transaction as collected")


    def get_pending_orders_with_company_matching(
        self, 
        user_id: UUID, 
        db: psycopg2.extensions.connection
    ) -> Optional[Dict[str, Any]]:
        """
        Get all pending orders for user and colleagues, grouped by restaurant.
        Returns order details with order_count (x1, x2, x3) and pickup window.
        
        Args:
            user_id: Current user ID
            db: Database connection
            
        Returns:
            Dictionary with pending orders or None if no orders found
        """
        from app.utils.db import db_read
        import pytz
        
        # Query for pending orders with company matching
        query = """
        SELECT 
            ppl.restaurant_id,
            r.name as restaurant_name,
            qc.qr_code_id,
            qc.qr_code_payload,
            ppl.status,
            MIN(ppl.created_date) as earliest_order_time,
            COUNT(*) as total_orders,
            STRING_AGG(
                CONCAT(prod.name, ':', 
                       CASE 
                           WHEN ppl.user_id = %s THEN 'x1'
                           WHEN pp.user_id = %s THEN 'x2'
                           ELSE 'x3'
                       END, ':',
                       COALESCE(p.delivery_time_minutes::text, '15')
                ), 
                '|'
            ) as orders_data
        FROM plate_pickup_live ppl
        LEFT JOIN pickup_preferences pp ON ppl.plate_selection_id = pp.plate_selection_id
        LEFT JOIN restaurant_info r ON ppl.restaurant_id = r.restaurant_id
        LEFT JOIN qr_code qc ON ppl.restaurant_id = qc.restaurant_id
        LEFT JOIN plate_selection ps ON ppl.plate_selection_id = ps.plate_selection_id
        LEFT JOIN plate_info p ON ps.plate_id = p.plate_id
        LEFT JOIN product_info prod ON p.product_id = prod.product_id
        WHERE ppl.status IN ('Pending', 'Arrived') 
        AND ppl.is_archived = FALSE
        AND qc.is_archived = FALSE
        AND qc.status = 'Active'
        AND (
            ppl.user_id = %s
            OR pp.user_id = %s
            OR pp.matched_with_preference_id IN (
                SELECT preference_id FROM pickup_preferences 
                WHERE user_id = %s
            )
        )
        GROUP BY ppl.restaurant_id, r.name, qc.qr_code_id, qc.qr_code_payload, ppl.status
        ORDER BY MIN(ppl.created_date) DESC
        LIMIT 1
        """
        
        result = db_read(query, (
            str(user_id), str(user_id),  # For order_count calculation
            str(user_id), str(user_id), str(user_id)  # For WHERE clause
        ), connection=db, fetch_one=True)
        
        if not result:
            return None
        
        # Get restaurant timezone for pickup window calculation
        restaurant = restaurant_service.get_by_id(UUID(result['restaurant_id']), db)
        if not restaurant:
            log_warning(f"Restaurant {result['restaurant_id']} not found")
            return None
            
        from app.services.crud_service import address_service
        address = address_service.get_by_id(restaurant.address_id, db)
        if not address:
            log_warning(f"Address not found for restaurant {restaurant.restaurant_id}")
            return None
        
        # Calculate pickup window in restaurant's local timezone
        restaurant_tz = pytz.timezone(address.timezone)
        earliest_time_utc = result['earliest_order_time']
        
        # Convert to restaurant's local time
        if isinstance(earliest_time_utc, str):
            from dateutil.parser import parse
            earliest_time_utc = parse(earliest_time_utc)
        
        earliest_time_local = earliest_time_utc.astimezone(restaurant_tz)
        
        # Calculate pickup window constrained to 11:30-14:30
        pickup_window = self._calculate_pickup_window(earliest_time_local)
        
        # Parse orders_data string
        orders = []
        if result['orders_data']:
            for order_str in result['orders_data'].split('|'):
                if order_str:
                    parts = order_str.split(':')
                    if len(parts) >= 2:
                        orders.append({
                            'plate_name': parts[0],
                            'order_count': parts[1],
                            'delivery_time_minutes': int(parts[2]) if len(parts) > 2 else 15
                        })
        
        return {
            'restaurant_id': UUID(result['restaurant_id']),
            'restaurant_name': result['restaurant_name'],
            'qr_code_id': UUID(result['qr_code_id']),
            'qr_code_payload': result['qr_code_payload'],
            'total_orders': result['total_orders'],
            'orders': orders,
            'pickup_window': pickup_window,
            'status': result['status'],
            'created_date': earliest_time_utc
        }
    
    def _calculate_pickup_window(self, earliest_order_time: datetime) -> Dict[str, Any]:
        """
        Calculate pickup window constrained to 11:30-14:30 local time.
        
        Args:
            earliest_order_time: Earliest order time in local timezone
            
        Returns:
            Dictionary with start_time, end_time, and window_minutes
        """
        from datetime import time
        
        # Define allowed time window (11:30 AM - 2:30 PM)
        window_start_time = time(11, 30)
        window_end_time = time(14, 30)
        
        # Get the date of the order
        order_date = earliest_order_time.date()
        
        # Start with the earliest possible time for the day (11:30 AM)
        window_start = datetime.combine(order_date, window_start_time)
        window_end = window_start + timedelta(minutes=15)
        
        # Ensure window doesn't go past 2:30 PM
        if window_end.time() > window_end_time:
            # If it would go past 2:30, set end to exactly 2:30
            window_end = datetime.combine(order_date, window_end_time)
        
        return {
            'start_time': window_start,
            'end_time': window_end,
            'window_minutes': 15
        }
    
    def scan_qr_code_simplified(
        self,
        qr_code_payload: str,
        current_user: Dict[str, Any],
        db: psycopg2.extensions.connection
    ) -> Dict[str, Any]:
        """
        Simplified QR code scanning with 4 error cases and no window enforcement.
        
        Args:
            qr_code_payload: QR code payload from scanned QR code
            current_user: Current user information
            db: Database connection
            
        Returns:
            Dictionary with scan result
            
        Raises:
            HTTPException: For various error cases
        """
        user_id = current_user["user_id"]
        
        # Case 4: Validate QR code exists
        if not self._validate_qr_code_exists(qr_code_payload, db):
            return {
                "status": "error",
                "message": "This QR code is not recognized by our system",
                "suggestion": "Please scan a valid restaurant QR code"
            }
        
        # Extract restaurant_id from payload
        try:
            restaurant_id = self._extract_restaurant_id(qr_code_payload)
        except ValueError:
            return {
                "status": "error",
                "message": "Invalid QR code format",
                "suggestion": "Please scan a valid restaurant QR code"
            }
        
        # Get simple order count for this restaurant
        order_count = self._get_simple_order_count(user_id, restaurant_id, db)
        
        if order_count > 0:
            # Case 1: Success - customer has orders at this restaurant
            confirmation_code = self._generate_confirmation_code()
            self._update_orders_arrival(user_id, restaurant_id, confirmation_code, db)
            
            return {
                "status": "success",
                "message": "Order confirmed! Show this to restaurant staff",
                "confirmation_code": confirmation_code
            }
        else:
            # Check if they have orders elsewhere or no orders at all
            return self._handle_wrong_restaurant_or_no_orders(user_id, restaurant_id, db)
    
    def _validate_qr_code_exists(self, qr_code_payload: str, db: psycopg2.extensions.connection) -> bool:
        """Check if QR code payload exists in our system"""
        from app.utils.db import db_read
        
        query = """
        SELECT 1 FROM qr_code 
        WHERE qr_code_payload = %s 
        AND is_archived = FALSE 
        AND status = 'Active'
        LIMIT 1
        """
        result = db_read(query, (qr_code_payload,), connection=db, fetch_one=True)
        return result is not None
    
    def _extract_restaurant_id(self, qr_code_payload: str) -> UUID:
        """Extract restaurant_id from QR code payload"""
        if not qr_code_payload.startswith("restaurant_id:"):
            raise ValueError("Invalid QR code format")
        
        restaurant_id_str = qr_code_payload.replace("restaurant_id:", "")
        try:
            return UUID(restaurant_id_str)
        except ValueError as e:
            raise ValueError(f"Invalid restaurant ID: {e}")
    
    def _get_simple_order_count(self, user_id: UUID, restaurant_id: UUID, db: psycopg2.extensions.connection) -> int:
        """Simple count query for QR scan - optimized for speed"""
        from app.utils.db import db_read
        
        query = """
        SELECT COUNT(*) as count
        FROM plate_pickup_live ppl
        LEFT JOIN pickup_preferences pp ON ppl.plate_selection_id = pp.plate_selection_id
        WHERE ppl.restaurant_id = %s
        AND ppl.status = 'Pending' 
        AND ppl.is_archived = FALSE
        AND (
            ppl.user_id = %s
            OR pp.user_id = %s
            OR pp.matched_with_preference_id IN (
                SELECT preference_id FROM pickup_preferences 
                WHERE user_id = %s
            )
        )
        """
        
        result = db_read(query, (
            str(restaurant_id),
            str(user_id), str(user_id), str(user_id)
        ), connection=db, fetch_one=True)
        
        return result['count'] if result else 0
    
    def _handle_wrong_restaurant_or_no_orders(
        self, 
        user_id: UUID, 
        scanned_restaurant_id: UUID, 
        db: psycopg2.extensions.connection
    ) -> Dict[str, Any]:
        """Handle cases where customer scanned wrong restaurant or has no orders"""
        from app.utils.db import db_read
        
        # Check if they have orders elsewhere
        query = """
        SELECT DISTINCT ppl.restaurant_id, r.name as restaurant_name
        FROM plate_pickup_live ppl
        LEFT JOIN pickup_preferences pp ON ppl.plate_selection_id = pp.plate_selection_id
        LEFT JOIN restaurant_info r ON ppl.restaurant_id = r.restaurant_id
        WHERE ppl.status = 'Pending' 
        AND ppl.is_archived = FALSE
        AND (
            ppl.user_id = %s
            OR pp.user_id = %s
            OR pp.matched_with_preference_id IN (
                SELECT preference_id FROM pickup_preferences 
                WHERE user_id = %s
            )
        )
        LIMIT 1
        """
        
        result = db_read(query, (str(user_id), str(user_id), str(user_id)), connection=db, fetch_one=True)
        
        if result:
            # Case 2: Wrong restaurant
            return {
                "status": "error",
                "message": f"You're at the wrong restaurant. Your order is at {result['restaurant_name']}",
                "correct_restaurant": {
                    "name": result['restaurant_name'],
                    "restaurant_id": result['restaurant_id']
                }
            }
        else:
            # Case 3: No orders
            return {
                "status": "error",
                "message": "You don't have any pending orders to pickup today",
                "suggestion": "Please place an order first before scanning QR codes"
            }
    
    def _generate_confirmation_code(self) -> str:
        """Generate a 6-character alphanumeric confirmation code"""
        import random
        import string
        
        characters = string.ascii_uppercase + string.digits
        return ''.join(random.choice(characters) for _ in range(6))
    
    def _update_orders_arrival(
        self, 
        user_id: UUID, 
        restaurant_id: UUID, 
        confirmation_code: str,
        db: psycopg2.extensions.connection
    ) -> None:
        """
        Update all orders for this user at this restaurant to 'Arrived' status.
        Also updates restaurant transactions and balance for pay-on-arrival model.
        """
        from app.services.crud_service import update_balance_on_arrival, plate_service
        from app.utils.db import db_read
        
        log_info(f"Starting _update_orders_arrival for user {user_id} at restaurant {restaurant_id}")
        
        arrival_time = datetime.now()
        expected_completion = arrival_time + timedelta(minutes=15)
        
        # Step 1: Get all affected plate_selection_ids first
        with db.cursor() as cursor:
            select_query = """
            SELECT ppl.plate_selection_id, ppl.plate_id
            FROM plate_pickup_live ppl
            WHERE ppl.restaurant_id = %s
            AND ppl.status = 'Pending'
            AND ppl.is_archived = FALSE
            AND (
                ppl.user_id = %s
                OR ppl.plate_selection_id IN (
                    SELECT plate_selection_id FROM pickup_preferences 
                    WHERE user_id = %s
                )
            )
            """
            cursor.execute(select_query, (str(restaurant_id), str(user_id), str(user_id)))
            selections = cursor.fetchall()
        
        if not selections:
            log_warning(f"No pending orders found for user {user_id} at restaurant {restaurant_id}")
            return
        
        log_info(f"Found {len(selections)} pending order(s) to update")
        
        # Step 2: Update plate_pickup_live records
        with db.cursor() as cursor:
            update_pickup_query = """
            UPDATE plate_pickup_live
            SET status = 'Arrived',
                arrival_time = %s,
                expected_completion_time = %s,
                confirmation_code = %s,
                was_collected = TRUE,
                modified_date = CURRENT_TIMESTAMP
            WHERE restaurant_id = %s
            AND status = 'Pending'
            AND is_archived = FALSE
            AND (
                user_id = %s
                OR plate_selection_id IN (
                    SELECT plate_selection_id FROM pickup_preferences 
                    WHERE user_id = %s
                )
            )
            """
            cursor.execute(update_pickup_query, (
                arrival_time,
                expected_completion,
                confirmation_code,
                str(restaurant_id),
                str(user_id),
                str(user_id)
            ))
            db.commit()
        
        log_info(f"Updated {len(selections)} plate_pickup_live record(s)")
        
        # Step 3: Update restaurant transactions and calculate balance increase
        total_balance_increase = 0.0
        for selection in selections:
            try:
                plate_selection_id = selection[0]
                plate_id = selection[1]
                
                log_info(f"Processing selection: plate_selection_id={plate_selection_id}, plate_id={plate_id}")
                
                # Get the plate to calculate the balance difference
                if isinstance(plate_id, str):
                    plate_id_uuid = UUID(plate_id)
                else:
                    plate_id_uuid = plate_id
                
                plate = plate_service.get_by_id(plate_id_uuid, db)
                if not plate:
                    log_warning(f"Plate not found for plate_id {plate_id}")
                    continue
                
                credit_decimal = plate.credit if isinstance(plate.credit, Decimal) else Decimal(str(plate.credit))
                
                # Retrieve existing transaction to capture discounted amount
                with db.cursor() as cursor:
                    get_transaction_query = """
                    SELECT transaction_id, final_amount 
                    FROM restaurant_transaction
                    WHERE plate_selection_id = %s AND is_archived = FALSE
                    FOR UPDATE
                    """
                    cursor.execute(get_transaction_query, (str(plate_selection_id),))
                    transaction_result = cursor.fetchone()
                    
                    discounted_decimal = credit_decimal
                    if transaction_result and transaction_result[1] is not None:
                        discounted_decimal = Decimal(str(transaction_result[1]))
                    
                    update_transaction_query = """
                    UPDATE restaurant_transaction
                    SET arrival_time = %s,
                        expected_completion_time = %s,
                        was_collected = TRUE,
                        collected_timestamp = %s,
                        final_amount = %s,
                        status = 'Arrived',
                        modified_by = %s,
                        modified_date = CURRENT_TIMESTAMP
                    WHERE plate_selection_id = %s
                    AND is_archived = FALSE
                    """
                    cursor.execute(update_transaction_query, (
                        arrival_time,
                        expected_completion,
                        arrival_time,
                        credit_decimal,
                        str(user_id),
                        str(plate_selection_id)
                    ))
                    db.commit()
                
                if transaction_result:
                    balance_difference = credit_decimal - discounted_decimal
                    if balance_difference < Decimal("0"):
                        balance_difference = Decimal("0")
                    total_balance_increase += float(balance_difference)
                    
                    log_info(f"Transaction for selection {plate_selection_id}: "
                            f"discounted={discounted_decimal}, full={credit_decimal}, "
                            f"difference={balance_difference}")
            except Exception as e:
                log_error(f"Error processing selection {selection}: {e}")
                import traceback
                log_error(f"Traceback: {traceback.format_exc()}")
                continue
        
        # Update restaurant balance with total difference (pay-on-arrival)
        if total_balance_increase > 0:
            balance_updated = update_balance_on_arrival(restaurant_id, total_balance_increase, db)
            if balance_updated:
                log_info(f"Restaurant {restaurant_id} balance increased by {total_balance_increase} "
                        f"for {len(selections)} arrived order(s)")
            else:
                log_error(f"Failed to update restaurant balance for arrival at {restaurant_id}")
        
        log_info(f"Updated {len(selections)} order(s) for user {user_id} at restaurant {restaurant_id} to 'Arrived' status")

# Create service instance
plate_pickup_service = PlatePickupService()
