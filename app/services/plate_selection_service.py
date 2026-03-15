# app/services/plate_selection_service.py
"""
Business logic service for plate selection operations.

This service handles the complex business logic for creating plate selections,
breaking down the large route function into smaller, testable components.
"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
import psycopg2.extensions
from fastapi import HTTPException

from app.dto.models import (
    PlateDTO, RestaurantDTO, QRCodeDTO, CreditCurrencyDTO,
    PlateSelectionDTO, ClientTransactionDTO, SubscriptionDTO
)
from app.services.crud_service import (
    plate_service, restaurant_service, credit_currency_service,
    plate_selection_service, plate_pickup_live_service,
    qr_code_service, subscription_service,
)
from app.utils.log import log_info, log_warning, log_error
from app.utils.db import db_read
from app.services.date_service import get_effective_current_day
from app.services.market_detection import MarketDetectionService
from app.config import Status
from app.services.credit_validation_service import (
    validate_sufficient_credits,
    handle_insufficient_credits
)
from app.services.billing import (
    apply_subscription_renewal,
    LOW_BALANCE_RENEWAL_THRESHOLD,
)
from app.services.restaurant_explorer_service import resolve_weekday_to_next_occurrence
from .plate_selection_validation import (
    validate_plate_selection_data,
    validate_restaurant_status,
    validate_restaurant,
    validate_pickup_time_range,
    determine_target_kitchen_day,
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
        timezone_str = getattr(context["address"], "timezone", None) or (
            __import__("app.config.market_config", fromlist=["MarketConfiguration"])
            .MarketConfiguration.get_market_timezone(context["address"].country_code)
            if context["address"].country_code else None
        ) or "America/Argentina/Buenos_Aires"
        country_code = context["address"].country_code
        context["target_day"] = determine_target_kitchen_day(
            payload.get("target_kitchen_day"),
            context["plate"],
            get_effective_current_day(timezone_str, country_code),
            context["kitchen_days"],
            country_code,
            db,
            timezone_str=timezone_str
        )
        
        # Step 2.5: Calculate target date and validate restaurant (status + holidays)
        try:
            target_date = resolve_weekday_to_next_occurrence(
                context["target_day"], timezone_str
            ).strftime('%Y-%m-%d')
            context["target_date"] = target_date

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

        # Step 2.6: Validate pickup_time_range is within market's allowed windows
        if country_code and context.get("target_day"):
            target_date = context.get("target_date")
            if not target_date:
                target_date = resolve_weekday_to_next_occurrence(context["target_day"], timezone_str)
            pickup_time_range = payload.get("pickup_time_range")
            if pickup_time_range:
                validate_pickup_time_range(
                    country_code, context["target_day"], target_date, pickup_time_range
                )

        # Step 2.7: Reject if user already has a plate selection for this kitchen_day (or handle replace flow)
        _existing = db_read(
            """
            SELECT plate_selection_id FROM plate_selection_info
            WHERE user_id = %s AND kitchen_day = %s AND is_archived = FALSE
            """,
            (str(current_user["user_id"]), context["target_day"]),
            connection=db,
            fetch_one=True,
        )
        if _existing:
            existing_id = str(_existing["plate_selection_id"])
            replace_existing = payload.get("replace_existing") is True
            payload_existing_id = payload.get("existing_plate_selection_id")
            payload_existing_id_str = str(payload_existing_id) if payload_existing_id else None

            if replace_existing and payload_existing_id_str and payload_existing_id_str == existing_id:
                # User confirmed replace: cancel existing (commit=False), then continue to create
                cancel_plate_selection(UUID(existing_id), current_user, db, commit=False)
            else:
                # Duplicate without valid replace: return structured 409 for frontend modal
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "DUPLICATE_KITCHEN_DAY",
                        "kitchen_day": context["target_day"],
                        "existing_plate_selection_id": existing_id,
                        "message": f"You already have a plate reserved for {context['target_day']}. "
                                   "Continue to cancel your meal and reserve this plate?",
                    },
                )

        # Step 2.75: Low-balance early renewal (only when renewal_date is in the future)
        subscription = subscription_service.get_by_user(current_user["user_id"], db)
        if subscription:
            balance = float(subscription.balance or 0)
            renewal_date = subscription.renewal_date
            if renewal_date is not None:
                if renewal_date.tzinfo is None:
                    renewal_date = renewal_date.replace(tzinfo=timezone.utc)
                else:
                    renewal_date = renewal_date.astimezone(timezone.utc)
                now_utc = datetime.now(timezone.utc)
                if balance < LOW_BALANCE_RENEWAL_THRESHOLD and renewal_date > now_utc:
                    user_id = current_user.get("user_id")
                    if isinstance(user_id, str):
                        user_id = UUID(user_id)
                    try:
                        apply_subscription_renewal(
                            subscription.subscription_id,
                            db,
                            modified_by=user_id,
                            commit=True,
                        )
                        log_info(f"Early renewal applied for user {current_user['user_id']} (balance {balance} < {LOW_BALANCE_RENEWAL_THRESHOLD}, renewal_date in future)")
                    except (HTTPException, ValueError) as e:
                        log_warning(f"Could not apply early renewal: {e}")
        
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
                detail=insufficient_credits_response.model_dump()
            )
        
        # Step 4: Create the plate selection (only if credits are sufficient)
        # Client transaction, subscription balance, plate_pickup_live, and restaurant_transaction
        # are all created at kitchen_start by the promotion cron.
        selection = _create_plate_selection_record(context, current_user, db)
        if not selection:
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create plate selection record")
        
        # Commit
        db.commit()
        log_info(f"Successfully created plate selection {selection.plate_selection_id} (plate_pickup created at kitchen_start)")
        
        return selection, None
        
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
    
    # Fetch credit currency (from institution_entity, not restaurant)
    from app.services.entity_service import get_credit_currency_id_for_restaurant
    credit_currency_id = get_credit_currency_id_for_restaurant(restaurant, db)
    credit_currency = credit_currency_service.get_by_id(credit_currency_id, db)
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
    
    payload_data = context.get("payload", {})
    pickup_intent = payload_data.get("pickup_intent", "self")
    flexible_on_time = payload_data.get("flexible_on_time") if pickup_intent == "request" else None

    target_date = context.get("target_date")
    if not target_date:
        raise HTTPException(status_code=500, detail="Missing target_date in context for plate selection creation")

    data = {
        "user_id": current_user["user_id"],
        "plate_id": plate.plate_id,
        "restaurant_id": plate.restaurant_id,
        "product_id": plate.product_id,
        "qr_code_id": qr_code.qr_code_id,
        "credit": plate.credit,
        "kitchen_day": target_day,
        "pickup_date": target_date,
        "pickup_time_range": payload_data.get("pickup_time_range"),
        "pickup_intent": pickup_intent,
        "flexible_on_time": flexible_on_time,
        "status": Status.PENDING,
        "modified_by": current_user["user_id"]
    }
    
    selection = plate_selection_service.create(data, db, commit=False)
    if selection:
        log_info(f"Created plate selection: {selection.plate_selection_id} (commit deferred)")
        return selection
    else:
        raise HTTPException(status_code=500, detail=f"Failed to create plate selection with data: {data}")


# Fields that may NOT be modified via PATCH. To change plate, user must cancel and create new.
_PATCH_FORBIDDEN_FIELDS = frozenset({
    "plate_id", "target_kitchen_day", "kitchen_day", "pickup_date", "user_id", "restaurant_id",
    "product_id", "qr_code_id", "credit", "plate_selection_id", "created_date",
    "modified_date", "is_archived", "status",
})


def update_plate_selection(
    plate_selection_id: UUID,
    payload: Dict[str, Any],
    current_user: Dict[str, Any],
    db: psycopg2.extensions.connection
) -> PlateSelectionDTO:
    """
    Update a plate selection. Only pickup_time_range, pickup_intent, flexible_on_time,
    and cancel are editable. plate_id and other fields cannot be changed; user must
    cancel and create a new selection to change the plate.
    Validates editability window before allowing updates.
    """
    from app.services.kitchen_day_service import is_plate_selection_editable

    # Reject attempts to modify non-editable fields
    forbidden_in_payload = [k for k in payload if k in _PATCH_FORBIDDEN_FIELDS]
    if forbidden_in_payload:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot modify {', '.join(sorted(forbidden_in_payload))}. "
                   "Only pickup_time_range, pickup_intent, and flexible_on_time are editable. "
                   "To change the plate, cancel this selection and create a new one.",
        )

    selection = plate_selection_service.get_by_id_non_archived(plate_selection_id, db)
    if not selection:
        raise HTTPException(status_code=404, detail="Plate selection not found")

    if str(selection.user_id) != str(current_user["user_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to update this plate selection")

    if not is_plate_selection_editable(plate_selection_id, db):
        raise HTTPException(
            status_code=400,
            detail="Plate selection is no longer editable. Edits are allowed until 1 hour before kitchen day opens."
        )

    updates = {}
    if "pickup_time_range" in payload and payload["pickup_time_range"] is not None:
        updates["pickup_time_range"] = payload["pickup_time_range"]
    if "pickup_intent" in payload and payload["pickup_intent"] is not None:
        intent = payload["pickup_intent"]
        if intent not in ("offer", "request", "self"):
            raise HTTPException(status_code=422, detail="pickup_intent must be offer, request, or self")
        updates["pickup_intent"] = intent
    if "flexible_on_time" in payload:
        updates["flexible_on_time"] = payload["flexible_on_time"] if payload.get("pickup_intent") == "request" else None

    if payload.get("cancel") is True:
        return cancel_plate_selection(plate_selection_id, current_user, db)

    if not updates:
        return selection

    updates["modified_by"] = current_user["user_id"]
    updated = plate_selection_service.update(plate_selection_id, updates, db)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update plate selection")
    log_info(f"Updated plate selection {plate_selection_id}")
    return updated


def cancel_plate_selection(
    plate_selection_id: UUID,
    current_user: Dict[str, Any],
    db: psycopg2.extensions.connection,
    commit: bool = True,
) -> PlateSelectionDTO:
    """
    Cancel a plate selection: soft-delete selection and related records.
    Allowed only until 1 hour before kitchen day (is_plate_selection_editable).
    No refund after lock: once promoted, credits are forfeited and restaurant keeps no-show.
    When commit=False, caller is responsible for committing (e.g. for atomic replace flow).
    """
    from app.services.kitchen_day_service import is_plate_selection_editable

    selection = plate_selection_service.get_by_id_non_archived(plate_selection_id, db)
    if not selection:
        raise HTTPException(status_code=404, detail="Plate selection not found")

    if str(selection.user_id) != str(current_user["user_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to cancel this plate selection")

    if not is_plate_selection_editable(plate_selection_id, db):
        raise HTTPException(
            status_code=400,
            detail="Plate selection is no longer editable. Cancellation is allowed until 1 hour before kitchen day opens."
        )

    plate = plate_service.get_by_id(selection.plate_id, db)
    if not plate:
        raise HTTPException(status_code=404, detail="Plate not found")

    try:
        # No refund after lock: credits are forfeited; restaurant keeps no-show discount.
        # Cancellation is only allowed before lock (is_plate_selection_editable enforces this).
        # If somehow we reach cancel on a locked selection, we still soft-delete but do not refund
        # (user forfeits credits) and do not reverse restaurant (restaurant keeps credited amount).
        plate_selection_service.soft_delete(plate_selection_id, current_user["user_id"], db)

        from app.utils.db import db_read
        pickup_rows = db_read(
            "SELECT plate_pickup_id FROM plate_pickup_live WHERE plate_selection_id = %s AND is_archived = FALSE",
            (str(plate_selection_id),),
            connection=db,
        )
        for row in pickup_rows or []:
            plate_pickup_live_service.soft_delete(row["plate_pickup_id"], current_user["user_id"], db)

        if commit:
            db.commit()
        log_info(f"Cancelled plate selection {plate_selection_id}")
        selection.is_archived = True
        selection.status = Status.CANCELLED if hasattr(Status, "CANCELLED") else Status.INACTIVE
        return selection
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        log_error(f"Error cancelling plate selection: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel plate selection")


def delete_plate_selection(
    plate_selection_id: UUID,
    current_user: Dict[str, Any],
    db: psycopg2.extensions.connection
) -> Dict[str, str]:
    """Delete (cancel) a plate selection. Same as cancel - soft-deletes selection and archives."""
    cancel_plate_selection(plate_selection_id, current_user, db)
    return {"detail": "Plate selection deleted successfully"}

