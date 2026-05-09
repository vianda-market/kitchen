# Demo-Day Buildup Guide

**Audience:** an agent or engineer adding a new market to the demo dataset (e.g. MX, CL, BR).
**Goal:** follow this doc and add a new market without re-reading the original PE or AR/US PRs.
**Scope:** dev-only narrative data. Not a reference for production seed or migration procedures.

Cross-reference: [docs/plans/demo_day_data.md](../plans/demo_day_data.md) — project tracker and decisions log.

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

### 3.2 Plate distribution

- **10 plates total** distributed unevenly across the 5 restaurants. A plausible distribution is 2/2/2/2/2, 3/2/2/2/1, or 3/3/2/1/1. Do not put all 10 in one restaurant.
- Each plate gets exactly **one product** and **one Mon–Fri plate-kitchen-day row per weekday** (5 PKDs per plate = 50 PKD upserts per market).
- Products belong to `demoInstitutionId` (the single shared demo supplier institution, seeded in `demo_baseline.sql`).
- Plate-kitchen-day upserts **must come after** their plate upsert in the Postman collection execution order. A plate's PKDs cannot be created if the plate_id variable has not been set. This was a real ordering bug fixed in commit `828b5f5`; don't re-introduce it.

### 3.3 Plan and savings band

Every market has exactly **one plan**: 20 credits at a locally-realistic price.

**Savings formula:**
```
credit_cost = plan_price / plan_credits
savings_pct = (price - credit × credit_cost) / price × 100
```

This value is clamped to 0 by `app/services/restaurant_explorer_service.py:_compute_savings_pct` — it will never go negative. Target: **15–25% per plate, fleet average ~20%**.

**Worked example (PE):** plan_price = 80 PEN, plan_credits = 20 → credit_cost = 4 PEN.
Plate: price = 45 PEN, credit = 9 → savings = (45 − 36) / 45 × 100 = **20.0 %**.

**Pick a credit_cost** such that rounding plate credits to whole numbers lands all 10 plates in the 15–25 % band. The simplest path: choose credit_cost so that most plates hit exactly 20 % (credit = price × 0.80 / credit_cost, rounded), then verify no plate falls outside 15–25 %.

**Currency scale guidance by market:**

| Market | Plan price range | Plate price range | Credit cost |
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

**Address UUID sub-ranges:**

| Sub-range | Content |
|---|---|
| `dddddddd-dec0-0010-0000-00000000000N` | PE addresses (N = 1 office, 2–6 restaurants) |
| `dddddddd-dec0-0020-0000-00000000000N` | AR addresses (N = 1 office, 2–6 restaurants) |
| `dddddddd-dec0-0030-0000-00000000000N` | US addresses (N = 1 office, 2–6 restaurants) |
| `dddddddd-dec0-0040-...` | Reserve for next market (CL, MX, BR, etc.) |

The institution entity UUID uses the `0001` sub-range with a per-market suffix:

| UUID | Entity |
|---|---|
| `dddddddd-dec0-0001-0000-000000000001` | Demo supplier institution (shared, PE-market primary) |
| `dddddddd-dec0-0001-0000-000000000002` | Demo super-admin user (shared) |
| `dddddddd-dec0-0001-0000-000000000003` | PE institution entity |
| `dddddddd-dec0-0001-0000-000000000004` | AR institution entity |
| `dddddddd-dec0-0001-0000-000000000005` | US institution entity |

When adding a new market: add the institution_market binding in Section 1 (the shared institution already exists), add addresses in Section 3 under a new sub-range, and add the institution entity in a new section following the PE/AR/US pattern. The institution entity must reference the correct currency_metadata_id from `reference_data.sql`.

### 4.2 API-created entities (Postman collection)

