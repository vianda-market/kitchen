"""Employer Benefits Program routes — program config, enrollment, billing."""
from typing import List, Optional
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query

from app.auth.dependencies import get_current_user, get_employee_user
from app.dependencies.database import get_db
from app.schemas.employer_program import (
    ProgramCreateSchema,
    ProgramUpdateSchema,
    ProgramResponseSchema,
    EmployeeEnrollSchema,
    EmployeeSubscribeSchema,
    BenefitEmployeeResponseSchema,
    BulkEnrollResultSchema,
    EmployerBillResponseSchema,
    EmployerBillDetailResponseSchema,
    GenerateBillRequestSchema,
    DomainCreateSchema,
    DomainCreateResponseSchema,
    DomainResponseSchema,
)
from app.services.employer import program_service, enrollment_service, billing_service

router = APIRouter(prefix="/employer", tags=["Employer Program"])


def _get_institution_id_param(
    institution_id: Optional[UUID] = Query(None, description="Employer institution ID (required for Internal users, ignored for Employer users)")
) -> Optional[UUID]:
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
    institution_id_param: Optional[UUID] = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """View own program config. Employer Admin or Internal (pass institution_id query param)."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    program = program_service.get_program_by_institution(institution_id, db)
    if not program:
        raise HTTPException(status_code=404, detail="No benefits program found for your institution")
    return program


@router.put("/program", response_model=ProgramResponseSchema)
def update_program(
    body: ProgramUpdateSchema,
    institution_id_param: Optional[UUID] = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_employee_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Update program config. Internal only. Requires institution_id query param or body."""
    institution_id = current_user.get("institution_id")
    program = program_service.get_program_by_institution(institution_id, db) if institution_id else None
    if not program:
        raise HTTPException(status_code=404, detail="No benefits program found")
    updates = body.model_dump(exclude_unset=True)
    return program_service.update_program(program.program_id, updates, db, modified_by=current_user["user_id"])


# =============================================================================
# Employee Enrollment
# =============================================================================

@router.post("/employees", response_model=BenefitEmployeeResponseSchema, status_code=201)
def enroll_employee(
    body: EmployeeEnrollSchema,
    institution_id_param: Optional[UUID] = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Enroll a single benefit employee. Employer Admin or Internal."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    employee_data = body.model_dump()

    from app.services.crud_service import city_service
    city = city_service.get_by_id(employee_data["city_id"], db)
    if not city:
        raise HTTPException(status_code=400, detail="City not found")
    employee_data["market_id"] = getattr(city, "market_id", None)
    employee_data["locale"] = getattr(city, "language", "en") or "en"

    user = enrollment_service.enroll_single_employee(
        institution_id, employee_data, db, modified_by=current_user["user_id"]
    )
    return _user_to_employee_response(user, db)


@router.post("/employees/bulk", response_model=BulkEnrollResultSchema)
async def enroll_employees_bulk(
    file: UploadFile = File(..., description="CSV file with columns: email, first_name, last_name"),
    city_id: UUID = Form(..., description="City for all employees in this batch"),
    institution_id_param: Optional[UUID] = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Bulk enroll benefit employees from CSV. Employer Admin only."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    _require_employer_admin(current_user)

    from app.services.crud_service import city_service
    city = city_service.get_by_id(city_id, db)
    if not city:
        raise HTTPException(status_code=400, detail="City not found")
    market_id = getattr(city, "market_id", None)
    locale = getattr(city, "language", "en") or "en"

    contents = await file.read()
    csv_text = contents.decode("utf-8")

    result = enrollment_service.enroll_bulk_employees(
        institution_id, csv_text, city_id, market_id, locale, db, modified_by=current_user["user_id"]
    )
    return result


@router.get("/employees", response_model=List[BenefitEmployeeResponseSchema])
def list_employees(
    institution_id_param: Optional[UUID] = Depends(_get_institution_id_param),
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
    institution_id_param: Optional[UUID] = Depends(_get_institution_id_param),
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
    institution_id_param: Optional[UUID] = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Subscribe a benefit employee to a plan (no payment for 100% subsidy)."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    subscription = enrollment_service.subscribe_employee(
        institution_id, user_id, body.plan_id, db, modified_by=current_user["user_id"]
    )
    return subscription


# =============================================================================
# Domain Management
# =============================================================================

@router.post("/domains", response_model=DomainCreateResponseSchema, status_code=201)
def add_domain(
    body: DomainCreateSchema,
    institution_id_param: Optional[UUID] = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Add an allowed email domain for domain-gated enrollment. Employer Admin only.
    Existing users with matching emails in Vianda Customers will be migrated to this institution."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    _require_employer_admin(current_user)

    from app.config.settings import EMPLOYER_DOMAIN_BLACKLIST
    domain = body.domain.lower().strip()
    if domain in EMPLOYER_DOMAIN_BLACKLIST:
        raise HTTPException(status_code=400, detail=f"'{domain}' is a common email provider and cannot be registered as an employer domain")

    from app.services.crud_service import employer_domain_service
    existing = employer_domain_service.get_all(
        db, scope=None,
        additional_conditions=[("domain = %s", domain)],
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Domain '{domain}' is already registered")

    domain_data = {
        "institution_id": str(institution_id),
        "domain": domain,
        "modified_by": str(current_user["user_id"]),
    }
    created = employer_domain_service.create(domain_data, db, scope=None)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to create domain")

    migrated_count = enrollment_service.migrate_existing_users_for_domain(
        domain, institution_id, db, modified_by=current_user["user_id"]
    )

    return {
        "domain_id": created.domain_id,
        "institution_id": created.institution_id,
        "domain": created.domain,
        "is_active": created.is_active,
        "migrated_user_count": migrated_count,
        "created_date": created.created_date,
    }


@router.get("/domains", response_model=List[DomainResponseSchema])
def list_domains(
    institution_id_param: Optional[UUID] = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List configured email domains for this employer institution."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    from app.services.crud_service import employer_domain_service
    return employer_domain_service.get_all(
        db, scope=None,
        additional_conditions=[("institution_id = %s::uuid", str(institution_id))],
    )


@router.delete("/domains/{domain_id}", status_code=204)
def remove_domain(
    domain_id: UUID,
    institution_id_param: Optional[UUID] = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """Remove an email domain. Employer Admin only. Existing users are NOT migrated back."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    _require_employer_admin(current_user)
    from app.services.crud_service import employer_domain_service
    domain = employer_domain_service.get_by_id(domain_id, db, scope=None)
    if not domain or str(domain.institution_id) != str(institution_id):
        raise HTTPException(status_code=404, detail="Domain not found")
    employer_domain_service.update(
        domain_id,
        {"is_archived": True, "is_active": False, "modified_by": str(current_user["user_id"])},
        db, scope=None,
    )


# =============================================================================
# Billing
# =============================================================================

@router.get("/billing", response_model=List[EmployerBillResponseSchema])
def list_bills(
    institution_id_param: Optional[UUID] = Depends(_get_institution_id_param),
    current_user: dict = Depends(get_current_user),
    db: psycopg2.extensions.connection = Depends(get_db),
):
    """List employer bills. Employer Admin or Internal."""
    institution_id = _resolve_employer_institution(current_user, institution_id_param)
    return billing_service.list_employer_bills(institution_id, db)


@router.get("/billing/{bill_id}", response_model=EmployerBillDetailResponseSchema)
def get_bill_detail(
    bill_id: UUID,
    institution_id_param: Optional[UUID] = Depends(_get_institution_id_param),
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

def _resolve_employer_institution(current_user: dict, institution_id_override: Optional[UUID] = None) -> UUID:
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
