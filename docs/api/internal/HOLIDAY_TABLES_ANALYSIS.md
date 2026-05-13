# Holiday tables: `national_holidays` vs `restaurant_holidays`

## Overview

Two separate tables: **national** (country-wide, often from Nager.Date import) and **restaurant** (per-restaurant closures). They are not merged; validation and enriched APIs can surface both.

**Rebuild-only**: schema changes are applied via `app/db/schema.sql` (tear down / rebuild). No row-level migration scripts.

---

## `national_holidays`

**Purpose**: Country-scoped holidays (vianda selection, billing skips, B2B CRUD).

**Key columns** (see `app/db/schema.sql` for full definition):

- `country_code` — ISO 3166-1 alpha-2, stored in `VARCHAR(3)` with `CHECK (length(country_code) = 2)`.
- `holiday_date`, `holiday_name`, `is_recurring`, `recurring_month`, `recurring_day`, `status`, `is_archived`, audit fields.
- **`source`**: `'manual' | 'nager_date'` (NOT NULL, default `'manual'`).

**DB rule (Nager rows are never “recurring”)**:

```sql
CHECK (
  source <> 'nager_date'
  OR (
    is_recurring = FALSE
    AND recurring_month IS NULL
    AND recurring_day IS NULL
  )
)
```

- **`nager_date`**: One concrete calendar row per `(country_code, holiday_date)` per year. Year coverage = **re-run sync**, not `is_recurring`.
- **`manual`**: Internal CRUD; may use `is_recurring` + `recurring_month` / `recurring_day` when the country is not in Nager or ops define an annual rule.

**Unique active row**: partial unique index on `(country_code, holiday_date) WHERE NOT is_archived`.

### Nager sync / re-sync (`app/services/cron/holiday_refresh.py`)

- Function **`_upsert_nager_holiday`**: `INSERT ... ON CONFLICT (country_code, holiday_date) WHERE NOT is_archived DO UPDATE SET holiday_name, modified_by, modified_date = NOW() WHERE national_holidays.source = 'nager_date'`.
- **Manual row wins**: if an active row for that date is `source = 'manual'`, the importer does not overwrite it (pre-check returns `skipped_manual`, or conflict update affects 0 rows).
- **Name refresh**: if the row is `nager_date`, re-sync updates `holiday_name` from the latest Nager payload.
- **`modified_by`**: cron uses **`SYSTEM_USER_ID`** (`bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb`), same as other system jobs; must exist in `user_info` seed.

**API hardening**: create / bulk / update request schemas do **not** allow clients to set `source = 'nager_date'`; routes set **`source = 'manual'`** on Internal writes. Sync is code-only.

---

## `restaurant_holidays`

**Purpose**: Closures for a single restaurant (supplier-scoped API).

**Key columns**:

- `restaurant_id`, `holiday_date`, `holiday_name` (NOT NULL).
- **`country_code`**: alpha-2, `VARCHAR(3)` with `CHECK (length(country_code) = 2)` — **server-derived** from `restaurant_info` → `address_info` (and optional name→code fallback), not sent as a free-form country name on create.
- `is_recurring`, `recurring_month`, `recurring_day` (nullable, 1–12 / 1–31 when set).
- **`source`**: `'manual' | 'national_sync'` (default `'manual'`). Clients must not set `national_sync` until a future auto-copy feature exists; routes hardcode **`manual`** on inserts.

**Partial unique index** (see `app/db/index.sql`): non-archived uniqueness on `(restaurant_id, holiday_date)`.

**Recurring index**: `idx_restaurant_holidays_recurring` on `(restaurant_id, recurring_month, recurring_day) WHERE is_recurring AND NOT is_archived`.

---

## History triggers

- **`national_holidays_history`**: includes **`source`**; trigger copies `NEW.source` on INSERT/UPDATE and `OLD.source` on DELETE.
- **`restaurant_holidays_history`**: mirrors main table including **`country_code`**, **`recurring_month` / `recurring_day`**, **`source`**.

---

## Application usage

| Area | National | Restaurant |
|------|----------|------------|
| Vianda selection / kitchen day helpers | `_is_date_national_holiday` in `vianda_selection_validation.py` (exact date + recurring month/day) | `_is_date_restaurant_holiday` (exact date + recurring **integers**) |
| Enriched list | `get_enriched_restaurant_holidays` in `entity_service.py` — national branch selects `recurring_month`, `recurring_day`, `source` | Restaurant branch selects `country_code`, `recurring_month`, `recurring_day`, `source` |
| B2B national CRUD | `app/routes/national_holidays.py` | — |
| Supplier restaurant CRUD | — | `app/routes/restaurant_holidays.py` |
| Nager import | `run_holiday_refresh`, cron in `billing_events.py` | — |

**Billing** (`crud_service.is_holiday`): exact `(country_code, holiday_date)` match on `national_holidays` only (no recurring branch in that helper).

---

## Client docs

- B2B national holidays: [API_CLIENT_NATIONAL_HOLIDAYS.md](../b2b_client/API_CLIENT_NATIONAL_HOLIDAYS.md) — sync summary includes **`updated`** vs **`inserted`** / **`skipped`**.
- Restaurant holiday API plan (historical phases + alignment notes): [RESTAURANT_HOLIDAY_API_PLAN.md](../../zArchive/roadmap/RESTAURANT_HOLIDAY_API_PLAN.md).

---

*Last updated: 2026-03-19*
