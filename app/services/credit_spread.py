"""
Credit-Currency Spread Guardrail Service

Enforces the per-market minimum spread between the cheapest customer per-credit
price (min(plan.price / plan.credit) across active plans) and the stable supplier
credit value (credit_value_supplier_local).

Design rationale: customers don't experience a single credit price; per-credit
cost is emergent from each plan (price/credit). The cheapest customer credit in
a market is the highest-tier plan's price/credit. The spread floor ensures
Vianda books gross margin per redemption even on the most generous plan tier.

Contract: writes that would violate the floor are not blocked outright; they
require an explicit acknowledge_spread_compression=True flag on the request,
at which point the write is accepted and an audit row is written to
audit.spread_acknowledgement for finance review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

import psycopg2.extensions

from app.utils.db import db_read
from app.utils.log import log_info


@dataclass
class SpreadAckContext:
    """Contextual fields for writing a spread acknowledgement audit row."""

    actor_user_id: UUID
    market_id: UUID
    write_kind: str
    entity_id: UUID | None
    justification: str | None


@dataclass
class SpreadCheck:
    """Result of a spread floor check for a given market."""

    ok: bool
    """True when the observed spread meets or exceeds the floor."""
    observed_pct: Decimal
    """min(plan.price/plan.credit) / credit_value_supplier_local - 1.
    Negative means below floor."""
    floor_pct: Decimal
    """The market's min_credit_spread_pct at check time."""
    offending_plan_ids: list[str] = field(default_factory=list)
    """UUIDs (as strings) of active plans whose price/credit violates the floor."""
    cheapest_per_credit: Decimal | None = None
    """The cheapest per-credit price across active plans (min plan.price/plan.credit)."""
    supplier_value: Decimal | None = None
    """credit_value_supplier_local for the market."""


def check_spread_floor(
    db: psycopg2.extensions.connection,
    market_id: UUID,
) -> SpreadCheck:
    """
    Check whether active plans in the given market meet the spread floor.

    Reads:
      - core.market_info.min_credit_spread_pct for the market
      - core.currency_metadata.credit_value_supplier_local for the market's currency
      - customer.plan_info (active, non-archived plans in that market): price, credit

    Returns a SpreadCheck. ok=True means all active plans satisfy:
        plan.price / plan.credit >= credit_value_supplier_local * (1 + min_credit_spread_pct)

    If there are no active plans in the market the check returns ok=True (nothing to
    enforce against an empty plan list).

    Note: this function reads a consistent snapshot; it does not account for the row
    being inserted/updated in the calling transaction. Callers must pass the proposed
    plan's price/credit explicitly when checking a plan write (see check_spread_floor_with_plan).
    """
    rows = db_read(
        """
        SELECT
            m.min_credit_spread_pct,
            cm.credit_value_supplier_local,
            p.plan_id,
            p.price,
            p.credit
        FROM core.market_info m
        JOIN core.currency_metadata cm ON cm.currency_metadata_id = m.currency_metadata_id
        LEFT JOIN customer.plan_info p
            ON p.market_id = m.market_id
            AND p.is_archived = FALSE
            AND p.status = 'active'
            AND p.credit > 0
        WHERE m.market_id = %s
        """,
        (str(market_id),),
        connection=db,
    )

    if not rows:
        # Market not found — return ok=True; the market-not-found error is the caller's concern.
        return SpreadCheck(ok=True, observed_pct=Decimal("0"), floor_pct=Decimal("0"))

    floor_pct = Decimal(str(rows[0]["min_credit_spread_pct"]))
    supplier_value = Decimal(str(rows[0]["credit_value_supplier_local"]))

    # Collect active plans (LEFT JOIN may return one row with plan_id=None if no active plans).
    plans = [(row["plan_id"], Decimal(str(row["price"])), int(row["credit"])) for row in rows if row["plan_id"]]

    if not plans:
        # No active plans — nothing to violate.
        return SpreadCheck(
            ok=True,
            observed_pct=Decimal("0"),
            floor_pct=floor_pct,
            supplier_value=supplier_value,
        )

    if supplier_value <= 0:
        # Supplier value of zero or negative: guard against division-by-zero.
        # Treat as ok (no meaningful spread to enforce).
        return SpreadCheck(
            ok=True,
            observed_pct=Decimal("0"),
            floor_pct=floor_pct,
            supplier_value=supplier_value,
        )

    threshold = supplier_value * (1 + floor_pct)
    offending = []
    cheapest = None

    for plan_id, price, credit in plans:
        per_credit = price / Decimal(str(credit))
        if cheapest is None or per_credit < cheapest:
            cheapest = per_credit
        if per_credit < threshold:
            offending.append(str(plan_id))

    observed_pct = (cheapest / supplier_value) - Decimal("1") if cheapest is not None else Decimal("0")

    return SpreadCheck(
        ok=len(offending) == 0,
        observed_pct=observed_pct,
        floor_pct=floor_pct,
        offending_plan_ids=offending,
        cheapest_per_credit=cheapest,
        supplier_value=supplier_value,
    )


