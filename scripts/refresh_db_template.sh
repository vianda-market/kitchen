#!/usr/bin/env bash
# scripts/refresh_db_template.sh — fingerprint-aware Postgres template builder.
#
# PURPOSE
#   Builds (or rebuilds) the `kitchen_template` Postgres database — a fully
#   migrated + seeded + upstream-synced snapshot that per-worktree DB clones are
#   created from in ~1-2 seconds (vs ~30 seconds for a full rebuild).
#
#   Run on every worktree session start (called automatically from
#   scripts/worktree_env.sh). It is a no-op when the migration + seed fingerprint
#   is unchanged; the full rebuild (migrations + seed + FX/holiday syncs) runs only
#   when the fingerprint changes or --force is passed.
#
# USAGE
#   bash scripts/refresh_db_template.sh          # no-op if fingerprint matches
#   bash scripts/refresh_db_template.sh --force  # force full rebuild
#
# PREREQUISITES
#   The dev Postgres user must have CREATEDB privilege. One-time setup (run as
#   Postgres superuser — e.g. `psql -U postgres`):
#
#     ALTER USER <your_db_user> CREATEDB;
#
#   To check your current user:
#     psql -c "\conninfo"
#
#   If this script exits with "ERROR: permission denied to create database",
#   run the ALTER USER command above and retry.
#
# ENVIRONMENT (all optional, inherits from build_kitchen_db.sh conventions)
#   DB_HOST      default: localhost
#   DB_PORT      default: 5432
#   DB_USER      default: cdeachaval
#   PGPASSWORD   password when required
#   SKIP_POST_REBUILD_SYNC=1  skip FX + holiday upstream API calls
#
# FINGERPRINT
#   SHA1 over: all migration filenames (sorted) + dev_fixtures.sql contents.
#   Stored in a .kitchen-template-fingerprint file in the repo root.
#   When the fingerprint changes, all existing kitchen_* clones are dropped first
#   (their schema would be stale), then kitchen_template is rebuilt.
#
# REFERENCES
#   Issue #199 — Postgres TEMPLATE-clone pattern for per-worktree DB cold-start.
#   Issue #197 — parallel Newman infrastructure (KITCHEN_DB_NAME env-var pattern).

