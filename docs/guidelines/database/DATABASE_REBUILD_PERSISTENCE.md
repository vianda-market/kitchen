# Database Persistence & Migration Guide

## **Two Paths: Migrate vs Rebuild**

| Path | Command | When to use |
|------|---------|-------------|
| **Migrate** | `bash app/db/migrate.sh` | Incremental schema changes — preserves existing data |
| **Rebuild** | `bash app/db/build_kitchen_db.sh` | New dev machine, CI, or intentional clean reset |

**Default to migrate.** Only rebuild when you need a fresh start.

## **Key Principle: All Changes Must Be in Repository Files**

Schema changes are made via **migration files** (`app/db/migrations/NNNN_description.sql`), then also applied to `schema.sql` so both paths stay in sync.

## **Database Structure Files**
```
app/db/
├── schema.sql                      Canonical DDL (updated after each migration)
├── index.sql                       Standard indexes
├── trigger.sql                     History triggers
├── archival_config_table.sql       Archival config table
├── archival_indexes.sql            15 archival performance indexes
├── migrate.sh                      Apply pending migrations (incremental)
├── build_kitchen_db.sh             Full tear-down and rebuild
├── post_rebuild_external_sync.py   Post-seed FX + holiday sync
├── seed.sql                        Shim that loads both seed files below
├── seed/
│   ├── reference_data.sql          Markets, currencies, system users, cuisines (all envs)
│   └── dev_fixtures.sql            Test data (dev only — never loaded in staging/production)
└── migrations/
    └── NNNN_description.sql        Versioned migration files (applied by migrate.sh)
```

### **2. Application Code Files**
```
app/
├── services/
│   ├── archival.py             ✅ Archival logic (uses archival_config)
│   └── cron/archival_job.py     ✅ Scheduled archival jobs
├── routes/admin/
│   ├── archival.py             ✅ Admin archival endpoints
│   └── archival_config.py      ✅ Archival config endpoints
├── config/
│   ├── archival_config.py      ✅ Table→category mapping, retention (source of truth)
│   └── settings.py             ✅ RETENTION_PERIODS (legacy/UI)
└── utils/log.py                ✅ Logging
```

### **3. Documentation Files**
```
docs/
├── archival/
│   ├── ARCHIVAL_STRATEGY.md              Strategic framework
│   ├── ARCHIVAL_SYSTEM_IMPLEMENTATION.md Technical details
│   ├── ARCHIVAL_ENHANCEMENT_SUMMARY.md   Completion summary
│   └── ARCHIVAL_CRON_STRATEGY.md         Cron job strategy
├── api/internal/
│   └── LOGGING_STRATEGY.md               Logging analysis
└── database/
    └── DATABASE_REBUILD_PERSISTENCE.md   This file
```

## **Build Process Integration**

### **Incremental Migrations (preferred)**

```bash
bash app/db/migrate.sh
```

Applies only pending migrations from `app/db/migrations/`. Each migration runs in a transaction. Applied versions are tracked in `core.schema_migration`.

Environment modes (`ENV` variable):
- `dev` (default) — applies all migrations
- `staging` — applies all migrations; rejects none (staging gets same schema as dev)
- `production` — blocks destructive statements (DROP TABLE, TRUNCATE, ALTER TYPE)

### **Full Rebuild (clean slate)**

```bash
bash app/db/build_kitchen_db.sh
```

Loads, in order:
```
DROP all schemas CASCADE → schema.sql → index.sql → trigger.sql →
archival_config_table.sql → archival_indexes.sql → seed/reference_data.sql
→ seed/dev_fixtures.sql (dev only) → baseline schema_migration rows
```

The rebuild script accepts `ENV=staging` to skip dev fixtures.

Set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `PGPASSWORD` for non-local targets (e.g. Cloud SQL). For CI/GCP without a venv or static assets, use `SKIP_PYTEST=1` and `SKIP_IMAGE_CLEANUP=1` (see comments in the script). Air-gapped CI or no outbound HTTP: set `SKIP_POST_REBUILD_SYNC=1` to skip FX and holiday API calls after the final seed.

### **Post-rebuild external sync (FX + national holidays)**

After the **final** `seed.sql` pass, `build_kitchen_db.sh` runs `app/db/post_rebuild_external_sync.py` (when a venv exists and `SKIP_POST_REBUILD_SYNC` is unset). This step:

- Updates `credit_currency_info.currency_conversion_usd` from **open.er-api.com** (non-USD rows; seed placeholders are `1.0` until then).
- Inserts **national_holidays** from **date.nager.at** (Nager.Date) for market countries in app config.

**Safety:** The script always exits successfully so a failed or blocked network does not abort the rebuild. It performs a short connectivity check per host before calling each API (avoids long timeouts when firewalled). Log lines are prefixed with `[post-rebuild-sync]` for grepping build logs.

**Env:** If you use `PGPASSWORD` for `psql` but not `DB_PASSWORD`, the script copies `PGPASSWORD` to `DB_PASSWORD` so `psycopg2` matches the same database.

**Manual run** (from repository root): `PYTHONPATH=. python app/db/post_rebuild_external_sync.py` — `PYTHONPATH=.` is required so `from app....` imports resolve.

You can instead run the same SQL files with `psql -f` (also from repo root); add `-v ON_ERROR_STOP=1`. The script’s initial `DROP SCHEMA public CASCADE` gives a clean slate; the raw `-f` chain does not unless you run that separately.

