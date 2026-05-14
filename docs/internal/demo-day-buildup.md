# Demo-Day Buildup Guide

**Audience:** an agent or engineer adding a new market to the demo dataset (e.g. MX, CL, BR).
**Goal:** follow this doc and add a new market without re-reading the original PE or AR/US PRs.
**Scope:** dev-only narrative data. Not a reference for production seed or migration procedures.

Cross-reference: [docs/plans/demo_day_data.md](../plans/demo_day_data.md) — project tracker and decisions log.
Related: [docs/guidelines/database/DEMO_DAY_DATASET.md](../guidelines/database/DEMO_DAY_DATASET.md) — permanent reference for what is in the dataset and how to log in.

---

## 1. Scope

Demo-day data is a stakeholder-facing, **dev-only**, opt-in dataset that makes the Vianda dev environment look like a live marketplace. It is:

- A fictional but geographically plausible restaurant cluster with real food names, real prices, and customers spread across neighborhoods.
- Reloadable at any time after `build_kitchen_db.sh` rebuilds the dev DB.
- Idempotent: running the loader twice produces no duplicates.
- Purgeable: `scripts/purge_demo_data.sh` removes everything and leaves the DB clean.

It is **not**:
- `app/db/seed/dev_fixtures.sql` — that file contains feature-verification fixtures (geo filters, etc.) unrelated to the narrative demo.
- `app/db/seed/reference_data.sql` — canonical system-level seed (markets, currencies, institutions). Never touch reference data to add demo content.
- Staging or production data. The loader exits non-zero on any non-dev DB.
- Included in the `kitchen_template` fingerprint. Demo data loads on top of the template, not inside it.

---

## 2. Files to Touch When Adding a Market

| File | What to change |
|---|---|
| `app/db/seed/demo_baseline.sql` | Add an institution_market binding, 5 restaurant addresses (1 office + 5 restaurants), and an institution entity section for the new country. Use a new dec0 address sub-range. |
| `docs/postman/collections/900_DEMO_DAY_SEED.postman_collection.json` | Add four sibling top-level folders: `10 Supplier menu (<CC>)`, `20 Customers (<CC>)`, `30 Subscribe each customer (<CC>)`, `40 Order history (<CC>)`. Extend `99 Sanity` with assertions for the new market. Add collection-level variables for the new market's entity IDs and tokens. |
| `scripts/load_demo_data.sh` | Add a `--- <Country Name> (<CC>) ---` subheader block in both the early-write and end-write credentials blocks. |
| `scripts/purge_demo_data.sh` | Verify the username `LIKE` pattern at every tier also catches the new market's pattern (e.g. `demo.cliente.ar.%@vianda.demo`). Add a new LIKE clause if needed. |
| `docs/postman/environments/dev.postman_environment.json` | Only needed if the new market requires a new environment variable not already present. The existing `baseUrl`, `demoAdminUsername`, etc. are shared. |
| `docs/plans/demo_day_data.md` | Add a checklist entry under Implementation Checklist and update the decisions log if choices differ from prior markets. |
| `docs/internal/demo-day-buildup.md` (this file) | Update with any new gotchas or reusable learnings discovered while adding the market. |

**Do not** create `demo_baseline_ar.sql`, `900_AR.postman_collection.json`, or any per-market file. Single-file per asset is the architecture decision.

---

## 3. The Narrative Shape per Market

### 3.1 Restaurant cluster

Pick **5 restaurants on a single recognizable street** in one city, all within 300 m of each other. The tight geographic cluster is intentional: it makes the map in the consumer app show a dense pin cluster, which is the "product-market fit" visual for stakeholder demos.

Requirements:
- One anchor address per cluster (the main street). Up to 4 additional addresses on cross-streets or adjacent blocks, all within 300 m.
- Real lat/lng — look them up or cross-check against OpenStreetMap. Wrong coordinates break the geo filter and will show no restaurants in the app.
- Use `street_type_enum` values correctly. The lowercase 2-letter code is `'st'` (street) and `'ave'` (avenue). The value `'str'` does **not** exist. See Section 6, gotcha 1.
- Restaurant names must feel local (Spanish for AR, English for US, etc.).

### 3.2 Vianda distribution

- **10 viandas total** distributed unevenly across the 5 restaurants. A plausible distribution is 2/2/2/2/2, 3/2/2/2/1, or 3/3/2/1/1. Do not put all 10 in one restaurant.
- Each vianda gets exactly **one product** and **one Mon–Fri vianda-kitchen-day row per weekday** (5 PKDs per vianda = 50 PKD upserts per market).
- Products belong to `demoInstitutionId` (the single shared demo supplier institution, seeded in `demo_baseline.sql`).
- Vianda-kitchen-day upserts **must come after** their vianda upsert in the Postman collection execution order. A vianda's PKDs cannot be created if the vianda_id variable has not been set. This was a real ordering bug fixed in commit `828b5f5`; don't re-introduce it.

