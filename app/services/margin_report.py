"""
Margin Report Service

Per-market, per-period aggregation of Vianda's gross margin per credit redemption.

Margin per redemption = plan.credit_cost_local_currency − credit_value_supplier_local

Because customers are on different plan tiers, the margin per redemption varies:
higher-tier plans have a lower per-credit cost (the upsell carrot), yielding a
narrower margin; lower-tier plans yield wider margins. The aggregation must join
through each customer's active subscription/plan to compute the correct
per-plan margin before summing.

Formula:
    Σ (plan.credit_cost_local_currency − credit_value_supplier_local) × credits_redeemed

where the sum is over all restaurant_transaction rows in the period for which the
redeeming customer holds an active subscription, grouped by their plan tier.

Usage: internal endpoint only — not customer-facing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import psycopg2.extensions

from app.utils.db import db_read


@dataclass
class PlanTierMarginRow:
    """Margin breakdown for one plan tier in a market."""

    plan_id: UUID
    plan_name: str
    credit_cost_local_currency: Decimal
    """Customer's per-credit price for this plan tier (plan.price / plan.credit)."""
    credit_value_supplier_local: Decimal
    """Supplier per-credit payout for the market."""
    margin_per_credit: Decimal
    """credit_cost_local_currency - credit_value_supplier_local."""
    credits_redeemed: Decimal
    """Total credits redeemed by customers on this plan tier in the period."""
    total_margin: Decimal
    """margin_per_credit × credits_redeemed."""


@dataclass
class MarketMarginReport:
    """Margin report for one market over a date range."""

    market_id: UUID
    period_start: datetime
    period_end: datetime
    credit_value_supplier_local: Decimal
    min_credit_spread_pct: Decimal
    plan_tiers: list[PlanTierMarginRow] = field(default_factory=list)
    total_credits_redeemed: Decimal = Decimal("0")
    total_margin: Decimal = Decimal("0")


def get_margin_report(
    db: psycopg2.extensions.connection,
    market_id: UUID,
    period_start: datetime,
    period_end: datetime,
) -> MarketMarginReport:
    """
    Compute per-market margin over a date range.

    Joins restaurant_transaction → vianda_selection → subscription → plan to resolve
    each redemption to the plan tier the customer was on when they redeemed the vianda.

    Only transactions with a linked vianda_selection (real vianda redemptions) are
    counted. Discretionary transactions (vianda_selection_id IS NULL) are excluded
    because they do not represent a margin-bearing redemption event.

    Args:
        db: Database connection.
        market_id: UUID of the market to report on.
        period_start: Start of the period (inclusive).
        period_end: End of the period (inclusive).

    Returns:
        MarketMarginReport with per-tier breakdown and totals.
    """
    # Fetch market metadata.
    market_rows = db_read(
        """
        SELECT
            m.min_credit_spread_pct,
            cm.credit_value_supplier_local
        FROM core.market_info m
        JOIN core.currency_metadata cm ON cm.currency_metadata_id = m.currency_metadata_id
        WHERE m.market_id = %s
        """,
        (str(market_id),),
        connection=db,
        fetch_one=True,
    )

    if not market_rows:
        return MarketMarginReport(
            market_id=market_id,
            period_start=period_start,
            period_end=period_end,
            credit_value_supplier_local=Decimal("0"),
            min_credit_spread_pct=Decimal("0"),
        )

    supplier_value = Decimal(str(market_rows["credit_value_supplier_local"]))
    floor_pct = Decimal(str(market_rows["min_credit_spread_pct"]))

    # Aggregate credits redeemed per plan tier.
    # Join path:
    #   restaurant_transaction (rt) — has vianda_selection_id
    #     → vianda_selection (ps) — links to subscription_id
    #       → subscription (s) — has plan_id
    #         → plan_info (p) — has credit_cost_local_currency
    # Filter: rt.market is determined via the restaurant's institution_entity → currency_metadata → market_info.
    # Simplification: use ps.market_id (vianda_selection stores market_id) if available,
    # otherwise join through subscription.
    rows = db_read(
        """
        SELECT
            p.plan_id,
            p.name AS plan_name,
            p.credit_cost_local_currency,
            SUM(rt.credit) AS credits_redeemed
        FROM billing.restaurant_transaction rt
        JOIN ops.vianda_selection ps ON ps.vianda_selection_id = rt.vianda_selection_id
        JOIN customer.subscription s ON s.subscription_id = ps.subscription_id
        JOIN customer.plan_info p ON p.plan_id = s.plan_id
        WHERE s.market_id = %s
          AND rt.ordered_timestamp >= %s
          AND rt.ordered_timestamp <= %s
          AND rt.vianda_selection_id IS NOT NULL
          AND rt.is_archived = FALSE
        GROUP BY p.plan_id, p.name, p.credit_cost_local_currency
        ORDER BY p.credit_cost_local_currency DESC
        """,
        (str(market_id), period_start, period_end),
        connection=db,
    )

    plan_tiers: list[PlanTierMarginRow] = []
    total_credits = Decimal("0")
    total_margin = Decimal("0")

    for row in rows or []:
        cost = Decimal(str(row["credit_cost_local_currency"]))
        redeemed = Decimal(str(row["credits_redeemed"] or 0))
        margin_per = cost - supplier_value
        tier_margin = margin_per * redeemed
        plan_tiers.append(
            PlanTierMarginRow(
                plan_id=row["plan_id"],
                plan_name=row["plan_name"],
                credit_cost_local_currency=cost,
                credit_value_supplier_local=supplier_value,
                margin_per_credit=margin_per,
                credits_redeemed=redeemed,
                total_margin=tier_margin,
            )
        )
        total_credits += redeemed
        total_margin += tier_margin

    return MarketMarginReport(
        market_id=market_id,
        period_start=period_start,
        period_end=period_end,
        credit_value_supplier_local=supplier_value,
        min_credit_spread_pct=floor_pct,
        plan_tiers=plan_tiers,
        total_credits_redeemed=total_credits,
        total_margin=total_margin,
    )