### **What Happens on Rebuild**
1. ✅ **Schema**: All tables created (enums stored on entities, no status_info/transaction_type_info)
2. ✅ **Indexes**: Standard indexes + 15 archival performance indexes
3. ✅ **Triggers**: History logging triggers
4. ✅ **Data**: Reference data from seed.sql
5. ✅ **Tests**: Pytest runs database integration tests
6. ✅ **Post-rebuild sync**: Optional FX + holiday fetch (see subsection above; skipped if no venv or `SKIP_POST_REBUILD_SYNC=1`)

### **IAM admin grants (`schema.sql` tail)**

`app/db/schema.sql` ends with a conditional block that grants full access on `public` tables, sequences, and functions to the Cloud SQL IAM role `viandallc@gmail.com` when that role exists in the cluster (so local rebuilds without that role skip it with no error).

**Note:** `ALTER DEFAULT PRIVILEGES` only applies to objects created later **by the role that executes** those `ALTER DEFAULT PRIVILEGES` statements (often your migration/schema superuser). That matches the usual “admin user gets defaults from the account that builds the schema” pattern; if you ever need defaults for objects created by a different role, that would need a separate `ALTER DEFAULT PRIVILEGES FOR ROLE ...`.

## **🚨 Critical Changes Made Persistent**

### **1. Archival Performance Indexes (15 total)**
```sql
-- Orders (plate_pickup_live)
idx_plate_pickup_archival, idx_plate_pickup_archival_eligible

-- Transactions (restaurant_transaction)
idx_restaurant_transaction_archival, idx_restaurant_transaction_archival_eligible

-- Client transactions
idx_client_transaction_archival, idx_client_transaction_archival_eligible

-- Subscriptions, User, Restaurant
idx_subscription_archival, idx_subscription_archival_eligible
idx_user_archival, idx_user_archival_eligible
idx_restaurant_archival, idx_restaurant_archival_eligible

-- Statistics
idx_plate_pickup_stats, idx_restaurant_transaction_stats, idx_client_transaction_stats
```

### **2. Archival Configuration**
Archival is configured in `app/config/archival_config.py` via `TABLE_CATEGORY_MAPPING` and `ArchivalCategory`. Tables are assigned retention periods by category (e.g. FINANCIAL_CRITICAL, CUSTOMER_SERVICE). Retention periods and grace periods are defined in `CATEGORY_SLA_CONFIG`.

### **3. Reference Data**
Status and transaction-type values are stored as PostgreSQL enums on entities (e.g. `status_enum`, `transaction_type_enum` in schema.sql). No separate status_info or transaction_type_info tables.

## **🔍 Validation After Rebuild**

### **Quick Verification Commands**
```bash
# 1. Verify archival indexes exist
psql -d kitchen -c "
SELECT count(*) FROM pg_indexes 
WHERE indexname LIKE '%archival%' OR indexname LIKE '%stats%';"
# Expected: 15

# 2. Verify core tables exist
psql -d kitchen -c "
SELECT table_name FROM information_schema.tables 
WHERE table_name IN ('user_info', 'plate_pickup_live', 'client_transaction', 'restaurant_info');"
# Expected: 4 rows

# 3. Run database tests
source venv/bin/activate && pytest app/tests/database/ -v --tb=short
```

### **Application Verification**
```python
# Test archival config loads
from app.config.archival_config import get_archival_priority_order, get_table_archival_config

tables = get_archival_priority_order()
print(f"Archival config: {len(tables)} tables")

# Verify a table has config
config = get_table_archival_config("plate_pickup_live")
assert config.retention_days > 0
```

## **Things to Never Do**

- **Never apply DDL directly** — changes will be lost on rebuild. Always use a migration file.
- **Never edit an already-applied migration** — write a new one instead.
- **Never use `build_kitchen_db.sh` to apply incremental changes** — use `migrate.sh` to preserve test data.
- **Never insert reference data only in `dev_fixtures.sql`** — reference data belongs in `reference_data.sql` (and a migration for existing DBs).

## **🎯 Rebuild Test Checklist**

After any database rebuild, verify:

- [ ] **15 archival indexes** created
- [ ] **Core tables** exist (user_info, plate_pickup_live, client_transaction, etc.)
- [ ] **Database tests** pass: `pytest app/tests/database/`
- [ ] **Archival config** loads: `get_archival_priority_order()` returns tables
- [ ] **Admin endpoints** accessible at `/admin/archival/*` and `/admin/archival-config/*`

## **Adding Schema Changes**

When adding new features that require database changes:

1. **Write a migration** → `app/db/migrations/NNNN_description.sql` (next sequence number)
2. **Update schema.sql** → Apply the same DDL change so a fresh rebuild produces the same result
3. **New indexes** → Include in the migration; also add to `app/db/index.sql` or `app/db/archival_indexes.sql`
4. **New triggers** → Include in the migration; also add to `app/db/trigger.sql`
5. **Reference data** → Include INSERT in the migration (with `ON CONFLICT DO NOTHING`); also add to `app/db/seed/reference_data.sql`
6. **New entity archival** → Add table to `TABLE_CATEGORY_MAPPING` in `app/config/archival_config.py`

**Dual-write rule:** Migration files and `schema.sql` must never contradict each other. The migration is the source of truth for "how we got here"; `schema.sql` is the source of truth for "what the DB looks like now."

**Never edit an already-applied migration.** If you need to fix something, write a new migration.

---

## **Current Status**

All archival system changes persist across rebuilds. Migration system is in place for incremental schema changes.

- **15 archival indexes** in `app/db/archival_indexes.sql`
- **Category-based retention** via `app/config/archival_config.py`
- **Admin endpoints** at `/admin/archival/*` and `/admin/archival-config/*`
- **Migration tracking** via `core.schema_migration` table
- **Seed data split** into `reference_data.sql` (all envs) + `dev_fixtures.sql` (dev only)