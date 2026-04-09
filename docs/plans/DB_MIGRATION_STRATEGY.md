# Database Migration Strategy: From Tear-Down to Incremental

**Status:** Planning
**Created:** 2026-04-09

---

## Problem Statement

Today every schema change requires a full tear-down and rebuild (`build_kitchen_db.sh`). This was fine during early development but now creates three compounding costs:

1. **Lost test data** -- every rebuild wipes manually-created test scenarios (users, subscriptions, orders, pickups) that took time to set up through the API.
2. **Blocked parallel work** -- developers cannot keep working while a rebuild is in progress; Postman collections that depend on specific UUIDs or states break.
3. **No path to staging** -- a `DROP SCHEMA CASCADE` strategy cannot be used on a staging environment that needs to hold realistic data for QA.

---

## Inventory: Pending Plans That Require Schema Changes

These plans from `docs/plans/` will each trigger a rebuild under the current model:

| # | Plan | Schema Impact | Complexity |
|---|------|---------------|------------|
| 1 | CUISINE_MANAGEMENT_ROADMAP | New `cuisine` + `cuisine_suggestion` tables; FK migration on `restaurant_info.cuisine` | High (FK change on existing column) |
| 2 | REFERRAL_SYSTEM_PLAN | New `referral_config`, `referral_info` tables; new columns on `user_info`; new enum `referral_status_enum` | Medium |
| 3 | STRUCTURED_INGREDIENTS_ROADMAP | New `ingredient_catalog`, `ingredient_alias`, `product_ingredient`, `ingredient_nutrition` tables; enum conversion on `product_info.dietary` | High (data migration on existing column) |
| 4 | RESTAURANT_VETTING_SYSTEM | New `restaurant_lead` table; new enum for qualification status | Low |
| 5 | VIANDA_EMPLOYER_BENEFITS_PROGRAM | New `employer_benefits_program`, `employer_bill`, `employer_bill_line`, `employer_domain` tables; 4 new enums | Medium |
| 6 | NOTIFICATION_BANNERS_PLAN | New `notification_banner` table; 3 new enums | Low |
| 7 | KIOSK_PICKUP_HANDOFF_DESIGN | Add value to `status_enum`; new boolean column on `restaurant_info` | Low |
| 8 | CONFIG_TO_DB_MIGRATION (Phase 9) | New `market_kitchen_config`, `location_info`, `enum_label`, `message_translation` tables | Medium |
| 9 | FREE_TRIAL_PLAN | Likely new trial config tables (design TBD) | TBD |
| 10 | GOOGLE_META_ADS_INTEGRATION_V2 | `ad_zone`, `ad_click_tracking` already in schema; may add campaign columns | Low |