### 3.3 Plan and savings band

Every market has exactly **one plan**: 20 credits at a locally-realistic price.

**Savings formula:**
```
credit_cost = plan_price / plan_credits
savings_pct = (price - credit × credit_cost) / price × 100
```

This value is clamped to 0 by `app/services/restaurant_explorer_service.py:_compute_savings_pct` — it will never go negative. Target: **15–25% per vianda, fleet average ~20%**.

**Worked example (PE):** plan_price = 80 PEN, plan_credits = 20 → credit_cost = 4 PEN.
Vianda: price = 45 PEN, credit = 9 → savings = (45 − 36) / 45 × 100 = **20.0 %**.

**Pick a credit_cost** such that rounding vianda credits to whole numbers lands all 10 viandas in the 15–25 % band. The simplest path: choose credit_cost so that most viandas hit exactly 20 % (credit = price × 0.80 / credit_cost, rounded), then verify no vianda falls outside 15–25 %.

**Currency scale guidance by market:**

| Market | Plan price range | Vianda price range | Credit cost |
|---|---|---|---|
| PE | 70–90 PEN | 30–55 PEN | 3–5 PEN/credit |
| AR | 14,000–20,000 ARS | 15,000–25,000 ARS | 700–1,000 ARS/credit |
| US | 15–20 USD | 12–18 USD | 0.70–1.00 USD/credit |
| CL (next) | 6,000–10,000 CLP | 5,000–9,000 CLP | 300–500 CLP/credit |

Do not use toy values (e.g. 10 ARS plan, $0.10 USD plan). The Stripe minimum check in `UPSERT_SEED_CONVENTION.md` gives minimum safe prices per currency.

### 3.4 Customers

Each market gets **7 customers**:

| Slot | Username pattern | Role in demo |
|---|---|---|
| C01–C05 | `demo.cliente.<cc>.0N@vianda.demo` | Full flow: signup → verify → address → subscribe → order 5 times → review |
| C06 | `demo.cliente.<cc>.06.no_plan@vianda.demo` | Signup + verify + login + address. Skipped from Subscribe and Order folders entirely. Shows the "buy a plan" purchase flow. |
| C07 | `demo.cliente.<cc>.07.no_orders@vianda.demo` | Subscribes to the plan. Skipped from Order folder. Shows the "start ordering" onboarding flow. |

The `.no_plan` and `.no_orders` suffixes in C06/C07's email local-part are load-bearing: the demo operator reads them at runtime to know which login demonstrates which flow. Do not use `demo.cliente.<cc>.06@vianda.demo` — that removes the signal.

C01–C05 customer addresses must be in different neighborhoods of the market's city, not on the restaurant cluster street. Spread them across 5 distinct named neighborhoods so the geo filter works for each customer.

---

## 4. Determinism Rules

### 4.1 SQL-only entities (demo_baseline.sql)

Entities without a `PUT /by-key` endpoint go into `demo_baseline.sql` using deterministic UUIDs with the `dddddddd-dec0-` prefix. This prefix is the purge selector used by `scripts/purge_demo_data.sh`. Every row uses `ON CONFLICT (...) DO UPDATE SET ...`.

**UUID sub-ranges (complete table):**

| Sub-range | Content |
|---|---|
| `dddddddd-dec0-0001-0000-000000000001` | Primary demo supplier institution (shared PE/AR/US) |
| `dddddddd-dec0-0001-0000-000000000002` | Demo super-admin user |
| `dddddddd-dec0-0001-0000-000000000003` | PE institution entity (primary supplier) |
| `dddddddd-dec0-0001-0000-000000000004` | AR institution entity (primary supplier) |
| `dddddddd-dec0-0001-0000-000000000005` | US institution entity (primary supplier) |
| `dddddddd-dec0-0002-0000-000000000001` | PE secondary institution (Cocina Andina S.A.C.) |
| `dddddddd-dec0-0002-0000-000000000002` | AR secondary institution (Cocina de Recoleta S.R.L.) |
| `dddddddd-dec0-0002-0000-000000000003` | US secondary institution (Capitol Hill Kitchen LLC) |
| `dddddddd-dec0-0002-0000-000000000004` | PE secondary institution entity |
| `dddddddd-dec0-0002-0000-000000000005` | AR secondary institution entity |
| `dddddddd-dec0-0002-0000-000000000006` | US secondary institution entity |
| `dddddddd-dec0-0010-0000-00000000000N` | PE primary addresses (N=1 office, 2–6 restaurants) |
| `dddddddd-dec0-0011-0000-00000000000N` | PE secondary addresses (N=1 office, N=2 restaurant) |
| `dddddddd-dec0-0020-0000-00000000000N` | AR primary addresses |
| `dddddddd-dec0-0021-0000-00000000000N` | AR secondary addresses |
| `dddddddd-dec0-0030-0000-00000000000N` | US primary addresses |
| `dddddddd-dec0-0031-0000-00000000000N` | US secondary addresses |
| `dddddddd-dec0-0040-...` | Reserved for next primary market (CL, MX, BR) |
| `dddddddd-dec0-0050-0000-00000000000N` | SQL-seeded institution_bill_info for secondary suppliers |

