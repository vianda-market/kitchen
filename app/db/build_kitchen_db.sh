#!/usr/bin/env bash
# Rebuild Kitchen PostgreSQL schema + seed from repo SQL files.
#
# Usage (from repository root — required so \i app/db/... paths resolve):
#   ./app/db/build_kitchen_db.sh
#
# Environment (optional; defaults suit local macOS dev):
#   DB_HOST      default: localhost
#   DB_PORT      default: 5432
#   DB_NAME      default: kitchen
#   DB_USER      default: cdeachaval
#   PGPASSWORD   set when the DB user requires a password (e.g. GCP / kitchen_app)
#   DB_SSLMODE   optional; non-local DB_HOST defaults to require (Cloud SQL TLS).
#                For local Postgres without SSL, use DB_SSLMODE=prefer or disable.
#
# GCP / CI toggles:
#   SKIP_IMAGE_CLEANUP=1     Skip clearing static/qr_codes and static/product_images
#   SKIP_PYTEST=1            Skip app/tests/database/ pytest after load
#   SKIP_RESEED=1            Skip final seed.sql pass (not recommended for local app)
#   SKIP_POST_REBUILD_SYNC=1 Skip FX + national holiday sync (open.er-api.com, date.nager.at)
#
# Post-rebuild sync runs: python app/db/post_rebuild_external_sync.py
#   Requires repository root on PYTHONPATH (the script sets PYTHONPATH=. when invoked from here).
#   Manual run from repo root: PYTHONPATH=. python app/db/post_rebuild_external_sync.py
#
# Equivalent manual load (also from repo root; does not drop public schema first):
#   export PGSSLMODE=require   # Cloud SQL public IP; omit or prefer for local only
#   PGPASSWORD=... psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
#     -v ON_ERROR_STOP=1 \
#     -f app/db/schema.sql \
#     -f app/db/index.sql \
#     -f app/db/trigger.sql \
#     -f app/db/archival_config_table.sql \
#     -f app/db/archival_indexes.sql \
#     -f app/db/seed.sql
#
set -euo pipefail

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-kitchen}"
DB_USER="${DB_USER:-cdeachaval}"

# psql uses libpq; Cloud SQL public IP requires TLS.
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
echo "→ PGSSLMODE=${PGSSLMODE}"

export PGOPTIONS='--client-min-messages=warning'

QR_CODE_DIR="static/qr_codes"
PRODUCT_IMAGE_DIR="static/product_images"

if [ "${SKIP_IMAGE_CLEANUP:-0}" != "1" ]; then
  echo "→ Cleaning generated image directories…"
  if [ -d "${QR_CODE_DIR}" ]; then
    find "${QR_CODE_DIR}" -mindepth 1 -delete || true
  else
    mkdir -p "${QR_CODE_DIR}"
  fi

  if [ -d "${PRODUCT_IMAGE_DIR}" ]; then
    find "${PRODUCT_IMAGE_DIR}" -mindepth 1 -delete || true
  else
    mkdir -p "${PRODUCT_IMAGE_DIR}"
  fi

  mkdir -p "${QR_CODE_DIR}" "${PRODUCT_IMAGE_DIR}"
else
  echo "→ Skipping image directory cleanup (SKIP_IMAGE_CLEANUP=1)"
fi

echo "→ Rebuilding schema in ${DB_NAME} on ${DB_HOST}:${DB_PORT}…"
psql \
  -h "${DB_HOST}" \
  -p "${DB_PORT}" \
  -U "${DB_USER}" \
  -d "${DB_NAME}" \
  -q -X -v ON_ERROR_STOP=1 <<'SQL'
-- Drop all app schemas (CASCADE removes all tables within them)
DROP SCHEMA IF EXISTS core     CASCADE;
DROP SCHEMA IF EXISTS ops      CASCADE;
DROP SCHEMA IF EXISTS customer CASCADE;
DROP SCHEMA IF EXISTS billing  CASCADE;
DROP SCHEMA IF EXISTS audit    CASCADE;
-- Reset public to a clean slate (extensions only)
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
\i app/db/schema.sql
\i app/db/index.sql
\i app/db/trigger.sql
\i app/db/archival_config_table.sql
\i app/db/archival_indexes.sql
\i app/db/seed.sql
SQL

# Set default search_path at the database level so all future connections inherit it.
# This allows bare table names (FROM user_info, etc.) to resolve without code changes.
psql \
  -h "${DB_HOST}" \
  -p "${DB_PORT}" \
  -U "${DB_USER}" \
  -d "${DB_NAME}" \
  -q -X -v ON_ERROR_STOP=1 \
  -c "ALTER DATABASE ${DB_NAME} SET search_path = core, ops, customer, billing, audit, public;"
echo "→ search_path set on database ${DB_NAME}"

if [ "${SKIP_PYTEST:-0}" != "1" ]; then
  if [ -f "venv/bin/activate" ]; then
    _VENV="venv/bin/activate"
  elif [ -f ".venv/bin/activate" ]; then
    _VENV=".venv/bin/activate"
  else
    _VENV=""
  fi
  if [ -n "${_VENV}" ]; then
    echo "→ Running database tests with pytest…"
    # shellcheck source=/dev/null
    source "${_VENV}"
    export DB_HOST DB_PORT DB_NAME DB_USER PGPASSWORD PGSSLMODE
    pytest app/tests/database/ -v --tb=short
  else
    echo "⚠️  Skipping pytest - venv not found. Set SKIP_PYTEST=1 to silence this, or create a venv."
  fi
else
  echo "→ Skipping pytest (SKIP_PYTEST=1)"
fi

if [ "${SKIP_RESEED:-0}" != "1" ]; then
  echo "→ Re-seeding final state…"
  psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -q -X -v ON_ERROR_STOP=1 <<'SQL'
\i app/db/seed.sql
SQL
else
  echo "→ Skipping final re-seed (SKIP_RESEED=1)"
fi

if [ "${SKIP_POST_REBUILD_SYNC:-0}" != "1" ]; then
  if [ -f "venv/bin/activate" ]; then
    _SYNC_VENV="venv/bin/activate"
  elif [ -f ".venv/bin/activate" ]; then
    _SYNC_VENV=".venv/bin/activate"
  else
    _SYNC_VENV=""
  fi
  if [ -n "${_SYNC_VENV}" ]; then
    echo "→ Post-rebuild external sync (FX + holidays)…"
    # shellcheck source=/dev/null
    source "${_SYNC_VENV}"
    export DB_HOST DB_PORT DB_NAME DB_USER PGPASSWORD PGSSLMODE DB_SSLMODE
    export PYTHONPATH=.
    python app/db/post_rebuild_external_sync.py
  else
    echo "⚠️  Skipping post-rebuild sync - venv not found. Set SKIP_POST_REBUILD_SYNC=1 to silence, or create a venv."
  fi
else
  echo "→ Skipping post-rebuild sync (SKIP_POST_REBUILD_SYNC=1)"
fi
