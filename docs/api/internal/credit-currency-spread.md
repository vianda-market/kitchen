# Credit-Currency Spread

**Permanent doc.** Covers the per-market spread floor between customer credit prices and the
supplier credit value, the warn-and-acknowledge enforcement contract, role gating, the audit
table, the margin report, and the headroom-readout endpoint.

---

## Conceptual model

### Why there is no single customer credit price

Customers do not experience a single per-credit price. The cost per credit is emergent from
the subscription plan: `plan.price / plan.credit`. Higher-tier plans intentionally give more
credits per dollar (the upsell carrot), so the cheapest per-credit price in a market is always
the highest-tier plan's `price/credit`.

Anchoring margin against a fictitious "single customer credit price" would drift every time a
new plan tier is introduced or an existing tier is repriced.

### Why the supplier side is a single stable value

Suppliers price their plates in credits ("this plate costs 4 credits"). If the per-credit
payout value changes, suppliers either absorb the change or must restate every plate price —
both paths produce churn and risk losing supply. So `credit_value_supplier_local` is a
discretionary, stable, Vianda-owned number set per market and changed rarely.

### The spread

Vianda's gross margin per credit redemption from a given plan tier is:

```
margin_per_credit = plan.price/plan.credit  −  credit_value_supplier_local
```

Margin is wider on lower-tier plans (customers pay more per credit) and narrower on
higher-tier plans. The asymmetry is by design — high-tier customers get the carrot; Vianda
still books margin on every tier.

The **spread floor** (`min_credit_spread_pct` on `core.market_info`) is the minimum required
gap, expressed as a fraction:

```
min(plan.price/plan.credit  for active_plans_in_market)
    >=  credit_value_supplier_local * (1 + min_credit_spread_pct)
```

Example: `credit_value_supplier_local = 1.00`, `min_credit_spread_pct = 0.20` → cheapest
plan per-credit must be ≥ 1.20.

---

## Data model

### `core.currency_metadata`

| Column | Type | Notes |
|---|---|---|
| `credit_value_supplier_local` | NUMERIC | Stable per-credit fiat payout to suppliers. Set by Internal users (increases) or Super Admin (decreases). |

### `core.market_info`

| Column | Type | Notes |
|---|---|---|
| `min_credit_spread_pct` | NUMERIC(5,4) | Minimum spread floor. Default 0.20 (20%). **Super Admin only.** |

### `audit.spread_acknowledgement`

Event log of every write accepted despite a spread floor violation.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Auto-generated. |
| `actor_user_id` | UUID | Internal user who acknowledged. |
| `market_id` | UUID NOT NULL | Always set — the market whose floor was evaluated. |
| `write_kind` | `spread_write_kind_enum` | `'plan'`, `'currency_value'`, or `'spread_floor'`. |
| `entity_id` | UUID NULL | The plan or currency row being written; NULL when `write_kind = 'spread_floor'`. |
| `observed_spread_pct` | NUMERIC(10,6) | `min(plan.price/plan.credit)/credit_value_supplier_local - 1` at acknowledgement time. |
| `floor_pct` | NUMERIC(5,4) | `min_credit_spread_pct` at acknowledgement time. |
| `offending_plan_ids` | JSONB | Array of plan UUIDs (strings) whose per-credit price was below the threshold. |
| `justification` | TEXT NULL | Free-text reason provided by the actor. |
| `acknowledged_at` | TIMESTAMPTZ | Server timestamp. |

CHECK constraint: `entity_id` is non-null when `write_kind` is `'plan'` or `'currency_value'`;
null when `write_kind` is `'spread_floor'` (market_id alone identifies the entity).

---

## Enforcement contract (warn-and-acknowledge)

Writes that would violate the spread floor are **not blocked outright**. They require an
explicit `acknowledge_spread_compression: true` flag on the request.

- Without ack: `422 SPREAD_FLOOR_VIOLATION` with structured fields.
- With ack: write is accepted and an audit row is written to `audit.spread_acknowledgement`.

This applies to:
- **Plan writes** (create, update, upsert-by-key) — evaluated against the proposed plan's
  `price/credit` plus all other active plans in the same market.
- **Currency writes** (create, update, upsert-by-key) — evaluated against all active plans
  in every market that references the currency.
- **Market spread-floor writes** (PATCH `/{market_id}/spread-floor`) — raising the floor can
  newly conflict with existing active plans.

### Error envelope

Code: `spread.floor_violation`

```json
{
  "detail": {
    "code": "spread.floor_violation",
    "message": "...",
    "params": {
      "observed_pct": 0.10,
      "floor_pct": 0.20,
      "offending_plan_ids": ["uuid-1", "uuid-2"]
    }
  }
}
```