set -euo pipefail

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-cdeachaval}"
TEMVIANDA_DB="kitchen_template"
FINGERPRINT_FILE=".kitchen-template-fingerprint"
FORCE=0

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    *) echo "refresh_db_template: unknown argument '$arg'" >&2; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# CREATEDB privilege check
# ---------------------------------------------------------------------------
_check_createdb() {
  local has_createdb
  has_createdb=$(psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -tAX \
    -c "SELECT rolcreatedb FROM pg_roles WHERE rolname = current_user;" 2>/dev/null || echo "f")
  if [ "${has_createdb}" != "t" ]; then
    echo "" >&2
    echo "ERROR: Postgres user '${DB_USER}' lacks CREATEDB privilege." >&2
    echo "       Fix (run once as a Postgres superuser, e.g. psql -U postgres):" >&2
    echo "         ALTER USER ${DB_USER} CREATEDB;" >&2
    echo "" >&2
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Compute current fingerprint
# ---------------------------------------------------------------------------
_compute_fingerprint() {
  # Hash: sorted list of migration filenames + dev_fixtures.sql contents.
  # This captures both schema changes (new migration files) and seed changes.
  {
    find app/db/migrations -maxdepth 1 -name '[0-9][0-9][0-9][0-9]_*.sql' \
      | sort \
      | xargs -I{} basename {}
    cat app/db/seed/dev_fixtures.sql 2>/dev/null || true
  } | shasum -a 1 | awk '{print $1}'
}

# ---------------------------------------------------------------------------
# Read stored fingerprint
# ---------------------------------------------------------------------------
_read_stored_fingerprint() {
  if [ -f "${FINGERPRINT_FILE}" ]; then
    cat "${FINGERPRINT_FILE}"
  else
    echo ""
  fi
}

# ---------------------------------------------------------------------------
# Check if template DB exists
# ---------------------------------------------------------------------------
_template_exists() {
  psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -tAX \
    -c "SELECT 1 FROM pg_database WHERE datname = '${TEMVIANDA_DB}';" 2>/dev/null | grep -q "^1$"
}

# ---------------------------------------------------------------------------
# Drop all kitchen_* clone DBs (not kitchen, not kitchen_template)
# Called before rebuilding the template so stale clones are evicted.
# ---------------------------------------------------------------------------
_drop_clone_dbs() {
  echo "refresh_db_template: dropping stale kitchen_* clone DBs…"
  local dbs
  dbs=$(psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -tAX \
    -c "SELECT datname FROM pg_database
        WHERE datname LIKE 'kitchen_%'
          AND datname NOT IN ('kitchen_template');" 2>/dev/null || true)
  for db in $dbs; do
    echo "  dropping clone: ${db}"
    psql \
      -h "${DB_HOST}" \
      -p "${DB_PORT}" \
      -U "${DB_USER}" \
      -d postgres \
      -q -X \
      -c "DROP DATABASE IF EXISTS \"${db}\";" || true
  done
}

# ---------------------------------------------------------------------------
# Full template rebuild
# ---------------------------------------------------------------------------
_build_template() {
  echo "refresh_db_template: building ${TEMVIANDA_DB}…"

  # Drop stale clones first (they'd be connected to the old template schema).
  _drop_clone_dbs

  # Drop the existing template (must unmark IS_TEMPLATE first, then drop).
  local template_exists
  template_exists=$(psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -tAX \
    -c "SELECT 1 FROM pg_database WHERE datname = '${TEMVIANDA_DB}';" 2>/dev/null || echo "")
  if [ -n "${template_exists}" ]; then
    echo "  unmarking and dropping old ${TEMVIANDA_DB}…"
    psql \
      -h "${DB_HOST}" \
      -p "${DB_PORT}" \
      -U "${DB_USER}" \
      -d postgres \
      -q -X \
      -c "UPDATE pg_database SET datistemplate = FALSE WHERE datname = '${TEMVIANDA_DB}';" || true
    psql \
      -h "${DB_HOST}" \
      -p "${DB_PORT}" \
      -U "${DB_USER}" \
      -d postgres \
      -q -X \
      -c "DROP DATABASE IF EXISTS \"${TEMVIANDA_DB}\";" || true
  fi

  # Create fresh DB from template0 (cleanest possible base).
  echo "  creating ${TEMVIANDA_DB} from template0…"
  psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -q -X -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE \"${TEMVIANDA_DB}\" TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8';" 2>/dev/null || \
  psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -q -X -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE \"${TEMVIANDA_DB}\" TEMPLATE template0;"

  # Set PGSSLMODE for subsequent connections.
  case "${DB_HOST}" in
    localhost|127.0.0.1|::1)
      export PGSSLMODE="${PGSSLMODE:-prefer}"
      ;;
    *)
      export PGSSLMODE="${PGSSLMODE:-require}"
      ;;
  esac
  export PGOPTIONS='--client-min-messages=warning'

  # Load schema + seed into template DB (mirrors build_kitchen_db.sh's psql block).
  echo "  loading schema + seed into ${TEMVIANDA_DB}…"
  psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${TEMVIANDA_DB}" \
    -q -X -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA IF EXISTS core     CASCADE;
DROP SCHEMA IF EXISTS ops      CASCADE;
DROP SCHEMA IF EXISTS customer CASCADE;
DROP SCHEMA IF EXISTS billing  CASCADE;
DROP SCHEMA IF EXISTS audit    CASCADE;
DROP SCHEMA IF EXISTS external CASCADE;
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
\i app/db/schema.sql
\i app/db/index.sql
\i app/db/trigger.sql
\i app/db/archival_config_table.sql
\i app/db/archival_indexes.sql
\i app/db/seed/reference_data.sql
SQL

  # Dev fixtures.
  echo "  loading dev fixtures…"
  psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${TEMVIANDA_DB}" \
    -q -X -v ON_ERROR_STOP=1 \
    -f app/db/seed/dev_fixtures.sql

  # Populate schema_migration baseline (same logic as build_kitchen_db.sh).
  echo "  populating schema_migration baseline…"
  local MIGRATIONS_DIR="app/db/migrations"
  for filepath in "${MIGRATIONS_DIR}"/[0-9][0-9][0-9][0-9]_*.sql; do
    [ -e "${filepath}" ] || continue
    local filename version_str version name checksum
    filename=$(basename "${filepath}")
    version_str="${filename%%_*}"
    version=$((10#${version_str}))
    name="${filename%.sql}"
    checksum=$(shasum -a 256 "${filepath}" | awk '{print $1}')
    psql \
      -h "${DB_HOST}" \
      -p "${DB_PORT}" \
      -U "${DB_USER}" \
      -d "${TEMVIANDA_DB}" \
      -q -X -v ON_ERROR_STOP=1 \
      -c "INSERT INTO core.schema_migration (version, name, applied_at, checksum) VALUES (${version}, '${name}', now(), '${checksum}') ON CONFLICT (version) DO NOTHING;"
  done

  # Set search_path.
  psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${TEMVIANDA_DB}" \
    -q -X -v ON_ERROR_STOP=1 \
    -c "ALTER DATABASE \"${TEMVIANDA_DB}\" SET search_path = core, ops, customer, billing, audit, public;"

  # Post-rebuild upstream sync: FX rates + national holidays.
  # This runs ONCE here; all per-worktree clones inherit the synced data for free.
  if [ "${SKIP_POST_REBUILD_SYNC:-0}" != "1" ]; then
    if [ -f "venv/bin/activate" ]; then
      _SYNC_VENV="venv/bin/activate"
    elif [ -f ".venv/bin/activate" ]; then
      _SYNC_VENV=".venv/bin/activate"
    else
      _SYNC_VENV=""
    fi
    if [ -n "${_SYNC_VENV}" ]; then
      echo "  post-rebuild external sync (FX + holidays)…"
      # shellcheck source=/dev/null
      source "${_SYNC_VENV}"
      export DB_HOST DB_PORT DB_USER PGPASSWORD PGSSLMODE
      # Override DB_NAME so post_rebuild_external_sync.py targets the template DB.
      DB_NAME="${TEMVIANDA_DB}" DB_SSLMODE="${PGSSLMODE}" PYTHONPATH=. \
        python3 app/db/post_rebuild_external_sync.py
    else
      echo "  WARNING: venv not found — skipping FX/holiday sync. Set SKIP_POST_REBUILD_SYNC=1 to silence."
    fi
  else
    echo "  skipping post-rebuild sync (SKIP_POST_REBUILD_SYNC=1)"
  fi

  # Mark as Postgres template — no new connections allowed; cloneable instantly.
  echo "  marking ${TEMVIANDA_DB} IS_TEMPLATE TRUE…"
  psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d postgres \
    -q -X -v ON_ERROR_STOP=1 \
    -c "UPDATE pg_database SET datistemplate = TRUE WHERE datname = '${TEMVIANDA_DB}';"

  echo "refresh_db_template: ${TEMVIANDA_DB} built and marked as template."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
_check_createdb

CURRENT_FP=$(_compute_fingerprint)
STORED_FP=$(_read_stored_fingerprint)

if [ "${FORCE}" -eq 1 ]; then
  echo "refresh_db_template: --force flag set — rebuilding template."
  _build_template
  echo "${CURRENT_FP}" > "${FINGERPRINT_FILE}"
elif [ "${CURRENT_FP}" = "${STORED_FP}" ] && _template_exists; then
  echo "refresh_db_template: fingerprint matches and ${TEMVIANDA_DB} exists — no-op."
  exit 0
else
  if [ "${CURRENT_FP}" != "${STORED_FP}" ]; then
    echo "refresh_db_template: fingerprint changed (${STORED_FP:-<none>} → ${CURRENT_FP}) — rebuilding."
  else
    echo "refresh_db_template: ${TEMVIANDA_DB} not found — building."
  fi
  _build_template
  echo "${CURRENT_FP}" > "${FINGERPRINT_FILE}"
fi

echo "refresh_db_template: done (fingerprint=${CURRENT_FP})."