When adding a new market: add the institution_market binding in Section 1 (the shared institution already exists), add addresses in Section 3 under a new sub-range (`0040` for the 4th market), and add the institution entity in a new section following the PE/AR/US pattern. The institution entity must reference the correct currency_metadata_id from `reference_data.sql`.

### 4.2 API-created entities (Postman collection)

All entities with a `PUT /by-key` endpoint are created in Postman, not SQL. Use `DEMO_*_<CC>_*` canonical keys, e.g.:
- `DEMO_RESTAURANT_AR_LA_LAVALLE`
- `DEMO_PRODUCT_AR_MILANESA`
- `DEMO_VIANDA_AR_R1_MILANESA`
- `DEMO_PKD_AR_R1_MILANESA_MONDAY`
- `DEMO_PLAN_AR_ESTANDAR`
- `DEMO_QR_AR_LA_LAVALLE`

Keys are UPPER_SNAKE_CASE. Once published to a collection or SQL file, a key must never be renamed (renaming orphans the old row).

Reference: `docs/api/internal/UPSERT_SEED_CONVENTION.md`.

---

## 5. Folder Layout in the Postman Collection

The collection has one set of folders per market, numbered by execution order:

```
00 Setup                           — shared: login as demo-admin; run once
10 Supplier menu (PE)              — PE restaurants, products, viandas, PKDs, plan
12 Secondary supplier (PE)         — PE secondary institution + restaurant + vianda + activate
20 Customers (PE)                  — PE customer signup flow
30 Subscribe each customer         — PE subscription steps
40 Order history loop              — PE orders
45 Supplier billing (PE)           — POST run-settlement-pipeline?country_code=PE
10 Supplier menu (AR)              — AR restaurants, products, viandas, PKDs, plan
12 Secondary supplier (AR)         — AR secondary institution + restaurant + vianda + activate
20 Customers (AR)                  — AR customer signup flow
30 Subscribe each customer (AR)    — AR subscription steps
40 Order history (AR)              — AR orders
45 Supplier billing (AR)           — POST run-settlement-pipeline?country_code=AR
10 Supplier menu (US)              — US restaurants, products, viandas, PKDs, plan
12 Secondary supplier (US)         — US secondary institution + restaurant + vianda + activate
20 Customers (US)                  — US customer signup flow
30 Subscribe each customer (US)    — US subscription steps
40 Order history (US)              — US orders
45 Supplier billing (US)           — POST run-settlement-pipeline?country_code=US
99 Sanity checks                   — shared: assertions for ALL markets
```

**Within each `10 Supplier menu (<CC>)` folder, execution order must be:**
1. Upsert all 5 restaurants (sets `restaurantXxRNId` variables).
2. Upsert QR codes (one per restaurant, inject `restaurant_id` from the variable set in step 1).
3. Upsert products (sets `productXxNameId` variables).
4. Upsert viandas — each injects `restaurant_id` AND `product_id` from step 1 and 3 variables.
5. Upsert vianda-kitchen-days — each injects `vianda_id` from step 4 variables.
6. Upsert plan (last, so collection variables are all set).

Steps 4 and 5 are the critical ordering constraint. A PKD upsert needs `vianda_id`; if the vianda upsert hasn't run yet, `vianda_id` is an empty string and the API returns 422.

**Folder 99 Sanity:** extend with new assertions for each new market. Use the established pattern: filter by `canonical_key.startsWith('DEMO_RESTAURANT_<CC>_')`, check counts, check savings band. Do not remove or loosen PE assertions when adding AR/US.

---

## 6. Known Gotchas

Every item here cost at least one round trip to discover. Document before forgetting.

### 6.1 `street_type_enum` lowercase code is `'st'`, not `'str'`

The `street_type_enum` in `app/db/schema.sql` uses `'st'` for "Street". Using `'str'` raises a PostgreSQL type-cast error when `demo_baseline.sql` runs. The correct values are `'st'`, `'ave'`, `'blvd'`, `'rd'`, etc. Always cross-check against the enum definition in the schema before adding a new address.

### 6.2 Folder 99 collection-level Bearer auth override

Sanity-check requests that need no auth (or admin auth) must explicitly override the collection-level Bearer token. Set `"auth": {"type": "noauth"}` in the request object AND use `pm.request.headers.upsert` in the pre-request script to inject the correct token. If you only set `"auth": {"type": "noauth"}` without the header upsert, the collection-level `{{demoAdminToken}}` Bearer still fires on the header, resulting in authentication as the admin when you expected no auth.