def check_spread_floor_with_plan(
    db: psycopg2.extensions.connection,
    market_id: UUID,
    proposed_price: float | Decimal,
    proposed_credit: int,
    exclude_plan_id: UUID | None = None,
) -> SpreadCheck:
    """
    Check spread floor including a proposed plan (not yet in the DB).

    Used for plan create/update: the plan being written may not yet be in the
    DB (create) or may have a different price/credit (update). We include it
    explicitly and optionally exclude the plan being replaced.

    All existing active plans plus the proposed plan are evaluated together.
    """
    rows = db_read(
        """
        SELECT
            m.min_credit_spread_pct,
            cm.credit_value_supplier_local,
            p.plan_id,
            p.price,
            p.credit
        FROM core.market_info m
        JOIN core.currency_metadata cm ON cm.currency_metadata_id = m.currency_metadata_id
        LEFT JOIN customer.plan_info p
            ON p.market_id = m.market_id
            AND p.is_archived = FALSE
            AND p.status = 'active'
            AND p.credit > 0
            AND (%s IS NULL OR p.plan_id != %s::uuid)
        WHERE m.market_id = %s
        """,
        (
            str(exclude_plan_id) if exclude_plan_id else None,
            str(exclude_plan_id) if exclude_plan_id else None,
            str(market_id),
        ),
        connection=db,
    )

    if not rows:
        return SpreadCheck(ok=True, observed_pct=Decimal("0"), floor_pct=Decimal("0"))

    floor_pct = Decimal(str(rows[0]["min_credit_spread_pct"]))
    supplier_value = Decimal(str(rows[0]["credit_value_supplier_local"]))

    # Existing plans (excluding the one being replaced).
    plans: list[tuple[str | None, Decimal, int]] = [
        (str(row["plan_id"]), Decimal(str(row["price"])), int(row["credit"])) for row in rows if row["plan_id"]
    ]
    # Add the proposed plan (use None as a sentinel plan_id for clear error messages).
    plans.append((None, Decimal(str(proposed_price)), int(proposed_credit)))

    if supplier_value <= 0:
        return SpreadCheck(
            ok=True,
            observed_pct=Decimal("0"),
            floor_pct=floor_pct,
            supplier_value=supplier_value,
        )

    threshold = supplier_value * (1 + floor_pct)
    offending: list[str] = []
    cheapest = None

    for plan_id, price, credit in plans:
        per_credit = price / Decimal(str(credit))
        if cheapest is None or per_credit < cheapest:
            cheapest = per_credit
        if per_credit < threshold:
            offending.append(str(plan_id) if plan_id else "proposed_plan")

    observed_pct = (cheapest / supplier_value) - Decimal("1") if cheapest is not None else Decimal("0")

    return SpreadCheck(
        ok=len(offending) == 0,
        observed_pct=observed_pct,
        floor_pct=floor_pct,
        offending_plan_ids=offending,
        cheapest_per_credit=cheapest,
        supplier_value=supplier_value,
    )


def check_spread_floor_with_new_supplier_value(
    db: psycopg2.extensions.connection,
    market_id: UUID,
    proposed_supplier_value: float | Decimal,
) -> SpreadCheck:
    """
    Check spread floor with a proposed new credit_value_supplier_local.

    Used for currency writes: if the supplier value increases (or decreases),
    we re-evaluate all active plans against the proposed value.
    """
    rows = db_read(
        """
        SELECT
            m.min_credit_spread_pct,
            p.plan_id,
            p.price,
            p.credit
        FROM core.market_info m
        LEFT JOIN customer.plan_info p
            ON p.market_id = m.market_id
            AND p.is_archived = FALSE
            AND p.status = 'active'
            AND p.credit > 0
        WHERE m.market_id = %s
        """,
        (str(market_id),),
        connection=db,
    )

    if not rows:
        return SpreadCheck(ok=True, observed_pct=Decimal("0"), floor_pct=Decimal("0"))

    floor_pct = Decimal(str(rows[0]["min_credit_spread_pct"]))
    supplier_value = Decimal(str(proposed_supplier_value))

    plans = [(row["plan_id"], Decimal(str(row["price"])), int(row["credit"])) for row in rows if row["plan_id"]]

    if not plans:
        return SpreadCheck(
            ok=True,
            observed_pct=Decimal("0"),
            floor_pct=floor_pct,
            supplier_value=supplier_value,
        )

    if supplier_value <= 0:
        return SpreadCheck(
            ok=True,
            observed_pct=Decimal("0"),
            floor_pct=floor_pct,
            supplier_value=supplier_value,
        )

    threshold = supplier_value * (1 + floor_pct)
    offending = []
    cheapest = None

    for plan_id, price, credit in plans:
        per_credit = price / Decimal(str(credit))
        if cheapest is None or per_credit < cheapest:
            cheapest = per_credit
        if per_credit < threshold:
            offending.append(str(plan_id))

    observed_pct = (cheapest / supplier_value) - Decimal("1") if cheapest is not None else Decimal("0")

    return SpreadCheck(
        ok=len(offending) == 0,
        observed_pct=observed_pct,
        floor_pct=floor_pct,
        offending_plan_ids=offending,
        cheapest_per_credit=cheapest,
        supplier_value=supplier_value,
    )


