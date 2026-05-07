#!/usr/bin/env bash
# =============================================================================
# load_demo_data.sh — Demo-day data loader (Layer A + B)
#
# Usage:
#   bash scripts/load_demo_data.sh
#
# Prerequisites:
#   1. kitchen dev DB is up (build_kitchen_db.sh ran successfully)
#   2. Kitchen API is running with PAYMENT_PROVIDER=mock in .env — start it with:
#      bash scripts/run_dev_quiet.sh
#   3. newman is installed globally:  npm install -g newman
#
# What this script does:
#   1. Refuses to run on non-dev environments (ENV guard + DB_HOST guard)
#   2. Requires PAYMENT_PROVIDER=mock (subscriptions go through the API, not SQL)
#   3. Runs Layer A — app/db/seed/demo_baseline.sql (SQL fixtures)
#   4. Generates a random password for the demo super-admin
#   5. Hashes the password with bcrypt (Python passlib) and UPDATEs the DB row
#   6. Probes the kitchen API health endpoint; exits with a clear message if down
#   7. Runs Layer B — Newman (900_DEMO_DAY_SEED.postman_collection.json)
#   8. Prints the demo credentials block
#   9. Writes credentials to .demo_credentials.local (gitignored)
#
# Re-running on an already-seeded DB will create duplicate customers/subscriptions/orders.
# To reset:  bash scripts/purge_demo_data.sh && bash scripts/load_demo_data.sh
#
# To purge demo data:  bash scripts/purge_demo_data.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Environment guards
# ---------------------------------------------------------------------------

ENV="${ENV:-dev}"
if [ "${ENV}" != "dev" ]; then
  echo "ERROR: load_demo_data.sh is dev-only. ENV=${ENV} is not permitted."
  echo "       Demo data must never be loaded in staging or production."
  exit 1
fi

DB_HOST="${DB_HOST:-localhost}"
case "${DB_HOST}" in
  *prod*|*staging*)
    echo "ERROR: load_demo_data.sh refuses to run against DB_HOST=${DB_HOST}."
    echo "       Detected a staging or production host. Aborting."
    exit 1
    ;;
esac

# ---------------------------------------------------------------------------
# PAYMENT_PROVIDER guard — subscriptions go through the API (not SQL bypass)
# ---------------------------------------------------------------------------

if [ "${PAYMENT_PROVIDER:-}" != "mock" ]; then
  echo ""
  echo "ERROR: PAYMENT_PROVIDER=mock is required to load demo data."
  echo ""
  echo "  The demo creates subscriptions via the API (POST /subscriptions/with-payment"
  echo "  + POST /subscriptions/{id}/confirm-payment). This requires mock mode."
  echo ""
  echo "  Add to your .env:  PAYMENT_PROVIDER=mock"
  echo "  Then restart the API:  bash scripts/run_dev_quiet.sh"
  echo ""
  exit 1
fi

# ---------------------------------------------------------------------------
# DB connection defaults (mirror build_kitchen_db.sh)
# ---------------------------------------------------------------------------

DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-kitchen}"
DB_USER="${DB_USER:-postgres}"

PSQL_ARGS=(
  -h "${DB_HOST}"
  -p "${DB_PORT}"
  -U "${DB_USER}"
  -d "${DB_NAME}"
  -v ON_ERROR_STOP=1
)

KITCHEN_API_PORT="${KITCHEN_API_PORT:-8000}"
HEALTH_URL="http://localhost:${KITCHEN_API_PORT}/health"

# Collection and environment paths (relative to repo root)
COLLECTION="docs/postman/collections/900_DEMO_DAY_SEED.postman_collection.json"
ENVIRONMENT="docs/postman/environments/dev.postman_environment.json"
CREDENTIALS_FILE=".demo_credentials.local"

# ---------------------------------------------------------------------------
# Step 1 — Layer A: SQL baseline
# ---------------------------------------------------------------------------

echo ""
echo "=== DEMO DAY LOADER ==="
echo ""
echo "[1/4] Running Layer A: demo_baseline.sql..."
psql "${PSQL_ARGS[@]}" -f app/db/seed/demo_baseline.sql
echo "      Layer A complete."

# ---------------------------------------------------------------------------
# Step 2 — Generate password and update demo admin
# ---------------------------------------------------------------------------

echo ""
echo "[2/4] Generating demo admin password and updating DB..."

DEMO_PASSWORD="$(openssl rand -base64 18)"

# Hash the password using kitchen's passlib bcrypt setup
DEMO_HASH=$(PYTHONPATH=. python3 -c "
from app.auth.security import hash_password
print(hash_password('${DEMO_PASSWORD}'))
")

psql "${PSQL_ARGS[@]}" -c \
  "UPDATE core.user_info SET hashed_password = '${DEMO_HASH}', modified_date = CURRENT_TIMESTAMP WHERE username = 'demo-admin@vianda.demo';"

echo "      Password hash updated for demo-admin@vianda.demo."

# ---------------------------------------------------------------------------
# Step 3 — Probe API health
# ---------------------------------------------------------------------------

echo ""
echo "[3/4] Checking kitchen API health at ${HEALTH_URL}..."

API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_URL}" 2>/dev/null || true)

if [ "${API_STATUS}" != "200" ]; then
  echo ""
  echo "ERROR: Kitchen API is not reachable (HTTP ${API_STATUS:-no response})."
  echo ""
  echo "  Start the API first:"
  echo "    bash scripts/run_dev_quiet.sh"
  echo ""
  echo "  Then re-run this script."
  exit 1
fi

echo "      API is healthy (HTTP 200)."

# ---------------------------------------------------------------------------
# Step 4 — Layer B: Newman
# ---------------------------------------------------------------------------

echo ""
echo "[4/4] Running Layer B: Newman demo collection..."

if ! command -v newman >/dev/null 2>&1; then
  echo ""
  echo "ERROR: newman is not installed."
  echo "  Install it with:  npm install -g newman"
  exit 1
fi

newman run "${COLLECTION}" \
  -e "${ENVIRONMENT}" \
  --env-var "demoAdminUsername=demo-admin@vianda.demo" \
  --env-var "demoAdminPassword=${DEMO_PASSWORD}" \
  --bail

echo "      Layer B complete."

# ---------------------------------------------------------------------------
# Print credentials block
# ---------------------------------------------------------------------------

CREDS_BLOCK="$(cat <<CREDS

=== DEMO CREDENTIALS ===
Super Admin:
  username: demo-admin@vianda.demo
  password: ${DEMO_PASSWORD}

Demo Customers (shared password: DemoPass1!):
  demo.cliente.pe.01@vianda.demo  (PE — Miraflores)
  demo.cliente.pe.02@vianda.demo  (PE — Barranco)
  demo.cliente.pe.03@vianda.demo  (PE — San Isidro)
  demo.cliente.pe.04@vianda.demo  (PE — Surco)
  demo.cliente.pe.05@vianda.demo  (PE — Jesus Maria)
========================

NOTE: Re-running this loader on a previously-seeded DB will create duplicate
customers/subscriptions/orders. To reset:
  bash scripts/purge_demo_data.sh && bash scripts/load_demo_data.sh
CREDS
)"

echo "${CREDS_BLOCK}"

# Write to .demo_credentials.local (gitignored)
echo "${CREDS_BLOCK}" > "${CREDENTIALS_FILE}"
echo ""
echo "Credentials also written to: ${CREDENTIALS_FILE}"
echo ""
echo "Demo data load complete. Happy demoing!"
