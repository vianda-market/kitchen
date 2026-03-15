#!/usr/bin/env bash
set -euo pipefail

DB_NAME=kitchen_db_dev
DB_USER=cdeachaval

export PGOPTIONS='--client-min-messages=warning'

QR_CODE_DIR="static/qr_codes"
PRODUCT_IMAGE_DIR="static/product_images"

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

echo "→ Rebuilding schema in ${DB_NAME}…"
psql \
  -h localhost \
  -U "${DB_USER}" \
  -d "${DB_NAME}" \
  -q -X -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
\i app/db/schema.sql
\i app/db/index.sql
\i app/db/trigger.sql
\i app/db/archival_config_table.sql
\i app/db/archival_indexes.sql
\i app/db/seed.sql
SQL

# 2) Run all database integration tests via pytest (if venv is available)
# Includes: schema, seed, integration workflows, customer payment methods, market subscription
# constraints, subscription payment table and flow. Export DB_NAME/DB_USER so the app's
# connection pool (used by some code paths) connects to the same DB.
if [ -f "venv/bin/activate" ]; then
  _VENV="venv/bin/activate"
elif [ -f ".venv/bin/activate" ]; then
  _VENV=".venv/bin/activate"
else
  _VENV=""
fi
if [ -n "${_VENV}" ]; then
  echo "→ Running database tests with pytest (schema, seed, integration, subscription payment, etc.)…"
  source "${_VENV}"
  export DB_NAME DB_USER
  pytest app/tests/database/ -v --tb=short
else
  echo "⚠️  Skipping pytest - venv not found. Create one and run: source venv/bin/activate && pytest app/tests/database/"
fi

# 3) Re-seed so your app sees the final state
echo "→ Re-seeding final state…"
psql \
  -h localhost \
  -U "${DB_USER}" \
  -d "${DB_NAME}" \
  -q -X -v ON_ERROR_STOP=1 <<'SQL'
\i app/db/seed.sql
SQL
