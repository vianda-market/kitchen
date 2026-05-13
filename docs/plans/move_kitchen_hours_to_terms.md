# Plan: Move Kitchen Hours from market_info to supplier_terms

## Status: Draft
## Created: 2026-04-12

---

## Motivation

`kitchen_open_time` and `kitchen_close_time` currently live on `core.market_info` as market-wide defaults. Restaurants inherit them at creation time into `ops.restaurant_info`. The problem: kitchen hours are a supplier-level operational concern, not a market-level one.

Both fields carry real operational meaning:

- **`kitchen_close_time`** — Drives the kitchen day cutoff: determines when reservations lock down for a vianda, triggers the `restaurant_transaction` finalization, and gates the vianda selection window.
- **`kitchen_open_time`** — Will define when pickup becomes available: the moment a customer can scan a QR code at a restaurant and when the "Scan QR Code" function appears in the B2C app. This enables suppliers to offer earlier time-of-day viandas (e.g., breakfast restaurants).

Moving both to `billing.supplier_terms` (1:1 with each supplier institution) allows per-supplier customization. Market-level defaults move to `billing.market_payout_aggregator` alongside existing defaults (`require_invoice`, `max_unmatched_bill_days`). Per-restaurant overrides on top of supplier_terms are deferred.

## Assumptions

- Full DB tear-down and rebuild — no incremental migration concerns.
- No active customers impacted — breaking changes are acceptable.
- `market_payout_aggregator` is the established market-level defaults table for supplier terms; kitchen hours defaults belong there, not on `market_info`.

## Current State

### Where kitchen hours live today

| Table | Role |
|---|---|
| `core.market_info` | Market-wide template (09:00 / 13:30 defaults) |
| `audit.market_history` | Audit mirror |
| `ops.restaurant_info` | Per-restaurant copy, inherited at creation |
| `audit.restaurant_history` | Audit mirror |

### Resolution chain (kitchen_day_service.py)

```
market_info.kitchen_close_time  →  MarketConfiguration (Python config)  →  hardcoded 13:30
```

### Consumers of kitchen hours

| File | Usage |
|---|---|
| `app/services/kitchen_day_service.py` | `_get_kitchen_close_time()` — drives kitchen day calculation, cutoff logic |
| `app/services/market_service.py` | CRUD, serialization, enriched queries |
| `app/services/entity_service.py` | Vianda enrichment JOINs select `m.kitchen_close_time` |
| `app/services/billing/institution_billing.py` | Kitchen day period, `is_kitchen_day_active()` |
| `app/routes/admin/markets.py` | Create/update market with kitchen hours |
| `app/schemas/consolidated_schemas.py` | Market create/update/response schemas |
| `app/dto/models.py` | MarketInfo DTO |
| `app/db/trigger.sql` | market_history + restaurant_history triggers |
| `app/tests/routes/test_markets.py` | Test fixtures |

### Target state for market-level defaults

`billing.market_payout_aggregator` already holds market-level supplier defaults:

| Current column | Purpose |
|---|---|
| `require_invoice` | Market default for invoice requirement |
| `max_unmatched_bill_days` | Market default for unmatched bill hold |

Kitchen hours defaults will join this table. Resolution pattern stays consistent: `supplier_terms (if set) → market_payout_aggregator (default)`.

---

## Proposed Design

### Target resolution chain

```
supplier_terms.kitchen_close_time  →  market_payout_aggregator.kitchen_close_time  →  hardcoded 13:30
supplier_terms.kitchen_open_time   →  market_payout_aggregator.kitchen_open_time   →  hardcoded 09:00
```

Per-restaurant overrides (supplier sets different hours per restaurant) are deferred — future work would add nullable overrides on `ops.restaurant_info` that take precedence over supplier_terms.

---

### Phase 1 — Schema changes (DB rebuild)

Since we're doing a full rebuild, all schema changes land at once.

#### 1a. Add columns to `billing.supplier_terms`

Nullable — NULL means "inherit from market default".

```sql
ALTER TABLE billing.supplier_terms
    ADD COLUMN kitchen_open_time  TIME NULL,
    ADD COLUMN kitchen_close_time TIME NULL;
```

#### 1b. Add columns to `billing.market_payout_aggregator`

Non-null with defaults — these are the market-level template values.

