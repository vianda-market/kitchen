"""Workplace group routes for B2C coworker pickup coordination."""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, Query, Response, status

from app.auth.dependencies import get_current_user, get_employee_user, oauth2_scheme
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.consolidated_schemas import (
    AddressCreateSchema,
    AddressResponseSchema,
    WorkplaceGroupCreateSchema,
    WorkplaceGroupEnrichedResponseSchema,
    WorkplaceGroupResponseSchema,
    WorkplaceGroupSearchResultSchema,
    WorkplaceGroupUpdateSchema,
)
from app.services.address_service import address_business_service
from app.services.crud_service import workplace_group_service
from app.services.error_handling import handle_business_operation
from app.utils.db import db_read
from app.utils.log import log_info
from app.utils.pagination import PaginationParams, get_pagination_params, set_pagination_headers

router = APIRouter(prefix="/workplace-groups", tags=["Workplace Groups"], dependencies=[Depends(oauth2_scheme)])
admin_router = APIRouter(
    prefix="/admin/workplace-groups", tags=["Admin Workplace Groups"], dependencies=[Depends(oauth2_scheme)]
)


# =============================================================================
# B2C ROUTES (any authenticated user)
# =============================================================================


@router.get("/search", response_model=list[WorkplaceGroupSearchResultSchema])
def search_workplace_groups(
    q: str = Query(..., min_length=1, description="Search query (fuzzy name match)"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Fuzzy search workplace groups by name using trigram similarity."""
    rows = db_read(
        """
        SELECT wg.workplace_group_id, wg.name,
               similarity(wg.name, %s) AS sim,
               (SELECT COUNT(*) FROM user_info
                WHERE workplace_group_id = wg.workplace_group_id
                  AND NOT is_archived) AS member_count
        FROM workplace_group wg
        WHERE wg.name %% %s AND NOT wg.is_archived
        ORDER BY sim DESC
        LIMIT %s
        """,
        (q, q, limit),
        connection=db,
    )
    return [WorkplaceGroupSearchResultSchema(**r) for r in rows]


@router.post("", response_model=WorkplaceGroupResponseSchema, status_code=status.HTTP_201_CREATED)
def create_workplace_group(
    body: WorkplaceGroupCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Create a new workplace group."""

    def _create():
        data = body.model_dump()
        data["created_by"] = current_user["user_id"]
        data["modified_by"] = current_user["user_id"]
        created = workplace_group_service.create(data, db, scope=None)
        if not created:
            raise envelope_exception(ErrorCode.WORKPLACE_GROUP_CREATION_FAILED, status=500, locale="en")
        log_info(f"Created workplace group: {created.workplace_group_id}")
        return WorkplaceGroupResponseSchema(**created.model_dump())

    return handle_business_operation(_create, "workplace group creation")


@router.get("/{group_id}", response_model=WorkplaceGroupResponseSchema)
def get_workplace_group(
    group_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get a workplace group by ID."""
    group = workplace_group_service.get_by_id(group_id, db, scope=None)
    if not group:
        raise envelope_exception(ErrorCode.WORKPLACE_GROUP_NOT_FOUND, status=404, locale="en")
    return WorkplaceGroupResponseSchema(**group.model_dump())


@router.get("/{group_id}/addresses", response_model=list[AddressResponseSchema])
def list_group_addresses(
    group_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List addresses linked to a workplace group."""
    # Validate group exists
    group = workplace_group_service.get_by_id(group_id, db, scope=None)
    if not group:
        raise envelope_exception(ErrorCode.WORKPLACE_GROUP_NOT_FOUND, status=404, locale="en")

    rows = db_read(
        """
        SELECT a.*,
               gc.name AS country_name,
               sp.floor,
               sp.apartment_unit
        FROM address_info a
        LEFT JOIN external.geonames_country gc ON gc.iso = a.country_code
        LEFT JOIN address_subpremise sp ON sp.address_id = a.address_id
        WHERE a.workplace_group_id = %s AND NOT a.is_archived
        """,
        (str(group_id),),
        connection=db,
    )
    return [AddressResponseSchema(**r) for r in rows]


@router.post("/{group_id}/addresses", response_model=AddressResponseSchema, status_code=status.HTTP_201_CREATED)
def add_group_address(
    group_id: UUID,
    body: AddressCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Add an address to a workplace group."""
    # Validate group exists
    group = workplace_group_service.get_by_id(group_id, db, scope=None)
    if not group:
        raise envelope_exception(ErrorCode.WORKPLACE_GROUP_NOT_FOUND, status=404, locale="en")

    def _create_address():
        data = body.model_dump(exclude_unset=True)
        data["workplace_group_id"] = str(group_id)
        new_addr = address_business_service.create_address_with_geocoding(data, current_user, db, commit=True)
        return new_addr

    return handle_business_operation(_create_address, "workplace group address creation")


# =============================================================================
# ADMIN ROUTES (Internal employees only)
# =============================================================================


@admin_router.get("", response_model=list[WorkplaceGroupResponseSchema])
def admin_list_workplace_groups(
    response: Response,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    pagination: PaginationParams | None = Depends(get_pagination_params),
):
    """List all workplace groups (paginated). Internal only."""
    result = workplace_group_service.get_all(db, scope=None, pagination=pagination)
    if pagination:
        set_pagination_headers(response, result)
        groups = result.items if hasattr(result, "items") else result
    else:
        groups = result
    return [WorkplaceGroupResponseSchema(**g.model_dump()) for g in groups]


@admin_router.get("/enriched", response_model=list[WorkplaceGroupEnrichedResponseSchema])
def admin_list_workplace_groups_enriched(
    response: Response,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
    pagination: PaginationParams | None = Depends(get_pagination_params),
):
    """List workplace groups with member count. Internal only."""
    rows = db_read(
        """
        SELECT wg.*,
               (SELECT COUNT(*) FROM user_info u
                WHERE u.workplace_group_id = wg.workplace_group_id
                  AND NOT u.is_archived) AS member_count
        FROM workplace_group wg
        WHERE NOT wg.is_archived
        ORDER BY wg.name
        """,
        connection=db,
    )
    return [WorkplaceGroupEnrichedResponseSchema(**r) for r in rows]


@admin_router.put("/{group_id}", response_model=WorkplaceGroupResponseSchema)
def admin_update_workplace_group(
    group_id: UUID,
    body: WorkplaceGroupUpdateSchema,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update a workplace group. Internal only."""
    existing = workplace_group_service.get_by_id(group_id, db, scope=None)
    if not existing:
        raise envelope_exception(ErrorCode.WORKPLACE_GROUP_NOT_FOUND, status=404, locale="en")

    def _update():
        data = body.model_dump(exclude_unset=True)
        data["modified_by"] = current_user["user_id"]
        updated = workplace_group_service.update(group_id, data, db, scope=None)
        if not updated:
            raise envelope_exception(ErrorCode.WORKPLACE_GROUP_UPDATE_FAILED, status=500, locale="en")
        log_info(f"Updated workplace group: {group_id}")
        return WorkplaceGroupResponseSchema(**updated.model_dump())

    return handle_business_operation(_update, "workplace group update")


@admin_router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_archive_workplace_group(
    group_id: UUID,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Soft-archive a workplace group. Internal only."""
    existing = workplace_group_service.get_by_id(group_id, db, scope=None)
    if not existing:
        raise envelope_exception(ErrorCode.WORKPLACE_GROUP_NOT_FOUND, status=404, locale="en")

    success = workplace_group_service.soft_delete(group_id, current_user["user_id"], db, scope=None)
    if not success:
        raise envelope_exception(ErrorCode.WORKPLACE_GROUP_ARCHIVE_FAILED, status=500, locale="en")
    log_info(f"Archived workplace group: {group_id}")


@admin_router.post("/bulk", response_model=list[WorkplaceGroupResponseSchema], status_code=status.HTTP_201_CREATED)
def admin_bulk_create_workplace_groups(
    bodies: list[WorkplaceGroupCreateSchema],
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Bulk create workplace groups. Internal only."""

    def _bulk_create():
        created_groups = []
        for body in bodies:
            data = body.model_dump()
            data["created_by"] = current_user["user_id"]
            data["modified_by"] = current_user["user_id"]
            created = workplace_group_service.create(data, db, scope=None, commit=False)
            if not created:
                raise envelope_exception(ErrorCode.WORKPLACE_GROUP_CREATION_FAILED, status=500, locale="en")
            created_groups.append(created)
        db.commit()
        log_info(f"Bulk created {len(created_groups)} workplace groups")
        return [WorkplaceGroupResponseSchema(**g.model_dump()) for g in created_groups]

    return handle_business_operation(_bulk_create, "bulk workplace group creation")
