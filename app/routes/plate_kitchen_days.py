# app/routes/plate_kitchen_days.py
"""
API routes for managing plate kitchen days.

Plate kitchen days define which plates are available on which days of the week.
This API allows Suppliers to manage kitchen days for plates in their institution,
and Internal users to manage all kitchen days.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
from uuid import UUID
from app.dto.models import PlateKitchenDaysDTO
from app.services.crud_service import plate_kitchen_days_service, plate_service
from app.schemas.consolidated_schemas import (
    PlateKitchenDayCreateSchema,
    PlateKitchenDayUpdateSchema,
    PlateKitchenDayResponseSchema,
    PlateKitchenDayEnrichedResponseSchema
)
from app.services.entity_service import (
    get_enriched_plate_kitchen_days,
    get_enriched_plate_kitchen_day_by_id
)
from app.auth.dependencies import get_current_user, get_employee_user
from app.dependencies.database import get_db
from app.utils.log import log_info, log_error
from app.utils.error_messages import entity_not_found
from app.services.error_handling import handle_business_operation
from app.security.institution_scope import InstitutionScope
from app.security.entity_scoping import EntityScopingService, ENTITY_PLATE_KITCHEN_DAYS
from app.security.scoping import resolve_institution_filter
from app.utils.query_params import institution_filter
from app.utils.db import db_read
import psycopg2.extensions

router = APIRouter(
    prefix="/plate-kitchen-days",
    tags=["Plate Kitchen Days"],
)

def _get_scope_for_entity(current_user: dict) -> Optional[InstitutionScope]:
    """
    Get institution scope for plate_kitchen_days entity.
    
    Uses centralized EntityScopingService to ensure consistency between
    base and enriched endpoints. The service handles Customer blocking
    and role-based scoping automatically.
    """
    return EntityScopingService.get_scope_for_entity(ENTITY_PLATE_KITCHEN_DAYS, current_user)

# Note: _validate_plate_belongs_to_institution is no longer needed
# CRUDService now handles JOIN-based scoping automatically via _validate_join_based_scope

def _check_unique_constraint(
    plate_id: UUID,
    kitchen_day: str,
    db: psycopg2.extensions.connection,
    exclude_id: Optional[UUID] = None
) -> bool:
    """
    Check if a (plate_id, kitchen_day) combination already exists for a non-archived record.

    Uniqueness rules:
    1. Same plate_id cannot be assigned to same kitchen_day more than once (per restaurant, via plate).
    2. Different plate_ids CAN share the same kitchen_day (e.g. plate A and plate B both on Monday).
    3. Archived records do not count - archiving is soft delete, so the slot is considered free.
    """
    base_where = """
        plate_id = %s AND kitchen_day = %s AND is_archived = FALSE
    """
    if exclude_id:
        query = f"""
            SELECT plate_kitchen_day_id
            FROM plate_kitchen_days
            WHERE {base_where}
              AND plate_kitchen_day_id != %s
        """
        result = db_read(query, (str(plate_id), kitchen_day, str(exclude_id)), connection=db, fetch_one=True)
    else:
        query = f"""
            SELECT plate_kitchen_day_id
            FROM plate_kitchen_days
            WHERE {base_where}
        """
        result = db_read(query, (str(plate_id), kitchen_day), connection=db, fetch_one=True)
    return result is not None

@router.get("", response_model=List[PlateKitchenDayResponseSchema])
def list_plate_kitchen_days(
    institution_id: Optional[UUID] = institution_filter(),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all plate kitchen day assignments. Optional institution_id filters by institution (B2B Internal dropdown scoping)."""
    scope = _get_scope_for_entity(current_user)
    effective_institution_id = resolve_institution_filter(institution_id, scope)
    if effective_institution_id is not None:
        effective_scope = InstitutionScope(
            institution_id=str(effective_institution_id), role_type="Internal", role_name="Manager"
        )
    else:
        effective_scope = scope
    
    try:
        # Use CRUDService with JOIN-based scoping (handles Internal and Suppliers automatically)
        results = plate_kitchen_days_service.get_all(
            db,
            scope=effective_scope,
            include_archived=False
        )
        return results
    except Exception as e:
        log_error(f"Error listing plate kitchen days: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing plate kitchen days: {str(e)}")

