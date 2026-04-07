"""
Plate Selection Promotion Service - Promote reservations to live at kitchen start.

At kitchen_start (business_hours.open = 11:30 local), locked plate selections
are promoted to plate_pickup_live and restaurant_transaction. This defers
restaurant crediting until 1 hour after the cancel cutoff to avoid reversals.
"""

from typing import Optional, Dict, Any
from uuid import UUID
from decimal import Decimal
import psycopg2.extensions

from app.dto.models import (
    PlateSelectionDTO, PlatePickupLiveDTO, RestaurantTransactionDTO,
    PlateDTO, RestaurantDTO, QRCodeDTO, CreditCurrencyDTO
)
from fastapi import HTTPException

from app.services.crud_service import (
    plate_service, restaurant_service, institution_service, credit_currency_service,
    plate_selection_service, plate_pickup_live_service,
    restaurant_transaction_service, client_transaction_service,
    subscription_service, qr_code_service, supplier_terms_service,
    create_with_conservative_balance_update,
    update_balance, mark_plate_selection_complete,
)
from app.services.entity_service import get_credit_currency_id_for_restaurant
from app.services.credit_validation_service import validate_sufficient_credits
from app.utils.log import log_info, log_warning, log_error
from app.utils.db import db_read
from app.config import Status


def promote_plate_selection_to_live(
    plate_selection_id: UUID,
    system_user_id: UUID,
    db: psycopg2.extensions.connection,
    *,
    commit: bool = True
) -> Optional[UUID]:
    """
    Promote a single plate selection to live (create plate_pickup_live + restaurant_transaction).

    Idempotent: returns existing plate_pickup_id if one already exists.

    Args:
        plate_selection_id: The plate selection to promote
        system_user_id: System user for modified_by
        db: Database connection
        commit: Whether to commit (default True for cron, False for atomic batch)

    Returns:
        plate_pickup_id if successful, None on failure
    """
    selection = plate_selection_service.get_by_id_non_archived(plate_selection_id, db)
    if not selection:
        log_warning(f"Plate selection {plate_selection_id} not found or archived, skip promotion")
        return None

    # Idempotency: already promoted?
    existing = db_read(
        "SELECT plate_pickup_id FROM plate_pickup_live WHERE plate_selection_id = %s AND is_archived = FALSE",
        (str(plate_selection_id),),
        connection=db,
        fetch_one=True,
    )
    if existing:
        log_info(f"Plate selection {plate_selection_id} already promoted (plate_pickup_id={existing['plate_pickup_id']})")
        return UUID(str(existing["plate_pickup_id"]))

    # Build context from selection
    plate = plate_service.get_by_id(selection.plate_id, db)
    if not plate:
        log_error(f"Plate {selection.plate_id} not found for promotion of {plate_selection_id}")
        return None

    restaurant = restaurant_service.get_by_id(selection.restaurant_id, db)
    if not restaurant:
        log_error(f"Restaurant {selection.restaurant_id} not found for promotion of {plate_selection_id}")
        return None

    qr_code = qr_code_service.get_by_restaurant(selection.restaurant_id, db)
    if not qr_code:
        log_error(f"QR code not found for restaurant {selection.restaurant_id}, promotion of {plate_selection_id}")
        return None

    credit_currency_id = get_credit_currency_id_for_restaurant(restaurant, db)
    credit_currency = credit_currency_service.get_by_id(credit_currency_id, db)
    if not credit_currency:
        log_error(f"Credit currency not found for restaurant {selection.restaurant_id}, promotion of {plate_selection_id}")
        return None

    institution = institution_service.get_by_id(restaurant.institution_id, db)
    if not institution:
        log_error(f"Institution {restaurant.institution_id} not found for promotion of {plate_selection_id}")
        return None

    supplier_terms = supplier_terms_service.get_by_field("institution_id", restaurant.institution_id, db)

    context: Dict[str, Any] = {
        "plate": plate,
        "restaurant": restaurant,
        "institution": institution,
        "supplier_terms": supplier_terms,
        "qr_code": qr_code,
        "credit_currency": credit_currency,
    }

    # Validate credits before promoting (charge deferred to promotion)
    try:
        credit_val = validate_sufficient_credits(selection.user_id, float(plate.credit), db)
        if not credit_val.can_proceed:
            log_warning(
                f"Insufficient credits for promotion of {plate_selection_id}: user {selection.user_id}, "
                f"required {plate.credit}, shortfall {credit_val.shortfall}. Skipping."
            )
            return None
    except HTTPException as e:
        log_warning(f"Credit validation failed for promotion of {plate_selection_id}: {e.detail}. Skipping.")
        return None

    # Create pickup record
    pickup_record = _create_pickup_record_for_promotion(selection, context, system_user_id, db)
    if not pickup_record:
        return None

    # Create restaurant transaction
    rt = _create_restaurant_transaction_for_promotion(
        selection, pickup_record, context, system_user_id, db
    )
    if not rt:
        return None

    # Create client transaction and update subscription balance (charge deferred to promotion)
    subscription = subscription_service.get_by_user(selection.user_id, db)
    if not subscription:
        log_error(f"Subscription not found for user {selection.user_id}, promotion of {plate_selection_id}")
        return None

    transaction_record = client_transaction_service.create({
        "user_id": selection.user_id,
        "source": "plate_selection",
        "plate_selection_id": plate_selection_id,
        "discretionary_id": None,
        "credit": -float(plate.credit),
        "is_archived": False,
        "modified_by": system_user_id,
    }, db, commit=False)
    if not transaction_record:
        log_error(f"Failed to create client transaction for promotion of {plate_selection_id}")
        return None

    success = update_balance(subscription.subscription_id, -float(plate.credit), db, commit=False)
    if not success:
        log_error(f"Failed to update subscription balance for promotion of {plate_selection_id}")
        return None

    success = mark_plate_selection_complete(
        transaction_record.transaction_id, selection.user_id, db, commit=False
    )
    if not success:
        log_error(f"Failed to mark plate selection complete for promotion of {plate_selection_id}")
        return None

    if commit:
        db.commit()
    log_info(f"Promoted plate selection {plate_selection_id} to live (plate_pickup_id={pickup_record.plate_pickup_id})")
    return pickup_record.plate_pickup_id


