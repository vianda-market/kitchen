"""Employer Benefits Program billing service — bill generation and benefit calculation."""
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from datetime import datetime, date, timezone
from decimal import Decimal

import psycopg2.extensions
from fastapi import HTTPException

from app.services.crud_service import (
    employer_bill_service,
    employer_bill_line_service,
)
from app.services.employer.program_service import get_program_by_institution
from app.dto.models import EmployerBenefitsProgramDTO
from app.config import Status
from app.utils.db import db_read
from app.utils.log import log_info


def compute_employee_benefit(
    plan_price: float,
    benefit_rate: int,
    benefit_cap: Optional[float],
    benefit_cap_period: str,
    already_used_this_month: float = 0.0,
) -> Tuple[float, float]:
    """Pure function: compute employer's contribution and employee's share for a renewal.

    Returns (employee_benefit, employee_share).
    """
    rate_amount = plan_price * (benefit_rate / 100)

    if benefit_cap is not None:
        if benefit_cap_period == "monthly":
            remaining_cap = max(0.0, benefit_cap - already_used_this_month)
            employee_benefit = min(rate_amount, remaining_cap)
        else:
            employee_benefit = min(rate_amount, benefit_cap)
    else:
        employee_benefit = rate_amount

    employee_share = plan_price - employee_benefit
    return (round(employee_benefit, 2), round(employee_share, 2))


def _get_renewal_events(
    institution_id: UUID,
    period_start: date,
    period_end: date,
    db: psycopg2.extensions.connection,
) -> List[Dict[str, Any]]:
    """Find subscription renewal events within a period by querying audit.subscription_history.

    A renewal event is detected when balance increased (new record has higher balance than previous).
    """
    rows = db_read(
        """
        SELECT
            sh.subscription_id,
            sh.user_id,
            si.plan_id,
            p.price as plan_price,
            p.name as plan_name,
            sh.modified_date as renewal_date
        FROM audit.subscription_history sh
        JOIN subscription_info si ON sh.subscription_id = si.subscription_id
        JOIN user_info u ON sh.user_id = u.user_id
        JOIN plan_info p ON si.plan_id = p.plan_id
        WHERE u.institution_id = %s::uuid
          AND u.role_type = 'Customer'
          AND sh.balance > 0
          AND sh.modified_date >= %s
          AND sh.modified_date < %s
          AND sh.is_current = FALSE
        ORDER BY sh.modified_date
        """,
        (str(institution_id), str(period_start), str(period_end)),
        connection=db,
    )
    return rows or []


def generate_employer_bill(
    institution_id: UUID,
    period_start: date,
    period_end: date,
    db: psycopg2.extensions.connection,
    modified_by: UUID,
) -> Dict[str, Any]:
    """Generate an employer bill for a billing period. Returns the bill DTO + lines."""
    program = get_program_by_institution(institution_id, db)
    if not program or not program.is_active:
        raise HTTPException(status_code=400, detail="No active benefits program for this institution")

    renewal_events = _get_renewal_events(institution_id, period_start, period_end, db)

    monthly_usage: Dict[str, float] = {}
    lines_data = []
    gross_total = Decimal("0")

    for event in renewal_events:
        user_key = str(event["user_id"])
        plan_price = float(event.get("plan_price", 0))
        already_used = monthly_usage.get(user_key, 0.0)

        benefit_cap = float(program.benefit_cap) if program.benefit_cap is not None else None
        employee_benefit, _ = compute_employee_benefit(
            plan_price=plan_price,
            benefit_rate=program.benefit_rate,
            benefit_cap=benefit_cap,
            benefit_cap_period=program.benefit_cap_period,
            already_used_this_month=already_used,
        )

        monthly_usage[user_key] = already_used + employee_benefit
        gross_total += Decimal(str(employee_benefit))

        lines_data.append({
            "subscription_id": str(event["subscription_id"]),
            "user_id": str(event["user_id"]),
            "plan_id": str(event["plan_id"]),
            "plan_price": plan_price,
            "benefit_rate": program.benefit_rate,
            "benefit_cap": float(program.benefit_cap) if program.benefit_cap is not None else None,
            "benefit_cap_period": program.benefit_cap_period,
            "employee_benefit": employee_benefit,
            "renewal_date": event["renewal_date"],
        })

    discount_rate = program.price_discount or 0
    discounted = gross_total * (Decimal("1") - Decimal(str(discount_rate)) / Decimal("100"))
    discounted = discounted.quantize(Decimal("0.01"))

    min_fee = Decimal(str(program.minimum_monthly_fee)) if program.minimum_monthly_fee else Decimal("0")
    minimum_fee_applied = discounted < min_fee and min_fee > 0
    billed_amount = max(discounted, min_fee)

    from app.services.crud_service import institution_service
    institution = institution_service.get_by_id(institution_id, db, scope=None)
    currency_code = "USD"
    if institution and hasattr(institution, "market_id") and institution.market_id:
        from app.services.crud_service import market_service
        market = market_service.get_by_id(institution.market_id, db)
        if market:
            currency_code = getattr(market, "currency_code", "USD") or "USD"

    bill_data = {
        "institution_id": str(institution_id),
        "billing_period_start": str(period_start),
        "billing_period_end": str(period_end),
        "billing_cycle": program.billing_cycle,
        "total_renewal_events": len(renewal_events),
        "gross_employer_share": float(gross_total),
        "price_discount": discount_rate,
        "discounted_amount": float(discounted),
        "minimum_fee_applied": minimum_fee_applied,
        "billed_amount": float(billed_amount),
        "currency_code": currency_code,
        "payment_status": "Pending",
        "status": Status.ACTIVE.value,
        "modified_by": str(modified_by),
    }

    bill = employer_bill_service.create(bill_data, db, scope=None)
    if not bill:
        raise HTTPException(status_code=500, detail="Failed to create employer bill")

    created_lines = []
    for line in lines_data:
        line["employer_bill_id"] = str(bill.employer_bill_id)
        created_line = employer_bill_line_service.create(line, db, scope=None)
        if created_line:
            created_lines.append(created_line)

    log_info(
        f"Generated employer bill {bill.employer_bill_id}: "
        f"institution={institution_id}, period={period_start}-{period_end}, "
        f"events={len(renewal_events)}, gross={gross_total}, "
        f"discount={discount_rate}%, billed={billed_amount}"
    )
    return {"bill": bill, "lines": created_lines}


def list_employer_bills(
    institution_id: UUID,
    db: psycopg2.extensions.connection,
) -> list:
    """List employer bills for an institution."""
    return employer_bill_service.get_all(
        db,
        scope=None,
        additional_conditions=[("institution_id = %s::uuid", str(institution_id))],
    )


def get_employer_bill_detail(
    bill_id: UUID,
    institution_id: UUID,
    db: psycopg2.extensions.connection,
) -> Optional[Dict[str, Any]]:
    """Get employer bill with line items."""
    bill = employer_bill_service.get_by_id(bill_id, db, scope=None)
    if not bill:
        return None
    if str(bill.institution_id) != str(institution_id):
        return None

    lines = employer_bill_line_service.get_all(
        db,
        scope=None,
        additional_conditions=[("employer_bill_id = %s::uuid", str(bill_id))],
    )
    return {"bill": bill, "lines": lines or []}