### 6.3 `PAYMENT_PROVIDER=mock` is required for folder 30

Subscription confirmation via `POST /subscriptions/{id}/confirm-payment` only works when the API is running with `PAYMENT_PROVIDER=mock`. Without it, the endpoint returns 400 and C07 stays in `pending` status. `load_demo_data.sh` enforces this upfront (errors out if not set for `--target=local`). The sanity assertions in folder 99 tolerate `pending` for C07 so the loader does not hard-fail when the operator forgot the env var.

### 6.4 macOS mypy phantom entry on `app/workers/image_pipeline/processing.py:112`

Running `mypy_baseline sync` on macOS adds an entry for `google.cloud has no attribute "vision"` on `processing.py:112`. This entry does not appear on CI (Linux). Adding it to `mypy-baseline.txt` causes CI to fail because `sync` resolves it. Do not add this entry. See `kitchen/CLAUDE.md`'s "Never manually fix the `application.py:0` WebSocket baseline entry" section for the same class of platform-phantom issue.

### 6.5 Idempotency check is the smoke test

Before declaring a market done, run:
```sh
bash scripts/purge_demo_data.sh && bash scripts/load_demo_data.sh
bash scripts/purge_demo_data.sh && bash scripts/load_demo_data.sh
```
Both runs must be green. The second run proves idempotency: all `ON CONFLICT DO UPDATE` clauses are exercised; all Postman upserts are re-entered; all signup flows handle "already exists" gracefully.

### 6.6 City metadata resolution — use GeoNames city name, not local alias

`demo_baseline.sql` resolves `city_metadata_id` by joining `core.city_metadata` → `external.geonames_city` on `gc.ascii_name` and `cm.country_iso`. Use the GeoNames ASCII name, not the local alias. For example:

- Buenos Aires correct GeoNames name: `'Buenos Aires'`
- Seattle correct GeoNames name: `'Seattle'`
- Lima correct GeoNames name: `'Lima'`

If the lookup returns NULL, `RAISE EXCEPTION` fires and the SQL load aborts. Verify with:
```sql
SELECT gc.ascii_name FROM core.city_metadata cm
JOIN external.geonames_city gc ON cm.geonames_id = gc.geonames_id
WHERE cm.country_iso = 'AR' ORDER BY gc.population DESC LIMIT 5;
```

### 6.7 Institution entity currency must match the institution's market

The institution entity `currency_metadata_id` must match the market's currency. Use the seeded IDs from `reference_data.sql`:

| Market | Currency | currency_metadata_id |
|---|---|---|
| AR | ARS | `66666666-6666-6666-6666-666666666601` |
| PE | PEN | `66666666-6666-6666-6666-666666666602` |
| US | USD | `55555555-5555-5555-5555-555555555555` |
| CL | CLP | `66666666-6666-6666-6666-666666666603` |
| MX | MXN | `66666666-6666-6666-6666-666666666604` |
| BR | BRL | `66666666-6666-6666-6666-666666666605` |

### 6.8 Purge script username pattern must be extended for each new market

`purge_demo_data.sh` identifies API-created customers by username LIKE patterns. When adding market `<cc>`, grep the purge script for every `LIKE 'demo.cliente.pe.%@vianda.demo'` clause and add a parallel clause for `LIKE 'demo.cliente.<cc>.%@vianda.demo'`. Missing a tier causes orphaned rows from the new market after purge, which then block re-load on the next run.

### 6.9 Market UUID lookup

Market UUIDs are seeded in `reference_data.sql` with stable values:

| Market | UUID |
|---|---|
| AR | `00000000-0000-0000-0000-000000000002` |
| PE | `00000000-0000-0000-0000-000000000003` |
| US | `00000000-0000-0000-0000-000000000004` |
| CL | `00000000-0000-0000-0000-000000000005` |
| MX | `00000000-0000-0000-0000-000000000006` |
| BR | `00000000-0000-0000-0000-000000000007` |

Use these literal UUIDs in Postman request bodies (e.g. `"market_id": "00000000-0000-0000-0000-000000000002"` for AR). The PE collection uses `00000000-0000-0000-0000-000000000003` throughout.

### 6.10 Plan upserts require `acknowledge_spread_compression: true` for non-PE markets

The `PUT /plans/by-key` endpoint guards against inadvertently pricing credits below the market's `min_credit_spread_pct` floor. When the plan's implicit credit cost (`plan_price / credit`) compresses the spread, the API returns 409 unless `"acknowledge_spread_compression": true` is present in the upsert body.