All entities with a `PUT /by-key` endpoint are created in Postman, not SQL. Use `DEMO_*_<CC>_*` canonical keys, e.g.:
- `DEMO_RESTAURANT_AR_LA_LAVALLE`
- `DEMO_PRODUCT_AR_MILANESA`
- `DEMO_PLATE_AR_R1_MILANESA`
- `DEMO_PKD_AR_R1_MILANESA_MONDAY`
- `DEMO_PLAN_AR_ESTANDAR`
- `DEMO_QR_AR_LA_LAVALLE`

Keys are UPPER_SNAKE_CASE. Once published to a collection or SQL file, a key must never be renamed (renaming orphans the old row).

Reference: `docs/api/internal/UPSERT_SEED_CONVENTION.md`.

---

## 5. Folder Layout in the Postman Collection

The collection has one set of folders per market, numbered by execution order:

```
00 Setup                        — shared: login as demo-admin; run once
10 Supplier menu (PE)           — PE restaurants, products, plates, PKDs, plan
10 Supplier menu (AR)           — AR restaurants, products, plates, PKDs, plan
10 Supplier menu (US)           — US restaurants, products, plates, PKDs, plan
20 Customers (PE)               — PE customer signup flow
20 Customers (AR)               — AR customer signup flow
20 Customers (US)               — US customer signup flow
30 Subscribe each customer      — shared folder: subscribe all markets' C01-C05 + C07
30 Subscribe each customer (AR) — AR subscription steps (inside 30, or separate 30 AR)
30 Subscribe each customer (US) — US subscription steps
40 Order history loop           — PE orders
40 Order history (AR)           — AR orders
40 Order history (US)           — US orders
99 Sanity checks                — shared: assertions for ALL markets
```

**Within each `10 Supplier menu (<CC>)` folder, execution order must be:**
1. Upsert all 5 restaurants (sets `restaurantXxRNId` variables).
2. Upsert QR codes (one per restaurant, inject `restaurant_id` from the variable set in step 1).
3. Upsert products (sets `productXxNameId` variables).
4. Upsert plates — each injects `restaurant_id` AND `product_id` from step 1 and 3 variables.
5. Upsert plate-kitchen-days — each injects `plate_id` from step 4 variables.
6. Upsert plan (last, so collection variables are all set).

Steps 4 and 5 are the critical ordering constraint. A PKD upsert needs `plate_id`; if the plate upsert hasn't run yet, `plate_id` is an empty string and the API returns 422.

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

### 6.11 DEV_MODE holiday bypass — pin `target_kitchen_day` explicitly in folder 40

`app/services/plate_selection_validation._find_next_available_kitchen_day_in_week` skips national holidays when auto-selecting a kitchen day. However, in `DEV_MODE` (which defaults to `True` in `app/config/settings.py`), Saturdays are mapped to `"friday"` so E2E flows work on weekends.

When today IS a national holiday for the plate's market AND `DEV_MODE=True`, the following sequence fires:
1. Auto-select tries today (holiday) → skips (correct).
2. Auto-select tries tomorrow (Saturday) → maps to `"friday"` via DEV_MODE logic.
3. Checks if Saturday's date (`tomorrow`) is a national holiday — it is NOT.
4. Returns `"friday"` with tomorrow's date as the target, **not today's** — bypassing the holiday guard.
5. `_validate_restaurant_for_day` then resolves `"friday"` to today (the actual nearest Friday) → 403 holiday block.

**Fix:** add `"target_kitchen_day": "wednesday"` (or any safe mid-week day) to every plate selection request body in folder 40 for non-PE markets. This bypasses auto-selection entirely and prevents the DEV_MODE edge case.

Confirmed safe days by market (no 2026 public holidays on Wednesday):
- AR: Wednesday is never a national holiday in 2026. Use `"wednesday"`.
- US: Only Veterans Day (Nov 11) falls on Wednesday in 2026. For year-round safety, use `"wednesday"` — demo days are unlikely to land on Veterans Day.

PE folder 40 uses auto-selection today (no Friday holidays in the near term), but should also be pinned for safety when the next engineer adds it.

