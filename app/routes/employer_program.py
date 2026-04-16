"""Employer Benefits Program routes — program config, enrollment, billing."""

from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.auth.dependencies import get_current_user, get_employee_user
from app.dependencies.database import get_db
from app.schemas.employer_program import (
    BenefitEmployeeResponseSchema,
    BulkEnrollResultSchema,
    EmployeeEnrollSchema,
    EmployeeSubscribeSchema,
    EmployerBillDetailResponseSchema,
    EmployerBillResponseSchema,
    GenerateBillRequestSchema,
    # Domain schemas REMOVED — email_domain is on institution_entity_info
    ProgramCreateSchema,
    ProgramResponseSchema,
    ProgramUpdateSchema,
)
from app.services.employer import billing_service, enrollment_service, program_service

router = APIRouter(prefix="/employer", tags=["Employer Program"])


def _get_institution_id_param(
    institution_id: UUID | None = Query(
        None, description="Employer institution ID (required for Internal users, ignored for Employer users)"
    ),
) -> UUID | None:
    """FastAPI dependency: extract optional institution_id query param."""
    return institution_id


# =============================================================================
# Program CRUD
# =============================================================================


@router.post("/program", response_model=ProgramResponseSchema, status_code=201)
def create_program(
    body: ProgramCreateSchema,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Create a benefits program for an Employer institution. Internal only."""
    data = body.model_dump(exclude_unset=True)
    return program_service.create_program(data, db, modified_by=current_user["user_id"])


@router.get("/program", response_model=ProgramResponseSchema)
def get_program(
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    institution_entity_id: UUID | None = Query(
        None, description="Entity ID for entity-level program. Omit for institution-level."
    ),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """View program config. Pass institution_entity_id for entity-level override, omit for institution default."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    if institution_entity_id:
        program = program_service.get_program_by_scope(institution_id, institution_entity_id, db)
    else:
        program = program_service.get_program_by_institution(institution_id, db)
    if not program:
        scope = f"entity {institution_entity_id}" if institution_entity_id else "your institution"
        raise HTTPException(status_code=404, detail=f"No benefits program found for {scope}")
    return program


@router.get("/programs", response_model=list[ProgramResponseSchema])
def list_programs(
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List all programs for an institution (institution-level default + entity overrides)."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    return program_service.get_all_programs_for_institution(institution_id, db)


@router.put("/program", response_model=ProgramResponseSchema)
def update_program(
    body: ProgramUpdateSchema,
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    institution_entity_id: UUID | None = Query(
        None, description="Entity ID for entity-level program. Omit for institution-level."
    ),
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update program config. Pass institution_entity_id for entity-level override, omit for institution default."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    program = program_service.get_program_by_scope(institution_id, institution_entity_id, db)
    if not program:
        scope = f"entity {institution_entity_id}" if institution_entity_id else "institution"
        raise HTTPException(status_code=404, detail=f"No benefits program found for {scope}")
    updates = body.model_dump(exclude_unset=True)
    return program_service.update_program(program.program_id, updates, db, modified_by=current_user["user_id"])


@router.delete("/program", status_code=204)
def archive_entity_program(
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    institution_entity_id: UUID = Query(..., description="Entity ID whose program override to archive (required)"),
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Archive entity-level program override. Entity reverts to institution defaults. Internal only."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    program = program_service.get_program_by_scope(institution_id, institution_entity_id, db)
    if not program:
        raise HTTPException(status_code=404, detail="Entity-level program not found")
    program_service.update_program(
        program.program_id,
        {"is_archived": True},
        db,
        modified_by=current_user["user_id"],
    )


# =============================================================================
# Employee Enrollment
# =============================================================================


@router.post("/employees", response_model=BenefitEmployeeResponseSchema, status_code=201)
def enroll_employee(
    body: EmployeeEnrollSchema,
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Enroll a single benefit employee. Employer Admin or Internal."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    employee_data = body.model_dump()

    market_id, locale = _resolve_market_and_locale_for_city(employee_data["city_metadata_id"], db)
    employee_data["market_id"] = market_id
    employee_data["locale"] = locale

    user = enrollment_service.enroll_single_employee(
        institution_id, employee_data, db, modified_by=current_user["user_id"]
    )
    return _user_to_employee_response(user, db)


@router.post("/employees/bulk", response_model=BulkEnrollResultSchema)
async def enroll_employees_bulk(
    file: UploadFile = File(..., description="CSV file with columns: email, first_name, last_name"),
    city_metadata_id: UUID = Form(..., description="City for all employees in this batch"),
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Bulk enroll benefit employees from CSV. Employer Admin only."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    _require_employer_admin(current_user)

    market_id, locale = _resolve_market_and_locale_for_city(city_metadata_id, db)

    contents = await file.read()
    csv_text = contents.decode("utf-8")

    result = enrollment_service.enroll_bulk_employees(
        institution_id, csv_text, city_metadata_id, market_id, locale, db, modified_by=current_user["user_id"]
    )
    return result


@router.get("/employees", response_model=list[BenefitEmployeeResponseSchema])
def list_employees(
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List benefit employees in the employer institution."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    rows = enrollment_service.list_benefit_employees(institution_id, db)
    return rows


@router.delete("/employees/{user_id}", status_code=204)
def deactivate_employee(
    user_id: UUID,
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Deactivate a benefit employee — archive user and cancel subscription."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    enrollment_service.deactivate_employee(institution_id, user_id, db, modified_by=current_user["user_id"])


@router.post("/employees/{user_id}/subscribe", status_code=201)
def subscribe_employee(
    user_id: UUID,
    body: EmployeeSubscribeSchema,
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Subscribe a benefit employee to a plan (no payment for 100% subsidy)."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    subscription = enrollment_service.subscribe_employee(
        institution_id, user_id, body.plan_id, db, modified_by=current_user["user_id"]
    )
    return subscription


# Domain Management REMOVED — email_domain is now a column on institution_entity_info,
# managed via entity CRUD. See docs/plans/MULTINATIONAL_INSTITUTIONS.md


# =============================================================================
# Billing
# =============================================================================


@router.get("/billing", response_model=list[EmployerBillResponseSchema])
def list_bills(
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List employer bills. Employer Admin or Internal."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    return billing_service.list_employer_bills(institution_id, db)


@router.get("/billing/{bill_id}", response_model=EmployerBillDetailResponseSchema)
def get_bill_detail(
    bill_id: UUID,
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get employer bill detail with line items."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    detail = billing_service.get_employer_bill_detail(bill_id, institution_id, db)
    if not detail:
        raise HTTPException(status_code=404, detail="Bill not found")
    return detail


@router.post("/billing/generate", response_model=EmployerBillDetailResponseSchema, status_code=201)
def generate_bill(
    body: GenerateBillRequestSchema,
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Manual trigger to generate an employer bill for a period. Internal only."""
    result = billing_service.generate_employer_bill(
        body.institution_id, body.period_start, body.period_end, db, modified_by=current_user["user_id"]
    )
    return result


@router.post("/billing/run-cron", status_code=200)
def run_billing_cron(
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Run the employer billing cron job. Internal only. Checks all active programs and generates bills where due."""
    from app.services.cron.employer_billing import run_employer_billing

    result = run_employer_billing()
    return result


# =============================================================================
# Helpers
# =============================================================================


def _resolve_employer_institution(current_user: dict, institution_id_override: UUID | None = None) -> UUID:
    """Resolve the employer institution_id.
    - Employer users: use their own institution_id from JWT.
    - Internal users: must provide institution_id via query param (they are global-scoped, not tied to an Employer institution)."""
    role_type = (current_user.get("role_type") or "").strip()
    if role_type == "internal":
        if institution_id_override:
            return institution_id_override
        raise HTTPException(
            status_code=400,
            detail="Internal users must provide institution_id query parameter to specify which Employer institution to operate on.",
        )
    if role_type == "employer":
        inst_id = current_user.get("institution_id")
        if not inst_id:
            raise HTTPException(status_code=403, detail="No institution found for your account")
        return inst_id if isinstance(inst_id, UUID) else UUID(str(inst_id))
    raise HTTPException(status_code=403, detail="Only Employer and Internal users can access this resource")


def _resolve_market_and_locale_for_city(
    city_metadata_id: UUID,
    db: psycopg2.extensions.connection,
) -> tuple:
    """Resolve (market_id, locale) from a city_metadata row.
    city_metadata doesn't carry market_id/language directly — both come from
    core.market_info joined on country_iso → country_code."""
    from app.utils.db import db_read

    row = db_read(
        """
        SELECT m.market_id, m.language
        FROM core.city_metadata cm
        JOIN core.market_info m ON m.country_code = cm.country_iso
        WHERE cm.city_metadata_id = %s AND cm.is_archived = FALSE AND m.is_archived = FALSE
        """,
        (str(city_metadata_id),),
        connection=db,
        fetch_one=True,
    )
    if not row:
        raise HTTPException(status_code=400, detail="City not found or has no active market")
    return str(row["market_id"]), (row.get("language") or "en")


def _require_employer_admin(current_user: dict):
    """Raise 403 if user is not Employer Admin."""
    role_type = (current_user.get("role_type") or "").strip()
    role_name = (current_user.get("role_name") or "").strip()
    if role_type == "internal":
        return
    if role_type != "employer" or role_name != "admin":
        raise HTTPException(status_code=403, detail="Only Employer Admin can perform this action")


def _user_to_employee_response(user, db) -> dict:
    """Convert a user DTO to BenefitEmployeeResponseSchema-compatible dict."""
    from app.services.crud_service import subscription_service

    sub = subscription_service.get_by_user(user.user_id, db)
    return {
        "user_id": user.user_id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "mobile_number": getattr(user, "mobile_number", None),
        "user_status": user.status,
        "subscription_id": sub.subscription_id if sub else None,
        "subscription_status": sub.subscription_status if sub else None,
        "plan_name": None,
        "plan_price": None,
        "balance": sub.balance if sub else None,
        "renewal_date": sub.renewal_date if sub else None,
        "created_date": user.created_date,
    }
