from typing import Optional
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user, get_employee_user, get_super_admin_user
from app.dependencies.database import get_db
from app.schemas.onboarding import (
    OnboardingStatusResponseSchema,
    OnboardingSummaryResponseSchema,
)
from app.security.scoping import InstitutionScope
from app.services.onboarding_service import get_onboarding_status, get_onboarding_summary
from app.utils.db import db_read

router = APIRouter(
    prefix="/institutions",
    tags=["Onboarding"],
)


@router.get(
    "/onboarding-summary",
    response_model=OnboardingSummaryResponseSchema,
)
def list_onboarding_summary(
    institution_type: str = Query("Supplier", description="Supplier or Employer"),
    market_id: Optional[UUID] = Query(None),
    onboarding_status: Optional[str] = Query(None),
    stalled_days: Optional[int] = Query(None),
    current_user: dict = Depends(get_super_admin_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Aggregated onboarding funnel view — Internal Super Admin only."""
    if institution_type not in ("Supplier", "Employer"):
        raise HTTPException(status_code=400, detail="institution_type must be Supplier or Employer")
    result = get_onboarding_summary(
        db,
        institution_type=institution_type,
        market_id=market_id,
        onboarding_status_filter=onboarding_status,
        stalled_days=stalled_days,
    )
    return result


@router.get(
    "/{institution_id}/onboarding-status",
    response_model=OnboardingStatusResponseSchema,
)
def get_institution_onboarding_status(
    institution_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Onboarding status for a single institution."""
    scope = InstitutionScope(
        institution_id=current_user.get("institution_id"),
        role_type=current_user.get("role_type"),
        role_name=current_user.get("role_name"),
    )
    scope.enforce(institution_id)

    # Fetch institution_type
    row = db_read(
        "SELECT institution_type FROM core.institution_info WHERE institution_id = %s",
        (str(institution_id),),
        connection=db,
        fetch_one=True,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Institution not found")

    institution_type = row["institution_type"]
    result = get_onboarding_status(institution_id, institution_type, db)
    if not result:
        raise HTTPException(status_code=404, detail="Institution not found")

    # Hide stalled status from non-Internal users
    if result["onboarding_status"] == "stalled" and current_user.get("role_type") != "Internal":
        result["onboarding_status"] = "in_progress"

    return result


@router.post("/onboarding-stall-detection", status_code=200)
def run_stall_detection_cron(
    current_user: dict = Depends(get_employee_user),
):
    """Run supplier stall detection cron. Internal only. Sends onboarding outreach emails."""
    from app.services.cron.supplier_stall_detection import run_supplier_stall_detection
    return run_supplier_stall_detection()


@router.post("/onboarding-customer-engagement", status_code=200)
def run_customer_engagement_cron(
    current_user: dict = Depends(get_employee_user),
):
    """Run customer engagement cron. Internal only. Sends subscription prompts to unsubscribed customers."""
    from app.services.cron.customer_engagement import run_customer_engagement
    return run_customer_engagement()