def check_spread_floor_with_new_floor_pct(
    db: psycopg2.extensions.connection,
    market_id: UUID,
    proposed_floor_pct: float | Decimal,
) -> SpreadCheck:
    """
    Check spread floor when min_credit_spread_pct itself is being changed.

    Raising the floor can cause existing active plans to newly violate it.
    """
    rows = db_read(
        """
        SELECT
            cm.credit_value_supplier_local,
            p.plan_id,
            p.price,
            p.credit
        FROM core.market_info m
        JOIN core.currency_metadata cm ON cm.currency_metadata_id = m.currency_metadata_id
        LEFT JOIN customer.plan_info p
            ON p.market_id = m.market_id
            AND p.is_archived = FALSE
            AND p.status = 'active'
            AND p.credit > 0
        WHERE m.market_id = %s
        """,
        (str(market_id),),
        connection=db,
    )

    if not rows:
        return SpreadCheck(ok=True, observed_pct=Decimal("0"), floor_pct=Decimal(str(proposed_floor_pct)))

    floor_pct = Decimal(str(proposed_floor_pct))
    supplier_value = Decimal(str(rows[0]["credit_value_supplier_local"]))

    plans = [(row["plan_id"], Decimal(str(row["price"])), int(row["credit"])) for row in rows if row["plan_id"]]

    if not plans or supplier_value <= 0:
        return SpreadCheck(
            ok=True,
            observed_pct=Decimal("0"),
            floor_pct=floor_pct,
            supplier_value=supplier_value,
        )

    threshold = supplier_value * (1 + floor_pct)
    offending = []
    cheapest = None

    for plan_id, price, credit in plans:
        per_credit = price / Decimal(str(credit))
        if cheapest is None or per_credit < cheapest:
            cheapest = per_credit
        if per_credit < threshold:
            offending.append(str(plan_id))

    observed_pct = (cheapest / supplier_value) - Decimal("1") if cheapest is not None else Decimal("0")

    return SpreadCheck(
        ok=len(offending) == 0,
        observed_pct=observed_pct,
        floor_pct=floor_pct,
        offending_plan_ids=offending,
        cheapest_per_credit=cheapest,
        supplier_value=supplier_value,
    )


def record_acknowledgement(
    db: psycopg2.extensions.connection,
    ctx: SpreadAckContext,
    spread_check: SpreadCheck,
) -> None:
    """
    Write an audit row to audit.spread_acknowledgement.

    Called whenever a write is accepted despite a spread floor violation
    (i.e. acknowledge_spread_compression=True was set by the caller).

    Args:
        db: Database connection (must be open; caller commits).
        ctx: Actor/market/entity context for the acknowledgement.
        spread_check: The SpreadCheck result for this write.
    """
    import json

    cursor = db.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO audit.spread_acknowledgement (
                actor_user_id,
                market_id,
                write_kind,
                entity_id,
                observed_spread_pct,
                floor_pct,
                offending_plan_ids,
                justification,
                acknowledged_at
            ) VALUES (
                %s::uuid, %s::uuid, %s::spread_write_kind_enum, %s,
                %s, %s, %s::jsonb, %s, CURRENT_TIMESTAMP
            )
            """,
            (
                str(ctx.actor_user_id),
                str(ctx.market_id),
                ctx.write_kind,
                str(ctx.entity_id) if ctx.entity_id else None,
                float(spread_check.observed_pct),
                float(spread_check.floor_pct),
                json.dumps(spread_check.offending_plan_ids),
                ctx.justification,
            ),
        )
    finally:
        cursor.close()
    log_info(
        f"Spread acknowledgement recorded: actor={ctx.actor_user_id}, market={ctx.market_id}, "
        f"write_kind={ctx.write_kind}, observed={spread_check.observed_pct:.4f}, "
        f"floor={spread_check.floor_pct:.4f}"
    )