```json
{
  "plate_id": "PLACEHOLDER",
  "pickup_time_range": "12:00-12:15",
  "target_kitchen_day": "wednesday"
}
```

---

## 7. Per-Market Checklist

Work through these in order. Each item has a verification gate before proceeding.

1. **Choose city and cluster street.** Pick a recognizable commercial street in the target city. Verify the street exists on OpenStreetMap and pick 5 real addresses within 300 m. Record lat/lng for each (you will need these for the geo filter smoke test).

2. **Resolve the market's `market_id` from `reference_data.sql`.** See Section 6.9. Record the UUID — it goes into every Postman plan body and sanity assertion.

3. **Identify the correct `city_metadata_id` lookup key.** Confirm the GeoNames ASCII name for the target city and country_iso code. Verify against the live DB after rebuild: `SELECT cm.city_metadata_id, gc.ascii_name FROM core.city_metadata cm JOIN external.geonames_city gc ON cm.geonames_id = gc.geonames_id WHERE cm.country_iso = '<CC>' ORDER BY gc.population DESC LIMIT 3;`

4. **Design the plan.** Choose credit_cost so that 10 plates priced at locally realistic values all land in the 15–25 % savings band. Plan price = credit_cost × 20. Verify with the formula from Section 3.3.

5. **Design 10 plates with locally realistic menu items.** Record for each: restaurant name, product name, price, credit count, computed savings %. Fleet average must be ~20 %.

6. **Draft the SQL block for `demo_baseline.sql`.** Add:
   - Institution market binding for the new market (Section 1 of the file).
   - 6 addresses under a new dec0 sub-range (1 office + 5 restaurants).
   - Institution entity with the correct currency_metadata_id.
   - Update the SUMMARY block at the end of the file.

7. **Draft Postman folders** following Section 5's layout. Start from the PE folders as a template: find-replace `PE` → `<CC>`, update names, prices, addresses, market_id, etc. Verify:
   - All plate upserts inject `restaurant_id` from the collection variable set by the preceding restaurant upsert.
   - All PKD upserts inject `plate_id` from the collection variable set by the preceding plate upsert.
   - C06 and C07 use the `.no_plan` / `.no_orders` suffixes.
   - Subscribe folder skips C06 and subscribes C07.
   - Order folder skips both C06 and C07.
   - Every plate selection request body in folder 40 includes `"target_kitchen_day": "wednesday"` (see Gotcha 6.11).
   - The plan upsert body in folder 10 includes `"acknowledge_spread_compression": true` (see Gotcha 6.10).

8. **Add collection-level variables** for all new entity IDs and tokens to the top of the collection JSON.

9. **Extend folder 99 Sanity** with assertions for the new market (5 restaurants, plates in savings band, correct customer count, C06 has no subscription, C07 has no orders). Do not break existing PE assertions.

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

## 8. What NOT to Do

- Do not write raw SQL outside `demo_baseline.sql` to create demo entities.
- Do not use `POST /<entity>` to create fixture entities. Use `PUT /<entity>/by-key`. The only POST calls in the collection are for transactional events: orders, reviews, favorites, subscriptions, and the customer signup flow (which has no by-key endpoint).
- Do not create new collection files per market. All markets live in `900_DEMO_DAY_SEED.postman_collection.json`.
- Do not run the loader with `--no-verify` on a failing run. Fix the failure.
- Do not touch `reference_data.sql` or migrations to add demo content.
- Do not add demo data UUIDs to `kitchen_template`'s fingerprint in `scripts/refresh_db_template.sh`.
- Do not hard-code `city_metadata_id` UUIDs in `demo_baseline.sql`. Always resolve them at runtime via the GeoNames JOIN — the UUID can change between rebuilds if the reference data is regenerated.
- Do not add a `DEV_MODE` holiday-bypass patch to `app/services/plate_selection_service.py` or `restaurant_explorer_service.py` to work around a failing folder 40. Fix it in the Postman collection instead (pin `target_kitchen_day`, see Gotcha 6.11).