```sql
ALTER TABLE billing.market_payout_aggregator
    ADD COLUMN kitchen_open_time  TIME NOT NULL DEFAULT '09:00',
    ADD COLUMN kitchen_close_time TIME NOT NULL DEFAULT '13:30';
```

#### 1c. Drop columns from `core.market_info`

```sql
-- Remove from market_info (no longer the source of truth)
ALTER TABLE core.market_info
    DROP COLUMN kitchen_open_time,
    DROP COLUMN kitchen_close_time;
```

#### 1d. Update audit tables and triggers

- `audit.supplier_terms_history` — add both columns
- `audit.market_payout_aggregator_history` — add both columns
- `audit.market_history` — remove both columns
- `trigger.sql` — update all three trigger functions

**Files:**
- `app/db/schema.sql`
- `app/db/trigger.sql`
- `app/db/seed/reference_data.sql` (market_payout_aggregator seed rows need kitchen hours)

---

### Phase 2 — DTO, schema, and route layer

#### 2a. DTOs (`app/dto/models.py`)

- `SupplierTermsDTO` — add `kitchen_open_time: Optional[time]`, `kitchen_close_time: Optional[time]`
- `MarketInfoDTO` — remove both fields

#### 2b. API schemas (`app/schemas/consolidated_schemas.py`)

**Supplier terms schemas** — add both fields:
- `SupplierTermsEmbedSchema` — `kitchen_open_time: Optional[str]`, `kitchen_close_time: Optional[str]`
- `SupplierTermsCreateSchema` — same
- `SupplierTermsUpdateSchema` — same (all optional)
- `SupplierTermsResponseSchema` — add raw fields + `effective_kitchen_open_time: str`, `effective_kitchen_close_time: str` (resolved values)

**Market payout aggregator schemas** — add both fields:
- `MarketPayoutAggregatorResponseSchema` — `kitchen_open_time: str`, `kitchen_close_time: str`
- Create/update schemas — same

**Market schemas** — remove both fields:
- `MarketCreateSchema` — drop `kitchen_open_time`, `kitchen_close_time`
- `MarketUpdateSchema` — drop both
- `MarketResponseSchema` — drop both + remove field validators

#### 2c. Routes

- `app/routes/supplier_terms.py` — enrich GET response with effective kitchen hours (same pattern as `effective_require_invoice`)
- `app/routes/admin/markets.py` — remove kitchen hours from create/update handlers
- `app/services/route_factory.py` — composite institution create passes kitchen hours to supplier_terms if provided

**Files:**
- `app/dto/models.py`
- `app/schemas/consolidated_schemas.py`
- `app/routes/supplier_terms.py`
- `app/routes/admin/markets.py`
- `app/services/route_factory.py`

---

### Phase 3 — Resolution service and kitchen_day_service

#### 3a. Extend `supplier_terms_resolution.py`

Add resolution for kitchen hours following the existing pattern:

```python
def resolve_effective_kitchen_hours(institution_id: UUID, db) -> dict:
    """
    Resolve kitchen hours: supplier_terms (if set) → market_payout_aggregator → hardcoded.
    Returns: effective_kitchen_open_time, effective_kitchen_close_time
    """
```

#### 3b. Rewrite `kitchen_day_service._get_kitchen_close_time()`

Current signature: `_get_kitchen_close_time(country_code, day_name) -> time`

New signature: `_get_kitchen_close_time(country_code, day_name, institution_id=None, db=None) -> time`

New resolution:
1. If `institution_id` provided → query `supplier_terms.kitchen_close_time`
2. If NULL → query `market_payout_aggregator.kitchen_close_time` via country_code
3. Fallback → `MarketConfiguration` → hardcoded 13:30

Same pattern for a new `_get_kitchen_open_time()` function.

#### 3c. Add `kitchen_open_time` gating logic

New function in `kitchen_day_service.py`:

```python
def is_pickup_available(institution_id: UUID, timezone_str: str, db) -> bool:
    """True if current local time >= effective kitchen_open_time for this supplier."""
```

This will be consumed by:
- QR code scan endpoint (gate the "Scan QR Code" action)
- Vianda pickup route (gate pickup availability)
- B2C app to show/hide pickup UI

#### 3d. Update all callers