For PE (credit_cost = 4 PEN) the spread is above the floor and the flag is not required. For AR (credit_cost = 800 ARS) and US (credit_cost = 0.75 USD), the flag is required. Add it to every plan upsert for non-PE markets:

```json
{
  "canonical_key": "DEMO_PLAN_AR_ESTANDAR",
  ...
  "acknowledge_spread_compression": true
}
```

This is an **audited API flag** — it signals "I know this plan compresses the spread and I accept it." It is not a workaround; the demo dataset intentionally uses a tight spread to maximise visible savings percentages for stakeholder demos.

### 6.11 DEV_MODE holiday bypass — ~~pin `target_kitchen_day` explicitly in folder 40~~ (FIXED in PR #258)

> **This workaround has been removed.** The root-cause bug was fixed in PR #258 (branch `fix/holiday-aware-weekday-remap`, closes kitchen#257). The `target_kitchen_day` overrides that were pinned in folder 40 for AR ("wednesday") and US ("monday") have been deleted from `900_DEMO_DAY_SEED.postman_collection.json`. Auto-resolution now correctly detects Friday holidays when the DEV_MODE weekend→Friday remap fires.

**Historical context (for reference only):** `_find_next_available_kitchen_day_in_week` mapped weekend days to `"friday"` in DEV_MODE but checked the holiday table against the weekend date itself (never a holiday), not the Friday date it had just resolved. This caused the auto-resolver to return a Friday that was a national holiday, which `_validate_restaurant_for_day` then rejected with `403 RESTAURANT_NATIONAL_HOLIDAY`. The workaround was to pin `target_kitchen_day` to a safe mid-week day in every folder 40 request body.

**The fix** (in `vianda_selection_validation.py`): after the weekend→Friday remap, `holiday_check_date` is set to the preceding Friday (`d - timedelta(days=d.weekday() - 4)`) instead of the weekend date. The holiday check now uses that Friday's date, so Friday holidays are correctly detected and the loop advances to the next working day. Covered by `TestFindNextAvailableKitchenDayHolidayAwareRemap` in `app/tests/services/test_vianda_selection_validation.py`.

---

## 7. Per-Market Checklist

Work through these in order. Each item has a verification gate before proceeding.

1. **Choose city and cluster street.** Pick a recognizable commercial street in the target city. Verify the street exists on OpenStreetMap and pick 5 real addresses within 300 m. Record lat/lng for each (you will need these for the geo filter smoke test).

2. **Resolve the market's `market_id` from `reference_data.sql`.** See Section 6.9. Record the UUID — it goes into every Postman plan body and sanity assertion.

3. **Identify the correct `city_metadata_id` lookup key.** Confirm the GeoNames ASCII name for the target city and country_iso code. Verify against the live DB after rebuild: `SELECT cm.city_metadata_id, gc.ascii_name FROM core.city_metadata cm JOIN external.geonames_city gc ON cm.geonames_id = gc.geonames_id WHERE cm.country_iso = '<CC>' ORDER BY gc.population DESC LIMIT 3;`

4. **Design the plan.** Choose credit_cost so that 10 viandas priced at locally realistic values all land in the 15–25 % savings band. Plan price = credit_cost × 20. Verify with the formula from Section 3.3.

5. **Design 10 viandas with locally realistic menu items.** Record for each: restaurant name, product name, price, credit count, computed savings %. Fleet average must be ~20 %.

6. **Draft the SQL block for `demo_baseline.sql`.** Add:
   - Institution market binding for the new market (Section 1 of the file).
   - 6 addresses under a new dec0 sub-range (1 office + 5 restaurants).
   - Institution entity with the correct currency_metadata_id.
   - Update the SUMMARY block at the end of the file.

7. **Draft Postman folders** following Section 5's layout. Start from the PE folders as a template: find-replace `PE` → `<CC>`, update names, prices, addresses, market_id, etc. Verify:
   - All vianda upserts inject `restaurant_id` from the collection variable set by the preceding restaurant upsert.
   - All PKD upserts inject `vianda_id` from the collection variable set by the preceding vianda upsert.
   - C06 and C07 use the `.no_plan` / `.no_orders` suffixes.
   - Subscribe folder skips C06 and subscribes C07.
   - Order folder skips both C06 and C07.
   - Vianda selection request bodies in folder 40 do NOT include `target_kitchen_day` — auto-resolution is now holiday-aware (see Gotcha 6.11).
   - The plan upsert body in folder 10 includes `"acknowledge_spread_compression": true` (see Gotcha 6.10).

8. **Add collection-level variables** for all new entity IDs and tokens to the top of the collection JSON.

9. **Extend folder 99 Sanity** with assertions for the new market (5 restaurants, viandas in savings band, correct customer count, C06 has no subscription, C07 has no orders). Do not break existing PE assertions.

10. **Update `scripts/load_demo_data.sh`** — add the new market's customer credentials in both the early-write and final-write blocks.

