from typing import Any
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import (
    CoworkerEligibilityItem,
    NotifyCoworkersRequest,
    NotifyCoworkersResponse,
    PlateSelectionResponseSchema,
)
from app.services.coworker_service import get_coworkers_with_eligibility, notify_coworkers
from app.services.crud_service import get_plate_pickup_id_for_selection
from app.services.kitchen_day_service import get_plate_selection_editable_until
from app.services.plate_selection_service import (
    create_plate_selection_with_transactions,
    delete_plate_selection,
    update_plate_selection,
)
from app.utils.log import log_info

router = APIRouter(
    prefix="/plate-selections",
    tags=["Plate Selections"],
)


@router.post("", response_model=PlateSelectionResponseSchema, status_code=201)
def create_plate_selection(
    payload: dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Create a new plate selection using business logic service.

    Expected payload format:
    {
        "plate_id": "uuid",
        "pickup_time_range": "12:00-12:15",
        "target_kitchen_day": "Monday" (optional)
    }

    When user already has a plate for the same kitchen day, returns 409 with structured
    detail (code, kitchen_day, existing_plate_selection_id, message). Frontend shows
    modal; if user confirms "Yes, cancel my current plate", retry with same payload plus:
    - replace_existing: true
    - existing_plate_selection_id: <from 409 response>
    """
    try:
        # Validate required fields
        if "plate_id" not in payload:
            raise HTTPException(status_code=422, detail="plate_id is required")

        if "pickup_time_range" not in payload:
            raise HTTPException(status_code=422, detail="pickup_time_range is required")

        # Create plate selection using business logic service (plate_pickup created at kitchen_start)
        selection, _ = create_plate_selection_with_transactions(payload, current_user, db)

        log_info(f"Successfully created plate selection: {selection.plate_selection_id}")
        # Build response with plate_pickup_id and editable_until
        selection_data = selection.model_dump()
        editable_until = get_plate_selection_editable_until(selection.plate_selection_id, db)
        plate_pickup_id = get_plate_pickup_id_for_selection(selection.plate_selection_id, db)
        return PlateSelectionResponseSchema(
            **selection_data, plate_pickup_id=plate_pickup_id, editable_until=editable_until
        )

    except HTTPException:
        # Re-raise HTTPExceptions (these have proper status codes and messages)
        raise
    except Exception as e:
        log_info(f"Error creating plate selection: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating plate selection: {str(e)}") from None


@router.get("/{plate_selection_id}", response_model=PlateSelectionResponseSchema)
def get_plate_selection(
    plate_selection_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get a plate selection by ID. Returns editable_until for client edit UI."""
    from app.services.crud_service import plate_selection_service
    from app.services.error_handling import handle_get_by_id

    entity = handle_get_by_id(
        plate_selection_service.get_by_id_non_archived,
        plate_selection_id,
        db,
        "plate selection",
        include_archived=False,
    )
    if str(entity.user_id) != str(current_user["user_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to access this plate selection")
    data = entity.model_dump()
    editable_until = get_plate_selection_editable_until(plate_selection_id, db)
    plate_pickup_id = get_plate_pickup_id_for_selection(plate_selection_id, db)
    return PlateSelectionResponseSchema(**data, plate_pickup_id=plate_pickup_id, editable_until=editable_until)


@router.get("", response_model=list[PlateSelectionResponseSchema])
def list_plate_selections(
    current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all plate selections for the current user. Each includes editable_until."""
    from app.services.crud_service import get_all_by_user

    items = get_all_by_user(current_user["user_id"], db)
    return [
        PlateSelectionResponseSchema(
            **(item.model_dump()),
            plate_pickup_id=get_plate_pickup_id_for_selection(item.plate_selection_id, db),
            editable_until=get_plate_selection_editable_until(item.plate_selection_id, db),
        )
        for item in items
    ]


@router.patch("/{plate_selection_id}", response_model=PlateSelectionResponseSchema)
def patch_plate_selection(
    plate_selection_id: UUID,
    payload: dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update a plate selection. Allowed: pickup_time_range, pickup_intent, flexible_on_time, cancel. Editable until 1h before kitchen day opens."""
    updated = update_plate_selection(plate_selection_id, payload, current_user, db)
    data = updated.model_dump()
    editable_until = get_plate_selection_editable_until(plate_selection_id, db)
    plate_pickup_id = get_plate_pickup_id_for_selection(plate_selection_id, db)
    return PlateSelectionResponseSchema(**data, plate_pickup_id=plate_pickup_id, editable_until=editable_until)


@router.delete("/{plate_selection_id}")
def delete_plate_selection_route(
    plate_selection_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Delete (cancel) a plate selection. Refunds credits. Editable until 1h before kitchen day opens."""
    return delete_plate_selection(plate_selection_id, current_user, db)


@router.get("/{plate_selection_id}/coworkers", response_model=list[CoworkerEligibilityItem])
def get_plate_selection_coworkers(
    plate_selection_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List coworkers (same employer) with eligibility for pickup notification. For 'Offer to pick up' flow."""
    coworkers = get_coworkers_with_eligibility(plate_selection_id, current_user["user_id"], db)
    return [CoworkerEligibilityItem(**c) for c in coworkers]


@router.post("/{plate_selection_id}/notify-coworkers", response_model=NotifyCoworkersResponse)
def notify_plate_selection_coworkers(
    plate_selection_id: UUID,
    body: NotifyCoworkersRequest,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Notify selected coworkers about pickup offer. All user_ids must be eligible."""
    return notify_coworkers(plate_selection_id, body.user_ids, current_user["user_id"], db)
