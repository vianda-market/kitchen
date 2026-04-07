"""
Employer benefits billing cron job.

Checks all active employer programs and generates bills for those where billing is due today.
Handles daily, weekly, and monthly billing cycles.
"""
from datetime import date, timedelta, datetime, timezone
from typing import Dict, Any, Optional
from uuid import UUID
from decimal import Decimal

from app.utils.db import db_read, get_db_connection, close_db_connection
from app.utils.log import log_info, log_warning, log_error
from app.services.employer.billing_service import generate_employer_bill, list_employer_bills

SYSTEM_USER_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _is_billing_due(program, today: date) -> bool:
    """Check if billing is due today for the given program's billing cycle."""
    cycle = program.billing_cycle
    if cycle == "daily":
        return True
    if cycle == "weekly":
        day_of_week = program.billing_day_of_week
        if day_of_week is None:
            day_of_week = 0  # Default Monday
        return today.weekday() == day_of_week
    if cycle == "monthly":
        billing_day = program.billing_day or 1
        # Handle months shorter than billing_day (e.g., Feb 28 for billing_day=30)
        last_day_of_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        effective_day = min(billing_day, last_day_of_month.day)
        return today.day == effective_day
    return False


def _compute_billing_period(program, today: date) -> tuple:
    """Compute (period_start, period_end) for a bill due today."""
    cycle = program.billing_cycle
    if cycle == "daily":
        yesterday = today - timedelta(days=1)
        return (yesterday, today)
    if cycle == "weekly":
        period_end = today
        period_start = today - timedelta(days=7)
        return (period_start, period_end)
    if cycle == "monthly":
        period_end = today
        if today.month == 1:
            period_start = today.replace(year=today.year - 1, month=12, day=1)
        else:
            period_start = today.replace(month=today.month - 1, day=1)
        return (period_start, period_end)
    return (today - timedelta(days=30), today)


def run_employer_billing(bill_date: Optional[date] = None) -> Dict[str, Any]:
    """Generate employer bills for all programs where billing is due today.

    Args:
        bill_date: Override date for testing (default: today UTC).

    Returns:
        Summary dict with counts and errors.
    """
    today = bill_date or datetime.now(timezone.utc).date()
    result: Dict[str, Any] = {
        "cron_job": "employer_billing",
        "run_date": today.isoformat(),
        "bills_generated": 0,
        "programs_checked": 0,
        "skipped": 0,
        "errors": [],
        "success": True,
    }

    connection = get_db_connection()
    try:
        rows = db_read(
            """
            SELECT program_id, institution_id, billing_cycle, billing_day, billing_day_of_week,
                   benefit_rate, benefit_cap, benefit_cap_period, price_discount, minimum_monthly_fee
            FROM employer_benefits_program
            WHERE is_active = TRUE AND is_archived = FALSE
            """,
            connection=connection,
        )
        if not rows:
            log_info("Employer billing cron: no active programs found.")
            return result

        from app.dto.models import EmployerBenefitsProgramDTO

        for row in rows:
            result["programs_checked"] += 1
            # Build a lightweight object for billing check
            class ProgramProxy:
                pass
            p = ProgramProxy()
            p.billing_cycle = row["billing_cycle"]
            p.billing_day = row.get("billing_day")
            p.billing_day_of_week = row.get("billing_day_of_week")

            if not _is_billing_due(p, today):
                result["skipped"] += 1
                continue

            institution_id = row["institution_id"]
            period_start, period_end = _compute_billing_period(p, today)

            try:
                bill_result = generate_employer_bill(
                    institution_id, period_start, period_end, connection, modified_by=SYSTEM_USER_ID
                )
                result["bills_generated"] += 1
                log_info(f"Generated employer bill for institution {institution_id}: period {period_start}-{period_end}")
            except Exception as e:
                log_error(f"Employer billing failed for institution {institution_id}: {e}")
                result["errors"].append(f"{institution_id}: {e}")
                result["success"] = False

        # Month-end minimum fee reconciliation for daily/weekly billing
        if _is_last_day_of_month(today):
            _reconcile_minimum_fees(rows, today, connection, result)

        log_info(f"Employer billing cron completed: {result}")
        return result
    finally:
        close_db_connection(connection)


def _is_last_day_of_month(d: date) -> bool:
    """Check if date is the last day of its month."""
    next_day = d + timedelta(days=1)
    return next_day.month != d.month


def _reconcile_minimum_fees(programs, today: date, connection, result: Dict[str, Any]):
    """For daily/weekly billing: check if month's total < minimum_monthly_fee. If so, generate adjustment."""
    month_start = today.replace(day=1)
    for row in programs:
        if row["billing_cycle"] == "monthly":
            continue  # Monthly billing already applies minimum in the single bill
        min_fee = row.get("minimum_monthly_fee")
        if not min_fee or float(min_fee) <= 0:
            continue

        institution_id = row["institution_id"]
        # Sum all bills this month for this institution
        bills_total = db_read(
            """
            SELECT COALESCE(SUM(billed_amount), 0) as total
            FROM employer_bill
            WHERE institution_id = %s::uuid
              AND billing_period_start >= %s
              AND billing_period_end <= %s
              AND is_archived = FALSE
            """,
            (str(institution_id), str(month_start), str(today + timedelta(days=1))),
            connection=connection,
            fetch_one=True,
        )
        total = float(bills_total["total"]) if bills_total else 0.0
        min_fee_float = float(min_fee)

        if total < min_fee_float:
            adjustment = min_fee_float - total
            try:
                from app.services.crud_service import employer_bill_service
                from app.config import Status
                adjustment_bill = {
                    "institution_id": str(institution_id),
                    "billing_period_start": str(month_start),
                    "billing_period_end": str(today),
                    "billing_cycle": row["billing_cycle"],
                    "total_renewal_events": 0,
                    "gross_employer_share": 0,
                    "price_discount": 0,
                    "discounted_amount": 0,
                    "minimum_fee_applied": True,
                    "billed_amount": adjustment,
                    "currency_code": "USD",
                    "payment_status": "Pending",
                    "status": Status.ACTIVE.value,
                    "modified_by": str(SYSTEM_USER_ID),
                }
                employer_bill_service.create(adjustment_bill, connection, scope=None)
                log_info(f"Minimum fee adjustment bill created for institution {institution_id}: ${adjustment:.2f}")
            except Exception as e:
                log_error(f"Minimum fee reconciliation failed for {institution_id}: {e}")
                result["errors"].append(f"min_fee {institution_id}: {e}")