11. **Update `scripts/purge_demo_data.sh`** — add `OR username LIKE 'demo.cliente.<cc>.%@vianda.demo'` at every tier.

12. **Rebuild the dev DB and run the loader:**
    ```sh
    bash app/db/build_kitchen_db.sh
    PAYMENT_PROVIDER=mock bash scripts/run_dev_quiet.sh   # terminal 1
    bash scripts/load_demo_data.sh                         # terminal 2
    ```
    Verify Newman completes green and all folder 99 assertions pass.

13. **Idempotency check:**
    ```sh
    bash scripts/purge_demo_data.sh && bash scripts/load_demo_data.sh
    ```
    Must be green.

14. **Update `docs/internal/demo-day-buildup.md`** with any new gotchas or refinements discovered while adding this market.

15. **Commit** with message `feat(demo): add <CC> market (<city>) to demo-day seed`.

---

## 8. Secondary Supplier Pattern (multi-tenant admin view)

Each market has a second, smaller supplier institution to demonstrate multi-tenant admin views. This is a "secondary tenant" that appears alongside the primary in `GET /institutions` filtered by market.

### 8.1 What the secondary supplier contains

Per market:
- 1 institution (distinct name, e.g. "Cocina Andina S.A.C." for PE)
- 1 institution entity with `payout_onboarding_status = 'complete'` (required for restaurant activation)
- 1 restaurant in a different neighborhood from the primary cluster
- 1 vianda with Mon–Fri PKDs (savings within 18–22 %)
- 1 supplier admin user (`demo.proveedor.<cc>.02.admin@vianda.demo`)

### 8.2 Why entities are pre-seeded in demo_baseline.sql

The restaurant activation gate (`restaurant.active_requires_entity_payouts`) checks `payout_onboarding_status`. The `PUT /institution-entities/by-key` upsert schema has `payout_onboarding_status` as optional (default `None`). If the upsert body omits it, the Postman update path would NULL out the field, blocking activation.

Resolution: pre-seed the secondary institution AND its entity in `demo_baseline.sql` with fixed dec0 UUIDs and `payout_onboarding_status = 'complete'`. Use `ON CONFLICT DO UPDATE SET canonical_key = ...` so that the subsequent `PUT /by-key` Postman call **adopts** the existing row (matching by canonical_key) and returns the stable UUID — it does not create a duplicate.

Key sub-ranges used:
| Sub-range | Content |
|---|---|
| `dddddddd-dec0-0002-0000-000000000001` | PE secondary institution |
| `dddddddd-dec0-0002-0000-000000000002` | AR secondary institution |
| `dddddddd-dec0-0002-0000-000000000003` | US secondary institution |
| `dddddddd-dec0-0002-0000-000000000004` | PE secondary institution entity |
| `dddddddd-dec0-0002-0000-000000000005` | AR secondary institution entity |
| `dddddddd-dec0-0002-0000-000000000006` | US secondary institution entity |
| `dddddddd-dec0-0011-0000-0000000000NN` | PE secondary addresses |
| `dddddddd-dec0-0021-0000-0000000000NN` | AR secondary addresses |
| `dddddddd-dec0-0031-0000-0000000000NN` | US secondary addresses |

### 8.3 The exclude_none=True fix on the entity upsert

`app/routes/institution_entity.py` `PUT /by-key` was updated to use `model_dump(exclude_none=True)` on the UPDATE path. Without this fix, optional fields absent from the request body (like `payout_onboarding_status`) were serialised as `None` and overwrote the existing DB value. This is a general correctness fix, not a demo-specific workaround.

### 8.4 Postman folder layout for secondary suppliers

Each market gets two new top-level folders immediately after its primary `40` order folder:

```
12 Secondary supplier (<CC>)  — institution + entity + user + restaurant + vianda + PKDs + activate
45 Supplier billing (<CC>)    — POST run-settlement-pipeline?country_code=<CC>
```

The secondary supplier folder follows the same canonical-key and prerequest pattern as the primary `10` folder. Auth uses the demo-admin token for all internal-facing steps.

### 8.5 Sanity check for secondary suppliers

Folder 99 now includes assertions:
- **"Assert 2 <CC> demo suppliers exist"** — filters `GET /institutions` by `institution_type=supplier`, `market_ids` contains the market UUID, and `canonical_key.startsWith('DEMO_')`. The primary institution has `canonical_key = 'DEMO_INSTITUTION_PE_VIANDA_DEMO'` (PE-prefix only, but it covers all three markets). The secondary has `DEMO_INSTITUTION_<CC>_<NAME>`. Together: 2 per market.
- **"Assert <CC> secondary restaurant visible in by-city"** — uses the pre-stored customer token (`customerXxN1Token`) because `GET /restaurants/by-city` is customer-scoped (admins see 0 restaurants). Filters by `name` in the response `restaurants` array.

