"""
National Holidays Routes

Routes for managing national holidays (employee-only access).
Supports single and bulk operations.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from uuid import UUID
from typing import Any, Dict, List, Optional
import psycopg2.extensions

from app.schemas.consolidated_schemas import (
    NationalHolidayCreateSchema,
    NationalHolidayUpdateSchema,
    NationalHolidayResponseSchema,
    NationalHolidayBulkCreateSchema,
    NationalHolidaySyncFromProviderSchema,
)
from app.services.crud_service import national_holiday_service
from app.auth.dependencies import get_employee_user
from app.dependencies.database import get_db
from app.services.error_handling import handle_business_operation
from app.utils.log import log_info
from app.utils.db import db_batch_insert, db_read
from app.services.cron.holiday_refresh import run_holiday_refresh

router = APIRouter(
    prefix="/national-holidays",
    tags=["National Holidays"]
)


@router.post("/sync-from-provider", response_model=Dict[str, Any])
def sync_national_holidays_from_provider(
    payload: Optional[NationalHolidaySyncFromProviderSchema] = Body(default=None),
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    Import public holidays from Nager.Date for all configured market countries.

    Internal-only. Body optional: `years` for explicit UTC-bounded calendar years;
    omit for default (current + next year, clamped). UPSERT refreshes nager_date rows; manual rows unchanged.
    """
    del db  # sync uses its own pooled connection
    del current_user
    years = None if payload is None else payload.years
    result = run_holiday_refresh(years=years)
    if result.get("status") == "error":
        reason = result.get("reason", "Holiday sync failed")
        if result.get("years") == []:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=reason)
    return result


