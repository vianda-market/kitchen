#!/usr/bin/env bash
# =============================================================================
# load_demo_data.sh — Demo-day data loader
#
# Two targets:
#   --target=local    (default) — laptop API, PAYMENT_PROVIDER=mock,
#                                 confirms subscriptions via the kitchen
#                                 mock-confirm endpoint. Fast, offline.
#   --target=gcp-dev             — points at the deployed GCP dev API + DB,
#                                 confirms PaymentIntents via Stripe sandbox
#                                 (test card pm_card_visa), then waits for
#                                 the Stripe webhook to activate each
#                                 subscription.
#
# Prerequisites (target=local):
#   1. kitchen dev DB rebuilt (build_kitchen_db.sh).
#   2. API running locally with PAYMENT_PROVIDER=mock.
#   3. newman installed:  npm install -g newman
#
# Prerequisites (target=gcp-dev):
#   1. cloud-sql-proxy (or equivalent) forwarding the dev Cloud SQL instance,
#      and DB_HOST/DB_PORT/DB_NAME/DB_USER/PGPASSWORD set accordingly.
#   2. KITCHEN_API_BASE pointing at the deployed dev API URL (must be HTTPS
#      and publicly reachable from Stripe so webhooks land).
#   3. STRIPE_SECRET_KEY set to a Stripe sandbox test key (sk_test_…). The
#      same Stripe account whose webhook is configured against the dev API.
#   4. newman installed:  npm install -g newman
#
# Usage examples:
#   bash scripts/load_demo_data.sh                      # local + mock
#   bash scripts/load_demo_data.sh --target=local       # explicit
#
#   STRIPE_SECRET_KEY=sk_test_xxx \
#   KITCHEN_API_BASE=https://kitchen-dev-xxx.run.app \
#   DB_HOST=127.0.0.1 DB_PORT=5433 DB_NAME=kitchen-dev DB_USER=kitchen-dev-app \
#   PGPASSWORD=… \
#   bash scripts/load_demo_data.sh --target=gcp-dev
#
# Re-running on a previously-loaded DB creates duplicate customers / orders.
# To reset:  bash scripts/purge_demo_data.sh && bash scripts/load_demo_data.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Parse --target flag
# ---------------------------------------------------------------------------

TARGET="local"
for arg in "$@"; do
  case "${arg}" in
    --target=*)
      TARGET="${arg#--target=}"
      ;;
    --help|-h)
      sed -n '2,40p' "$0"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: ${arg}"
      echo "Usage: $0 [--target=local|gcp-dev]"
      exit 1
      ;;
  esac
done

case "${TARGET}" in
  local|gcp-dev) ;;
  *)
    echo "ERROR: --target must be 'local' or 'gcp-dev' (got: ${TARGET})"
    exit 1
    ;;
esac

# ---------------------------------------------------------------------------
# Environment guards (apply to both targets)
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
# Per-target guards
# ---------------------------------------------------------------------------

if [ "${TARGET}" = "local" ]; then
  if [ "${PAYMENT_PROVIDER:-}" != "mock" ]; then
    echo ""
    echo "ERROR: --target=local requires PAYMENT_PROVIDER=mock."
    echo ""
    echo "  Add to your .env:  PAYMENT_PROVIDER=mock"
    echo "  Then restart the API:  bash scripts/run_dev_quiet.sh"
    echo ""
    echo "  Alternative: target the deployed dev environment with"
    echo "    bash scripts/load_demo_data.sh --target=gcp-dev"
    exit 1
  fi
  PAYMENT_MODE="mock"
  KITCHEN_API_BASE="${KITCHEN_API_BASE:-http://localhost:${KITCHEN_API_PORT:-8000}}"
  STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-}"  # not used in mock mode
fi

if [ "${TARGET}" = "gcp-dev" ]; then
  if [ -z "${KITCHEN_API_BASE:-}" ]; then
    echo "ERROR: --target=gcp-dev requires KITCHEN_API_BASE (e.g. https://kitchen-dev-xxx.run.app)."
    exit 1
  fi
  case "${KITCHEN_API_BASE}" in
    https://*) ;;
    *)
      echo "ERROR: KITCHEN_API_BASE must start with https:// for gcp-dev (got: ${KITCHEN_API_BASE})."
      echo "       Stripe webhooks won't reach an http:// endpoint."
      exit 1
      ;;
  esac
  case "${KITCHEN_API_BASE}" in
    *prod*|*staging*)
      echo "ERROR: KITCHEN_API_BASE=${KITCHEN_API_BASE} smells like prod or staging. Aborting."
      exit 1
      ;;
  esac
  if [ -z "${STRIPE_SECRET_KEY:-}" ]; then
    echo "ERROR: --target=gcp-dev requires STRIPE_SECRET_KEY (sk_test_…)."
    echo "       Use the test key from the same Stripe account whose webhook is configured against ${KITCHEN_API_BASE}."
    exit 1
  fi
  case "${STRIPE_SECRET_KEY}" in
    sk_test_*) ;;
    sk_live_*)
      echo "ERROR: STRIPE_SECRET_KEY appears to be a LIVE key (sk_live_…). Refusing — demo seeding must use sandbox only."
      exit 1
      ;;
    *)
      echo "WARNING: STRIPE_SECRET_KEY does not look like a Stripe key (expected sk_test_…). Continuing anyway."
      ;;
  esac
  PAYMENT_MODE="stripe"
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

HEALTH_URL="${KITCHEN_API_BASE}/health"

COLLECTION="docs/postman/collections/900_DEMO_DAY_SEED.postman_collection.json"
ENVIRONMENT="docs/postman/environments/dev.postman_environment.json"
CREDENTIALS_FILE=".demo_credentials.local"