---

## 9. Supplier Billing

### 9.1 Pipeline-generated bills (primary supplier, all markets)

Postman folder `45 Supplier billing (<CC>)` calls `POST /api/v1/institution-bills/run-settlement-pipeline?country_code=<CC>` once per market, after the order history folder. This generates `institution_bill_info` rows for the primary supplier's entity (standard UUID, not dec0 prefix).

### 9.2 SQL-seeded bills (secondary supplier, all markets)

`demo_baseline.sql` Section 7 backfills 2 `institution_bill_info` rows per market for the secondary supplier entity. The dec0-0050 sub-range is used:

| UUID | Market | Status |
|---|---|---|
| `dddddddd-dec0-0050-0000-000000000001` | PE | pending |
| `dddddddd-dec0-0050-0000-000000000002` | PE | paid |
| `dddddddd-dec0-0050-0000-000000000003` | AR | pending |
| `dddddddd-dec0-0050-0000-000000000004` | AR | paid |
| `dddddddd-dec0-0050-0000-000000000005` | US | pending |
| `dddddddd-dec0-0050-0000-000000000006` | US | paid |

### 9.3 Purge script additions for billing

The purge handles the billing tables in this FK order:
1. `institution_settlement_history` (audit) — references `institution_settlement`
2. `institution_settlement` — references `restaurant_balance_history`, `institution_bill_info`
3. `institution_bill_history` (audit)
4. `institution_bill_info` — purges all demo entity bills (both dec0-0050 and dynamic pipeline UUIDs)

The institution bills purge uses `WHERE institution_entity_id::text LIKE 'dddddddd-dec0-%'` to catch both SQL-seeded and pipeline-generated bills for demo entities.

### 9.4 Known purge gotcha — circular FK between institution_info and user_info

`institution_info.modified_by → user_info` (RESTRICT, NOT NULL) and `user_info.institution_id → institution_info` (RESTRICT). The secondary institutions are modified by the demo admin user. Resolution in the purge script:

1. `UPDATE institution_info SET modified_by = superadmin_user_id WHERE institution_id LIKE 'dddddddd-dec0-%'` — neutralises the modified_by FK.
2. `DELETE FROM institution_history` — also references users via modified_by.
3. `DELETE FROM user_info` — now unblocked.
4. `DELETE FROM institution_market` + `DELETE FROM institution_info` — institutions are deleted last.

---

## 10. Employer Flow (B2B demo)

Each market has one employer institution with an admin user and one or more
employee users. The employer flow demonstrates the B2B subsidy model: the
employer pays a configured benefit rate, and employees subscribe to plans at a
reduced net cost.

### 10.1 Data model overview

Per market:
- 1 employer institution (`institution_type = 'employer'`) — upserted via `PUT /institutions/by-key`.
- 1 employer institution entity — upserted via `PUT /institution-entities/by-key`.
- 1 employer benefits program — upserted via `PUT /employer/program/by-key`.
- 1 employer admin user (`role_type = Employer`, `role_name = Admin`) — upserted via `PUT /users/by-key`.
- N employee users (`role_type = Customer`, `role_name = Comensal`) — upserted via `PUT /users/by-key`.
- N employer employee links — upserted via `PUT /employer/employee-link/by-key`.

### 10.2 Canonical key conventions

```
DEMO_INSTITUTION_{CC}_EMPLOYER             — employer institution
DEMO_INSTITUTION_ENTITY_{CC}_EMPLOYER      — employer entity
DEMO_EMPLOYER_{CC}_PROGRAM                 — employer benefits program
DEMO_USER_{CC}_EMPLOYER_ADMIN              — employer admin user
DEMO_USER_{CC}_EMPLOYER_EE_01 ... N        — employee users
DEMO_EMPLOYER_{CC}_EE_DEMO_EMPLEADO_{CC}_01_VIANDA_DEMO_LINK  — employee link
```

### 10.3 UUID sub-ranges for employer entities

Employer institutions are API-created (via `PUT /by-key`) so they do not use
deterministic dec0 UUIDs. The dec0 sub-range `0060` is reserved for
employer-related SQL-seeded rows if ever needed:

| Sub-range | Content |
|---|---|
| `dddddddd-dec0-0060-0000-000000000001` | Reserved — employer address PE (if SQL-seeded) |

Currently all employer entities are API-created (no dec0 UUIDs). The employer
institutions, entities, and program rows all get database-generated UUIDs and
are tracked by canonical_key only.

### 10.4 Folder layout in the Postman collection

Employer setup runs as top-level folders numbered `15` (employer institution,
entity, program, admin user) and `35` (employee users, employee links), nested
between the existing customer (`20`) and subscribe (`30`) folders:

```
15 Employer setup (<CC>)     — institution + entity + program + admin user enrollment
35 Employee links (<CC>)     — employee users (PUT /users/by-key) + PUT /employee-link/by-key
```

