# app/services/plate_selection_service.py
"""
Business logic service for plate selection operations.

This service handles the complex business logic for creating plate selections,
breaking down the large route function into smaller, testable components.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import psycopg2.extensions

from app.config import Status
from app.dto.models import (
    PlateSelectionDTO,
)
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.services.billing import (
    apply_subscription_renewal,
)
from app.services.credit_validation_service import handle_insufficient_credits, validate_sufficient_credits
from app.services.crud_service import (
    credit_currency_service,
    plate_pickup_live_service,
    plate_selection_service,
    plate_service,
    qr_code_service,
    restaurant_service,
    subscription_service,
)
from app.services.date_service import get_effective_current_day
from app.services.restaurant_explorer_service import resolve_weekday_to_next_occurrence
from app.utils.db import db_read
from app.utils.log import log_error, log_info, log_warning

from .plate_selection_validation import (
    determine_target_kitchen_day,
    validate_pickup_time_range,
    validate_restaurant,
    validate_restaurant_status,
)


def create_plate_selection_with_transactions(
    payload: dict[str, Any], current_user: dict[str, Any], db: psycopg2.extensions.connection, locale: str = "en"
) -> PlateSelectionDTO:
    """
    Create a plate selection with all related transactions.

    This function orchestrates the entire plate selection creation process,
    delegating to smaller, focused functions for each step.

    Raises:
        HTTPException: For validation errors, missing resources, or system failures
    """
    from fastapi import HTTPException

    try:
        # Step 1: Validate and fetch required data
        context = _fetch_plate_selection_context(payload, db, locale)
        if not context:
            raise envelope_exception(ErrorCode.PLATE_SELECTION_NOT_FOUND, status=400, locale=locale)

        # Step 2: Resolve timezone and determine target kitchen day
        timezone_str = _resolve_restaurant_timezone(context["address"])
        country_code = context["address"].country_code
        context["target_day"] = determine_target_kitchen_day(
            payload.get("target_kitchen_day"),
            context["plate"],
            get_effective_current_day(timezone_str, country_code),
            context["kitchen_days"],
            country_code,
            db,
            timezone_str=timezone_str,
        )

        # Step 2.5: Calculate target date and validate restaurant (status + holidays)
        _validate_restaurant_for_day(context, db, locale, timezone_str)

        # Step 2.6: Validate pickup_time_range is within market's allowed windows
        _validate_pickup_window(context, payload, country_code, timezone_str)

        # Step 2.7: Reject if user already has a plate selection for this kitchen_day (or handle replace flow)
        _handle_duplicate_day(payload, current_user, context, db, locale)

        # Step 2.75: Low-balance early renewal (only when renewal_date is in the future and threshold is set)
        subscription = subscription_service.get_by_user(current_user["user_id"], db)
        _apply_early_renewal_if_needed(current_user, subscription, db)

        # Step 3: Validate sufficient credits BEFORE creating any records
        _assert_sufficient_credits(current_user, context, db, locale)

        # Step 4: Create the plate selection (only if credits are sufficient)
        # Client transaction, subscription balance, plate_pickup_live, and restaurant_transaction
        # are all created at kitchen_start by the promotion cron.
        selection = _create_plate_selection_record(context, current_user, db, locale)
        if not selection:
            db.rollback()
            raise envelope_exception(
                ErrorCode.ENTITY_CREATION_FAILED, status=500, locale=locale, entity="plate selection"
            )

        # Commit
        db.commit()
        log_info(
            f"Successfully created plate selection {selection.plate_selection_id} (plate_pickup created at kitchen_start)"
        )

        return selection, None

    except HTTPException:
        # HTTPException already handled rollback, just re-raise
        raise
    except Exception as e:
        # Rollback on any unexpected error
        db.rollback()
        log_error(f"Error creating plate selection: {e}")
        raise envelope_exception(
            ErrorCode.ENTITY_CREATION_FAILED, status=500, locale=locale, entity="plate selection"
        ) from None


def _resolve_restaurant_timezone(address: Any) -> str:
    """
    Derive the IANA timezone string for a restaurant's address.

    Resolution order: address.timezone → market config lookup by country_code →
    hardcoded fallback ("America/Argentina/Buenos_Aires").
    """
    from app.config.market_config import MarketConfiguration

    return (
        getattr(address, "timezone", None)
        or (MarketConfiguration.get_market_timezone(address.country_code) if address.country_code else None)
        or "America/Argentina/Buenos_Aires"
    )


def _validate_restaurant_for_day(
    context: dict[str, Any], db: psycopg2.extensions.connection, locale: str, timezone_str: str
) -> None:
    """
    Calculate the calendar date for the target kitchen day and validate the restaurant
    is open (active status + no holiday) on that date.

    On date calculation failure the function falls back to a status-only check so that
    a bad timezone config never blocks a valid selection.
    """
    try:
        target_date = resolve_weekday_to_next_occurrence(context["target_day"], timezone_str).strftime("%Y-%m-%d")
        context["target_date"] = target_date
        country_code = context["address"].country_code
        if country_code:
            validate_restaurant(
                restaurant=context["restaurant"], target_date=target_date, country_code=country_code, db=db
            )
        else:
            validate_restaurant_status(context["restaurant"])
    except (ValueError, IndexError) as e:
        log_warning(f"Could not calculate target date for holiday validation: {e}")
        validate_restaurant_status(context["restaurant"])


def _validate_pickup_window(
    context: dict[str, Any], payload: dict[str, Any], country_code: str | None, timezone_str: str
) -> None:
    """
    Validate that the requested pickup_time_range falls within the market's allowed
    pickup windows for the target kitchen day.  No-op when country_code is absent or
    no pickup_time_range was supplied.
    """
    if not (country_code and context.get("target_day")):
        return
    target_date = context.get("target_date")
    if not target_date:
        target_date = resolve_weekday_to_next_occurrence(context["target_day"], timezone_str)
    pickup_time_range = payload.get("pickup_time_range")
    if pickup_time_range:
        validate_pickup_time_range(country_code, context["target_day"], target_date, pickup_time_range)


def _handle_duplicate_day(
    payload: dict[str, Any],
    current_user: dict[str, Any],
    context: dict[str, Any],
    db: psycopg2.extensions.connection,
    locale: str,
) -> None:
    """
    Guard against duplicate plate selections on the same kitchen day.

    When an existing selection is found:
    - If the caller sent replace_existing=True and the correct existing_plate_selection_id,
      the existing selection is cancelled (commit=False) so creation can proceed atomically.
    - Otherwise a 409 is raised with structured metadata for the frontend confirm-replace modal.
    """
    _existing = db_read(
        """
        SELECT plate_selection_id FROM plate_selection_info
        WHERE user_id = %s AND kitchen_day = %s AND is_archived = FALSE
        """,
        (str(current_user["user_id"]), context["target_day"]),
        connection=db,
        fetch_one=True,
    )
    if not _existing:
        return
    existing_id = str(_existing["plate_selection_id"])
    replace_existing = payload.get("replace_existing") is True
    payload_existing_id = payload.get("existing_plate_selection_id")
    payload_existing_id_str = str(payload_existing_id) if payload_existing_id else None
    if replace_existing and payload_existing_id_str and payload_existing_id_str == existing_id:
        # User confirmed replace: cancel existing (commit=False), then continue to create
        cancel_plate_selection(UUID(existing_id), current_user, db, commit=False)
    else:
        # Duplicate without valid replace: return structured 409 for frontend modal
        raise envelope_exception(
            ErrorCode.PLATE_SELECTION_DUPLICATE_KITCHEN_DAY,
            status=409,
            locale=locale,
            kitchen_day=context["target_day"],
            existing_plate_selection_id=existing_id,
        )


def _apply_early_renewal_if_needed(
    current_user: dict[str, Any],
    subscription: Any,
    db: psycopg2.extensions.connection,
) -> None:
    """
    Trigger a low-balance early renewal when all conditions are met:
    - The subscription has an early_renewal_threshold set (not NULL).
    - The current balance is below that threshold.
    - The next renewal_date is still in the future (avoids double-renewing at period end).

    Failures are best-effort: any HTTPException or ValueError is logged as a warning and
    swallowed so the plate selection flow continues.
    """
    from fastapi import HTTPException

    if not subscription:
        return
    threshold = subscription.early_renewal_threshold
    if threshold is None:
        return
    balance = float(subscription.balance or 0)
    renewal_date = subscription.renewal_date
    if renewal_date is None:
        return
    if renewal_date.tzinfo is None:
        renewal_date = renewal_date.replace(tzinfo=UTC)
    else:
        renewal_date = renewal_date.astimezone(UTC)
    now_utc = datetime.now(UTC)
    if not (balance < threshold and renewal_date > now_utc):
        return
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
        log_info(
            f"Early renewal applied for user {current_user['user_id']} (balance {balance} < {threshold}, renewal_date in future)"
        )
    except (HTTPException, ValueError) as e:
        log_warning(f"Could not apply early renewal: {e}")


def _assert_sufficient_credits(
    current_user: dict[str, Any],
    context: dict[str, Any],
    db: psycopg2.extensions.connection,
    locale: str,
) -> None:
    """
    Raise HTTP 402 if the user's credit balance is insufficient for the plate's credit cost.
    Must be called BEFORE any records are inserted.
    """
    from fastapi import HTTPException

    credit_validation = validate_sufficient_credits(current_user["user_id"], context["plate"].credit, db)
    if not credit_validation.has_sufficient_credits:
        insufficient_credits_response = handle_insufficient_credits(
            current_user["user_id"], context["plate"].credit, credit_validation.current_balance
        )
        raise HTTPException(
            status_code=402,  # Payment Required
            detail=insufficient_credits_response.model_dump(),
        )


def _fetch_plate_selection_context(
    payload: dict[str, Any], db: psycopg2.extensions.connection, locale: str = "en"
) -> dict[str, Any]:
    """
    Fetch all required data for plate selection in one place.

    Returns a context dictionary with all required entities.

    Raises:
        HTTPException: For invalid data or missing resources
    """
    try:
        plate_id = UUID(str(payload["plate_id"]))
    except (ValueError, KeyError):
        raise envelope_exception(ErrorCode.DATABASE_INVALID_UUID, status=400, locale=locale) from None

    # Fetch plate
    plate = plate_service.get_by_id(plate_id, db)
    if not plate:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Plate")

    # Fetch restaurant
    restaurant = restaurant_service.get_by_id(plate.restaurant_id, db)
    if not restaurant:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Restaurant")

    # Validate restaurant status - must be 'Active' to accept plate selections
    validate_restaurant_status(restaurant)

    # Fetch restaurant address to get country information
    from app.services.crud_service import address_service

    address = address_service.get_by_id(restaurant.address_id, db)
    if not address:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Address")

    # Fetch QR code
    qr_code = qr_code_service.get_by_restaurant(plate.restaurant_id, db)
    if not qr_code:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="QR code")

    # Fetch credit currency (from institution_entity, not restaurant)
    from app.services.entity_service import get_currency_metadata_id_for_restaurant

    currency_metadata_id = get_currency_metadata_id_for_restaurant(restaurant, db)
    credit_currency = credit_currency_service.get_by_id(currency_metadata_id, db)
    if not credit_currency:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Credit currency")

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
        "payload": payload,
    }


def _create_plate_selection_record(
    context: dict[str, Any], current_user: dict[str, Any], db: psycopg2.extensions.connection, locale: str = "en"
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
        raise envelope_exception(ErrorCode.ENTITY_CREATION_FAILED, status=500, locale=locale, entity="plate selection")

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
        "modified_by": current_user["user_id"],
    }

    selection = plate_selection_service.create(data, db, commit=False)
    if selection:
        log_info(f"Created plate selection: {selection.plate_selection_id} (commit deferred)")
        return selection
    raise envelope_exception(ErrorCode.ENTITY_CREATION_FAILED, status=500, locale=locale, entity="plate selection")


# Fields that may NOT be modified via PATCH. To change plate, user must cancel and create new.
_PATCH_FORBIDDEN_FIELDS = frozenset(
    {
        "plate_id",
        "target_kitchen_day",
        "kitchen_day",
        "pickup_date",
        "user_id",
        "restaurant_id",
        "product_id",
        "qr_code_id",
        "credit",
        "plate_selection_id",
        "created_date",
        "modified_date",
        "is_archived",
        "status",
    }
)


def update_plate_selection(
    plate_selection_id: UUID,
    payload: dict[str, Any],
    current_user: dict[str, Any],
    db: psycopg2.extensions.connection,
    locale: str = "en",
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
        raise envelope_exception(
            ErrorCode.PLATE_SELECTION_IMMUTABLE_FIELDS,
            status=400,
            locale=locale,
            fields=", ".join(sorted(forbidden_in_payload)),
        )

    selection = plate_selection_service.get_by_id_non_archived(plate_selection_id, db)
    if not selection:
        raise envelope_exception(ErrorCode.PLATE_SELECTION_NOT_FOUND, status=404, locale=locale)

    if str(selection.user_id) != str(current_user["user_id"]):
        raise envelope_exception(ErrorCode.PLATE_SELECTION_ACCESS_DENIED, status=403, locale=locale)

    if not is_plate_selection_editable(plate_selection_id, db):
        raise envelope_exception(ErrorCode.PLATE_SELECTION_NOT_EDITABLE, status=400, locale=locale)

    updates = {}
    if "pickup_time_range" in payload and payload["pickup_time_range"] is not None:
        updates["pickup_time_range"] = payload["pickup_time_range"]
    if "pickup_intent" in payload and payload["pickup_intent"] is not None:
        intent = payload["pickup_intent"]
        if intent not in ("offer", "request", "self"):
            raise envelope_exception(ErrorCode.PLATE_SELECTION_PICKUP_INTENT_INVALID, status=422, locale=locale)
        updates["pickup_intent"] = intent
    if "flexible_on_time" in payload:
        updates["flexible_on_time"] = payload["flexible_on_time"] if payload.get("pickup_intent") == "request" else None

    if payload.get("cancel") is True:
        return cancel_plate_selection(plate_selection_id, current_user, db, locale=locale)

    if not updates:
        return selection

    updates["modified_by"] = current_user["user_id"]
    updated = plate_selection_service.update(plate_selection_id, updates, db)
    if not updated:
        raise envelope_exception(ErrorCode.ENTITY_UPDATE_FAILED, status=500, locale=locale, entity="plate selection")
    log_info(f"Updated plate selection {plate_selection_id}")
    return updated


def cancel_plate_selection(
    plate_selection_id: UUID,
    current_user: dict[str, Any],
    db: psycopg2.extensions.connection,
    commit: bool = True,
    locale: str = "en",
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
        raise envelope_exception(ErrorCode.PLATE_SELECTION_NOT_FOUND, status=404, locale=locale)

    if str(selection.user_id) != str(current_user["user_id"]):
        raise envelope_exception(ErrorCode.PLATE_SELECTION_ACCESS_DENIED, status=403, locale=locale)

    if not is_plate_selection_editable(plate_selection_id, db):
        raise envelope_exception(ErrorCode.PLATE_SELECTION_NOT_CANCELLABLE, status=400, locale=locale)

    plate = plate_service.get_by_id(selection.plate_id, db)
    if not plate:
        raise envelope_exception(ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Plate")

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
    except Exception as e:
        from fastapi import HTTPException

        if isinstance(e, HTTPException):
            db.rollback()
            raise
        db.rollback()
        log_error(f"Error cancelling plate selection: {e}")
        raise envelope_exception(
            ErrorCode.ENTITY_DELETION_FAILED, status=500, locale=locale, entity="plate selection"
        ) from None


def delete_plate_selection(
    plate_selection_id: UUID, current_user: dict[str, Any], db: psycopg2.extensions.connection, locale: str = "en"
) -> dict[str, str]:
    """Delete (cancel) a plate selection. Same as cancel - soft-deletes selection and archives."""
    cancel_plate_selection(plate_selection_id, current_user, db, locale=locale)
    return {"detail": "Plate selection deleted successfully"}