### Request fields

| Field | Type | Where |
|---|---|---|
| `acknowledge_spread_compression` | `bool` (default `false`) | Plan/currency/market write body |
| `spread_acknowledgement_justification` | `str \| null` | Plan/currency/market write body |

---

## Role gating

| Operation | Auth |
|---|---|
| Increase `credit_value_supplier_local` | `get_employee_user` (any Internal) |
| Decrease `credit_value_supplier_local` | `get_super_admin_user` (Super Admin) |
| Change `min_credit_spread_pct` | `get_super_admin_user` (Super Admin) |
| Plan create/update (any price) | `get_employee_user` |
| Headroom readout | `get_employee_user` |
| Margin report | `get_super_admin_user` |

---

## Endpoints

### Headroom readout

`GET /api/v1/markets/{market_id}/spread-readout`

Auth: `get_employee_user`.

Returns the current spread state for a market — useful for the admin UI to display the
live headroom before editing the floor or repricing a plan.

Response:
```json
{
  "cheapest_plan_per_credit": 1.50,
  "supplier_value": 1.00,
  "headroom_pct": 0.50,
  "floor_pct": 0.20,
  "offending_plan_ids": []
}
```

If the market has no active plans, `cheapest_plan_per_credit` and `headroom_pct` are null.

### Market spread-floor update

`PATCH /api/v1/markets/{market_id}/spread-floor`

Auth: `get_super_admin_user`.

Body:
```json
{
  "min_credit_spread_pct": 0.25,
  "acknowledge_spread_compression": false,
  "spread_acknowledgement_justification": null
}
```

Returns the updated market (enriched shape).

### Margin report

`GET /internal/margin-report?market_id=<uuid>&period_start=<iso>&period_end=<iso>`

Auth: `get_super_admin_user` (finance-only).

Aggregates:
```
Σ (plan.credit_cost_local_currency − credit_value_supplier_local) × credits_redeemed
```
grouped by plan tier. Only real redemptions (restaurant_transaction rows with a linked
plate_selection) are counted; discretionary transactions are excluded.

Response:
```json
{
  "market_id": "uuid",
  "period_start": "2026-01-01T00:00:00Z",
  "period_end": "2026-01-31T23:59:59Z",
  "total_margin_local": 1234.56,
  "total_credits_redeemed": 980,
  "currency_code": "ARS",
  "by_plan": [
    {
      "plan_id": "uuid",
      "plan_name": "Premium 50",
      "redemptions": 500,
      "margin_per_credit": 0.20,
      "margin_local": 100.0
    }
  ]
}
```

---

## Service layer

### `app/services/credit_spread.py`

Core spread-floor logic. All functions return `SpreadCheck`.

| Function | Purpose |
|---|---|
| `check_spread_floor(db, market_id)` | Check current state (existing plans vs current floor). |
| `check_spread_floor_with_plan(db, market_id, proposed_price, proposed_credit, exclude_plan_id)` | Include a proposed plan (not yet in DB). Used for plan create/update. |
| `check_spread_floor_with_new_supplier_value(db, market_id, proposed_supplier_value)` | Re-evaluate against a proposed supplier value change. |
| `check_spread_floor_with_new_floor_pct(db, market_id, proposed_floor_pct)` | Re-evaluate when the floor itself is being raised. |
| `record_acknowledgement(db, ctx, spread_check)` | Write audit row to `audit.spread_acknowledgement`. |

`SpreadCheck.ok` is `True` when no active plan violates the floor.
`SpreadCheck.offending_plan_ids` lists the UUIDs of violating plans (as strings).

Row locking: all check functions issue `SELECT … FOR UPDATE` on the market and currency rows
inside the caller's transaction, preventing two concurrent writes from each passing in
isolation and together violating the floor.

### `app/services/margin_report.py`

`get_margin_report(db, market_id, period_start, period_end) → MarketMarginReport`

Join path: `restaurant_transaction → plate_selection → subscription → plan_info`. Groups by
`plan_id` and sums credits redeemed. Returns `MarketMarginReport` with `plan_tiers` and totals.

---

## Cases to watch

- **Retired plan with unredeemed credits.** Customer ledger still references the retired plan's
  `credit_cost_local_currency`. Margin reporting keeps the historical plan reachable; never
  hard-delete plans — soft-archive only. Already enforced by `is_archived` soft-delete.

- **Currency revaluation.** A one-shot market re-denomination may need to temporarily violate
  the floor while plan prices are restated. Gate this behind an explicit admin operation;
  the acknowledge path covers it for incremental changes. Full coordinated revaluation is out
  of scope for this feature.

- **Cross-market customers.** Today the plan's market governs the credits granted; redemption
  in another market is not modeled. Known gap.
