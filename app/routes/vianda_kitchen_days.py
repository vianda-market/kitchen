# app/routes/vianda_kitchen_days.py
"""
API routes for managing vianda kitchen days.

Vianda kitchen days define which viandas are available on which days of the week.
This API allows Suppliers to manage kitchen days for viandas in their institution,
and Internal users to manage all kitchen days.
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.dependencies import get_current_user, get_employee_user, get_resolved_locale
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    RestaurantActivatedSchema,
    ViandaKitchenDayCreateResponseSchema,
    ViandaKitchenDayCreateSchema,
    ViandaKitchenDayEnrichedResponseSchema,
    ViandaKitchenDayResponseSchema,
    ViandaKitchenDayUpdateSchema,
    ViandaKitchenDayUpsertByKeySchema,
)
from app.security.entity_scoping import ENTITY_VIANDA_KITCHEN_DAYS, EntityScopingService
from app.security.institution_scope import InstitutionScope
from app.security.scoping import resolve_institution_filter
from app.services.activation_service import maybe_activate_restaurant
from app.services.crud_service import (
    find_vianda_kitchen_day_by_canonical_key,
    vianda_kitchen_days_service,
    vianda_service,
)
from app.services.entity_service import get_enriched_vianda_kitchen_day_by_id, get_enriched_vianda_kitchen_days
from app.services.error_handling import handle_business_operation
from app.utils.db import db_read
from app.utils.log import log_error, log_info
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers
from app.utils.query_params import institution_filter

router = APIRouter(
    prefix="/vianda-kitchen-days",
    tags=["Vianda Kitchen Days"],
)


def _get_scope_for_entity(current_user: dict) -> InstitutionScope | None:
    """
    Get institution scope for vianda_kitchen_days entity.

    Uses centralized EntityScopingService to ensure consistency between
    base and enriched endpoints. The service handles Customer blocking
    and role-based scoping automatically.
    """
    return EntityScopingService.get_scope_for_entity(ENTITY_VIANDA_KITCHEN_DAYS, current_user)


# Note: _validate_vianda_belongs_to_institution is no longer needed
# CRUDService now handles JOIN-based scoping automatically via _validate_join_based_scope


def _check_unique_constraint(
    vianda_id: UUID, kitchen_day: str, db: psycopg2.extensions.connection, exclude_id: UUID | None = None
) -> bool:
    """
    Check if a (vianda_id, kitchen_day) combination already exists for a non-archived record.

    Uniqueness rules:
    1. Same vianda_id cannot be assigned to same kitchen_day more than once (per restaurant, via vianda).
    2. Different vianda_ids CAN share the same kitchen_day (e.g. vianda A and vianda B both on Monday).
    3. Archived records do not count - archiving is soft delete, so the slot is considered free.
    """
    base_where = """
        vianda_id = %s AND kitchen_day = %s AND is_archived = FALSE
    """
    if exclude_id:
        query = f"""
            SELECT vianda_kitchen_day_id
            FROM vianda_kitchen_days
            WHERE {base_where}
              AND vianda_kitchen_day_id != %s
        """
        result = db_read(query, (str(vianda_id), kitchen_day, str(exclude_id)), connection=db, fetch_one=True)
    else:
        query = f"""
            SELECT vianda_kitchen_day_id
            FROM vianda_kitchen_days
            WHERE {base_where}
        """
        result = db_read(query, (str(vianda_id), kitchen_day), connection=db, fetch_one=True)
    return result is not None


@router.get("", response_model=list[ViandaKitchenDayResponseSchema])
def list_vianda_kitchen_days(
    institution_id: UUID | None = institution_filter(),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List all vianda kitchen day assignments. Optional institution_id filters by institution (B2B Internal dropdown scoping)."""
    scope = _get_scope_for_entity(current_user)
    effective_institution_id = resolve_institution_filter(institution_id, scope)
    if effective_institution_id is not None:
        effective_scope = InstitutionScope(
            institution_id=str(effective_institution_id), role_type="internal", role_name="manager"
        )
    else:
        effective_scope = scope

    try:
        # Use CRUDService with JOIN-based scoping (handles Internal and Suppliers automatically)
        results = vianda_kitchen_days_service.get_all(db, scope=effective_scope, include_archived=False)
        return results
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error listing vianda kitchen days: {e}")
        raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAYS_LIST_FAILED, status=500, locale="en") from None


