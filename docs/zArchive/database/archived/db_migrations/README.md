# Archived: Database Migrations

**Archived**: 2026-03-14

These migrations were used for incremental schema updates on existing databases. They are now **archived** because:

1. **Fresh builds**: `schema.sql` already includes all migration changes (province_code, created_by, place_id, viewport, formatted_address_google, chk_plan_info_not_global_market). For local, cloud, and new environments, the schema is torn down and rebuilt—migrations are not run.

2. **Prod migration strategy**: When you design a DB migration strategy for production (where tear-down is not an option), reference these files as examples of incremental ALTER patterns. You may need to adapt them for your migration tooling (e.g., version tracking, rollback).

## Contents

| File | Purpose |
|------|---------|
| `uuid7_function.sql` | Custom uuidv7() for PostgreSQL &lt; 18 (PG 18+ has built-in). Run before schema if on PG 14–17. |
| `001_forbid_plans_global_marketplace.sql` | Archive invalid plans, add CHECK constraint |
| `002_add_province_to_city.sql` | Add province_code to city_info |
| `003_add_created_by_audit_trail.sql` | Add created_by to audit tables |
| `004_add_geolocation_google_fields.sql` | Add place_id, viewport, formatted_address_google to geolocation |

**Build order**: Schema is now idempotent (DROP + CREATE IF NOT EXISTS). No migrations in normal build flow. PostgreSQL 18+ provides `uuidv7()` natively.