echo ""
echo "=== DEMO DAY LOADER ==="
echo "  target:           ${TARGET}"
echo "  payment mode:     ${PAYMENT_MODE}"
echo "  API base:         ${KITCHEN_API_BASE}"
echo "  DB:               ${DB_HOST}:${DB_PORT}/${DB_NAME} (user=${DB_USER})"
echo ""

# ---------------------------------------------------------------------------
# Step 1 — Layer A: SQL baseline
# ---------------------------------------------------------------------------

echo "[1/4] Running Layer A: demo_baseline.sql..."
psql "${PSQL_ARGS[@]}" -f app/db/seed/demo_baseline.sql
echo "      Layer A complete."

# ---------------------------------------------------------------------------
# Step 2 — Generate password and update demo admin
# ---------------------------------------------------------------------------

echo ""
echo "[2/4] Generating demo admin password and updating DB..."

DEMO_PASSWORD="$(openssl rand -base64 18)"

# Hash the password. Prefer kitchen's passlib helper when this script runs
# from a checkout that has it on PYTHONPATH; otherwise fall back to passlib
# directly so gcp-dev runs from any workstation.
DEMO_HASH=$(PYTHONPATH=. python3 -c "
try:
    from app.auth.security import hash_password
    print(hash_password('''${DEMO_PASSWORD}'''))
except ImportError:
    from passlib.context import CryptContext
    print(CryptContext(schemes=['bcrypt'], deprecated='auto').hash('''${DEMO_PASSWORD}'''))
")

psql "${PSQL_ARGS[@]}" -c \
  "UPDATE core.user_info SET hashed_password = '${DEMO_HASH}', modified_date = CURRENT_TIMESTAMP WHERE username = 'demo-admin@vianda.market';"

echo "      Password hash updated for demo-admin@vianda.market."

# Write credentials to file IMMEDIATELY so a failed Newman run still leaves
# debug-able state. Re-written at the end with the same content (defense in
# depth — if writes are flaky, the later one rescues the earlier one).
cat > "${CREDENTIALS_FILE}" <<EARLYCREDS

=== DEMO CREDENTIALS ===
Target:           ${TARGET}
API base:         ${KITCHEN_API_BASE}

Super Admin:
  username: demo-admin@vianda.market
  password: ${DEMO_PASSWORD}

Demo Customers (shared password: DemoPass1!):
  C01  demo.cliente.pe.01@vianda.demo  (PE — Miraflores)
  C02  demo.cliente.pe.02@vianda.demo  (PE — Barranco)
  C03  demo.cliente.pe.03@vianda.demo  (PE — San Isidro)
  C04  demo.cliente.pe.04@vianda.demo  (PE — Surco)
  C05  demo.cliente.pe.05@vianda.demo  (PE — Jesus Maria)
  C06  demo.cliente.pe.06.no_plan@vianda.demo   (NO PLAN — show purchase flow)
  C07  demo.cliente.pe.07.no_orders@vianda.demo  (NO ORDERS — show ordering flow)
========================
EARLYCREDS

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
  if [ "${TARGET}" = "local" ]; then
    echo "  Start the API first:"
    echo "    bash scripts/run_dev_quiet.sh"
  else
    echo "  Verify KITCHEN_API_BASE=${KITCHEN_API_BASE} is correct and the dev API is up."
  fi
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

NEWMAN_ARGS=(
  run "${COLLECTION}"
  -e "${ENVIRONMENT}"
  --env-var "demoAdminUsername=demo-admin@vianda.market"
  --env-var "demoAdminPassword=${DEMO_PASSWORD}"
  --env-var "baseUrl=${KITCHEN_API_BASE}"
  --env-var "paymentMode=${PAYMENT_MODE}"
  --bail
)

if [ "${TARGET}" = "gcp-dev" ]; then
  NEWMAN_ARGS+=(--env-var "stripeSecretKey=${STRIPE_SECRET_KEY}")
fi

newman "${NEWMAN_ARGS[@]}"

echo "      Layer B complete."

# ---------------------------------------------------------------------------
# Print credentials block
# ---------------------------------------------------------------------------

CREDS_BLOCK="$(cat <<CREDS

=== DEMO CREDENTIALS ===
Target:           ${TARGET}
API base:         ${KITCHEN_API_BASE}

Super Admin:
  username: demo-admin@vianda.market
  password: ${DEMO_PASSWORD}

Demo Customers (shared password: DemoPass1!):
  C01  demo.cliente.pe.01@vianda.demo  (PE — Miraflores)
  C02  demo.cliente.pe.02@vianda.demo  (PE — Barranco)
  C03  demo.cliente.pe.03@vianda.demo  (PE — San Isidro)
  C04  demo.cliente.pe.04@vianda.demo  (PE — Surco)
  C05  demo.cliente.pe.05@vianda.demo  (PE — Jesus Maria)
  C06  demo.cliente.pe.06.no_plan@vianda.demo   (NO PLAN — show purchase flow)
  C07  demo.cliente.pe.07.no_orders@vianda.demo  (NO ORDERS — show ordering flow)
========================

NOTE: Re-running this loader on a previously-seeded DB will create duplicate
customers/subscriptions/orders. To reset:
  bash scripts/purge_demo_data.sh && bash scripts/load_demo_data.sh --target=${TARGET}
CREDS
)"

echo "${CREDS_BLOCK}"

# Write to .demo_credentials.local (gitignored)
echo "${CREDS_BLOCK}" > "${CREDENTIALS_FILE}"
echo ""
echo "Credentials also written to: ${CREDENTIALS_FILE}"
echo ""
echo "Demo data load complete. Happy demoing!"