# Enriched routes MUST be before /{kitchen_day_id} so /enriched is not parsed as kitchen_day_id
@router.get("/enriched", response_model=list[ViandaKitchenDayEnrichedResponseSchema])
def list_enriched_vianda_kitchen_days(
    response: Response,
    institution_id: UUID | None = institution_filter(),
    pagination: PaginationParams | None = Depends(get_pagination_params),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List all vianda kitchen day assignments with enriched data. Optional institution_id filters by institution (B2B Internal dropdown scoping)."""
    scope = _get_scope_for_entity(current_user)
    effective_institution_id = resolve_institution_filter(institution_id, scope)

    try:
        enriched_days = get_enriched_vianda_kitchen_days(
            db,
            scope=scope,
            include_archived=False,
            institution_id=effective_institution_id,
            page=pagination.page if pagination else None,
            page_size=pagination.page_size if pagination else None,
        )
        set_pagination_headers(response, enriched_days)
        return enriched_days
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched vianda kitchen days: {e}")
        raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAYS_ENRICHED_LIST_FAILED, status=500, locale="en") from None


@router.get("/enriched/{kitchen_day_id}", response_model=ViandaKitchenDayEnrichedResponseSchema)
def get_enriched_vianda_kitchen_day(
    kitchen_day_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get a single vianda kitchen day assignment with enriched data"""
    scope = _get_scope_for_entity(current_user)

    try:
        enriched_day = get_enriched_vianda_kitchen_day_by_id(kitchen_day_id, db, scope=scope, include_archived=False)
        if not enriched_day:
            raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAY_NOT_FOUND, status=404, locale=locale)
        return enriched_day
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched vianda kitchen day {kitchen_day_id}: {e}")
        raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAYS_ENRICHED_GET_FAILED, status=500, locale="en") from None


