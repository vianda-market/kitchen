"""Employer Benefits Program billing service — bill generation and benefit calculation."""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg2.extensions

from app.config import Status
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode
from app.services.crud_service import (
    employer_bill_line_service,
    employer_bill_service,
)
from app.utils.db import db_read
from app.utils.log import log_info


def compute_employee_benefit(
    plan_price: float,
    benefit_rate: int,
    benefit_cap: float | None,
    benefit_cap_period: str,
    already_used_this_month: float = 0.0,
) -> tuple[float, float]:
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
) -> list[dict[str, Any]]:
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
          AND u.role_type = 'customer'
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
    *,
    institution_entity_id: UUID | None = None,
    locale: str = "en",
) -> dict[str, Any]:
    """Generate an employer bill for a billing period. Returns the bill DTO + lines.

    institution_entity_id is required — bills are always per-entity (NOT NULL on employer_bill).
    Uses resolve_effective_program (entity → institution cascade) and derives currency
    from the entity's currency_metadata.
    """
    if not institution_entity_id:
        raise envelope_exception(
            ErrorCode.ENROLLMENT_EMPLOYER_INSTITUTION_ID_REQUIRED,
            status=400,
            locale=locale,
        )
    from app.services.employer.program_service import resolve_effective_program

    program = resolve_effective_program(institution_id, institution_entity_id, db)
    if not program or not program.is_active:
        raise envelope_exception(
            ErrorCode.ENROLLMENT_NO_ACTIVE_PROGRAM,
            status=400,
            locale=locale,
        )

    renewal_events = _get_renewal_events(institution_id, period_start, period_end, db)

    monthly_usage: dict[str, float] = {}
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

        lines_data.append(
            {
                "subscription_id": str(event["subscription_id"]),
                "user_id": str(event["user_id"]),
                "plan_id": str(event["plan_id"]),
                "plan_price": plan_price,
                "benefit_rate": program.benefit_rate,
                "benefit_cap": float(program.benefit_cap) if program.benefit_cap is not None else None,
                "benefit_cap_period": program.benefit_cap_period,
                "employee_benefit": employee_benefit,
                "renewal_date": event["renewal_date"],
            }
        )

    discount_rate = program.price_discount or 0
    discounted = gross_total * (Decimal("1") - Decimal(str(discount_rate)) / Decimal("100"))
    discounted = discounted.quantize(Decimal("0.01"))

    min_fee = Decimal(str(program.minimum_monthly_fee)) if program.minimum_monthly_fee else Decimal("0")
    minimum_fee_applied = discounted < min_fee and min_fee > 0
    billed_amount = max(discounted, min_fee)

    # Currency resolution: entity → market fallback → USD
    currency_code = "USD"
    if institution_entity_id:
        from app.utils.db import db_read as _db_read

        entity_currency = _db_read(
            "SELECT cm.currency_code FROM ops.institution_entity_info ie "
            "JOIN core.currency_metadata cm ON ie.currency_metadata_id = cm.currency_metadata_id "
            "WHERE ie.institution_entity_id = %s",
            (str(institution_entity_id),),
            connection=db,
            fetch_one=True,
        )
        if entity_currency:
            currency_code = entity_currency["currency_code"]
    if currency_code == "USD":
        # Fallback: primary market currency via institution_market junction
        market_currency = db_read(
            "SELECT cm.currency_code FROM core.institution_market im "
            "JOIN core.market_info m ON im.market_id = m.market_id "
            "JOIN core.currency_metadata cm ON m.currency_metadata_id = cm.currency_metadata_id "
            "WHERE im.institution_id = %s ORDER BY im.is_primary DESC LIMIT 1",
            (str(institution_id),),
            connection=db,
            fetch_one=True,
        )
        if market_currency:
            currency_code = market_currency["currency_code"]

    bill_data = {
        "institution_id": str(institution_id),
        "institution_entity_id": str(institution_entity_id) if institution_entity_id else None,
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
        "payment_status": "pending",
        "status": Status.ACTIVE.value,
        "modified_by": str(modified_by),
    }

    bill = employer_bill_service.create(bill_data, db, scope=None)
    if not bill:
        raise envelope_exception(ErrorCode.EMPLOYER_BILL_CREATION_FAILED, status=500, locale="en")

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
    return employer_bill_service.get_all_by_field("institution_id", institution_id, db, scope=None)


def get_employer_bill_detail(
    bill_id: UUID,
    institution_id: UUID,
    db: psycopg2.extensions.connection,
) -> dict[str, Any] | None:
    """Get employer bill with line items."""
    bill = employer_bill_service.get_by_id(bill_id, db, scope=None)
    if not bill:
        return None
    if str(bill.institution_id) != str(institution_id):
        return None

    # employer_bill_line has no is_archived column — use raw query instead of
    # CRUDService.get_all_by_field which hardcodes AND is_archived = FALSE.
    from app.dto.models import EmployerBillLineDTO
    from app.utils.db import db_read

    rows = db_read(
        "SELECT * FROM employer_bill_line WHERE employer_bill_id = %s ORDER BY renewal_date",
        (str(bill_id),),
        connection=db,
    )
    lines = [EmployerBillLineDTO(**r) for r in rows] if rows else []
    return {"bill": bill, "lines": lines}
