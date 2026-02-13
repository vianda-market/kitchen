# UUID7 Implementation Plan

## Executive Summary

**Recommendation**: ✅ **Full UUID7 for all tables**

We will **tear down and rebuild** the database (no in-place migration). All tables that use UUID primary keys will use **UUID7** for new row generation. This gives time-ordered, sortable IDs and allows simpler indexing and query patterns.

**PostgreSQL**: Use native `uuidv7()` on PostgreSQL 18+; on PostgreSQL &lt; 18 use the custom function in `app/db/uuid7_function.sql`.

---

## Scope: Tables to Update

The following tables are in the current schema and must use UUID7 for their UUID primary-key default. Any table added after this plan was written should also use UUID7.

### Tables using `uuid_generate_v4()` (replace with `uuidv7()`)

| Table | Primary Key Column | Notes |
|-------|--------------------|--------|
| institution_info | institution_id | |
| address_info | address_id | |
| address_history | event_id | |
| employer_info | employer_id | |
| employer_history | event_id | |
| user_info | user_id | |
| credit_currency_info | credit_currency_id | |
| credit_currency_history | event_id | |
| **market_info** | **market_id** | Added since original plan |
| **market_history** | **event_id** | Added since original plan |
| institution_history | event_id | |
| user_history | event_id | |
| credential_recovery | token | |
| geolocation_info | geolocation_id | |
| geolocation_history | event_id | |
| institution_entity_info | institution_entity_id | |
| institution_entity_history | event_id | |
| restaurant_info | restaurant_id | |
| restaurant_history | event_id | |
| qr_code | qr_code_id | |
| product_info | product_id | |
| product_history | event_id | |
| plate_info | plate_id | |
| restaurant_holidays | holiday_id | |
| restaurant_holidays_history | event_id | |
| plate_kitchen_days | plate_kitchen_day_id | |
| plate_kitchen_days_history | event_id | |
| plate_history | event_id | |
| plate_selection | plate_selection_id | |
| plate_pickup_live | plate_pickup_id | |
| pickup_preferences | preference_id | |
| plan_info | plan_id | |
| plan_history | event_id | |
| fintech_link_info | fintech_link_id | |
| fintech_link_history | event_id | |
| discretionary_info | discretionary_id | |
| discretionary_history | history_id | |
| discretionary_resolution_info | approval_id | |
| discretionary_resolution_history | history_id | |
| client_transaction | transaction_id | |
| subscription_info | subscription_id | |
| subscription_history | event_id | |
| payment_method | payment_method_id | |
| credit_card | credit_card_id | |
| bank_account | bank_account_id | |
| appstore_account | appstore_account_id | |
| fintech_link_assignment | fintech_link_assignment_id | |
| fintech_wallet | fintech_wallet_id | |
| fintech_wallet_auth | fintech_wallet_auth_id | |
| client_payment_attempt | payment_id | |
| client_bill_info | client_bill_id | |
| client_bill_history | event_id | |
| restaurant_transaction | transaction_id | |
| restaurant_balance_history | event_id | |
| institution_bill_info | institution_bill_id | |
| institution_bill_history | event_id | |
| institution_bank_account | bank_account_id | |
| institution_payment_attempt | payment_id | |

### Tables using `gen_random_uuid()` (replace with `uuidv7()`)

| Table | Primary Key Column | Notes |
|-------|--------------------|--------|
| national_holidays | holiday_id | |
| national_holidays_history | history_id | |

### Tables with no default (no change)

| Table | Primary Key Column | Reason |
|-------|--------------------|--------|
| restaurant_balance_info | restaurant_id | PK is FK from restaurant_info; no default. |

---

## Approach: Rebuild, Not Migration

- **Tear down** the database (or drop all objects) and **rebuild** from `schema.sql`, `index.sql`, `trigger.sql`, and seed (if any).
- **No** in-place data migration, no backfilling of existing rows.
- **Seed data**: If seed uses hardcoded UUIDs (e.g. for test data), those remain as-is; only **new** rows created after rebuild will get UUID7 from the default.

---

## PostgreSQL UUID7 Support

### Option A: PostgreSQL 18+

- Use **native** `uuidv7()`.
- No custom function; ensure `schema.sql` does not depend on `uuid-ossp` for UUID generation (we still need it for `uuid_generate_v4()` until we remove it; after switch, we can rely only on `uuidv7()`).

### Option B: PostgreSQL &lt; 18

- **Include** `app/db/uuid7_function.sql` in the build (creates `uuidv7()`).
- Run it **before** table creation in `schema.sql` (e.g. `\i app/db/uuid7_function.sql` or equivalent in your run order).
- See `app/db/uuid7_function.sql` for the implementation.

### Naming

- Use **`uuidv7()`** in schema so the same name works with PG18 native and the custom function.
- In PG18 docs the native function may be named `uuid_generate_v7()`; if so, we can add a compatibility wrapper or use the name that PG18 actually provides and document it here after verification.

---

## Schema Changes (Implementation Phase)

1. **UUID7 function**
   - If PG18+: rely on native `uuidv7()` (or `uuid_generate_v7()` — confirm name).
   - If PG &lt; 18: run `uuid7_function.sql` before creating tables.

