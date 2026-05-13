# Supplier Institution Payment: Atomic Closeout-to-Payout

## Overview

Institution (supplier) payment follows a **settlement → bill → payout** flow. There are no $0 settlements, bills, or payments. One settlement per restaurant (only when balance > 0), one bill per entity (aggregating that entity’s settlements), one payment per bill. All institution payment goes through this pipeline; manual payment APIs have been removed.

## Flow

1. **Settlement (Phase 1)**  
   For a given bill date and country, for each restaurant with balance > 0:
   - Create one row in `institution_settlement` (restaurant, period, amount, currency, `settlement_run_id`, etc.).
   - Close uncollected transactions/pickups, record balance event, reset restaurant balance.
   - Idempotent: if a settlement already exists for that restaurant/period, it is returned and no duplicate is created.

2. **Bill per entity (Phase 2)**  
   Only after Phase 1 has completed:
   - For each **entity** that has at least one settlement in the run, create **one** `institution_bill_info` row:
     - `institution_id`, `institution_entity_id`, `period_start`, `period_end`, `amount` = sum of that entity’s settlements, `currency_code`, `credit_currency_id`, `transaction_count` = sum. Bills have no `restaurant_id`; "restaurants per bill" is derived via `institution_settlement` (each settlement has `institution_bill_id` and `restaurant_id`).
   - Update each of that entity’s settlements: set `institution_settlement.institution_bill_id` to the new bill.

3. **Tax doc**  
   For each bill, a tax document is issued (stub returns a placeholder `tax_doc_external_id`; country-specific e-invoicing can be added later). The id is stored on the bill.

4. **Payout**
   For each bill, the Connect gateway is called (`connect_gateway.execute_supplier_payout` or `connect_mock.execute_supplier_payout` depending on `SUPPLIER_PAYOUT_PROVIDER`). The gateway inserts a `billing.institution_bill_payout` row (Pending), creates a Stripe Transfer (or mock), and writes the `provider_transfer_id` back. On success, the bill is marked paid via `institution_bill_service.mark_paid` (sets `status = 'Processed'`, `resolution = 'Paid'`). If the entity has no payout provider account or payouts are not enabled, the bill is skipped (stays Pending for manual payout later).

**Bill resolution (enum)**
`institution_bill_info.resolution` uses PostgreSQL enum `bill_resolution_enum`: **Pending**, **Paid**, **Failed**, **Rejected**. New bills start as Pending; after payout confirmation (via `payout.paid` webhook), the bill moves to Paid. Failed payouts (via `transfer.reversed` or `payout.failed` webhooks) set Failed. Admin rejection sets Rejected. Python: `app.config.enums.BillResolution`.

**Where to see the payment record (mock or live)**
- **Pipeline response:** `POST .../run-settlement-pipeline` returns `bill_ids` (UUIDs) and `paid_bills` (array of `{ institution_bill_id, bill_payout_id, provider_transfer_id }`) for each paid bill. The mock sets `provider_transfer_id` to a placeholder like `tr_mock_<hex>`.
- **Payout table:** `billing.institution_bill_payout` holds one row per payout attempt per bill. The table is append-only — retries insert a new row. Fields: `bill_payout_id`, `institution_bill_id`, `provider`, `provider_transfer_id`, `amount`, `currency_code`, `status`, `idempotency_key`, `created_at`, `completed_at`.
- **Admin endpoint:** `GET /api/v1/institution-entities/{entity_id}/stripe-connect/payouts` lists all payout attempts for an entity's bills (Internal role only).

## Pipeline entry point

- **Service:** `InstitutionBillingService.run_daily_settlement_bill_and_payout(bill_date, system_user_id, country_code=None, location_id=None, connection=None)`  
  Runs Phase 1 → Phase 2 → for each bill: tax doc → payout → set payout fields → mark_paid. When `location_id` is provided, only restaurants in that location's timezone are processed (e.g. US-Pacific for LA kitchens).

- **Cron (location-based):** `app.services.cron.billing_events.multi_market_billing_entry(location_id=None)`  
  When `location_id` is provided (e.g. `"AR"`, `"US-Pacific"`), processes only that location. When `None`, iterates all locations (AR, PE, US-Eastern, US-Central, US-Mountain, US-Pacific). Use for GCP Cloud Scheduler per-location jobs.

- **Cron (legacy):** `run_daily_settlement_bill_and_payout`, `run_kitchen_day_closure_billing`, `run_daily_billing` — support `country_code` for market-level runs. For US multi-timezone, use `multi_market_billing_entry(location_id)` instead.

- **API (manual/test):** `POST /api/v1/institution-bills/run-settlement-pipeline?bill_date=YYYY-MM-DD&country_code=XX`  
  Triggers the same pipeline; use for testing or one-off runs. Requires auth. Query params: `bill_date` (default: today), `country_code` (optional; auto-detected if omitted).

## Configuration

- **SUPPLIER_PAYOUT_PROVIDER** (settings): `mock` (default) or `stripe`. Mock returns success and a placeholder transfer id; live Stripe calls `stripe.Transfer.create` via `app/services/payment_provider/stripe/connect_gateway.py`.

## Why might there be no rows in institution_bill_info?

The pipeline only creates bills when **Phase 1** creates at least one settlement, which happens only when at least one restaurant has **balance > 0** in `restaurant_balance_info`.

