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
#   DB_SSLMODE       optional; non-local DB_HOST defaults to require (Cloud SQL TLS).
#                    For local Postgres without SSL, use DB_SSLMODE=prefer or disable.
#   IAM_OWNER_ACCOUNT  optional; Cloud SQL IAM user for full access (Cloud SQL Studio / DBeaver)
#   IAM_ADMIN_EMAIL  optional; Cloud SQL IAM user for read-only access (monitoring / support)
#                    Both from Pulumi config. Skipped if not set or role doesn't exist.
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
ENV="${ENV:-dev}"

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

echo "→ Rebuilding schema in ${DB_NAME} on ${DB_HOST}:${DB_PORT} (ENV=${ENV})…"
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
DROP SCHEMA IF EXISTS external CASCADE;
-- Reset public to a clean slate (extensions only)
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
\i app/db/schema.sql
\i app/db/index.sql
\i app/db/trigger.sql
\i app/db/archival_config_table.sql
\i app/db/archival_indexes.sql
\i app/db/seed/reference_data.sql
SQL

# ---------------------------------------------------------------------------
# IAM grants (optional — env-var-driven, safe to skip locally)
# ---------------------------------------------------------------------------

# IAM_OWNER_ACCOUNT: full access (Cloud SQL Studio, DBeaver, admin operations)
if [ -n "${IAM_OWNER_ACCOUNT:-}" ]; then
  echo "→ Granting full access to IAM owner: ${IAM_OWNER_ACCOUNT}…"
  psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -q -X -v ON_ERROR_STOP=1 <<EOSQL
DO \$\$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = '${IAM_OWNER_ACCOUNT}') THEN
        GRANT USAGE ON SCHEMA core, ops, customer, billing, audit, public TO "${IAM_OWNER_ACCOUNT}";
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA core TO "${IAM_OWNER_ACCOUNT}";
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ops TO "${IAM_OWNER_ACCOUNT}";
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA customer TO "${IAM_OWNER_ACCOUNT}";
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA billing TO "${IAM_OWNER_ACCOUNT}";
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA audit TO "${IAM_OWNER_ACCOUNT}";
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "${IAM_OWNER_ACCOUNT}";
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA core TO "${IAM_OWNER_ACCOUNT}";
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "${IAM_OWNER_ACCOUNT}";
        GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA core TO "${IAM_OWNER_ACCOUNT}";
        GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO "${IAM_OWNER_ACCOUNT}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT ALL ON TABLES TO "${IAM_OWNER_ACCOUNT}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA ops GRANT ALL ON TABLES TO "${IAM_OWNER_ACCOUNT}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA customer GRANT ALL ON TABLES TO "${IAM_OWNER_ACCOUNT}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA billing GRANT ALL ON TABLES TO "${IAM_OWNER_ACCOUNT}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT ALL ON TABLES TO "${IAM_OWNER_ACCOUNT}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "${IAM_OWNER_ACCOUNT}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT ALL ON SEQUENCES TO "${IAM_OWNER_ACCOUNT}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "${IAM_OWNER_ACCOUNT}";
        RAISE NOTICE 'Full-access grants applied for %', '${IAM_OWNER_ACCOUNT}';
    ELSE
        RAISE NOTICE 'IAM role % does not exist — skipping owner grants', '${IAM_OWNER_ACCOUNT}';
    END IF;
END
\$\$;
EOSQL
else
  echo "→ Skipping IAM owner grants (IAM_OWNER_ACCOUNT not set)"
fi

# IAM_ADMIN_EMAIL: read-only access (monitoring, dashboards, support)
if [ -n "${IAM_ADMIN_EMAIL:-}" ]; then
  echo "→ Granting read-only access to IAM admin: ${IAM_ADMIN_EMAIL}…"
  psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -q -X -v ON_ERROR_STOP=1 <<EOSQL
