"""Schemas for Employer Benefits Program: program config, employee enrollment, billing."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.config import Status
from app.schemas.types import MoneyDecimal, NullableMoneyDecimal

# =============================================================================
# Program CRUD
# =============================================================================


class ProgramCreateSchema(BaseModel):
    """Schema for creating an employer benefits program."""

    institution_id: UUID = Field(..., description="Employer institution ID (must be institution_type='Employer')")
    institution_entity_id: UUID | None = Field(
        None, description="Entity ID for entity-level override. NULL = institution-level defaults."
    )
    benefit_rate: int = Field(..., ge=0, le=100, description="Percentage of plan price employer covers (0-100)")
    benefit_cap: Decimal | None = Field(
        None, ge=0, description="Max amount employer subsidizes per employee. NULL = no cap."
    )
    benefit_cap_period: str = Field("monthly", description="'per_renewal' or 'monthly'")
    price_discount: int = Field(0, ge=0, le=100, description="Negotiated discount on employer's bill (0-100)")
    minimum_monthly_fee: Decimal | None = Field(
        None, ge=0, description="Floor for monthly employer charges. NULL = no minimum."
    )
    billing_cycle: str = Field("monthly", description="'daily', 'weekly', or 'monthly'")
    billing_day: int | None = Field(1, ge=1, le=28, description="Day of month for monthly billing (1-28)")
    enrollment_mode: str = Field("managed", description="'managed' or 'domain_gated'")
    allow_early_renewal: bool = Field(
        False, description="If FALSE, benefit employees default to period-end-only renewal"
    )


class ProgramUpdateSchema(BaseModel):
    """Schema for updating an employer benefits program."""

    benefit_rate: int | None = Field(None, ge=0, le=100)
    benefit_cap: Decimal | None = Field(None, ge=0)
    benefit_cap_period: str | None = None
    price_discount: int | None = Field(None, ge=0, le=100)
    minimum_monthly_fee: Decimal | None = Field(None, ge=0)
    billing_cycle: str | None = None
    billing_day: int | None = Field(None, ge=1, le=28)
    enrollment_mode: str | None = None
    allow_early_renewal: bool | None = None
    is_active: bool | None = None


class ProgramResponseSchema(BaseModel):
    """Schema for employer benefits program response."""

    program_id: UUID
    institution_id: UUID
    institution_entity_id: UUID | None = None
    benefit_rate: int
    benefit_cap: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    benefit_cap_period: str
    price_discount: int
    minimum_monthly_fee: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    billing_cycle: str
    billing_day: int | None = None
    billing_day_of_week: int | None = None
    enrollment_mode: str
    allow_early_renewal: bool
    stripe_customer_id: str | None = None
    stripe_payment_method_id: str | None = None
    payment_method_type: str | None = None
    is_active: bool
    is_archived: bool
    status: Status
    canonical_key: str | None = None
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployerProgramUpsertSchema(BaseModel):
    """Schema for idempotent employer benefits program upsert by canonical_key.

    INTERNAL SEED/FIXTURE ENDPOINT ONLY. Use this endpoint for Postman seed runs
    and demo fixture data — NEVER for production program creation (use POST
    /employer/program instead).

    If a program with the given canonical_key already exists it is updated in-place;
    otherwise a new program is inserted. Running the same request twice is a no-op.

    Auth: Internal only (get_employee_user). Returns 403 for non-Internal roles.
    HTTP 200 on both insert and update (unlike POST which returns 201).
    """

    canonical_key: str = Field(
        ...,
        max_length=200,
        description=(
            "Stable identifier for this program fixture. "
            "Convention: EMPLOYER_<INSTITUTION_SLUG>_PROGRAM[_ENTITY_<CC>]. "
            "Once set, never rename."
        ),
    )
    institution_id: UUID = Field(..., description="Employer institution ID (must be institution_type='Employer')")
    institution_entity_id: UUID | None = Field(
        None,
        description="Entity ID for entity-level override. NULL = institution-level defaults.",
    )
    benefit_rate: int = Field(..., ge=0, le=100, description="Percentage of plan price employer covers (0-100)")
    benefit_cap: Decimal | None = Field(None, ge=0, description="Max subsidy amount per cap period. NULL = no cap.")
    benefit_cap_period: str = Field("monthly", description="'per_renewal' or 'monthly'")
    price_discount: int = Field(0, ge=0, le=100, description="Negotiated discount on employer's bill (0-100)")
    minimum_monthly_fee: Decimal | None = Field(None, ge=0, description="Floor for monthly charges. NULL = no floor.")
    billing_cycle: str = Field("monthly", description="'daily', 'weekly', or 'monthly'")
    billing_day: int | None = Field(1, ge=1, le=28, description="Day of month for monthly billing (1-28)")
    enrollment_mode: str = Field("managed", description="'managed' or 'domain_gated'")
    allow_early_renewal: bool = Field(False, description="Whether employees can trigger early renewal")


class EmployerEmployeeLinkUpsertSchema(BaseModel):
    """Schema for idempotent employer employee program-link upsert by canonical_key.

    INTERNAL SEED/FIXTURE ENDPOINT ONLY. This endpoint idempotently creates an
    employer-sponsored subscription for a Customer Comensal user in an employer
    institution. It is equivalent to POST /employer/employees/{user_id}/subscribe
    but is idempotent: if the user already has an active subscription to the
    specified plan, it returns the existing subscription with HTTP 200.

    Differences from POST /employer/employees/{user_id}/subscribe:
    - No invite email is sent (the user must already exist via PUT /users/by-key).
    - Idempotent: re-running with the same canonical_key is a no-op.
    - The canonical_key is stamped on the subscription_info row.

    Auth: Internal only (get_employee_user). Returns 403 for non-Internal roles.
    HTTP 200 on both insert and update.
    """

    canonical_key: str = Field(
        ...,
        max_length=200,
        description=(
            "Stable identifier for this employee-program link fixture. "
            "Convention: EMPLOYER_<INSTITUTION_SLUG>_EE_<USERNAME_SLUG>_LINK. "
            "Once set, never rename."
        ),
    )
    user_id: UUID = Field(
        ...,
        description="User ID of the employee (Customer Comensal in the employer institution).",
    )
    plan_id: UUID = Field(..., description="Plan to subscribe the employee to.")


class EmployerEmployeeLinkResponseSchema(BaseModel):
    """Response schema for employer employee-link upsert."""

    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    market_id: UUID
    balance: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    renewal_date: datetime
    subscription_status: str | None = None
    canonical_key: str | None = None
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Employee Enrollment
# =============================================================================


class EmployeeEnrollSchema(BaseModel):
    """Schema for enrolling a single benefit employee."""

    email: str = Field(..., max_length=255, description="Employee email address")
    first_name: str = Field(..., max_length=50)
    last_name: str = Field(..., max_length=50)
    mobile_number: str | None = Field(None, max_length=16, description="E.164 format: +1234567890")
    city_metadata_id: UUID = Field(
        ..., description="City for the employee (cannot be Global). FK to core.city_metadata."
    )


class EmployeeSubscribeSchema(BaseModel):
    """Schema for subscribing a benefit employee to a plan (no payment for 100% subsidy)."""

    plan_id: UUID = Field(..., description="Plan to subscribe the employee to")


class BenefitEmployeeResponseSchema(BaseModel):
    """Schema for benefit employee in list response (enriched with subscription status)."""

    user_id: UUID
    email: str
    first_name: str | None = None
    last_name: str | None = None
    mobile_number: str | None = None
    user_status: Status
    subscription_id: UUID | None = None
    subscription_status: str | None = None
    plan_name: str | None = None
    plan_price: float | None = None
    balance: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    renewal_date: datetime | None = None
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkEnrollResultSchema(BaseModel):
    """Result of a bulk employee enrollment operation."""

    created_count: int
    skipped_count: int
    error_count: int
    created: list[str] = Field(default_factory=list, description="Emails successfully enrolled")
    skipped: list[dict] = Field(default_factory=list, description="[{'email': '...', 'reason': '...'}]")
    errors: list[dict] = Field(default_factory=list, description="[{'row': 3, 'email': '...', 'reason': '...'}]")


# =============================================================================
# Billing
# =============================================================================


class EmployerBillResponseSchema(BaseModel):
    """Schema for employer bill response."""

    employer_bill_id: UUID
    institution_id: UUID
    institution_entity_id: UUID
    billing_period_start: date
    billing_period_end: date
    billing_cycle: str
    total_renewal_events: int
    gross_employer_share: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    price_discount: int
    discounted_amount: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    minimum_fee_applied: bool
    billed_amount: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    currency_code: str
    stripe_invoice_id: str | None = None
    payment_status: str
    paid_date: datetime | None = None
    is_archived: bool
    status: Status
    created_date: datetime
    modified_date: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployerBillLineResponseSchema(BaseModel):
    """Schema for employer bill line item response."""

    line_id: UUID
    employer_bill_id: UUID
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    plan_price: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    benefit_rate: int
    benefit_cap: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    benefit_cap_period: str | None = None
    employee_benefit: MoneyDecimal  # serialises as JSON number; see app/schemas/types.py
    renewal_date: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployerBillDetailResponseSchema(BaseModel):
    """Schema for employer bill detail with line items."""

    bill: EmployerBillResponseSchema
    lines: list[EmployerBillLineResponseSchema]


class GenerateBillRequestSchema(BaseModel):
    """Schema for manual bill generation trigger."""

    institution_id: UUID = Field(..., description="Employer institution to generate bill for")
    period_start: date = Field(..., description="Billing period start date")
    period_end: date = Field(..., description="Billing period end date")


## Domain schemas REMOVED — email_domain is now a column on institution_entity_info,
## managed via entity CRUD. See docs/plans/MULTINATIONAL_INSTITUTIONS.md

# =============================================================================
# Benefit Plan Breakdown (for B2C app)
# =============================================================================


class BenefitPlanBreakdownSchema(BaseModel):
    """Schema for plan with employer benefit breakdown."""

    plan_id: UUID
    plan_name: str
    plan_price: float
    plan_credit: int
    employer_covers: float = Field(description="Amount employer covers")
    employee_pays: float = Field(description="Amount employee must pay")
    benefit_rate: int
    benefit_cap: NullableMoneyDecimal = None  # serialises as JSON number; see app/schemas/types.py
    benefit_cap_period: str | None = None
    remaining_monthly_cap: float | None = Field(None, description="Remaining monthly cap budget")
    period_start: date = Field(..., description="Billing period start date")
    period_end: date = Field(..., description="Billing period end date")
