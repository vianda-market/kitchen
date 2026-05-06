"""
Internal Margin Report Routes

Finance-only endpoint for per-market, per-period gross margin reporting.
"""

from datetime import datetime
from uuid import UUID

import psycopg2.extensions
from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_resolved_locale, get_super_admin_user
from app.dependencies.database import get_db
from app.schemas.consolidated_schemas import MarginReportPlanRow, MarginReportResponseSchema
from app.services.market_service import market_service

router = APIRouter(prefix="/internal", tags=["Internal Finance"])


@router.get("/margin-report", response_model=MarginReportResponseSchema)
def get_margin_report(
    market_id: UUID = Query(..., description="UUID of the market to report on."),
    period_start: datetime = Query(..., description="Start of the period (ISO datetime, inclusive)."),
    period_end: datetime = Query(..., description="End of the period (ISO datetime, inclusive)."),
    current_user: dict = Depends(get_super_admin_user),  # Finance-only: Super Admin
    locale: str = Depends(get_resolved_locale),
    db: psycopg2.extensions.connection = Depends(get_db),
) -> MarginReportResponseSchema:
    """
    Per-market gross margin report for a given date range.

    **Authorization**: Super Admin only (finance-only endpoint).

    Aggregates:
        Σ (plan.credit_cost_local_currency − credit_value_supplier_local) × credits_redeemed

    grouped by plan tier. Margin varies by tier: high-tier plans (cheaper per credit for
    customers) yield narrower margin; low-tier plans yield wider margin.

    Only redemption transactions (restaurant_transaction rows with a linked plate_selection)
    are counted. Discretionary transactions are excluded.

    **Query Parameters**:
    - `market_id`: UUID of the market
    - `period_start`: Period start (ISO datetime, inclusive)
    - `period_end`: Period end (ISO datetime, inclusive)

    **Returns**:
    - `market_id`, `period_start`, `period_end`
    - `total_margin_local`: Total gross margin in local currency
    - `total_credits_redeemed`: Total credits redeemed
    - `by_plan`: Per-plan-tier breakdown
    - `currency_code`: ISO currency code for the market
    """
    from app.services.margin_report import get_margin_report as _get_margin_report

    report = _get_margin_report(db, market_id=market_id, period_start=period_start, period_end=period_end)

    # Resolve currency_code from the market's currency metadata.
    market_row = market_service.get_by_id(market_id)
    currency_code: str | None = market_row.get("currency_code") if market_row else None

    by_plan = [
        MarginReportPlanRow(
            plan_id=tier.plan_id,
            plan_name=tier.plan_name,
            redemptions=tier.credits_redeemed,
            margin_per_credit=tier.margin_per_credit,
            margin_local=tier.total_margin,
        )
        for tier in report.plan_tiers
    ]

    return MarginReportResponseSchema(
        market_id=report.market_id,
        period_start=report.period_start,
        period_end=report.period_end,
        total_margin_local=report.total_margin,
        total_credits_redeemed=report.total_credits_redeemed,
        by_plan=by_plan,
        currency_code=currency_code,
    )