- **Check balance:** `SELECT restaurant_id, balance, currency_code FROM restaurant_balance_info WHERE is_archived = FALSE AND balance > 0;`  
  If this returns no rows, the pipeline will return `settlements_created: 0`, `bills_created: 0` and no rows in `institution_settlement` or `institution_bill_info`.
- **How balance gets created:** Restaurant balance is increased when the customer’s visit is recorded (e.g. **Post QR Code Scan** / mark arrival in vianda_pickup flow). There must already be a row in `restaurant_balance_info` for that restaurant (e.g. from restaurant registration); then `update_balance_on_arrival` adds to `balance`.
- **API response:** When no restaurant has balance, the run-settlement-pipeline response includes `"message": "No restaurants had balance > 0. Check restaurant_balance_info ..."`.
- **Check settlements:** If the pipeline ran with balance, you should see rows in `institution_settlement` and then in `institution_bill_info`.  
  `SELECT * FROM institution_settlement ORDER BY created_at DESC LIMIT 5;`

### Balance exists but still no bills

If `restaurant_balance_info` has balance > 0 but the pipeline returns `settlements_created: 0` and no bills, **Phase 1** is skipping every entity. Common causes:

1. **Entity country not detected** — Phase 1 uses `MarketDetectionService.get_country_from_entity` (entity’s **address_id** → `address_info.country_code`). The entity must be created with an **address** (POST `/institution-entities` requires `address_id`). After creating an institution entity, the backend calls `update_address_type_from_linkages` so the address is marked as Entity Address/Entity Billing. Ensure "Register Supplier Entity" runs after "Register Supplier Address" and sends that address’s ID; the E2E collection asserts the response `address_id` matches. **Optional:** Call the pipeline with `?country_code=AR` so detection is not required if the entity’s address is missing or wrong.
2. **Bill date not a billable kitchen day** — Market config (e.g. AR/PE) only has Mon–Fri enabled. If `bill_date` is Saturday/Sunday, the code uses Friday for weekend; if the market has no Friday either, the entity is skipped. **Fix:** Use a weekday for `bill_date`, or set **DEV_OVERRIDE_DAY=Monday** on the server so the pipeline treats any date as Monday.
3. **National holiday** — For the entity’s country, `bill_date` is a holiday; the entity is skipped. Check `national_holidays` for that country.

The E2E collection step **Generate daily restaurant settlement (pipeline)** runs settlement and billing in one request and asserts: when `settlements_created > 0`, then `bills_created >= 1`.

## Removed / deprecated

- **Manual payment APIs** have been removed: `POST /institution-bills/{bill_id}/mark-paid` and `POST /institution-bills/{bill_id}/record-payment` are no longer available. All institution payment goes through the settlement → bill → payout pipeline.
- **Single-bill creation** (e.g. `POST /institution-bills/` with a restaurant or `create_bill_for_restaurant` / `generate_daily_bills`) has been removed. All bills are created only via the pipeline. `POST /institution-bills/generate-daily-bills` now calls the same pipeline as `run-settlement-pipeline`.
- **Bank-account-based payment** and the `institution_bank_account` table have been removed. Payout is Stripe-only (mock or live via `SUPPLIER_PAYOUT_PROVIDER`).
- **Cron** uses only the settlement → bill → payout pipeline: `run_daily_billing`, `run_kitchen_day_closure_billing`, and `run_monthly_billing` all call `run_daily_settlement_bill_and_payout`.

## Audit and reporting

- **Per restaurant:** `institution_settlement` rows (one per restaurant per period when balance > 0), with `settlement_number`, `settlement_run_id`, `institution_bill_id`.
- **Per entity:** One `institution_bill_info` per entity per run, with `tax_doc_external_id`. Payout details are in `billing.institution_bill_payout` (one row per attempt, linked via `institution_bill_id`).
- **Settlement report (minimal):**  
  - `InstitutionBillingService.get_settlement_report_by_run_id(settlement_run_id, connection)` — JSON payload by run (settlements list, by_entity summary, totals).  
  - `InstitutionBillingService.get_settlement_report_by_bill_id(institution_bill_id, connection)` — JSON payload for one bill (its settlement lines).

## Key code locations

- **Billing:** `app/services/billing/institution_billing.py` — Phase 1 (`run_phase1_settlements`), Phase 2 (`run_phase2_bills_and_payout`), pipeline (`run_daily_settlement_bill_and_payout`), report helpers.
- **Tax doc:** `app/services/billing/tax_doc_service.py` — `issue_tax_doc_for_bill` (stub).
- **Payout:** `app/services/payment_provider/stripe/connect_gateway.py` (live) and `connect_mock.py` (mock) — `execute_supplier_payout`. Provider selected by `SUPPLIER_PAYOUT_PROVIDER` setting.
- **Cron:** `app/services/cron/billing_events.py` — `multi_market_billing_entry(location_id)`, `run_billing_for_location(location_id)`, `run_daily_settlement_bill_and_payout`.
- **CRUD:** `app/services/crud_service.py` — `institution_settlement_service`, `get_settlements_by_run_id`, `get_settlements_by_entity_and_period`, `institution_bill_service` (create, update, mark_paid).

## Related docs

- [RESTAURANT_PAYMENT_FLOW_AND_APIS.md](RESTAURANT_PAYMENT_FLOW_AND_APIS.md) — Credit/currency model → balance → settlement → bill → Stripe payout; APIs; investigation of balance units vs `final_amount`.
- [CREDIT_AND_CURRENCY_CLIENT.md](../shared_client/CREDIT_AND_CURRENCY_CLIENT.md) — Credit values, plan pricing, vianda payouts.