DO \$\$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = '${IAM_ADMIN_EMAIL}') THEN
        GRANT USAGE ON SCHEMA core, ops, customer, billing, audit TO "${IAM_ADMIN_EMAIL}";
        GRANT SELECT ON ALL TABLES IN SCHEMA core TO "${IAM_ADMIN_EMAIL}";
        GRANT SELECT ON ALL TABLES IN SCHEMA ops TO "${IAM_ADMIN_EMAIL}";
        GRANT SELECT ON ALL TABLES IN SCHEMA customer TO "${IAM_ADMIN_EMAIL}";
        GRANT SELECT ON ALL TABLES IN SCHEMA billing TO "${IAM_ADMIN_EMAIL}";
        GRANT SELECT ON ALL TABLES IN SCHEMA audit TO "${IAM_ADMIN_EMAIL}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA core GRANT SELECT ON TABLES TO "${IAM_ADMIN_EMAIL}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA ops GRANT SELECT ON TABLES TO "${IAM_ADMIN_EMAIL}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA customer GRANT SELECT ON TABLES TO "${IAM_ADMIN_EMAIL}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA billing GRANT SELECT ON TABLES TO "${IAM_ADMIN_EMAIL}";
        ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT SELECT ON TABLES TO "${IAM_ADMIN_EMAIL}";
        RAISE NOTICE 'Read-only grants applied for %', '${IAM_ADMIN_EMAIL}';
    ELSE
        RAISE NOTICE 'IAM role % does not exist — skipping admin grants', '${IAM_ADMIN_EMAIL}';
    END IF;
END
\$\$;
EOSQL
else
  echo "→ Skipping IAM admin grants (IAM_ADMIN_EMAIL not set)"
fi

# Dev fixtures (dev only — never loaded in staging/production)
if [ "${ENV}" = "dev" ]; then
  echo "→ Loading dev fixtures…"
  psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -q -X -v ON_ERROR_STOP=1 \
    -f app/db/seed/dev_fixtures.sql
else
  echo "→ Skipping dev fixtures (ENV=${ENV})"
fi

# Populate schema_migration baseline so migrate.sh knows this DB is current.
# Every migration file that exists at rebuild time is marked as already applied.
echo "→ Populating schema_migration baseline…"
MIGRATIONS_DIR="app/db/migrations"
MIGRATION_COUNT=0
for filepath in "${MIGRATIONS_DIR}"/[0-9][0-9][0-9][0-9]_*.sql; do
  [ -e "${filepath}" ] || continue
  filename=$(basename "${filepath}")
  version_str="${filename%%_*}"
  version=$((10#${version_str}))
  name="${filename%.sql}"
  checksum=$(shasum -a 256 "${filepath}" | awk '{print $1}')
  psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -q -X -v ON_ERROR_STOP=1 \
    -c "INSERT INTO core.schema_migration (version, name, applied_at, checksum) VALUES (${version}, '${name}', now(), '${checksum}') ON CONFLICT (version) DO NOTHING;"
  MIGRATION_COUNT=$((MIGRATION_COUNT + 1))
done
echo "→ Registered ${MIGRATION_COUNT} migration(s) as baseline"

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
    -q -X -v ON_ERROR_STOP=1 \
    -f app/db/seed/reference_data.sql
  if [ "${ENV}" = "dev" ]; then
    psql \
      -h "${DB_HOST}" \
      -p "${DB_PORT}" \
      -U "${DB_USER}" \
      -d "${DB_NAME}" \
      -q -X -v ON_ERROR_STOP=1 \
      -f app/db/seed/dev_fixtures.sql
  fi
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
    python3 app/db/post_rebuild_external_sync.py
  else
    echo "⚠️  Skipping post-rebuild sync - venv not found. Set SKIP_POST_REBUILD_SYNC=1 to silence, or create a venv."
  fi
else
  echo "→ Skipping post-rebuild sync (SKIP_POST_REBUILD_SYNC=1)"
fi
