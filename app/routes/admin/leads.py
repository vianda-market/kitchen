"""
Admin Leads Routes — Internal-only visibility into lead interest data.

Read-only for Phase 1. Future: mark as contacted, bulk export, aggregate charts.
"""

from datetime import datetime
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_employee_user
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import LeadInterestResponseSchema
from app.services.leads_public_service import get_lead_interests

router = APIRouter(prefix="/admin/leads", tags=["Admin Leads"])


@router.get("/interest", response_model=list[LeadInterestResponseSchema])
async def list_lead_interests(
    country_code: str | None = Query(None, description="Filter by country code (e.g. US)"),
    city_name: str | None = Query(None, description="Filter by city name"),
    interest_type: str | None = Query(None, description="Filter: customer, employer, supplier"),
    status: str | None = Query(None, description="Filter: active, notified, unsubscribed"),
    cuisine_id: UUID | None = Query(None, description="Filter by cuisine UUID"),
    employee_count_range: str | None = Query(None, description="Filter by company size range (e.g. 51-100)"),
    created_after: datetime | None = Query(None, description="Filter: created on or after this date (ISO 8601)"),
    created_before: datetime | None = Query(None, description="Filter: created on or before this date (ISO 8601)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Results per page"),
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """
    List lead interest records with optional filters. Internal employees only.

    Returns paginated results with total count in X-Total-Count header.
    """
    rows, total = get_lead_interests(
        db,
        country_code=country_code,
        city_name=city_name,
        interest_type=interest_type,
        interest_status=status,
        cuisine_id=str(cuisine_id) if cuisine_id else None,
        employee_count_range=employee_count_range,
        created_after=created_after.isoformat() if created_after else None,
        created_before=created_before.isoformat() if created_before else None,
        page=page,
        page_size=page_size,
    )
    # Total count as response header for pagination
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse

    response = JSONResponse(
        content=jsonable_encoder([LeadInterestResponseSchema(**r) for r in rows]),
    )
    response.headers["X-Total-Count"] = str(total)
    return response
