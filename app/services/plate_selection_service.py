# app/services/plate_selection_service.py
"""
Business logic service for plate selection operations.

This service handles the complex business logic for creating plate selections,
breaking down the large route function into smaller, testable components.
"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from decimal import Decimal
import psycopg2.extensions
from fastapi import HTTPException

from app.dto.models import (
    PlateDTO, RestaurantDTO, QRCodeDTO, CreditCurrencyDTO, 
    PlateSelectionDTO, PlatePickupLiveDTO, RestaurantTransactionDTO, 
    ClientTransactionDTO, SubscriptionDTO
)
from app.services.crud_service import (
    plate_service, restaurant_service, credit_currency_service,
    plate_selection_service, plate_pickup_live_service, 
    client_transaction_service, restaurant_transaction_service,
    qr_code_service, subscription_service, update_balance, 
    mark_plate_selection_complete, create_with_conservative_balance_update
)
from app.utils.log import log_info, log_warning, log_error
from app.services.date_service import get_effective_current_day
from app.services.market_detection import MarketDetectionService
from app.config import Status
from app.services.credit_validation_service import (
    validate_sufficient_credits,
    handle_insufficient_credits
)
from .plate_selection_validation import (
    validate_plate_selection_data,
    validate_restaurant_status,
    validate_restaurant,
    determine_target_kitchen_day,
    _is_day_in_remainder_of_week,
    _find_next_available_kitchen_day_in_week
)


def create_plate_selection_with_transactions(
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    db: psycopg2.extensions.connection
) -> PlateSelectionDTO:
    """
    Create a plate selection with all related transactions.
    
    This function orchestrates the entire plate selection creation process,
    delegating to smaller, focused functions for each step.
    
    Raises:
        HTTPException: For validation errors, missing resources, or system failures
    """
    try:
        # Step 1: Validate and fetch required data
        context = _fetch_plate_selection_context(payload, db)
        if not context:
            raise HTTPException(status_code=400, detail="Invalid plate selection data or missing required resources")
            
        # Step 2: Determine target kitchen day
        context["target_day"] = determine_target_kitchen_day(
            payload.get("target_kitchen_day"),
            context["plate"],
            get_effective_current_day(),
            context["kitchen_days"],
            context["address"].country_code,
            db
        )
        
        # Step 2.5: Calculate target date and validate restaurant (status + holidays)
        from datetime import datetime, timedelta
        current_day = get_effective_current_day()
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        
        try:
            current_index = days_of_week.index(current_day)
            target_index = days_of_week.index(context["target_day"])
            days_ahead = target_index - current_index
            if days_ahead < 0:
                # Target day is next week
                days_ahead += 7
            
            target_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            
            # Get country code for holiday validation (already stored in address)
            country_code = context["address"].country_code
            
            # Validate restaurant (status + holidays for target date)
            if country_code:
                validate_restaurant(
                    restaurant=context["restaurant"],
                    target_date=target_date,
                    country_code=country_code,
                    db=db
                )
            else:
                # If country code not available, just validate status
                validate_restaurant_status(context["restaurant"])
        except (ValueError, IndexError) as e:
            # If we can't calculate the date, just validate status
            log_warning(f"Could not calculate target date for holiday validation: {e}")
            validate_restaurant_status(context["restaurant"])
        
        # Step 3: NEW - Validate sufficient credits BEFORE creating any records
        credit_validation = validate_sufficient_credits(
            current_user["user_id"],
            context["plate"].credit,
            db
        )
        
        if not credit_validation.has_sufficient_credits:
            # Return user-friendly insufficient credits response
            insufficient_credits_response = handle_insufficient_credits(
                current_user["user_id"],
                context["plate"].credit,
                credit_validation.current_balance
            )
            # Raise HTTPException with user-friendly response
            raise HTTPException(
                status_code=402,  # Payment Required
                detail=insufficient_credits_response.dict()
            )
        
        # Step 4: Create the plate selection (only if credits are sufficient)
        # All operations use commit=False for atomic transaction
        selection = _create_plate_selection_record(context, current_user, db)
        if not selection:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create plate selection record")
            
        # Step 5: Create related records (pickup, transactions, etc.)
        _create_related_records(selection, context, current_user, db)
        
        # Commit all operations atomically
        db.commit()
        log_info(f"Successfully created plate selection {selection.plate_selection_id} with all related records (atomic transaction)")
        
        return selection
        
    except HTTPException:
        # HTTPException already handled rollback, just re-raise
        raise
    except Exception as e:
        # Rollback on any unexpected error
        db.rollback()
        log_error(f"Error creating plate selection: {e}")
        raise HTTPException(status_code=500, detail="Failed to create plate selection")


def _fetch_plate_selection_context(
    payload: Dict[str, Any], 
    db: psycopg2.extensions.connection
) -> Dict[str, Any]:
    """
    Fetch all required data for plate selection in one place.
    
    Returns a context dictionary with all required entities.
    
    Raises:
        HTTPException: For invalid data or missing resources
    """
    try:
        plate_id = UUID(str(payload["plate_id"]))
    except (ValueError, KeyError):
        raise HTTPException(status_code=400, detail=f"Invalid plate_id format: {payload.get('plate_id')}")
    
    # Fetch plate
    plate = plate_service.get_by_id(plate_id, db)
    if not plate:
        raise HTTPException(status_code=404, detail=f"Plate not found for plate_id {plate_id}")
    
    # Fetch restaurant
    restaurant = restaurant_service.get_by_id(plate.restaurant_id, db)
    if not restaurant:
        raise HTTPException(status_code=404, detail=f"Restaurant not found for restaurant_id {plate.restaurant_id}")
    
    # Validate restaurant status - must be 'Active' to accept plate selections
    validate_restaurant_status(restaurant)
    
    # Fetch restaurant address to get country information
    from app.services.crud_service import address_service
    address = address_service.get_by_id(restaurant.address_id, db)
    if not address:
        raise HTTPException(status_code=404, detail=f"Address not found for address_id {restaurant.address_id}")
    
    # Fetch QR code
    qr_code = qr_code_service.get_by_restaurant(plate.restaurant_id, db)
    if not qr_code:
        raise HTTPException(status_code=404, detail=f"No QR code found for restaurant {plate.restaurant_id}")
    
    # Fetch credit currency
    credit_currency = credit_currency_service.get_by_id(restaurant.credit_currency_id, db)
    if not credit_currency:
        raise HTTPException(status_code=404, detail=f"Credit currency not found for restaurant {plate.restaurant_id}")
    
    # Fetch kitchen days for the plate
    # Note: We pass scope=None to get all kitchen days (not filtered by institution)
    # This is correct for plate selection, as customers should see all available days for a plate
    # The filtering by plate_id happens below
    from app.services.crud_service import plate_kitchen_days_service
    kitchen_days = plate_kitchen_days_service.get_all(db, scope=None, include_archived=False)
    plate_kitchen_days = [kd.kitchen_day for kd in kitchen_days if kd.plate_id == plate_id]
    
    return {
        "plate": plate,
        "restaurant": restaurant,
        "address": address,
        "qr_code": qr_code,
        "credit_currency": credit_currency,
        "kitchen_days": plate_kitchen_days,
        "payload": payload
    }


def _create_plate_selection_record(
    context: Dict[str, Any],
    current_user: Dict[str, Any],
    db: psycopg2.extensions.connection
) -> PlateSelectionDTO:
    """
    Create the main plate selection record.
    
    Raises:
        HTTPException: If plate selection creation fails
    """
    plate = context["plate"]
    qr_code = context["qr_code"]
    target_day = context["target_day"]
    
    data = {
        "user_id": current_user["user_id"],
        "plate_id": plate.plate_id,
        "restaurant_id": plate.restaurant_id,
        "product_id": plate.product_id,
        "qr_code_id": qr_code.qr_code_id,
        "credit": plate.credit,
        "kitchen_day": target_day,
        "pickup_time_range": context.get("payload", {}).get("pickup_time_range"),
        "status": Status.PENDING,
        "modified_by": current_user["user_id"]
    }
    
    selection = plate_selection_service.create(data, db, commit=False)
    if selection:
        log_info(f"Created plate selection: {selection.plate_selection_id} (commit deferred)")
        return selection
    else:
        raise HTTPException(status_code=500, detail=f"Failed to create plate selection with data: {data}")


def _create_related_records(
    selection: PlateSelectionDTO,
    context: Dict[str, Any],
    current_user: Dict[str, Any],
    db: psycopg2.extensions.connection
) -> None:
    """
    Create all related records (pickup, transactions, etc.).
    
    This function handles the creation of:
    - PlatePickupLive record
    - RestaurantTransaction record
    - ClientTransaction record
    - Subscription balance update
    
    All operations use commit=False for atomic transaction.
    """
    # Create pickup record
    pickup_record = _create_pickup_record(selection, context, current_user, db)
    if not pickup_record:
        raise HTTPException(status_code=500, detail="Failed to create plate pickup record")
    
    # Create restaurant transaction
    restaurant_transaction = _create_restaurant_transaction(
        selection, pickup_record, context, current_user, db
    )
    if not restaurant_transaction:
        raise HTTPException(status_code=500, detail="Failed to create restaurant transaction")
    
    # Create client transaction and update subscription
    _create_client_transaction_and_update_balance(
        selection, context, current_user, db
    )


def _create_pickup_record(
    selection: PlateSelectionDTO,
    context: Dict[str, Any],
    current_user: Dict[str, Any],
    db: psycopg2.extensions.connection
) -> Optional[PlatePickupLiveDTO]:
    """
    Create the plate pickup live record.
    """
    plate = context["plate"]
    qr_code = context["qr_code"]
    
    pickup_data = {
        "plate_selection_id": selection.plate_selection_id,
        "user_id": current_user["user_id"],
        "restaurant_id": plate.restaurant_id,
        "plate_id": plate.plate_id,
        "product_id": plate.product_id,
        "qr_code_id": qr_code.qr_code_id,
        "qr_code_payload": qr_code.qr_code_payload,
        "is_archived": False,
        "status": Status.PENDING,  # Explicitly set status to Pending
        "was_collected": False,
        "modified_by": current_user["user_id"]
    }
    
    pickup_record = plate_pickup_live_service.create(pickup_data, db, commit=False)
    if pickup_record:
        log_info(f"Created plate pickup live record: {pickup_record.plate_pickup_id} (commit deferred)")
    else:
        log_warning(f"Failed to create plate pickup live record with data: {pickup_data}")
    
    return pickup_record


def _create_restaurant_transaction(
    selection: PlateSelectionDTO,
    pickup_record: PlatePickupLiveDTO,
    context: Dict[str, Any],
    current_user: Dict[str, Any],
    db: psycopg2.extensions.connection
) -> Optional[RestaurantTransactionDTO]:
    """
    Create the restaurant transaction record.
    """
    plate = context["plate"]
    restaurant = context["restaurant"]
    credit_currency = context["credit_currency"]
    
    # Calculate final amount with no-show discount
    credit_decimal = plate.credit if isinstance(plate.credit, Decimal) else Decimal(str(plate.credit))
    discount_decimal = Decimal(str(plate.no_show_discount))
    discount_multiplier = (Decimal("100") - discount_decimal) / Decimal("100")
    final_amount = credit_decimal * discount_multiplier
    
    restaurant_transaction_data = {
        "transaction_id": pickup_record.plate_pickup_id,
        "restaurant_id": plate.restaurant_id,
        "plate_selection_id": selection.plate_selection_id,
        "discretionary_id": None,
        "credit_currency_id": restaurant.credit_currency_id,
        "was_collected": False,
        "ordered_timestamp": pickup_record.created_date,
        "collected_timestamp": None,
        "arrival_time": None,
        "completion_time": None,
        "expected_completion_time": None,
        "transaction_type": "Order",
        "credit": credit_decimal,
        "no_show_discount": discount_decimal,
        "currency_code": credit_currency.currency_code,
        "final_amount": final_amount,
        "is_archived": False,
        "status": Status.PENDING,
        "created_date": pickup_record.created_date,
        "modified_by": current_user["user_id"],
        "modified_date": pickup_record.created_date
    }
    
    restaurant_transaction = create_with_conservative_balance_update(
        restaurant_transaction_data, db, commit=False  # Defer commit for atomic transaction
    )
    
    if restaurant_transaction:
        log_info(f"Created restaurant transaction record: {restaurant_transaction.transaction_id} (commit deferred)")
    else:
        raise HTTPException(status_code=500, detail="Failed to create restaurant transaction record")
    
    return restaurant_transaction


def _create_client_transaction_and_update_balance(
    selection: PlateSelectionDTO,
    context: Dict[str, Any],
    current_user: Dict[str, Any],
    db: psycopg2.extensions.connection
) -> None:
    """
    Create client transaction and update subscription balance.
    """
    plate = context["plate"]
    
    # Create client transaction
    transaction_data = {
        "user_id": current_user["user_id"],
        "source": "plate_selection",
        "plate_selection_id": selection.plate_selection_id,
        "discretionary_id": None,
        "credit": -plate.credit,  # Negative credit = deduction
        "is_archived": False,
        "modified_by": current_user["user_id"]
    }
    
    transaction_record = client_transaction_service.create(transaction_data, db, commit=False)
    if not transaction_record:
        raise HTTPException(status_code=500, detail="Failed to create client transaction record")
    
    log_info(f"Created client transaction record: {transaction_record.transaction_id} (commit deferred)")
    
    # Update subscription balance (commit=False for atomic transaction)
    subscription = subscription_service.get_by_user(current_user["user_id"], db)
    if not subscription:
        raise HTTPException(status_code=404, detail=f"Subscription not found for user {current_user['user_id']}")
    
    credit_deduction = -plate.credit
    success = update_balance(subscription.subscription_id, credit_deduction, db, commit=False)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update subscription balance")
    
    log_info(f"Updated subscription balance for user {current_user['user_id']}: deducted {plate.credit} credits (commit deferred)")
    
    # Mark transaction as complete (commit=False for atomic transaction)
    success = mark_plate_selection_complete(transaction_record.transaction_id, current_user["user_id"], db, commit=False)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to mark transaction as complete")
    
    log_info(f"Marked client transaction {transaction_record.transaction_id} as complete (commit deferred)")