@router.get("/{kitchen_day_id}", response_model=ViandaKitchenDayResponseSchema)
def get_vianda_kitchen_day(
    kitchen_day_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get a single vianda kitchen day assignment by ID"""
    scope = _get_scope_for_entity(current_user)

    # Use CRUDService with JOIN-based scoping (handles Employees and Suppliers automatically)
    kitchen_day = vianda_kitchen_days_service.get_by_id(kitchen_day_id, db, scope=scope)
    if not kitchen_day:
        raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAY_NOT_FOUND, status=404, locale=locale)

    if kitchen_day.is_archived:
        raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAY_NOT_FOUND, status=404, locale=locale)

    return kitchen_day


@router.post("", response_model=ViandaKitchenDayCreateResponseSchema, status_code=status.HTTP_201_CREATED)
def create_vianda_kitchen_day(
    payload: ViandaKitchenDayCreateSchema,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Create one or more vianda kitchen day assignments atomically.

    Accepts a list of kitchen_days and creates all assignments in a single transaction.
    If any assignment fails (e.g., duplicate), all operations are rolled back.

    After successful creation, attempts lazy restaurant activation: if the restaurant
    is 'pending' and all activation prereqs are now met, it is promoted to 'active'
    silently. The ``restaurant_activated`` field in the response is populated when
    activation fires, null otherwise.
    """
    scope = _get_scope_for_entity(current_user)

    # Resolve restaurant_id before the batch insert so we can run lazy activation after.
    vianda = vianda_service.get_by_id(payload.vianda_id, db)
    if not vianda:
        raise envelope_exception(
            ErrorCode.ENTITY_NOT_FOUND, status=404, locale=locale, entity="Vianda", id=str(payload.vianda_id)
        )
    restaurant_id = vianda.restaurant_id

    def create_operation(connection: psycopg2.extensions.connection):
        # Validate all days before creating any (fail fast)
        for day in payload.kitchen_days:
            if _check_unique_constraint(payload.vianda_id, day, connection):
                raise envelope_exception(
                    ErrorCode.VIANDA_KITCHEN_DAY_DUPLICATE,
                    status=409,
                    locale=locale,
                    vianda_id=str(payload.vianda_id),
                    kitchen_day=day,
                )

        # Prepare data for batch insert
        data_list = []
        status_value = payload.status or "active"  # Default to 'active' if not provided
        for day in payload.kitchen_days:
            data_list.append(
                {
                    "vianda_id": str(payload.vianda_id),
                    "kitchen_day": day,
                    "status": status_value,
                    "is_archived": False,
                    "modified_by": current_user["user_id"],
                }
            )

        # Batch insert all days atomically using db_batch_insert (commits internally)
        from app.utils.db import db_batch_insert

        inserted_ids = db_batch_insert("vianda_kitchen_days", data_list, connection)

        # Fetch created records to return (with scoping)
        created_days = []
        for inserted_id in inserted_ids:
            kitchen_day = vianda_kitchen_days_service.get_by_id(UUID(inserted_id), connection, scope=scope)
            if kitchen_day:
                created_days.append(kitchen_day)

        log_info(f"Created {len(created_days)} kitchen days for vianda {payload.vianda_id}")
        return created_days

    items = handle_business_operation(create_operation, "create vianda kitchen days", None, db)

    # Lazy activation: best-effort, must not fail the HTTP response.
    # db_batch_insert already committed; this runs in a new implicit transaction.
    activated: RestaurantActivatedSchema | None = None
    try:
        activation_result = maybe_activate_restaurant(restaurant_id, db)
        if activation_result is not None:
            db.commit()
            activated = RestaurantActivatedSchema(
                restaurant_id=activation_result["id"],
                name=activation_result["name"],
            )
    except Exception as _exc:
        log_error(f"Lazy activation check failed for restaurant {restaurant_id}: {_exc}")
        try:
            db.rollback()
        except Exception:
            pass

    return ViandaKitchenDayCreateResponseSchema(items=items, restaurant_activated=activated)


# PUT /vianda-kitchen-days/by-key — idempotent upsert (seed/fixture endpoint).
# MUST be registered before PUT /{kitchen_day_id} so the static segment "by-key"
# wins over the UUID path parameter (FastAPI evaluates in registration order).
@router.put("/by-key", response_model=ViandaKitchenDayResponseSchema, status_code=200)
def upsert_vianda_kitchen_day_by_key(
    upsert_data: ViandaKitchenDayUpsertByKeySchema,
    current_user: dict = Depends(get_employee_user),  # Internal-only
    db: psycopg2.extensions.connection = Depends(get_db),
) -> ViandaKitchenDayResponseSchema:
    """Idempotent upsert a vianda kitchen day by canonical_key.

    INTERNAL SEED/FIXTURE ENDPOINT — never use for ad-hoc kitchen day creation
    (use POST /vianda-kitchen-days instead).

    Vianda kitchen days are unique by (vianda_id, kitchen_day).  If a row with the
    given canonical_key already exists it is updated in-place; otherwise a new
    row is inserted.

    Immutable fields on UPDATE:
        - ``vianda_id`` — FK to the vianda; cannot change after creation.
        - ``kitchen_day`` — the weekday this row represents; cannot change after
          creation.  Archive the old row and create a new canonical row to change
          either of these.

    Auth: Internal only (get_employee_user dependency).  Returns 403 for
    Customer/Supplier roles.

    Returns HTTP 200 on both insert and update (unlike POST which returns 201).
    """

    def _upsert() -> ViandaKitchenDayResponseSchema:
        key = upsert_data.canonical_key
        modified_by = current_user["user_id"]

        existing = find_vianda_kitchen_day_by_canonical_key(key, db)

        if existing is not None:
            # UPDATE path — vianda_id and kitchen_day are immutable.
            with db.cursor() as cur:
                cur.execute(
                    """UPDATE ops.vianda_kitchen_days
                       SET status = %s,
                           canonical_key = %s,
                           modified_by = %s::uuid,
                           modified_date = CURRENT_TIMESTAMP
                       WHERE vianda_kitchen_day_id = %s""",
                    (
                        upsert_data.status.value,
                        key,
                        str(modified_by),
                        str(existing.vianda_kitchen_day_id),
                    ),
                )
            db.commit()
            log_info(f"Upsert updated vianda kitchen day {existing.vianda_kitchen_day_id} with canonical_key '{key}'")
            updated = vianda_kitchen_days_service.get_by_id(existing.vianda_kitchen_day_id, db)
            if updated is None:
                raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAY_NOT_FOUND, status=404, locale="en")
            return ViandaKitchenDayResponseSchema.model_validate(updated)

        # INSERT path.
        # Validate that vianda_id exists.
        vianda = vianda_service.get_by_id(upsert_data.vianda_id, db)
        if vianda is None:
            raise envelope_exception(
                ErrorCode.ENTITY_NOT_FOUND,
                status=404,
                locale="en",
                entity="Vianda",
                id=str(upsert_data.vianda_id),
            )

        # Check (vianda_id, kitchen_day) uniqueness for non-archived rows.
        if _check_unique_constraint(upsert_data.vianda_id, upsert_data.kitchen_day.value, db):
            # A non-canonical row already owns this slot.  Stamp it with the canonical_key
            # instead of creating a duplicate — mirrors the markets "adopt existing" pattern.
            with db.cursor() as cur:
                cur.execute(
                    """UPDATE ops.vianda_kitchen_days
                       SET canonical_key = %s,
                           status = %s,
                           modified_by = %s::uuid,
                           modified_date = CURRENT_TIMESTAMP
                       WHERE vianda_id = %s
                         AND kitchen_day = %s
                         AND is_archived = FALSE""",
                    (
                        key,
                        upsert_data.status.value,
                        str(modified_by),
                        str(upsert_data.vianda_id),
                        upsert_data.kitchen_day.value,
                    ),
                )
            db.commit()
            log_info(
                f"Upsert adopted existing vianda kitchen day for "
                f"vianda {upsert_data.vianda_id} / {upsert_data.kitchen_day.value} "
                f"with canonical_key '{key}'"
            )
            adopted = find_vianda_kitchen_day_by_canonical_key(key, db)
            if adopted is None:
                raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAY_NOT_FOUND, status=404, locale="en")
            return ViandaKitchenDayResponseSchema.model_validate(adopted)

        # No existing row — perform a clean insert.
        with db.cursor() as cur:
            cur.execute(
                """INSERT INTO ops.vianda_kitchen_days
                       (vianda_id, kitchen_day, status, canonical_key, is_archived,
                        created_by, modified_by)
                   VALUES (%s, %s, %s, %s, FALSE, %s::uuid, %s::uuid)
                   RETURNING vianda_kitchen_day_id""",
                (
                    str(upsert_data.vianda_id),
                    upsert_data.kitchen_day.value,
                    upsert_data.status.value,
                    key,
                    str(modified_by),
                    str(modified_by),
                ),
            )
            row = cur.fetchone()
        db.commit()
        new_id = row["vianda_kitchen_day_id"] if isinstance(row, dict) else row[0]
        log_info(f"Upsert inserted vianda kitchen day {new_id} with canonical_key '{key}'")
        created = vianda_kitchen_days_service.get_by_id(new_id, db)
        if created is None:
            raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAY_NOT_FOUND, status=404, locale="en")
        return ViandaKitchenDayResponseSchema.model_validate(created)

    return handle_business_operation(_upsert, "vianda kitchen day upsert by canonical key")


