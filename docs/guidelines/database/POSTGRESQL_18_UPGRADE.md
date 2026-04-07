# PostgreSQL 18 Upgrade Guide

## Overview

This codebase uses `uuidv7()` for time-ordered primary keys throughout the schema and triggers. On PostgreSQL 18+, `uuidv7()` is built-in. On PostgreSQL 14–17, the custom `docs/archived/db_migrations/uuid7_function.sql` must be run before the schema. The build script assumes PostgreSQL 18+.

## Current Status

- **Current PostgreSQL Version**: 14.17 (Homebrew)
- **Target Version**: PostgreSQL 18+
- **Native UUIDv7 Support**: Built-in in PostgreSQL 18+
- **Platform**: This guide is for macOS with Homebrew (Apple Silicon: `/opt/homebrew/`; Intel: paths may differ)

## Upgrade Steps (macOS with Homebrew)

### 1. Backup Your Database

```bash
# Backup your current database
pg_dump -U cdeachaval -h localhost kitchen > backup_$(date +%Y%m%d).sql
```

### 2. Install PostgreSQL 18

```bash
# Install PostgreSQL 18 via Homebrew
brew install postgresql@18

# Link the new version
brew link postgresql@18

# Start PostgreSQL 18 service
brew services start postgresql@18
```

### 3. Verify Installation

```bash
# Check PostgreSQL version
psql --version

# Should show: psql (PostgreSQL) 18.x
```

### 4. Upgrade Database Cluster (if migrating data)

If you need to migrate existing data, use `pg_upgrade`:

```bash
# Stop both PostgreSQL services
brew services stop postgresql@14
brew services stop postgresql@18

# Run pg_upgrade (adjust paths for your system: Apple Silicon uses /opt/homebrew/, Intel may use /usr/local/)
pg_upgrade \
  -b /opt/homebrew/opt/postgresql@14/bin \
  -B /opt/homebrew/opt/postgresql@18/bin \
  -d /opt/homebrew/var/postgresql@14 \
  -D /opt/homebrew/var/postgresql@18

# Start PostgreSQL 18
brew services start postgresql@18
```

**Note**: For development databases that are frequently rebuilt, you can skip `pg_upgrade` and just recreate the database with the new schema.

**If you used `pg_upgrade`**: The custom `uuidv7()` function from PostgreSQL 14 will be migrated. You can optionally drop it to use the native PG 18 function: `DROP FUNCTION IF EXISTS uuidv7() CASCADE;` — the native `uuidv7()` will then be used. This is optional; the migrated custom function will work.

### 5. Recreate Database (Recommended for Development)

Since this is a development database that gets rebuilt frequently, you can simply:

```bash
# Drop and recreate the database
dropdb -U cdeachaval -h localhost kitchen
createdb -U cdeachaval -h localhost kitchen

# Rebuild schema (this will work with PostgreSQL 18+)
./app/db/build_kitchen_db.sh
```

### 6. Using Native UUIDv7 Function

After upgrading to PostgreSQL 18+, you can use the native `uuidv7()` function:

```sql
-- Generate UUIDv7 (time-ordered UUID)
SELECT uuidv7();

-- Use in table defaults
CREATE TABLE example_table (
    id UUID PRIMARY KEY DEFAULT uuidv7(),
    ...
);
```

## Code Changes Made

1. ✅ Build script assumes PostgreSQL 18+ (no uuid7_function in normal flow)
2. ✅ `uuid7_function.sql` archived to `docs/archived/db_migrations/`; run it manually before `schema.sql` if on PG 14–17
3. ✅ Added comment in `schema.sql` noting PostgreSQL 18+ native support

## Notes

- **Current Usage**: The schema and triggers use `uuidv7()` everywhere for primary keys and history events (e.g. `DEFAULT uuidv7()`). On PostgreSQL 14–17 this comes from `docs/archived/db_migrations/uuid7_function.sql`; on PostgreSQL 18+ it is built-in.
- **PostgreSQL 14–17**: The build script expects `uuidv7()` to exist. Add `\i docs/archived/db_migrations/uuid7_function.sql` after `CREATE SCHEMA public;` and before `\i app/db/schema.sql`. Or run on PG 18+ where `uuidv7()` is built-in.
- **PostgreSQL 18+**: No custom function needed; `uuidv7()` is native. The build script works as-is.

## Verification

After upgrade, verify PostgreSQL 18 is working:

```bash
# Connect to database
psql -U cdeachaval -h localhost -d kitchen

# Test native uuidv7() function (PostgreSQL 18+ only)
SELECT uuidv7();

# Should return a UUIDv7 value
```

## Rollback

If you need to rollback to PostgreSQL 14:

```bash
# Switch back to PostgreSQL 14
brew services stop postgresql@18
brew unlink postgresql@18
brew link postgresql@14
brew services start postgresql@14
```

The custom `uuid7_function.sql` file is archived at `docs/archived/db_migrations/uuid7_function.sql`. Run it before `schema.sql` when using PostgreSQL 14–17:
`psql -U cdeachaval -h localhost -d kitchen -f docs/archived/db_migrations/uuid7_function.sql`