| Caller | Has institution_id? | Change |
|---|---|---|
| `app/services/billing/institution_billing.py` | Yes (core context) | Pass `institution_id` + `db` |
| `app/services/entity_service.py` | Yes (via JOINs) | Pass `institution_id` + `db` |
| `app/services/cron/kitchen_start_promotion.py` | Yes (iterates restaurants) | Pass `institution_id` + `db` |
| `app/services/cron/notification_banner_cron.py` | Yes (restaurant context) | Pass `institution_id` + `db` |
| `app/routes/vianda_kitchen_days.py` | Depends on endpoint | Pass if available, fallback to market |
| `app/services/restaurant_explorer_service.py` | Yes (restaurant context) | Pass `institution_id` + `db` |

**Files:**
- `app/services/billing/supplier_terms_resolution.py`
- `app/services/kitchen_day_service.py`
- `app/services/billing/institution_billing.py`
- `app/services/entity_service.py`
- `app/services/cron/kitchen_start_promotion.py`
- `app/services/cron/notification_banner_cron.py`
- `app/routes/vianda_kitchen_days.py`
- `app/routes/vianda_pickup.py` (pickup availability gating)
- `app/services/restaurant_explorer_service.py`

---

### Phase 4 — Clean up market_service and remaining references

#### 4a. `app/services/market_service.py`

- Remove `kitchen_open_time` and `kitchen_close_time` from all SELECT queries
- Remove from `_serialize_market()`
- Remove from `create()` and `update()` parameter lists
- Add kitchen hours to `get_billing_config()` / `update_billing_config()` (since they now live on `market_payout_aggregator`)
- Update `get_billing_propagation_preview()` to include kitchen hours inheritance preview

#### 4b. Entity service JOINs

- `app/services/entity_service.py` — replace `m.kitchen_close_time` in vianda enrichment queries with a JOIN to `supplier_terms` or resolve via service call

#### 4c. Restaurant onboarding

- `app/services/onboarding_service.py` — restaurant creation copies kitchen hours from `supplier_terms` (resolved) instead of `market_info`

#### 4d. Config cleanup

- `app/config/market_config.py` — remove `kitchen_day_config` fallback (market_payout_aggregator replaces it)
- `app/config/location_config.py` — no change needed (timezone concern, not kitchen hours)

**Files:**
- `app/services/market_service.py`
- `app/services/entity_service.py`
- `app/services/onboarding_service.py`
- `app/config/market_config.py`

---

### Phase 5 — Tests and documentation

- `app/tests/routes/test_markets.py` — remove kitchen hours from market test fixtures
- Add test coverage for supplier_terms kitchen hours resolution
- Add test coverage for `is_pickup_available()` gating
- `app/tests/security/test_field_policies.py` — no change (access control unchanged)
- Update `docs/api/internal/KITCHEN_DAY_SERVICE.md` — new resolution chain
- Update `CLAUDE_ARCHITECTURE.md` — reflect new ownership
- Produce `docs/api/` doc for B2C agent (QR scan gating, pickup window)

**Files:** ~5-6

---

## Effort Summary

| Phase | Scope | Files |
|---|---|---|
| 1 — Schema (DB rebuild) | schema.sql, trigger.sql, seed data | 3 |
| 2 — DTO / schemas / routes | dto, schemas, supplier_terms route, market route, route_factory | 5 |
| 3 — Resolution + kitchen_day_service | resolution service, kitchen_day_service, all callers, new gating | ~9 |
| 4 — Cleanup market_service + entity | market_service, entity_service, onboarding, config | 4 |
| 5 — Tests + docs | tests, architecture doc, API docs | ~5-6 |

**Total: ~26-27 files across 5 phases.**

---

## Deferred Work

- **Per-restaurant kitchen hours overrides** — Supplier sets different hours for specific restaurants. Would add nullable `kitchen_open_time` / `kitchen_close_time` on `ops.restaurant_info` that override `supplier_terms` when set. Resolution chain becomes: `restaurant_info → supplier_terms → market_payout_aggregator → hardcoded`. The restaurant columns already exist today — they would just need to be re-wired as overrides instead of copies.

---

## Cross-Repo Impact

| Repo | Impact | Doc to produce |
|---|---|---|
| **vianda-platform** (B2B) | Supplier terms UI gains kitchen hours fields; market admin loses them | `docs/api/b2b_client/` update |
| **vianda-app** (B2C) | New `is_pickup_available` gating on QR scan and pickup flow | `docs/api/b2c_client/` new doc |
| **infra-kitchen-gcp** | None — cron jobs already pass through kitchen_day_service | No change |
