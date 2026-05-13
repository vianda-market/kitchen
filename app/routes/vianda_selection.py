from typing import Any
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user, get_resolved_locale
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    CoworkerEligibilityItem,
    NotifyCoworkersRequest,
    NotifyCoworkersResponse,
    ViandaSelectionResponseSchema,
)
from app.services.coworker_service import get_coworkers_with_eligibility, notify_coworkers
from app.services.crud_service import get_vianda_pickup_id_for_selection
from app.services.kitchen_day_service import get_vianda_selection_editable_until
from app.services.vianda_selection_service import (
    create_vianda_selection_with_transactions,
    delete_vianda_selection,
    update_vianda_selection,
)
from app.utils.log import log_info

router = APIRouter(
    prefix="/vianda-selections",
    tags=["Vianda Selections"],
)


@router.post("", response_model=ViandaSelectionResponseSchema, status_code=201)
def create_vianda_selection(
    payload: dict[str, Any],
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Create a new vianda selection using business logic service.

    Expected payload format:
    {
        "vianda_id": "uuid",
        "pickup_time_range": "12:00-12:15",
        "target_kitchen_day": "Monday" (optional)
    }

    When user already has a vianda for the same kitchen day, returns 409 with structured
    detail (code, kitchen_day, existing_vianda_selection_id, message). Frontend shows
    modal; if user confirms "Yes, cancel my current vianda", retry with same payload plus:
    - replace_existing: true
    - existing_vianda_selection_id: <from 409 response>
    """
    try:
        # Validate required fields
        if "vianda_id" not in payload:
            raise envelope_exception(ErrorCode.VIANDA_SELECTION_VIANDA_ID_REQUIRED, status=422, locale=locale)

        if "pickup_time_range" not in payload:
            raise envelope_exception(ErrorCode.VIANDA_SELECTION_PICKUP_TIME_REQUIRED, status=422, locale=locale)

        # Create vianda selection using business logic service (vianda_pickup created at kitchen_start)
        selection, _ = create_vianda_selection_with_transactions(payload, current_user, db)

        log_info(f"Successfully created vianda selection: {selection.vianda_selection_id}")
        # Build response with vianda_pickup_id and editable_until
        selection_data = selection.model_dump()
        editable_until = get_vianda_selection_editable_until(selection.vianda_selection_id, db)
        vianda_pickup_id = get_vianda_pickup_id_for_selection(selection.vianda_selection_id, db)
        return ViandaSelectionResponseSchema(
            **selection_data, vianda_pickup_id=vianda_pickup_id, editable_until=editable_until
        )

    except HTTPException:
        # Re-raise HTTPExceptions (these have proper status codes and messages)
        raise
    except Exception as e:
        log_info(f"Error creating vianda selection: {e}")
        raise envelope_exception(ErrorCode.VIANDA_SELECTION_CREATION_FAILED, status=500, locale="en") from None


@router.get("/{vianda_selection_id}", response_model=ViandaSelectionResponseSchema)
def get_vianda_selection(
    vianda_selection_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get a vianda selection by ID. Returns editable_until for client edit UI."""
    from app.services.crud_service import vianda_selection_service
    from app.services.error_handling import handle_get_by_id

    entity = handle_get_by_id(
        vianda_selection_service.get_by_id_non_archived,
        vianda_selection_id,
        db,
        "vianda selection",
        include_archived=False,
    )
    if str(entity.user_id) != str(current_user["user_id"]):
        raise envelope_exception(ErrorCode.VIANDA_SELECTION_ACCESS_DENIED, status=403, locale=locale)
    data = entity.model_dump()
    editable_until = get_vianda_selection_editable_until(vianda_selection_id, db)
    vianda_pickup_id = get_vianda_pickup_id_for_selection(vianda_selection_id, db)
    return ViandaSelectionResponseSchema(**data, vianda_pickup_id=vianda_pickup_id, editable_until=editable_until)


@router.get("", response_model=list[ViandaSelectionResponseSchema])
def list_vianda_selections(
    current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all vianda selections for the current user. Each includes editable_until."""
    from app.services.crud_service import get_all_by_user

    items = get_all_by_user(current_user["user_id"], db)
    return [
        ViandaSelectionResponseSchema(
            **(item.model_dump()),
            vianda_pickup_id=get_vianda_pickup_id_for_selection(item.vianda_selection_id, db),
            editable_until=get_vianda_selection_editable_until(item.vianda_selection_id, db),
        )
        for item in items
    ]


@router.patch("/{vianda_selection_id}", response_model=ViandaSelectionResponseSchema)
def patch_vianda_selection(
    vianda_selection_id: UUID,
    payload: dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update a vianda selection. Allowed: pickup_time_range, pickup_intent, flexible_on_time, cancel. Editable until 1h before kitchen day opens."""
    updated = update_vianda_selection(vianda_selection_id, payload, current_user, db)
    data = updated.model_dump()
    editable_until = get_vianda_selection_editable_until(vianda_selection_id, db)
    vianda_pickup_id = get_vianda_pickup_id_for_selection(vianda_selection_id, db)
    return ViandaSelectionResponseSchema(**data, vianda_pickup_id=vianda_pickup_id, editable_until=editable_until)


@router.delete("/{vianda_selection_id}")
def delete_vianda_selection_route(
    vianda_selection_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Delete (cancel) a vianda selection. Refunds credits. Editable until 1h before kitchen day opens."""
    return delete_vianda_selection(vianda_selection_id, current_user, db)


@router.get("/{vianda_selection_id}/coworkers", response_model=list[CoworkerEligibilityItem])
def get_vianda_selection_coworkers(
    vianda_selection_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List coworkers (same employer) with eligibility for pickup notification. For 'Offer to pick up' flow."""
    coworkers = get_coworkers_with_eligibility(vianda_selection_id, current_user["user_id"], db)
    return [CoworkerEligibilityItem(**c) for c in coworkers]


@router.post("/{vianda_selection_id}/notify-coworkers", response_model=NotifyCoworkersResponse)
def notify_vianda_selection_coworkers(
    vianda_selection_id: UUID,
    body: NotifyCoworkersRequest,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Notify selected coworkers about pickup offer. All user_ids must be eligible."""
    return notify_coworkers(vianda_selection_id, body.user_ids, current_user["user_id"], db)
