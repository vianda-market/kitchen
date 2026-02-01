# PostgreSQL 18 Upgrade Guide

## Overview

This codebase has been updated to support PostgreSQL 18+, which includes native `uuidv7()` function support. The custom `uuid7_function.sql` has been removed.

## Current Status

- **Current PostgreSQL Version**: 14.17 (Homebrew)
- **Target Version**: PostgreSQL 18+
- **Native UUIDv7 Support**: Available in PostgreSQL 18+

## Upgrade Steps (macOS with Homebrew)

### 1. Backup Your Database

```bash
# Backup your current database
pg_dump -U cdeachaval -h localhost kitchen_db_dev > backup_$(date +%Y%m%d).sql
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

# Run pg_upgrade (adjust paths as needed)
pg_upgrade \
  -b /opt/homebrew/opt/postgresql@14/bin \
  -B /opt/homebrew/opt/postgresql@18/bin \
  -d /opt/homebrew/var/postgresql@14 \
  -D /opt/homebrew/var/postgresql@18

# Start PostgreSQL 18
brew services start postgresql@18
```

**Note**: For development databases that are frequently rebuilt, you can skip `pg_upgrade` and just recreate the database with the new schema.

### 5. Recreate Database (Recommended for Development)

Since this is a development database that gets rebuilt frequently, you can simply:

```bash
# Drop and recreate the database
dropdb -U cdeachaval -h localhost kitchen_db_dev
createdb -U cdeachaval -h localhost kitchen_db_dev

# Rebuild schema (this will work with PostgreSQL 18+)
./app/db/build_kitchen_db_dev.sh
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

1. ✅ Removed `\i app/db/uuid7_function.sql` from `schema.sql`
2. ✅ Custom `uuid7_function.sql` file is no longer included in build
3. ✅ Added comment in `schema.sql` noting PostgreSQL 18+ native support

## Notes

- **Current Usage**: The codebase currently uses `uuid_generate_v4()` from `uuid-ossp` extension, not UUIDv7
- **Future Usage**: If you want to use UUIDv7 in the future, use the native `uuidv7()` function in PostgreSQL 18+
- **No Breaking Changes**: Since UUIDv7 wasn't being used, removing the custom function has no impact on current functionality

## Verification

After upgrade, verify PostgreSQL 18 is working:

```bash
# Connect to database
psql -U cdeachaval -h localhost -d kitchen_db_dev

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

You would need to restore the custom `uuid7_function.sql` if you need UUIDv7 support on PostgreSQL 14.

