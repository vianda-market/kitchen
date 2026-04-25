from typing import Any
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user, get_resolved_locale
from app.config.archival_config import (
    ArchivalCategory,
    get_archival_priority_order,
    get_config_source,
    get_table_archival_config,
    refresh_config_cache,
)
from app.dependencies.database import get_db
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.services.error_handling import handle_business_operation
from app.utils.db import db_insert, db_read, db_update
from app.utils.log import log_error

router = APIRouter(prefix="/admin/archival-config", tags=["Admin - Archival Configuration"])


class ArchivalConfigRequest(BaseModel):
    table_name: str = Field(..., max_length=100)
    category: ArchivalCategory
    retention_days: int = Field(..., ge=0)
    grace_period_days: int = Field(..., ge=0)
    priority: int = Field(..., ge=1)
    description: str = Field("", max_length=500)
    is_active: bool = True


class ArchivalConfigResponse(BaseModel):
    config_id: UUID
    table_name: str
    category: str
    retention_days: int
    grace_period_days: int
    priority: int
    description: str
    is_active: bool
    effective_date: str
    modified_by: UUID
    modified_date: str


@router.get("", response_model=list[ArchivalConfigResponse])
async def get_all_archival_configs(
    current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get all archival configurations"""

    def _get_all_archival_configs():
        query = """
        SELECT config_id, table_name, category, retention_days, grace_period_days,
               priority, description, is_active, effective_date, modified_by, modified_date
        FROM archival_config
        ORDER BY priority, table_name
        """

        results = db_read(query, fetch_one=False, connection=db)
        if not results:
            return []

        configs = []
        for result in results:
            configs.append(
                ArchivalConfigResponse(
                    config_id=result[0],
                    table_name=result[1],
                    category=result[2],
                    retention_days=result[3],
                    grace_period_days=result[4],
                    priority=result[5],
                    description=result[6] or "",
                    is_active=result[7],
                    effective_date=result[8].isoformat(),
                    modified_by=result[9],
                    modified_date=result[10].isoformat(),
                )
            )

        return configs

    return handle_business_operation(_get_all_archival_configs, "archival configurations retrieval")


@router.get("/table/{table_name}", response_model=dict[str, Any])
async def get_table_config(
    table_name: str,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get archival configuration for a specific table"""

    def _get_table_config():
        config = get_table_archival_config(table_name)
        return {
            "table_name": table_name,
            "category": config.category.value,
            "retention_days": config.retention_days,
            "grace_period_days": config.grace_period_days,
            "priority": config.priority,
            "description": config.description,
            "config_source": get_config_source(),
        }

    return handle_business_operation(_get_table_config, "table configuration retrieval")


@router.post("", response_model=dict[str, Any])
async def create_archival_config(
    config: ArchivalConfigRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Create a new archival configuration"""

    def _create_archival_config():
        # Check if configuration already exists
        existing_query = """
        SELECT config_id FROM archival_config WHERE table_name = %s
        """
        existing = db_read(existing_query, (config.table_name,), fetch_one=True, connection=db)

        if existing:
            raise envelope_exception(
                ErrorCode.ARCHIVAL_CONFIG_ALREADY_EXISTS, status=400, locale=locale, table_name=config.table_name
            )

        # Insert new configuration using db_insert
        data = {
            "table_name": config.table_name,
            "category": config.category.value,
            "retention_days": config.retention_days,
            "grace_period_days": config.grace_period_days,
            "priority": config.priority,
            "description": config.description,
            "is_active": config.is_active,
            "modified_by": current_user["user_id"],
        }

        result = db_insert("archival_config", data, connection=db)
        if not result:
            log_error(f"Failed to create archival configuration for table {config.table_name}")
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)

        # Refresh cache after creating new config
        refresh_config_cache()

        return {
            "message": "Archival configuration created successfully",
            "config_id": result,
            "table_name": config.table_name,
        }

    return handle_business_operation(_create_archival_config, "archival configuration creation")


@router.put("/{config_id}", response_model=dict[str, Any])
async def update_archival_config(
    config_id: UUID,
    config: ArchivalConfigRequest,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update an existing archival configuration"""

    def _update_archival_config():
        # Check if configuration exists
        existing_query = """
        SELECT config_id FROM archival_config WHERE config_id = %s
        """
        existing = db_read(existing_query, (config_id,), fetch_one=True, connection=db)

        if not existing:
            raise envelope_exception(ErrorCode.ARCHIVAL_CONFIG_NOT_FOUND, status=404, locale=locale)

        # Update configuration using db_update
        data = {
            "table_name": config.table_name,
            "category": config.category.value,
            "retention_days": config.retention_days,
            "grace_period_days": config.grace_period_days,
            "priority": config.priority,
            "description": config.description,
            "is_active": config.is_active,
            "modified_by": current_user["user_id"],
        }

        where_clause = {"config_id": str(config_id)}
        success = db_update("archival_config", data, where_clause, connection=db)

        if not success:
            log_error(f"Failed to update archival configuration {config_id}")
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)

        # Refresh cache after updating config
        refresh_config_cache()

        return {
            "message": "Archival configuration updated successfully",
            "config_id": config_id,
            "table_name": config.table_name,
        }

    return handle_business_operation(_update_archival_config, "archival configuration update")


@router.delete("/{config_id}", response_model=dict[str, Any])
async def delete_archival_config(
    config_id: UUID,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Delete an archival configuration"""

    def _delete_archival_config():
        # Check if configuration exists
        existing_query = """
        SELECT config_id FROM archival_config WHERE config_id = %s
        """
        existing = db_read(existing_query, (config_id,), fetch_one=True, connection=db)

        if not existing:
            raise envelope_exception(ErrorCode.ARCHIVAL_CONFIG_NOT_FOUND, status=404, locale=locale)

        # Soft delete by setting is_active to False
        data = {"is_active": False, "modified_by": current_user["user_id"]}

        where_clause = {"config_id": str(config_id)}
        success = db_update("archival_config", data, where_clause, connection=db)

        if not success:
            log_error(f"Failed to delete archival configuration {config_id}")
            raise envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)

        # Refresh cache after deleting config
        refresh_config_cache()

        return {"message": "Archival configuration deleted successfully", "config_id": config_id}

    return handle_business_operation(_delete_archival_config, "archival configuration deletion")


@router.post("/refresh-cache", response_model=dict[str, Any])
async def refresh_archival_cache(
    current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
):
    """Refresh the archival configuration cache"""

    def _refresh_archival_cache():
        refresh_config_cache()
        return {
            "message": "Archival configuration cache refreshed successfully",
            "refreshed_by": current_user["user_id"],
        }

    return handle_business_operation(_refresh_archival_cache, "archival configuration cache refresh")


@router.get("/priority-order", response_model=list[str])
async def get_priority_order(
    current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get the current archival priority order"""

    def _get_priority_order():
        priority_order = get_archival_priority_order()
        return priority_order

    return handle_business_operation(_get_priority_order, "archival priority order retrieval")


@router.get("/categories", response_model=dict[str, Any])
async def get_archival_categories(
    current_user: dict = Depends(get_current_user), db: psycopg2.extensions.connection = Depends(get_db)
):
    """Get available archival categories"""

    def _get_archival_categories():
        categories = []
        for category in ArchivalCategory:
            categories.append(
                {
                    "value": category.value,
                    "name": category.name,
                    "description": category.value.replace("_", " ").title(),
                }
            )

        return {"categories": categories, "total_categories": len(categories)}

    return handle_business_operation(_get_archival_categories, "archival categories retrieval")


@router.get("/history/{config_id}", response_model=list[dict[str, Any]])
async def get_config_history(
    config_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get change history for a specific configuration"""

    def _get_config_history():
        query = """
        SELECT event_id, table_name, category, retention_days, grace_period_days,
               priority, description, is_active, effective_date, modified_by,
               modified_date, is_current, valid_until, change_reason
        FROM archival_config_history
        WHERE config_id = %s
        ORDER BY event_id DESC
        """

        results = db_read(query, (config_id,), fetch_one=False, connection=db)
        if not results:
            return []

        history = []
        for result in results:
            history.append(
                {
                    "event_id": result[0],
                    "table_name": result[1],
                    "category": result[2],
                    "retention_days": result[3],
                    "grace_period_days": result[4],
                    "priority": result[5],
                    "description": result[6] or "",
                    "is_active": result[7],
                    "effective_date": result[8].isoformat(),
                    "modified_by": result[9],
                    "modified_date": result[10].isoformat(),
                    "is_current": result[11],
                    "valid_until": result[12].isoformat() if result[12] != "infinity" else "infinity",
                    "change_reason": result[13] or "",
                }
            )

        return history

    return handle_business_operation(_get_config_history, "configuration history retrieval")