# Enriched routes MUST be before /{kitchen_day_id} so /enriched is not parsed as kitchen_day_id
@router.get("/enriched", response_model=List[PlateKitchenDayEnrichedResponseSchema])
def list_enriched_plate_kitchen_days(
    institution_id: Optional[UUID] = institution_filter(),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """List all plate kitchen day assignments with enriched data. Optional institution_id filters by institution (B2B Internal dropdown scoping)."""
    scope = _get_scope_for_entity(current_user)
    effective_institution_id = resolve_institution_filter(institution_id, scope)
    
    try:
        enriched_days = get_enriched_plate_kitchen_days(
            db,
            scope=scope,
            include_archived=False,
            institution_id=effective_institution_id
        )
        return enriched_days
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched plate kitchen days: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting enriched plate kitchen days: {str(e)}")

@router.get("/enriched/{kitchen_day_id}", response_model=PlateKitchenDayEnrichedResponseSchema)
def get_enriched_plate_kitchen_day(
    kitchen_day_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single plate kitchen day assignment with enriched data"""
    scope = _get_scope_for_entity(current_user)
    
    try:
        enriched_day = get_enriched_plate_kitchen_day_by_id(
            kitchen_day_id,
            db,
            scope=scope,
            include_archived=False
        )
        if not enriched_day:
            raise HTTPException(status_code=404, detail="Plate kitchen day not found")
        return enriched_day
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting enriched plate kitchen day {kitchen_day_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting enriched plate kitchen day: {str(e)}")

@router.get("/{kitchen_day_id}", response_model=PlateKitchenDayResponseSchema)
def get_plate_kitchen_day(
    kitchen_day_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get a single plate kitchen day assignment by ID"""
    scope = _get_scope_for_entity(current_user)
    
    # Use CRUDService with JOIN-based scoping (handles Employees and Suppliers automatically)
    kitchen_day = plate_kitchen_days_service.get_by_id(kitchen_day_id, db, scope=scope)
    if not kitchen_day:
        raise HTTPException(status_code=404, detail="Plate kitchen day not found")
    
    if kitchen_day.is_archived:
        raise HTTPException(status_code=404, detail="Plate kitchen day not found")
    
    return kitchen_day

@router.post("", response_model=List[PlateKitchenDayResponseSchema], status_code=status.HTTP_201_CREATED)
def create_plate_kitchen_day(
    payload: PlateKitchenDayCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Create one or more plate kitchen day assignments atomically.
    
    Accepts a list of kitchen_days and creates all assignments in a single transaction.
    If any assignment fails (e.g., duplicate), all operations are rolled back.
    """
    scope = _get_scope_for_entity(current_user)
    
    def create_operation(connection: psycopg2.extensions.connection):
        # Validate plate exists
        plate = plate_service.get_by_id(payload.plate_id, connection)
        if not plate:
            raise HTTPException(status_code=404, detail=f"Plate not found: {payload.plate_id}")
        
        # Validate all days before creating any (fail fast)
        for day in payload.kitchen_days:
            if _check_unique_constraint(payload.plate_id, day, connection):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Plate {payload.plate_id} is already assigned to {day}"
                )
        
        # Prepare data for batch insert
        data_list = []
        status_value = payload.status or 'Active'  # Default to 'Active' if not provided
        for day in payload.kitchen_days:
            data_list.append({
                "plate_id": str(payload.plate_id),
                "kitchen_day": day,
                "status": status_value,
                "is_archived": False,
                "modified_by": current_user["user_id"]
            })
        
        # Batch insert all days atomically using db_batch_insert
        from app.utils.db import db_batch_insert
        inserted_ids = db_batch_insert("plate_kitchen_days", data_list, connection)
        
        # Fetch created records to return (with scoping)
        created_days = []
        for inserted_id in inserted_ids:
            kitchen_day = plate_kitchen_days_service.get_by_id(
                UUID(inserted_id), connection, scope=scope
            )
            if kitchen_day:
                created_days.append(kitchen_day)
        
        log_info(f"Created {len(created_days)} kitchen days for plate {payload.plate_id}")
        return created_days
    
    return handle_business_operation(create_operation, "create plate kitchen days", None, db)

@router.put("/{kitchen_day_id}", response_model=PlateKitchenDayResponseSchema)
def update_plate_kitchen_day(
    kitchen_day_id: UUID,
    payload: PlateKitchenDayUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Update an existing plate kitchen day assignment. plate_id is immutable; use create + archive to change it."""
    # Reject plate_id on update - must create new record and archive old one
    if payload.plate_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="plate_id cannot be changed on an existing kitchen day; create a new record and archive the old one if needed.",
        )

    scope = _get_scope_for_entity(current_user)

    def update_operation(connection: psycopg2.extensions.connection):
        # Get existing record (with scoping - will return None if not accessible)
        existing = plate_kitchen_days_service.get_by_id(kitchen_day_id, connection, scope=scope)
        if not existing:
            raise HTTPException(status_code=404, detail="Plate kitchen day not found")

        kitchen_day = payload.kitchen_day if payload.kitchen_day is not None else existing.kitchen_day

        # If kitchen_day is being changed, validate unique constraint (plate_id unchanged)
        if payload.kitchen_day is not None:
            if _check_unique_constraint(existing.plate_id, kitchen_day, connection, exclude_id=kitchen_day_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Plate {existing.plate_id} is already assigned to {kitchen_day}"
                )

        # Build update data - plate_id is immutable, never include it
        update_data = {}
        if payload.kitchen_day is not None:
            update_data["kitchen_day"] = payload.kitchen_day
        if payload.status is not None:
            update_data["status"] = payload.status
        if payload.is_archived is not None:
            update_data["is_archived"] = payload.is_archived
        
        update_data["modified_by"] = current_user["user_id"]
        
        # CRUDService will automatically validate plate belongs to institution via JOIN-based scoping
        updated = plate_kitchen_days_service.update(kitchen_day_id, update_data, connection, scope=scope)
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update plate kitchen day")
        
        log_info(f"Updated plate kitchen day: {kitchen_day_id}")
        return updated
    
    return handle_business_operation(update_operation, "update plate kitchen day", None, db)

@router.delete("/{kitchen_day_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plate_kitchen_day(
    kitchen_day_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """Soft delete (archive) a plate kitchen day assignment"""
    scope = _get_scope_for_entity(current_user)
    
    def delete_operation(connection: psycopg2.extensions.connection):
        # Get existing record (with scoping - will return None if not accessible)
        existing = plate_kitchen_days_service.get_by_id(kitchen_day_id, connection, scope=scope)
        if not existing:
            raise HTTPException(status_code=404, detail="Plate kitchen day not found")
        
        # Soft delete (archive) - CRUDService handles scoping automatically
        success = plate_kitchen_days_service.soft_delete(
            kitchen_day_id,
            current_user["user_id"],
            connection,
            scope=scope
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete plate kitchen day")
        
        log_info(f"Deleted (archived) plate kitchen day: {kitchen_day_id}")
        return None
    
    handle_business_operation(delete_operation, "delete plate kitchen day", None, db)
    return None

