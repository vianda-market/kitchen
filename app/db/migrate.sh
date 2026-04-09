#!/usr/bin/env bash
# Apply pending SQL migrations to an existing Kitchen database.
#
# Usage (from repository root):
#   bash app/db/migrate.sh
#
# Environment (same as build_kitchen_db.sh):
#   DB_HOST      default: localhost
#   DB_PORT      default: 5432
#   DB_NAME      default: kitchen
#   DB_USER      default: cdeachaval
#   PGPASSWORD   set when the DB user requires a password
#   DB_SSLMODE   optional; non-local DB_HOST defaults to require
#   ENV          dev (default) | staging | production
#
# Migrations live in app/db/migrations/ as NNNN_short_description.sql files.
# Each migration runs inside a transaction. Only migrations not yet recorded
# in core.schema_migration are applied.
#
set -euo pipefail

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-kitchen}"
DB_USER="${DB_USER:-cdeachaval}"
ENV="${ENV:-dev}"

# SSL handling (same logic as build_kitchen_db.sh)
if [ -n "${DB_SSLMODE:-}" ]; then
  export PGSSLMODE="${DB_SSLMODE}"
else
  case "${DB_HOST}" in
    localhost|127.0.0.1|::1)
      export PGSSLMODE="${PGSSLMODE:-prefer}"
      ;;
    *)
      export PGSSLMODE="${PGSSLMODE:-require}"
      ;;
  esac
fi

PSQL="psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -X -v ON_ERROR_STOP=1"

MIGRATIONS_DIR="app/db/migrations"

# -------------------------------------------------------------------------
# Ensure schema_migration table exists (safe for first run on older DBs)
# -------------------------------------------------------------------------
${PSQL} -q <<'SQL'
CREATE TABLE IF NOT EXISTS core.schema_migration (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum    TEXT NOT NULL
);
SQL

# -------------------------------------------------------------------------
# Collect migration files sorted by version number
# -------------------------------------------------------------------------
shopt -s nullglob
MIGRATION_FILES=("${MIGRATIONS_DIR}"/[0-9][0-9][0-9][0-9]_*.sql)
shopt -u nullglob

if [ ${#MIGRATION_FILES[@]} -eq 0 ]; then
  echo "No migration files found in ${MIGRATIONS_DIR}/. Nothing to do."
  exit 0
fi

# -------------------------------------------------------------------------
# Get already-applied versions and checksums (one "version|checksum" per line)
# -------------------------------------------------------------------------
APPLIED_FILE=$(mktemp)
${PSQL} -t -A -F'|' -c "SELECT version, checksum FROM core.schema_migration ORDER BY version;" > "${APPLIED_FILE}"

# -------------------------------------------------------------------------
# Apply pending migrations
# -------------------------------------------------------------------------
APPLIED_COUNT=0

for filepath in "${MIGRATION_FILES[@]}"; do
  filename=$(basename "${filepath}")
  # Extract version number (first 4 digits)
  version_str="${filename%%_*}"
  version=$((10#${version_str}))  # strip leading zeros
  name="${filename%.sql}"

  # Compute checksum
  checksum=$(shasum -a 256 "${filepath}" | awk '{print $1}')

  # Already applied? Look up version in the applied file
  existing_line=$(grep "^${version}|" "${APPLIED_FILE}" || true)
  if [ -n "${existing_line}" ]; then
    existing_checksum="${existing_line#*|}"
    if [ "${existing_checksum}" != "${checksum}" ]; then
      echo "ERROR: Migration ${filename} has been modified after it was applied."
      echo "  Expected checksum: ${existing_checksum}"
      echo "  Current checksum:  ${checksum}"
      echo "  Aborting. Do NOT edit already-applied migrations."
      rm -f "${APPLIED_FILE}"
      exit 1
    fi
    continue  # already applied, checksum matches
  fi

  # Production safety: reject destructive statements
  if [ "${ENV}" = "production" ]; then
    if grep -qiE '^\s*(DROP\s+TABLE|DROP\s+SCHEMA|ALTER\s+.*\s+TYPE|TRUNCATE)' "${filepath}"; then
      echo "ERROR: Migration ${filename} contains destructive statements."
      echo "  ENV=production blocks DROP TABLE, DROP SCHEMA, ALTER ... TYPE, and TRUNCATE."
      echo "  To override, apply manually."
      exit 1
    fi
  fi

  echo "Applying migration ${filename}..."

  # Run migration inside a transaction (PostgreSQL DDL is transactional)
  ${PSQL} -q <<EOSQL
BEGIN;
\i ${filepath}
INSERT INTO core.schema_migration (version, name, applied_at, checksum)
VALUES (${version}, '${name}', now(), '${checksum}');
COMMIT;
EOSQL

  APPLIED_COUNT=$((APPLIED_COUNT + 1))
  echo "  Applied."
done

rm -f "${APPLIED_FILE}"

if [ ${APPLIED_COUNT} -eq 0 ]; then
  echo "All migrations already applied. Nothing to do."
else
  echo "Applied ${APPLIED_COUNT} migration(s) successfully."
fi
