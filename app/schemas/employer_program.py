"""Schemas for Employer Benefits Program: program config, employee enrollment, billing."""
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, date
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from app.config import Status


# =============================================================================
# Program CRUD
# =============================================================================

class ProgramCreateSchema(BaseModel):
    """Schema for creating an employer benefits program."""
    institution_id: UUID = Field(..., description="Employer institution ID (must be institution_type='Employer')")
    benefit_rate: int = Field(..., ge=0, le=100, description="Percentage of plan price employer covers (0-100)")
    benefit_cap: Optional[Decimal] = Field(None, ge=0, description="Max amount employer subsidizes per employee. NULL = no cap.")
    benefit_cap_period: str = Field("monthly", description="'per_renewal' or 'monthly'")
    price_discount: int = Field(0, ge=0, le=100, description="Negotiated discount on employer's bill (0-100)")
    minimum_monthly_fee: Optional[Decimal] = Field(None, ge=0, description="Floor for monthly employer charges. NULL = no minimum.")
    billing_cycle: str = Field("monthly", description="'daily', 'weekly', or 'monthly'")
    billing_day: Optional[int] = Field(1, ge=1, le=28, description="Day of month for monthly billing (1-28)")
    enrollment_mode: str = Field("managed", description="'managed' or 'domain_gated'")
    allow_early_renewal: bool = Field(False, description="If FALSE, benefit employees default to period-end-only renewal")


class ProgramUpdateSchema(BaseModel):
    """Schema for updating an employer benefits program."""
    benefit_rate: Optional[int] = Field(None, ge=0, le=100)
    benefit_cap: Optional[Decimal] = Field(None, ge=0)
    benefit_cap_period: Optional[str] = None
    price_discount: Optional[int] = Field(None, ge=0, le=100)
    minimum_monthly_fee: Optional[Decimal] = Field(None, ge=0)
    billing_cycle: Optional[str] = None
    billing_day: Optional[int] = Field(None, ge=1, le=28)
    enrollment_mode: Optional[str] = None
    allow_early_renewal: Optional[bool] = None
    is_active: Optional[bool] = None


class ProgramResponseSchema(BaseModel):
    """Schema for employer benefits program response."""
    program_id: UUID
    institution_id: UUID
    benefit_rate: int
    benefit_cap: Optional[Decimal] = None
    benefit_cap_period: str
    price_discount: int
    minimum_monthly_fee: Optional[Decimal] = None
    billing_cycle: str
    billing_day: Optional[int] = None
    billing_day_of_week: Optional[int] = None
    enrollment_mode: str
    allow_early_renewal: bool
    stripe_customer_id: Optional[str] = None
    stripe_payment_method_id: Optional[str] = None
    payment_method_type: Optional[str] = None
    is_active: bool
    is_archived: bool
    status: Status
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
    mobile_number: Optional[str] = Field(None, max_length=16, description="E.164 format: +1234567890")
    city_id: UUID = Field(..., description="City for the employee (cannot be Global)")


class EmployeeSubscribeSchema(BaseModel):
    """Schema for subscribing a benefit employee to a plan (no payment for 100% subsidy)."""
    plan_id: UUID = Field(..., description="Plan to subscribe the employee to")


class BenefitEmployeeResponseSchema(BaseModel):
    """Schema for benefit employee in list response (enriched with subscription status)."""
    user_id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    mobile_number: Optional[str] = None
    user_status: Status
    subscription_id: Optional[UUID] = None
    subscription_status: Optional[str] = None
    plan_name: Optional[str] = None
    plan_price: Optional[float] = None
    balance: Optional[Decimal] = None
    renewal_date: Optional[datetime] = None
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkEnrollResultSchema(BaseModel):
    """Result of a bulk employee enrollment operation."""
    created_count: int
    skipped_count: int
    error_count: int
    created: List[str] = Field(default_factory=list, description="Emails successfully enrolled")
    skipped: List[dict] = Field(default_factory=list, description="[{'email': '...', 'reason': '...'}]")
    errors: List[dict] = Field(default_factory=list, description="[{'row': 3, 'email': '...', 'reason': '...'}]")


# =============================================================================
# Billing
# =============================================================================

class EmployerBillResponseSchema(BaseModel):
    """Schema for employer bill response."""
    employer_bill_id: UUID
    institution_id: UUID
    billing_period_start: date
    billing_period_end: date
    billing_cycle: str
    total_renewal_events: int
    gross_employer_share: Decimal
    price_discount: int
    discounted_amount: Decimal
    minimum_fee_applied: bool
    billed_amount: Decimal
    currency_code: str
    stripe_invoice_id: Optional[str] = None
    payment_status: str
    paid_date: Optional[datetime] = None
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
    plan_price: Decimal
    benefit_rate: int
    benefit_cap: Optional[Decimal] = None
    benefit_cap_period: Optional[str] = None
    employee_benefit: Decimal
    renewal_date: datetime

    model_config = ConfigDict(from_attributes=True)


class EmployerBillDetailResponseSchema(BaseModel):
    """Schema for employer bill detail with line items."""
    bill: EmployerBillResponseSchema
    lines: List[EmployerBillLineResponseSchema]


class GenerateBillRequestSchema(BaseModel):
    """Schema for manual bill generation trigger."""
    institution_id: UUID = Field(..., description="Employer institution to generate bill for")
    period_start: date = Field(..., description="Billing period start date")
    period_end: date = Field(..., description="Billing period end date")


# =============================================================================
# Domain Management
# =============================================================================

class DomainCreateSchema(BaseModel):
    """Schema for adding an employer domain."""
    domain: str = Field(..., max_length=255, description="Email domain (e.g., 'acme.com')")


class DomainCreateResponseSchema(BaseModel):
    """Response after creating a domain, including retroactive migration count."""
    domain_id: UUID
    institution_id: UUID
    domain: str
    is_active: bool
    migrated_user_count: int = Field(0, description="Number of existing users migrated to this employer institution")
    created_date: datetime


class DomainResponseSchema(BaseModel):
    """Schema for domain list response."""
    domain_id: UUID
    institution_id: UUID
    domain: str
    is_active: bool
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


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
    benefit_cap: Optional[Decimal] = None
    benefit_cap_period: Optional[str] = None
    remaining_monthly_cap: Optional[float] = Field(None, description="Remaining monthly cap budget")
    period_start: date = Field(..., description="Billing period start date")
    period_end: date = Field(..., description="Billing period end date")
