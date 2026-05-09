"""Employer Benefits Program routes — program config, enrollment, billing."""

from typing import Any
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.auth.dependencies import get_current_user, get_employee_user, get_resolved_locale
from app.dependencies.database import get_db
from app.dto.models import EmployerBenefitsProgramDTO
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.schemas.employer_program import (
    BenefitEmployeeResponseSchema,
    BulkEnrollResultSchema,
    EmployeeEnrollSchema,
    EmployeeSubscribeSchema,
    EmployerBillDetailResponseSchema,
    EmployerBillResponseSchema,
    EmployerEmployeeLinkResponseSchema,
    EmployerEmployeeLinkUpsertSchema,
    EmployerProgramUpsertSchema,
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
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Create a benefits program for an Employer institution. Internal only."""
    data = body.model_dump(exclude_unset=True)
    return program_service.create_program(data, db, modified_by=current_user["user_id"], locale=locale)


@router.get("/program", response_model=ProgramResponseSchema)
def get_program(
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    institution_entity_id: UUID | None = Query(
        None, description="Entity ID for entity-level program. Omit for institution-level."
    ),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """View program config. Pass institution_entity_id for entity-level override, omit for institution default."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param, locale)
    if institution_entity_id:
        program = program_service.get_program_by_scope(institution_id, institution_entity_id, db)
    else:
        program = program_service.get_program_by_institution(institution_id, db)
    if not program:
        raise envelope_exception(
            ErrorCode.EMPLOYER_BENEFIT_PROGRAM_NOT_FOUND,
            status=404,
            locale=locale,
        )
    return program


@router.get("/programs", response_model=list[ProgramResponseSchema])
def list_programs(
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List all programs for an institution (institution-level default + entity overrides)."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param, locale)
    return program_service.get_all_programs_for_institution(institution_id, db)


@router.put("/program", response_model=ProgramResponseSchema)
def update_program(
    body: ProgramUpdateSchema,
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    institution_entity_id: UUID | None = Query(
        None, description="Entity ID for entity-level program. Omit for institution-level."
    ),
    current_user: dict = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update program config. Pass institution_entity_id for entity-level override, omit for institution default."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param, locale)
    program = program_service.get_program_by_scope(institution_id, institution_entity_id, db)
    if not program:
        raise envelope_exception(
            ErrorCode.EMPLOYER_BENEFIT_PROGRAM_NOT_FOUND,
            status=404,
            locale=locale,
        )
    updates = body.model_dump(exclude_unset=True)
    return program_service.update_program(
        program.program_id, updates, db, modified_by=current_user["user_id"], locale=locale
    )


@router.put("/program/by-key", response_model=ProgramResponseSchema, status_code=200)
def upsert_program_by_key(
    body: EmployerProgramUpsertSchema,
    current_user: dict = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> EmployerBenefitsProgramDTO:
    """Idempotent upsert an employer benefits program by canonical_key.

    INTERNAL SEED/FIXTURE ENDPOINT ONLY — never use for production program
    creation (use POST /employer/program instead).

    If a program with the given canonical_key already exists it is updated
    in-place; otherwise a new program is inserted. Running the same request
    twice is a no-op (idempotent).

    Auth: Internal only (get_employee_user). Returns 403 for non-Internal roles.
    HTTP 200 on both insert and update.
    """
    data = body.model_dump(exclude={"canonical_key"})
    return program_service.upsert_program_by_canonical_key(
        body.canonical_key, data, db, modified_by=current_user["user_id"], locale=locale
    )


@router.delete("/program", status_code=204)
def archive_entity_program(
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    institution_entity_id: UUID = Query(..., description="Entity ID whose program override to archive (required)"),
    current_user: dict = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Archive entity-level program override. Entity reverts to institution defaults. Internal only."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param, locale)
    program = program_service.get_program_by_scope(institution_id, institution_entity_id, db)
    if not program:
        raise envelope_exception(
            ErrorCode.EMPLOYER_BENEFIT_PROGRAM_NOT_FOUND,
            status=404,
            locale=locale,
        )
    program_service.update_program(
        program.program_id,
        {"is_archived": True},
        db,
        modified_by=current_user["user_id"],
        locale=locale,
    )


# =============================================================================
# Employee Enrollment
# =============================================================================


@router.post("/employees", response_model=BenefitEmployeeResponseSchema, status_code=201)
def enroll_employee(
    body: EmployeeEnrollSchema,
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Enroll a single benefit employee. Employer Admin or Internal."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param, locale)
    employee_data = body.model_dump()

    market_id, city_locale = _resolve_market_and_locale_for_city(employee_data["city_metadata_id"], db, locale)
    employee_data["market_id"] = market_id
    employee_data["locale"] = city_locale

    user = enrollment_service.enroll_single_employee(
        institution_id, employee_data, db, modified_by=current_user["user_id"], locale=locale
    )
    return _user_to_employee_response(user, db)


@router.post("/employees/bulk", response_model=BulkEnrollResultSchema)
async def enroll_employees_bulk(
    file: UploadFile = File(..., description="CSV file with columns: email, first_name, last_name"),
    city_metadata_id: UUID = Form(..., description="City for all employees in this batch"),
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Bulk enroll benefit employees from CSV. Employer Admin only."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param, locale)
    _require_employer_admin(current_user, locale)

    market_id, city_locale = _resolve_market_and_locale_for_city(city_metadata_id, db, locale)

    contents = await file.read()
    csv_text = contents.decode("utf-8")

    result = enrollment_service.enroll_bulk_employees(
        institution_id, csv_text, city_metadata_id, market_id, city_locale, db, modified_by=current_user["user_id"]
    )
    return result


@router.get("/employees", response_model=list[BenefitEmployeeResponseSchema])
def list_employees(
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List benefit employees in the employer institution."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param, locale)
    rows = enrollment_service.list_benefit_employees(institution_id, db)
    return rows


@router.delete("/employees/{user_id}", status_code=204)
def deactivate_employee(
    user_id: UUID,
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Deactivate a benefit employee — archive user and cancel subscription."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param, locale)
    enrollment_service.deactivate_employee(
        institution_id, user_id, db, modified_by=current_user["user_id"], locale=locale
    )


@router.put("/employee-link/by-key", response_model=EmployerEmployeeLinkResponseSchema, status_code=200)
def upsert_employee_link_by_key(
    body: EmployerEmployeeLinkUpsertSchema,
    current_user: dict = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> Any:
    """Idempotent upsert an employer-sponsored subscription by canonical_key.

    INTERNAL SEED/FIXTURE ENDPOINT ONLY. This endpoint idempotently creates an
    employer-sponsored subscription (active, fully-subsidized) for a Customer
    Comensal user in an employer institution. It is equivalent to POST
    /employer/employees/{user_id}/subscribe but is idempotent and sends no
    invite email.

    Prerequisites:
    - The user must already exist (via PUT /users/by-key or POST /employer/employees).
    - The employer institution must have an active benefits program.
    - The plan must be 100% employer-subsidized (benefit_rate=100 or no employee share).

    Auth: Internal only (get_employee_user). Returns 403 for non-Internal roles.
    HTTP 200 on both insert and update.
    """
    result = enrollment_service.upsert_employee_link_by_canonical_key(
        body.canonical_key,
        body.user_id,
        body.plan_id,
        db,
        modified_by=current_user["user_id"],
        locale=locale,
    )
    return result


@router.post("/employees/{user_id}/subscribe", status_code=201)
def subscribe_employee(
    user_id: UUID,
    body: EmployeeSubscribeSchema,
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Subscribe a benefit employee to a plan (no payment for 100% subsidy)."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param, locale)
    subscription = enrollment_service.subscribe_employee(
        institution_id, user_id, body.plan_id, db, modified_by=current_user["user_id"], locale=locale
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
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List employer bills. Employer Admin or Internal."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param, locale)
    return billing_service.list_employer_bills(institution_id, db)


@router.get("/billing/{bill_id}", response_model=EmployerBillDetailResponseSchema)
def get_bill_detail(
    bill_id: UUID,
    institution_id_param: UUID | None = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Get employer bill detail with line items."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param, locale)
    detail = billing_service.get_employer_bill_detail(bill_id, institution_id, db)
    if not detail:
        raise envelope_exception(
            ErrorCode.BILLING_BILL_NOT_FOUND,
            status=404,
            locale=locale,
        )
    return detail


@router.post("/billing/generate", response_model=EmployerBillDetailResponseSchema, status_code=201)
def generate_bill(
    body: GenerateBillRequestSchema,
    current_user: dict = Depends(get_employee_user),
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Manual trigger to generate an employer bill for a period. Internal only."""
    result = billing_service.generate_employer_bill(
        body.institution_id, body.period_start, body.period_end, db, modified_by=current_user["user_id"], locale=locale
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


def _resolve_employer_institution(
    current_user: dict, institution_id_override: UUID | None = None, locale: str = "en"
) -> UUID:
    """Resolve the employer institution_id.
    - Employer users: use their own institution_id from JWT.
    - Internal users: must provide institution_id via query param (they are global-scoped, not tied to an Employer institution)."""
    role_type = (current_user.get("role_type") or "").strip()
    if role_type == "internal":
        if institution_id_override:
            return institution_id_override
        raise envelope_exception(
            ErrorCode.ENROLLMENT_EMPLOYER_INSTITUTION_ID_REQUIRED,
            status=400,
            locale=locale,
        )
    if role_type == "employer":
        inst_id = current_user.get("institution_id")
        if not inst_id:
            raise envelope_exception(
                ErrorCode.SECURITY_FORBIDDEN,
                status=403,
                locale=locale,
            )
        return inst_id if isinstance(inst_id, UUID) else UUID(str(inst_id))
    raise envelope_exception(
        ErrorCode.SECURITY_FORBIDDEN,
        status=403,
        locale=locale,
    )


def _resolve_market_and_locale_for_city(
    city_metadata_id: UUID,
    db: psycopg2.extensions.connection,
    locale: str = "en",
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
        raise envelope_exception(
            ErrorCode.ENROLLMENT_CITY_NO_MARKET,
            status=400,
            locale=locale,
        )
    return str(row["market_id"]), (row.get("language") or "en")


def _require_employer_admin(current_user: dict, locale: str = "en"):
    """Raise 403 if user is not Employer Admin."""
    role_type = (current_user.get("role_type") or "").strip()
    role_name = (current_user.get("role_name") or "").strip()
    if role_type == "internal":
        return
    if role_type != "employer" or role_name != "admin":
        raise envelope_exception(
            ErrorCode.SECURITY_INSUFFICIENT_PERMISSIONS,
            status=403,
            locale=locale,
        )


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