@router.put("/{kitchen_day_id}", response_model=ViandaKitchenDayResponseSchema)
def update_vianda_kitchen_day(
    kitchen_day_id: UUID,
    payload: ViandaKitchenDayUpdateSchema,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update an existing vianda kitchen day assignment. vianda_id is immutable; use create + archive to change it."""
    # Reject vianda_id on update - must create new record and archive old one
    if payload.vianda_id is not None:
        raise envelope_exception(
            ErrorCode.VIANDA_KITCHEN_DAY_VIANDA_ID_IMMUTABLE,
            status=400,
            locale=locale,
        )

    scope = _get_scope_for_entity(current_user)

    def update_operation(connection: psycopg2.extensions.connection):
        # Get existing record (with scoping - will return None if not accessible)
        existing = vianda_kitchen_days_service.get_by_id(kitchen_day_id, connection, scope=scope)
        if not existing:
            raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAY_NOT_FOUND, status=404, locale=locale)

        kitchen_day = payload.kitchen_day if payload.kitchen_day is not None else existing.kitchen_day

        # If kitchen_day is being changed, validate unique constraint (vianda_id unchanged)
        if payload.kitchen_day is not None:
            if _check_unique_constraint(existing.vianda_id, kitchen_day, connection, exclude_id=kitchen_day_id):
                raise envelope_exception(
                    ErrorCode.VIANDA_KITCHEN_DAY_DUPLICATE,
                    status=409,
                    locale=locale,
                    vianda_id=str(existing.vianda_id),
                    kitchen_day=kitchen_day,
                )

        # Build update data - vianda_id is immutable, never include it.
        # Handle is_archived separately: CRUDService.update() re-fetches via get_by_id()
        # which filters is_archived=FALSE → returns None for a just-archived row → false 500.
        # Use soft_delete() for archival; .update() only for non-archive field changes.
        wants_archive = payload.is_archived is True
        update_data = {}
        if payload.kitchen_day is not None:
            update_data["kitchen_day"] = payload.kitchen_day
        if payload.status is not None:
            update_data["status"] = payload.status
        update_data["modified_by"] = current_user["user_id"]

        if wants_archive:
            # Apply non-archive updates first (if any), then soft_delete
            if len(update_data) > 1:  # more than just modified_by
                vianda_kitchen_days_service.update(kitchen_day_id, update_data, connection, scope=scope, commit=False)
            ok = vianda_kitchen_days_service.soft_delete(
                kitchen_day_id, current_user["user_id"], connection, scope=scope
            )
            if not ok:
                raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAY_ARCHIVE_FAILED, status=500, locale=locale)
            # Return pre-archive DTO with flag flipped
            existing.is_archived = True
            updated = existing
        else:
            if payload.is_archived is not None:
                update_data["is_archived"] = payload.is_archived  # False (un-archive)
            updated = vianda_kitchen_days_service.update(kitchen_day_id, update_data, connection, scope=scope)
            if not updated:
                raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAY_UPDATE_FAILED, status=500, locale=locale)

        log_info(f"Updated vianda kitchen day: {kitchen_day_id}")
        return updated

    return handle_business_operation(update_operation, "update vianda kitchen day", None, db)


@router.delete("/{kitchen_day_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vianda_kitchen_day(
    kitchen_day_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Soft delete (archive) a vianda kitchen day assignment"""
    scope = _get_scope_for_entity(current_user)

    def delete_operation(connection: psycopg2.extensions.connection):
        # Get existing record (with scoping - will return None if not accessible)
        existing = vianda_kitchen_days_service.get_by_id(kitchen_day_id, connection, scope=scope)
        if not existing:
            raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAY_NOT_FOUND, status=404, locale=locale)

        # Soft delete (archive) - CRUDService handles scoping automatically
        success = vianda_kitchen_days_service.soft_delete(
            kitchen_day_id, current_user["user_id"], connection, scope=scope
        )
        if not success:
            raise envelope_exception(ErrorCode.VIANDA_KITCHEN_DAY_DELETE_FAILED, status=500, locale=locale)

        log_info(f"Deleted (archived) vianda kitchen day: {kitchen_day_id}")
        return

    handle_business_operation(delete_operation, "delete vianda kitchen day", None, db)
    return