Execution ordering: folder 15 must run after folder 12 (secondary supplier) so
the admin token is stable. Folder 35 must run after folder 30 (customer subscribe)
so that `planId<CC>` collection variables are already set.

### 10.5 Enrollment prerequisites in Postman

`PUT /employer/employee-link/by-key` looks up the user's employer institution
membership by checking `user_info.institution_id`. The employer admin user must
be enrolled first — the admin enrollment step (`POST /employer/employees`) sets
`user_info.institution_id` for the admin. Without this step, the employee link
upsert returns 403 (`security.institution_type_mismatch`) because the employee's
`institution_id` is still NULL.

Order within folder 15:
1. Upsert employer institution.
2. Upsert employer entity.
3. Login as demo admin (get admin token).
4. Upsert employer benefits program.
5. Upsert employer admin user (via `PUT /users/by-key`).
6. Enroll employer admin (`POST /employer/employees` — sets `institution_id` on the admin user).

Order within folder 35:
1. Upsert employee user (via `PUT /users/by-key`).
2. Upsert employee link (via `PUT /employer/employee-link/by-key`).

### 10.6 Purge script additions for employer

The purge handles employer entities in FK dependency order:

1. `audit.subscription_history` — delete where `subscription_id IN (... canonical_key LIKE 'DEMO_EMPLOYER_%')`.
2. `customer.subscription_info` — delete where `canonical_key LIKE 'DEMO_EMPLOYER_%'`.
3. `audit.institution_entity_history` — delete where `canonical_key LIKE 'DEMO_INSTITUTION_ENTITY_%_EMPLOYER'`.
4. `ops.institution_entity_info` — delete where `canonical_key LIKE 'DEMO_INSTITUTION_ENTITY_%_EMPLOYER'`.
5. `core.employer_benefits_program` — delete where `canonical_key LIKE 'DEMO_EMPLOYER_%_PROGRAM'`.
6. Users and institutions follow the standard username/canonical_key LIKE patterns.

The employer entity delete (steps 3–4) must happen **before** the address deletion
tier because `institution_entity_info.address_id → address_info` is RESTRICT.

Employee users follow the same `demo.empleado.%@vianda.demo` username pattern;
add this LIKE clause to every tier in the purge script alongside the
`demo.cliente.<cc>.%@vianda.demo` clauses.

### 10.7 Known gotchas

**RoleType.value vs str(RoleType):** `str(RoleType.CUSTOMER)` returns
`'RoleType.CUSTOMER'`, not `'customer'`. Use `.value` when comparing role types
in Python: `role_attr.value if hasattr(role_attr, "value") else str(role_attr).lower()`.
This was a silent bug in `enrollment_service.py` that caused all employee link
upserts to return 403 before the fix.

**model_dump(exclude_none=True) on the user upsert route:** `PUT /users/by-key`
must use `model_dump(exclude_none=True)` so that optional schema fields absent
from the request body (e.g. `city_metadata_id`) do not override the DB column's
NOT NULL default. Without this, employer admin creation returned 500 due to a
NOT NULL constraint violation on `city_metadata_id`.

**subscription_history FK before subscription delete:** `audit.subscription_history`
references `customer.subscription_info` with RESTRICT. Employee link rows have
a `canonical_key` on `subscription_info`; purge must delete history before info.

---

## 11. What NOT to Do

- Do not write raw SQL outside `demo_baseline.sql` to create demo entities.
- Do not use `POST /<entity>` to create fixture entities. Use `PUT /<entity>/by-key`. The only POST calls in the collection are for transactional events: orders, reviews, favorites, subscriptions, and the customer signup flow (which has no by-key endpoint).
- Do not create new collection files per market. All markets live in `900_DEMO_DAY_SEED.postman_collection.json`.
- Do not run the loader with `--no-verify` on a failing run. Fix the failure.
- Do not touch `reference_data.sql` or migrations to add demo content.
- Do not add demo data UUIDs to `kitchen_template`'s fingerprint in `scripts/refresh_db_template.sh`.
- Do not hard-code `city_metadata_id` UUIDs in `demo_baseline.sql`. Always resolve them at runtime via the GeoNames JOIN — the UUID can change between rebuilds if the reference data is regenerated.
- Do not add a `DEV_MODE` holiday-bypass patch to `app/services/vianda_selection_service.py` or `restaurant_explorer_service.py` to work around a failing folder 40. The root-cause fix lives in `_find_next_available_kitchen_day_in_week` (see Gotcha 6.11); do not reintroduce `target_kitchen_day` pins in folder 40 request bodies.
- Do not update the dec0 sub-range table in Section 4.1 without also documenting the new sub-range in the UUID SCHEME comment block at the top of `demo_baseline.sql`.