2. **Replace defaults in `schema.sql`**
   - Replace every `DEFAULT uuid_generate_v4()` with `DEFAULT uuidv7()` (or the chosen name).
   - Replace every `DEFAULT gen_random_uuid()` with `DEFAULT uuidv7()`.

3. **Extension**
   - After full switch, we may be able to stop using `uuid-ossp` if no remaining references to `uuid_generate_v4()`. Leave as-is if other code still references it.

4. **Replace counts (for verification)**
   - In `schema.sql` as of Feb 2026: **58** occurrences of `DEFAULT uuid_generate_v4()` and **2** of `DEFAULT gen_random_uuid()`. All 60 must become `DEFAULT uuidv7()` (or the chosen PG18 function name).

---

## Index and Query Simplifications (Implementation Phase)

### Indexes that can be removed or simplified

- Indexes that exist only to order by `created_date` can often be removed or changed to order by the UUID7 primary key instead (time-ordered).
- **To be verified** in `app/db/index.sql`:
  - Any index on `(is_archived, created_date)` for time-ordering → consider `(is_archived, {id_column})`.
  - Archival indexes that use `created_date` → consider using the ID column for time-range queries.

### Query patterns

- **Default ordering**: Prefer `ORDER BY {id_column} DESC` instead of `ORDER BY created_date DESC` where time-ordering is the goal.
- **Archival**: Where we today use `created_date < cutoff`, we can use `{id_column} < uuid7_at(cutoff)` (with a small helper or DB function) so archival remains time-based.
- **Keep** `created_date` for display, audit, and reporting; use ID for sorting and time-range filters where beneficial.

---

## Application Code (Implementation Phase)

- **Validation**: API schemas should accept any valid UUID (e.g. standard `UUID` type in Pydantic), so that UUID7-generated IDs (and any remaining seed IDs) are accepted.
- **Ordering**: In `crud_service.py` and elsewhere, replace `ORDER BY created_date DESC` with `ORDER BY {id_column} DESC` where the intent is “newest first.”
- **Archival**: In `archival.py` (or equivalent), consider time-range by ID using a UUID7-from-timestamp helper if we add one; otherwise keep using `created_date` for cutoff until we introduce the helper.
- **New utility** (optional): `app/utils/uuid7.py` with `timestamp_from_uuid7()` and, if needed, `uuid7_from_timestamp()` for archival boundaries.

---

## Implementation Checklist (No Code Yet)

### Database (schema rebuild)

- [ ] Decide PostgreSQL version path: 18+ (native) vs &lt; 18 (custom `uuidv7()`).
- [ ] If PG &lt; 18: ensure `uuid7_function.sql` is run before table creation.
- [ ] In `schema.sql`: replace all `DEFAULT uuid_generate_v4()` with `DEFAULT uuidv7()` (or PG18 equivalent).
- [ ] In `schema.sql`: replace all `DEFAULT gen_random_uuid()` with `DEFAULT uuidv7()`.
- [ ] Review `index.sql`: remove or adjust indexes that only supported `created_date` ordering.
- [ ] Rebuild DB (tear down + run schema, index, trigger, seed).
- [ ] Verify: `SELECT uuidv7();` and insert into a table, confirm PK is UUID7 (version 7).

### Application code (after schema is done)

- [ ] Update default ordering in `crud_service.py` to use ID where appropriate.
- [ ] Update archival logic to use ID for time-ranges if we add a UUID7 timestamp helper; otherwise leave `created_date`-based cutoff.
- [ ] Add `app/utils/uuid7.py` if we need timestamp extraction or UUID7-from-timestamp for queries.
- [ ] Ensure all API schemas that accept UUIDs use a type that accepts UUID7 (e.g. `UUID`, not only `UUID4`).
- [ ] Run tests and Postman collections after rebuild.

### Documentation

- [ ] Update this plan with the exact PG18 function name once confirmed (`uuidv7()` vs `uuid_generate_v7()`).
- [ ] Note in `cursorrules.md` or README that the project uses UUID7 for new rows and rebuild (no migration).

---

## What We Keep

- **`created_date`** (and `modified_date`): Keep for display, audit, reporting. Do not remove; use for human-facing and compliance needs.
- **Seed data**: If seed uses fixed UUIDs for test data, leave them; only defaults for new rows change to UUID7.

---

## Benefits

- **Time-ordered IDs**: Sortable by creation time without a separate timestamp column for ordering.
- **Index efficiency**: Better insert locality, fewer page splits, smaller/faster indexes.
- **Simpler queries**: “Latest N” and pagination by ID; optional simplification of archival windows by ID.
- **Consistency**: All new tables and all existing tables (after rebuild) use the same UUID7 default.

---

## Risks and Notes

- **PostgreSQL version**: PG18+ gives native UUID7; older versions require the custom function and correct build order.
- **Time in IDs**: UUID7 encodes creation time; do not rely on it for security-sensitive ordering only (use `created_date` where audit matters).
- **Seed**: Rebuild will re-insert seed; ensure seed does not depend on v4-only validation in the app (we already accept any UUID in client_bill and similar).

---

**Last Updated**: February 2026  
**Status**: Plan approved; implementation to start after repo push. No code changes until then.