def _create_pickup_record_for_promotion(
    selection: PlateSelectionDTO,
    context: Dict[str, Any],
    modified_by: UUID,
    db: psycopg2.extensions.connection
) -> Optional[PlatePickupLiveDTO]:
    """Create plate_pickup_live record for a promoted selection."""
    plate = context["plate"]
    qr_code = context["qr_code"]

    pickup_data = {
        "plate_selection_id": selection.plate_selection_id,
        "user_id": selection.user_id,
        "restaurant_id": plate.restaurant_id,
        "plate_id": plate.plate_id,
        "product_id": plate.product_id,
        "qr_code_id": qr_code.qr_code_id,
        "qr_code_payload": qr_code.qr_code_payload,
        "is_archived": False,
        "status": Status.PENDING,
        "was_collected": False,
        "modified_by": modified_by
    }

    pickup_record = plate_pickup_live_service.create(pickup_data, db, commit=False)
    if pickup_record:
        log_info(f"Created plate_pickup_live {pickup_record.plate_pickup_id} for promotion")
    return pickup_record


def _create_restaurant_transaction_for_promotion(
    selection: PlateSelectionDTO,
    pickup_record: PlatePickupLiveDTO,
    context: Dict[str, Any],
    modified_by: UUID,
    db: psycopg2.extensions.connection
) -> Optional[RestaurantTransactionDTO]:
    """Create restaurant_transaction for a promoted selection. no_show_discount comes from supplier_terms."""
    plate = context["plate"]
    supplier_terms = context.get("supplier_terms")
    credit_currency = context["credit_currency"]

    credit_decimal = plate.credit if isinstance(plate.credit, Decimal) else Decimal(str(plate.credit))
    no_show = supplier_terms.no_show_discount if supplier_terms else 0
    discount_decimal = Decimal(str(no_show))
    discount_multiplier = (Decimal("100") - discount_decimal) / Decimal("100")
    final_amount = credit_decimal * discount_multiplier

    restaurant_transaction_data = {
        "transaction_id": pickup_record.plate_pickup_id,
        "restaurant_id": plate.restaurant_id,
        "plate_selection_id": selection.plate_selection_id,
        "discretionary_id": None,
        "credit_currency_id": credit_currency.credit_currency_id,
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
        "modified_by": modified_by,
        "modified_date": pickup_record.created_date
    }

    rt = create_with_conservative_balance_update(restaurant_transaction_data, db, commit=False)
    if rt:
        log_info(f"Created restaurant_transaction {rt.transaction_id} for promotion")
    return rt