@router.get("", response_model=List[NationalHolidayResponseSchema])
def list_national_holidays(
    country_code: Optional[str] = Query(None, description="Filter by country code"),
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    List all national holidays.
    
    Internal-only endpoint. Supports filtering by country code and archived status.
    """
    def get_operation(connection: psycopg2.extensions.connection):
        conditions = ["is_archived = FALSE"]
        params = []
        
        if country_code:
            conditions.append("country_code = %s")
            params.append(country_code)
        
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"""
            SELECT 
                holiday_id,
                country_code,
                holiday_name,
                holiday_date,
                is_recurring,
                recurring_month,
                recurring_day,
                COALESCE(status, 'active') as status,
                is_archived,
                created_date,
                modified_by,
                modified_date,
                source
            FROM national_holidays 
            {where_clause}
            ORDER BY country_code, holiday_date
        """
        
        results = db_read(query, tuple(params) if params else None, connection=connection)
        return [national_holiday_service.dto_class(**row) for row in results] if results else []
    
    return handle_business_operation(get_operation, "national holidays retrieval", None, db)


@router.get("/{holiday_id}", response_model=NationalHolidayResponseSchema)
def get_national_holiday(
    holiday_id: UUID,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Get a single national holiday by ID.
    
    Internal-only endpoint.
    """
    def get_operation(connection: psycopg2.extensions.connection):
        holiday = national_holiday_service.get_by_id(holiday_id, connection)
        if not holiday or holiday.is_archived:
            raise HTTPException(status_code=404, detail=f"National holiday not found: {holiday_id}")
        return holiday
    
    return handle_business_operation(get_operation, "national holiday retrieval", None, db)


@router.post("", response_model=NationalHolidayResponseSchema, status_code=status.HTTP_201_CREATED)
def create_national_holiday(
    payload: NationalHolidayCreateSchema,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Create a single national holiday.
    
    Internal-only endpoint.
    """
    def create_operation(connection: psycopg2.extensions.connection):
        # Prepare data for insert
        holiday_data = {
            "country_code": payload.country_code,
            "holiday_name": payload.holiday_name,
            "holiday_date": payload.holiday_date.isoformat(),
            "is_recurring": payload.is_recurring,
            "recurring_month": payload.recurring_month,
            "recurring_day": payload.recurring_day,
            "status": payload.status if payload.status else "active",  # Use provided status or default to active
            "is_archived": False,
            "modified_by": current_user["user_id"],
            "source": "manual",
        }

        # Create holiday
        created_holiday = national_holiday_service.create(holiday_data, connection, modified_by=current_user["user_id"])
        
        log_info(f"Created national holiday: {created_holiday.holiday_id} ({payload.holiday_name})")
        return created_holiday
    
    return handle_business_operation(create_operation, "national holiday creation", None, db)


@router.post("/bulk", response_model=List[NationalHolidayResponseSchema], status_code=status.HTTP_201_CREATED)
def create_national_holidays_bulk(
    payload: NationalHolidayBulkCreateSchema,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Create multiple national holidays atomically.
    
    Internal-only endpoint. All holidays are created in a single transaction.
    If any holiday fails validation, all operations are rolled back.
    """
    def create_bulk_operation(connection: psycopg2.extensions.connection):
        # Prepare data for batch insert
        data_list = []
        for holiday in payload.holidays:
            data_list.append({
                "country_code": holiday.country_code,
                "holiday_name": holiday.holiday_name,
                "holiday_date": holiday.holiday_date.isoformat(),
                "is_recurring": holiday.is_recurring,
                "recurring_month": holiday.recurring_month,
                "recurring_day": holiday.recurring_day,
                "status": holiday.status if holiday.status else "active",  # Use provided status or default to active
                "is_archived": False,
                "modified_by": current_user["user_id"],
                "source": "manual",
            })
        
        # Batch insert all holidays atomically using db_batch_insert
        inserted_ids = db_batch_insert("national_holidays", data_list, connection)
        
        # Fetch created records to return
        created_holidays = []
        for inserted_id in inserted_ids:
            holiday = national_holiday_service.get_by_id(UUID(inserted_id), connection)
            if holiday:
                created_holidays.append(holiday)
        
        log_info(f"Created {len(created_holidays)} national holidays in bulk")
        return created_holidays
    
    return handle_business_operation(create_bulk_operation, "bulk national holidays creation", None, db)


@router.put("/{holiday_id}", response_model=NationalHolidayResponseSchema)
def update_national_holiday(
    holiday_id: UUID,
    payload: NationalHolidayUpdateSchema,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Update a national holiday.
    
    Internal-only endpoint.
    """
    def update_operation(connection: psycopg2.extensions.connection):
        # Get existing holiday
        existing = national_holiday_service.get_by_id(holiday_id, connection)
        if not existing:
            raise HTTPException(status_code=404, detail=f"National holiday not found: {holiday_id}")
        
        # Prepare update data (only include fields that are provided)
        update_data = {}
        if payload.country_code is not None:
            update_data["country_code"] = payload.country_code
        if payload.holiday_name is not None:
            update_data["holiday_name"] = payload.holiday_name
        if payload.holiday_date is not None:
            update_data["holiday_date"] = payload.holiday_date.isoformat()
        if payload.is_recurring is not None:
            update_data["is_recurring"] = payload.is_recurring
        if payload.recurring_month is not None:
            update_data["recurring_month"] = payload.recurring_month
        if payload.recurring_day is not None:
            update_data["recurring_day"] = payload.recurring_day
        if payload.status is not None:
            update_data["status"] = payload.status
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        
        # Update holiday
        updated = national_holiday_service.update(
            holiday_id,
            update_data,
            connection,
            modified_by=current_user["user_id"]
        )
        
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update national holiday")
        
        log_info(f"Updated national holiday: {holiday_id}")
        return updated
    
    return handle_business_operation(update_operation, "national holiday update", None, db)


@router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_national_holiday(
    holiday_id: UUID,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db)
):
    """
    Soft delete (archive) a national holiday.
    
    Internal-only endpoint.
    """
    def delete_operation(connection: psycopg2.extensions.connection):
        # Get existing holiday
        existing = national_holiday_service.get_by_id(holiday_id, connection)
        if not existing:
            raise HTTPException(status_code=404, detail=f"National holiday not found: {holiday_id}")
        
        # Soft delete (archive)
        success = national_holiday_service.soft_delete(
            holiday_id,
            current_user["user_id"],
            connection
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete national holiday")
        
        log_info(f"Deleted (archived) national holiday: {holiday_id}")
        return None
    
    handle_business_operation(delete_operation, "national holiday deletion", None, db)
    return None