**Key observation:** Most pending changes are **additive** (new tables, new columns, new enum values). Only two plans touch existing columns in ways that require data migration (#1 cuisine FK, #3 dietary enum conversion). This means the vast majority of future work can be handled with forward-only migration scripts.

---

## Strategy Overview

### Phase 1 -- Introduce Migration Scripts (keep rebuild as fallback)

**Goal:** New schema changes go through versioned SQL migration files. The rebuild script remains available but is no longer the default path.

#### 1.1 Migration file structure

```
app/db/
  migrations/
    0001_cuisine_tables.sql
    0002_referral_system.sql
    0003_kiosk_handoff_status.sql
    ...
  migrate.sh            # applies pending migrations
  build_kitchen_db.sh   # existing full rebuild (kept)
  schema.sql            # still the canonical DDL (updated after each migration)
```

Each migration file:
- Named `NNNN_short_description.sql` (zero-padded sequence number)
- Idempotent where possible (`CREATE TABLE IF NOT EXISTS`, `DO $$ ... END $$` guards for enum values)
- Contains both **up** logic (the change) and a comment block documenting what a **rollback** would look like (no automated down -- too risky at this stage)

#### 1.2 Migration tracking table

```sql
CREATE TABLE IF NOT EXISTS core.schema_migration (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum    TEXT NOT NULL  -- SHA-256 of the migration file
);
```

`migrate.sh` reads this table, compares against files in `migrations/`, and applies only what is missing (in order). If a checksum mismatch is detected on an already-applied migration, it aborts with an error.

#### 1.3 Keep schema.sql as the canonical DDL

After writing a migration, the developer also applies the same change to `schema.sql`. This means:
- `build_kitchen_db.sh` still works for a clean environment (new developer, CI, fresh staging)
- `schema.sql` remains the single-file source of truth for "what the DB looks like right now"
- Migrations are the source of truth for "how we got here"

**Rule:** `schema.sql` and `migrations/` must never contradict each other. The rebuild script will insert rows into `schema_migration` for all existing migrations so the two paths converge.

#### 1.4 Audit/trigger/index files

- `trigger.sql` and `index.sql` remain as-is. Migrations that add tables needing triggers/indexes will include those statements inline.
- After the migration is applied, the canonical `trigger.sql` / `index.sql` files are also updated (same dual-write pattern as `schema.sql`).

---

### Phase 2 -- Seed Data Strategy

#### 2.1 Split seed.sql

Current `seed.sql` mixes two concerns:
- **Reference data** (markets, countries, currencies, cuisines, enum labels) -- required in every environment
- **Dev fixtures** (test users, test restaurants, sample subscriptions) -- only useful in dev

Split into:

```
app/db/
  seed/
    reference_data.sql   # markets, countries, currencies, config rows
    dev_fixtures.sql     # test users, restaurants, sample orders
```

- `build_kitchen_db.sh` loads both (full dev reset)
- `migrate.sh` loads only `reference_data.sql` for new reference rows (via a dedicated migration when reference data changes)
- Staging and production never load `dev_fixtures.sql`

#### 2.2 Reference data migrations

When reference data changes (e.g., new market, new currency), create a migration that inserts/updates the specific rows. Also update `reference_data.sql` so a fresh build includes them.

---

### Phase 3 -- Dev-to-Staging Promotion

#### 3.1 The bad-data problem

Dev databases accumulate garbage: half-finished test entities, orphaned rows, invalid states. This data must **never** reach staging.

**Principle:** Staging is built from **code**, not from dev data.

Promotion path:

```
dev DB (messy)  -->  NOT copied to staging
                     
code (migrations + reference_data.sql)  -->  staging DB (clean)
```

#### 3.2 Staging environment setup

1. **First time:** Run `build_kitchen_db.sh` with only `reference_data.sql` (no dev fixtures). This gives a clean schema with all reference data.
2. **Subsequent deploys:** Run `migrate.sh`. Only pending migrations are applied. Reference data inserts in migrations use `ON CONFLICT DO NOTHING` or `INSERT ... WHERE NOT EXISTS` to be idempotent.
3. **Test data for QA:** A separate `staging_fixtures.sql` (optional) with curated, realistic test data. This is version-controlled and reviewed. Unlike dev fixtures, staging fixtures represent valid, complete business scenarios.

#### 3.3 Environment flag

`migrate.sh` accepts an `ENV` variable:

| ENV | Behavior |
|-----|----------|
| `dev` (default) | Apply migrations + reference data. Dev fixtures loaded on full rebuild only. |
| `staging` | Apply migrations + reference data + optional staging fixtures. Never loads dev fixtures. |
| `production` | Apply migrations + reference data only. Fails if any migration is destructive (DROP, ALTER COLUMN TYPE). |

---

### Phase 4 -- Adjust CLAUDE.md and Developer Workflow

#### 4.1 Update CLAUDE.md rules

Current rule:
> Never run or write migrations -- tear down and rebuild: `bash app/db/build_kitchen_db.sh`

New rule:
> **Schema changes:** Write a migration in `app/db/migrations/` and update `schema.sql` to match. Apply with `bash app/db/migrate.sh`. Full rebuild (`build_kitchen_db.sh`) is for fresh environments only -- never use it to apply incremental changes on a database with test data you want to keep.

#### 4.2 DB Schema Change checklist update

Current: `schema.sql -> trigger.sql -> seed.sql -> models.py -> schemas.py`

New: `migration file -> schema.sql -> trigger.sql -> seed/reference_data.sql (if needed) -> models.py -> schemas.py`

#### 4.3 When full rebuild is still appropriate

- Setting up a new developer machine
- CI pipeline (always starts clean)
- Schema has diverged too far from migrations (recovery scenario)
- Developer explicitly wants a fresh start

---

## Implementation Order

### Batch 1: Foundation (do this first, before any pending plan)

1. Create `core.schema_migration` table (add to `schema.sql`)
2. Write `migrate.sh` script
3. Split `seed.sql` into `reference_data.sql` + `dev_fixtures.sql`
4. Update `build_kitchen_db.sh` to load split seed files and populate `schema_migration` with a baseline version
5. Update `CLAUDE.md` with new rules
6. Update `DATABASE_REBUILD_PERSISTENCE.md`

### Batch 2: First migration (validate the system)

Pick the simplest pending schema change as the pilot:

**Recommended pilot:** NOTIFICATION_BANNERS_PLAN (new table + enums, no existing-column changes, low risk)

1. Write `0001_notification_banners.sql`
2. Apply with `migrate.sh` on dev (no rebuild)
3. Verify data survives, test via Postman
4. Update `schema.sql` to match
5. Run `build_kitchen_db.sh` on a separate test DB to verify convergence

### Batch 3: Remaining plans (incremental)

Apply remaining plans as migrations in priority order. The two high-complexity plans (cuisine FK migration, ingredient dietary conversion) should be written with extra care:

- Cuisine FK: migration adds the new tables first, then a second migration converts the column (ALTER COLUMN + data backfill)
- Ingredient dietary: same two-step pattern (add new structure, then migrate existing data)

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Migration and schema.sql drift apart | CI check: rebuild from schema.sql on a test DB, then verify `schema_migration` table matches migration count |
| Destructive migration applied to staging/prod | `migrate.sh` in `production` mode rejects DROP/ALTER TYPE statements; manual override required |
| Migration fails mid-way, leaves DB in partial state | Each migration runs inside a transaction (`BEGIN; ... COMMIT;`). PostgreSQL DDL is transactional. |
| Developer forgets to write migration (edits schema.sql directly) | CI check: diff schema.sql against last known state; if changed without a corresponding migration file, fail the build |
| Bad dev data leaks to staging | Staging is never populated from dev. Only code-defined data (migrations + reference_data.sql) reaches staging. |

---

## What This Does NOT Change

- **PostgreSQL enums** are still used (not replaced with lookup tables). Adding a value to an enum is a one-line migration: `ALTER TYPE x ADD VALUE 'y';`
- **Audit/history tables** still mirror main tables via triggers. Migrations that add columns must also update the history table and trigger (same rule as today).
- **DTOs and schemas** still need manual sync (migration does not auto-generate Python code).
- **Postman testing** remains the integration test strategy for services/routes.
- **Archival system** continues as-is; archival indexes are part of schema.sql.

---

## Success Criteria

1. A developer can apply a schema change without losing existing test data
2. Staging can be set up from scratch or incrementally updated, with no dev garbage
3. `build_kitchen_db.sh` still works as a complete reset when needed
4. CI validates that schema.sql and migrations are in sync
5. The first three pending plans (notification banners, kiosk handoff, referral system) ship as migrations without a full rebuild
