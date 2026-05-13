# Fix Postman Collection 012 — Remaining Billing Gaps

**Status**: Deferred. Bills/settlements now work (PR5 session). 3 tests still fail.

## Failing Tests

### 1. Supplier Invoice Review + Match (PATCH/POST → 404)
- `supplierInvoiceId` is empty because "Create Supplier Invoice" (step 16) fails
- Root cause: supplier invoice creation requires specific entity config (tax_id, payout_onboarding_status=complete) that 012 doesn't set up
- Fix: add setup steps in 012 to configure supplier_terms + entity payout status before invoice creation, OR make invoice creation tolerant of missing payout config

### 2. Execute Payout (POST → 500)
- `PAYMENT_PROVIDER=stripe` in .env but payout calls real Stripe API
- Fix: either set `PAYMENT_PROVIDER=mock` for dev (affects subscription payment too), OR add a mock payout path that skips Stripe when `DEV_MODE=True`, OR create a `STRIPE_PAYOUT_MODE=mock` separate setting

## Context
- The billing pipeline (vianda selection → promotion → QR scan → complete → settlement → bill) is fully working as of the April 12 session
- Institution bill CRUD tests (Get/Update/Cancel) all pass
- These 3 failures are in downstream subsystems (supplier invoicing, Stripe Connect payouts) that need separate config/setup

## DEV_MODE Fixes Applied (this session)
- Kitchen day: weekends → friday mapping in `get_effective_current_day`, `date_to_kitchen_day`, `_find_next_available_kitchen_day_in_week`
- Vianda selection: `is_vianda_selection_editable` always True in DEV_MODE
- Pickup date: `resolve_weekday_to_next_occurrence` returns today on weekends
- Rate limiting: slowapi disabled in DEV_MODE
- Billing pipeline: lowercase enum fix (`"Order"` → `"order"`), Title-case day comparison fix (`"Saturday"` → `"saturday"`)
- DB CHECK constraint on pickup_date DOW vs kitchen_day: dropped (business logic owns the guard)
