# Upsert Endpoint & Canonical Fixture Convention

Applies to: **plans** (issue #130) and **plates** (issue #166).

## Overview

Postman collections and dev seed scripts that create plans or plates should use
the idempotent upsert endpoints (`PUT /api/v1/plans/by-key`,
`PUT /api/v1/plates/by-key`) rather than the corresponding `POST` endpoints.
Using POST creates a new row on every run, causing duplicate rows to accumulate
in the dev DB.

---

## Plans — `PUT /api/v1/plans/by-key`

```http
PUT /api/v1/plans/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `MARKET_AR_PLAN_STANDARD_50000_ARS` |
| `market_id` | UUID | yes | Market this plan belongs to (must not be Global) |
| `name` | string (<=100 chars) | yes | Human-readable plan name |
| `credit` | int (> 0) | yes | Credits granted per renewal |
| `price` | float (>= 0) | yes | Price in market local currency |
| `highlighted` | bool | no | Whether this plan is featured in plan selection UI |
| `status` | string | no | `active` (default) or `inactive` |
| `marketing_description` | string | no | Marketing copy (max 1000 chars) |
| `features` | list[string] | no | Feature bullet points |
| `cta_label` | string | no | Call-to-action label |
| `*_i18n` | object | no | Locale maps for localised fields |

`rollover` and `rollover_cap` are always forced to `true` and `null` respectively
(same enforcement as `POST /plans`).

Response body is `PlanResponseSchema` (same shape as `GET /api/v1/plans/{plan_id}`).

### canonical_key convention for plans

```
MARKET_{ISO2_CODE}_PLAN_{DESCRIPTION}_{PRICE}_{CURRENCY}
```

Examples:
- `MARKET_AR_PLAN_STANDARD_50000_ARS` — Argentina standard plan at 50 000 ARS
- `MARKET_US_PLAN_STANDARD_15_USD` — US standard plan at 15 USD
- `MARKET_AR_PLAN_PERMISSIONS_TEST` — Permissions test fixture (no price suffix)

### Stripe Minimum Price Requirement

Stripe rejects charges below its USD-equivalent minimum (~$0.50). Canonical
fixture plans must use realistic prices:

| Market | Minimum safe price | Canonical fixture price |
|---|---|---|
| AR (Argentine Peso) | ~500 ARS | **50 000 ARS** (comfortable margin) |
| US (USD) | $1.00 | **$15.00** |

Never create a plan priced at 10 ARS or $0.10.

### Schema Notes (plans)

- `customer.plan_info.canonical_key VARCHAR(200) NULL` — added in
  migration `0002_plan_canonical_key.sql`.
- Partial index `uq_plan_info_canonical_key` (sparse: only indexed when non-null).
- `PlanResponseSchema` includes `canonical_key` (nullable string).

---

## Plates — `PUT /api/v1/plates/by-key`

```http
PUT /api/v1/plates/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `RESTAURANT_LA_COCINA_PORTENA_PLATE_BONDIOLA` |
| `product_id` | UUID | yes | FK to `ops.product_info` — the recipe this plate is based on |
| `restaurant_id` | UUID | yes | FK to `ops.restaurant_info` — the restaurant offering this plate |
| `price` | decimal (>= 0) | yes | Local-currency price charged to subscribers |
| `credit` | int (> 0) | yes | Credit cost deducted from the subscriber's balance |
| `delivery_time_minutes` | int (> 0) | no | Estimated minutes to readiness (default 15) |
| `status` | string | no | `active` (default) or `inactive` |

Response body is `PlateResponseSchema` (same shape as `GET /api/v1/plates/{plate_id}`).

### canonical_key convention for plates

```
RESTAURANT_{RESTAURANT_SLUG}_PLATE_{PLATE_SLUG}
```

Examples:
- `RESTAURANT_LA_COCINA_PORTENA_PLATE_BONDIOLA` — La Cocina Portena's bondiola plate
- `RESTAURANT_LA_COCINA_PORTENA_PLATE_ENSALADA_GRIEGA` — same restaurant, different plate
- `RESTAURANT_E2E_PLATE_STANDARD` — generic E2E test fixture plate

### Pricing guidance for plates

Use realistic prices that reflect actual ARS subscription values:

| Market | Recommended plate price |
|---|---|
| AR | 15 000 - 25 000 ARS |
| US | $8 - $15 USD |

The E2E collection fixture uses 20 000 ARS / 8 credits.

### Why SQL fixtures are not used for plates

Unlike plans (which reference only `market_id` from reference data), plates
require both `product_id` and `restaurant_id`, which are created at test run
time via Postman. Therefore canonical plate fixtures live in the Postman
collection as `PUT /plates/by-key` calls rather than as SQL `INSERT` statements.

If you need a fully SQL-driven plate fixture (e.g. for geo tests), create the
product and restaurant rows with fixed UUIDs first, then use:

```sql
INSERT INTO ops.plate_info (...)
ON CONFLICT (canonical_key) WHERE canonical_key IS NOT NULL
DO UPDATE SET ...
```

### Schema Notes (plates)

- `ops.plate_info.canonical_key VARCHAR(200) NULL` — added in
  migration `0003_plate_canonical_key.sql`.
- Partial index `uq_plate_info_canonical_key` (sparse: only indexed when non-null).
- `PlateResponseSchema` includes `canonical_key` (nullable string).

---

## Shared Semantics (both entities)

- If a row with the given `canonical_key` **does not exist**: a new row is
  inserted with that `canonical_key`.
- If a row with the given `canonical_key` **already exists**: the row is
  updated in-place; the primary key does not change.
- Running the same request twice with identical payload is a no-op after the
  first call (idempotent).
- HTTP **200** on both insert and update (unlike POST which returns 201).
- Auth: Internal only. Returns 403 for Customer/Supplier roles.
- Keys are UPPER_SNAKE_CASE. Once published to a Postman collection or seed
  file the key must **not** be renamed (renaming would create a new row,
  orphaning the old one).

---

## When to Use Upsert vs POST

| Situation | Use |
|---|---|
| Postman seed request (create test data before a test run) | `PUT /by-key` |
| `dev_fixtures.sql` canonical plan row | `INSERT ... ON CONFLICT (canonical_key) DO UPDATE` |
| Admin creating a real production plan | `POST /plans` |
| Supplier creating a real production plate | `POST /plates` |
| Updating a known existing row | `PUT /{entity}/{id}` |

---

## Duplicate Cleanup Scripts

If the dev DB already has duplicate rows accumulated before the upsert
endpoints existed, run the cleanup scripts.

### Plans

```bash
# Dry-run first:
python scripts/cleanup_duplicate_plans.py --dry-run

# Live run — archives duplicates, keeps the oldest row per market+name:
python scripts/cleanup_duplicate_plans.py
```

Plans with a `canonical_key` are never touched by the cleanup script.

### Plates

```bash
# Dry-run first:
python scripts/cleanup_duplicate_plates.py --dry-run

# Live run — archives duplicates, keeps the oldest row per restaurant+product:
python scripts/cleanup_duplicate_plates.py
```

Plates with a `canonical_key` are never touched by the cleanup script.

Both scripts are idempotent: running again after a clean state does nothing.
