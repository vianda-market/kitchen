# Plan Upsert Endpoint & Canonical Fixture Convention

## Overview

Postman collections and dev seed scripts that create plans should use the idempotent
upsert endpoint (`PUT /api/v1/plans/by-key`) rather than `POST /api/v1/plans`.
Using POST creates a new row on every run, causing duplicate plans to accumulate
in the dev DB.

---

## Upsert Endpoint

```http
PUT /api/v1/plans/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (≤200 chars) | yes | Stable identifier, e.g. `MARKET_AR_PLAN_STANDARD_50000_ARS` |
| `market_id` | UUID | yes | Market this plan belongs to (must not be Global) |
| `name` | string (≤100 chars) | yes | Human-readable plan name |
| `credit` | int (> 0) | yes | Credits granted per renewal |
| `price` | float (≥ 0) | yes | Price in market local currency |
| `highlighted` | bool | no | Whether this plan is featured in plan selection UI |
| `status` | string | no | `active` (default) or `inactive` |
| `marketing_description` | string | no | Marketing copy (max 1000 chars) |
| `features` | list[string] | no | Feature bullet points |
| `cta_label` | string | no | Call-to-action label |
| `*_i18n` | object | no | Locale maps for localised fields |

`rollover` and `rollover_cap` are always forced to `true` and `null` respectively
(same enforcement as `POST /plans`).

### Response

HTTP **200** on both insert and update.  Response body is `PlanResponseSchema`
(same shape as `GET /api/v1/plans/{plan_id}`).

### Semantics

- If a plan with the given `canonical_key` **does not exist**: a new plan is
  inserted with that `canonical_key`.
- If a plan with the given `canonical_key` **already exists**: the row is
  updated in-place; the `plan_id` does not change.
- Running the same request twice with identical payload is a no-op after the
  first call (idempotent).

### Auth

Internal only (same as `POST /plans`).  Returns 403 for Customer/Supplier roles.

---

## canonical_key Convention

`canonical_key` values follow this naming pattern:

```
MARKET_{ISO2_CODE}_PLAN_{DESCRIPTION}_{PRICE}_{CURRENCY}
```

Examples:
- `MARKET_AR_PLAN_STANDARD_50000_ARS` — Argentina standard plan at 50 000 ARS
- `MARKET_US_PLAN_STANDARD_15_USD` — US standard plan at 15 USD
- `MARKET_AR_PLAN_PERMISSIONS_TEST` — Permissions test fixture (no price suffix)

Keys are UPPER_SNAKE_CASE.  Keep them human-readable and unique across all
markets.  Once published to a Postman collection or seed file the key must
**not** be renamed (renaming would create a new row, orphaning the old one).

---

## Stripe Minimum Price Requirement

Stripe rejects charges below its USD-equivalent minimum (~$0.50).  Canonical
fixture plans must use realistic prices:

| Market | Minimum safe price | Canonical fixture price |
|---|---|---|
| AR (Argentine Peso) | ~500 ARS | **50 000 ARS** (comfortable margin) |
| US (USD) | $1.00 | **$15.00** |

Never create a plan priced at 10 ARS or $0.10 — it cannot be subscribed to
end-to-end and pollutes the dev DB with unusable data.

---

## When to Use Upsert vs POST

| Situation | Use |
|---|---|
| Postman seed request (create test data before a test run) | `PUT /by-key` |
| `dev_fixtures.sql` canonical plan row | `INSERT ... ON CONFLICT (canonical_key) DO UPDATE` |
| Admin creating a real production plan | `POST /plans` |
| Updating an existing known plan | `PUT /plans/{plan_id}` |

---

## Duplicate Plan Cleanup

If the dev DB already has duplicate plan rows (accumulated before this upsert
endpoint existed) run the cleanup script:

```bash
# Dry-run first — preview what would be archived:
python scripts/cleanup_duplicate_plans.py --dry-run

# Live run — archives duplicates, keeps the oldest row per market+name:
python scripts/cleanup_duplicate_plans.py
```

The script is idempotent: running it again after a clean state does nothing.

Plans with a `canonical_key` are never touched by the cleanup script.

---

## Schema Notes

- `customer.plan_info.canonical_key VARCHAR(200) NULL` — new column added in
  migration `0002_plan_canonical_key.sql`.
- Uniqueness enforced by partial index `uq_plan_info_canonical_key` (sparse:
  only indexed when not null, so ad-hoc plans with `canonical_key = NULL` are
  not affected).
- `PlanResponseSchema` now includes `canonical_key` (nullable string).
