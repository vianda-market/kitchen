#!/usr/bin/env bash
# =============================================================================
# build_dev_db.sh — Dev full-rebuild wrapper
#
# This is the daily driver for local dev environments and the CI DB-reset
# workflow. It runs two steps in order:
#   1. bash app/db/build_kitchen_db.sh  — schema + reference data + dev
#      fixtures (the reusable primitive shared with future staging/prod
#      compositions; never modified by this wrapper).
#   2. bash scripts/load_demo_data.sh   — demo-day dataset: demo_baseline.sql
#      (Layer A) + 900 Newman collection (Layer B) + billing backfill (Layer C).
#
# After this script completes, the dev DB is fully populated: schema,
# reference data, dev fixtures, and all demo-day users, restaurants, plans,
# subscriptions, and order history. This matches the state the team expects
# during stakeholder demos and local development sessions.
#
# Targets:
#   --target=local    (default) — laptop API, PAYMENT_PROVIDER=mock,
#                                 confirms subscriptions via the kitchen
#                                 mock-confirm endpoint. Fast, offline.
#   --target=gcp-dev             — deployed GCP dev Cloud Run API + Cloud SQL,
#                                 confirms PaymentIntents via Stripe sandbox,
#                                 waits for Stripe webhook to activate
#                                 subscriptions. Used by db-reset-dev.yml.
#
# When to use:
#   - Setting up a new dev machine from scratch.
#   - Resetting the dev DB to a known-good state after local experiments.
#   - Before a demo: guarantees demo users, credentials, and order history exist.
#   - From CI (db-reset-dev.yml) with --target=gcp-dev to reset Cloud SQL +
#     load demo data via Stripe sandbox.
#
# When NOT to use:
#   - Applying incremental schema changes to a DB you want to keep — use
#     bash app/db/migrate.sh instead.
#   - Staging or production environments — demo data must never be loaded there.
#     build_kitchen_db.sh is the primitive for those compositions.
#   - Inside a worktree session — the worktree fast-path (TEMPLATE clone) in
#     build_kitchen_db.sh is not compatible with the demo loader's Newman run;
#     use the primary working tree for this script.
#
# PREREQUISITE — API must be running:
#   scripts/load_demo_data.sh (Layer B) runs Newman against the live kitchen
#   API. This script checks the health endpoint before delegating and will
#   fail fast with a clear message if the API is not reachable.
#
#   --target=local: start the API first (in a separate terminal):
#     bash scripts/run_dev_quiet.sh
#
#   The API requires PAYMENT_PROVIDER=mock for local demo loading. Set this in
#   your .env file before starting the API.
#
#   --target=gcp-dev: the CI workflow opens the IAP tunnel and sets all env
#   vars before calling this script. No local API startup needed.
#
# Usage (from repository root — required so \i app/db/... paths in psql resolve):
#   bash app/db/build_dev_db.sh                          # local target (default)
#   PAYMENT_PROVIDER=mock bash app/db/build_dev_db.sh    # local + explicit mock
#   bash app/db/build_dev_db.sh --target=gcp-dev         # GCP dev (CI use)
#
# Environment — local target:
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, PGPASSWORD — DB connection (default: local)
#   PAYMENT_PROVIDER  must be "mock" (enforced by load_demo_data.sh)
#   KITCHEN_API_PORT  API port (default: 8000)
#   KITCHEN_API_BASE  API base URL (default: http://localhost:${KITCHEN_API_PORT})
#   SKIP_PYTEST=1     Skip pytest after build_kitchen_db.sh (speeds up the run)
#   SKIP_POST_REBUILD_SYNC=1  Skip FX/holiday sync (useful when firewalled)
#   SKIP_GEOCODE_BACKFILL=1   Skip Mapbox geocode backfill
#
# Environment — gcp-dev target:
#   DB_HOST, DB_PORT, DB_NAME, DB_USER, PGPASSWORD — tunneled Cloud SQL connection
#   KITCHEN_API_BASE  deployed dev Cloud Run URL (https://...)
#   STRIPE_SECRET_KEY Stripe sandbox test key (sk_test_...)
#   SKIP_PYTEST=1, SKIP_POST_REBUILD_SYNC=1, SKIP_GEOCODE_BACKFILL=1 — same toggles
#
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
      sed -n '2,80p' "$0"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: ${arg}" >&2
      echo "Usage: $0 [--target=local|gcp-dev]" >&2
      exit 1
      ;;
  esac
done

case "${TARGET}" in
  local|gcp-dev) ;;
  *)
    echo "ERROR: --target must be 'local' or 'gcp-dev' (got: ${TARGET})" >&2
    exit 1
    ;;
esac

# ---------------------------------------------------------------------------
# Sanity: refuse to run in staging or production
# ---------------------------------------------------------------------------

ENV="${ENV:-dev}"
if [ "${ENV}" != "dev" ]; then
  echo "" >&2
  echo "ERROR: build_dev_db.sh is dev-only. ENV=${ENV} is not permitted." >&2
  echo "       Use build_kitchen_db.sh (without demo data) for other environments." >&2
  echo "" >&2
  exit 1
fi

DB_HOST="${DB_HOST:-localhost}"
case "${DB_HOST}" in
  *prod*|*staging*)
    echo "ERROR: build_dev_db.sh refuses to run against DB_HOST=${DB_HOST}." >&2
    echo "       Detected a staging or production host. Aborting." >&2
    exit 1
    ;;
esac

# ---------------------------------------------------------------------------
# Sanity: must be run from repository root so psql \i paths resolve
# ---------------------------------------------------------------------------

if [ ! -f "app/db/build_kitchen_db.sh" ]; then
  echo "" >&2
  echo "ERROR: build_dev_db.sh must be run from the repository root." >&2
  echo "       cd to the kitchen repo root, then:" >&2
  echo "         bash app/db/build_dev_db.sh" >&2
  echo "" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Prerequisite: API must be running (load_demo_data.sh requires it for Newman)
# Only checked for local target; for gcp-dev the loader validates its own
# KITCHEN_API_BASE and the deployed API must already be up.
# ---------------------------------------------------------------------------

if [ "${TARGET}" = "local" ]; then
  KITCHEN_API_PORT="${KITCHEN_API_PORT:-8000}"
  KITCHEN_API_BASE="${KITCHEN_API_BASE:-http://localhost:${KITCHEN_API_PORT}}"
  HEALTH_URL="${KITCHEN_API_BASE}/health"

  echo ""
  echo "[pre-check] Verifying kitchen API is reachable at ${HEALTH_URL}..."
  API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_URL}" 2>/dev/null || true)
  if [ "${API_STATUS}" != "200" ]; then
    echo "" >&2
    echo "ERROR: Kitchen API is not reachable (HTTP ${API_STATUS:-no response})." >&2
    echo "" >&2
    echo "  Start the API first (in a separate terminal):" >&2
    echo "    bash scripts/run_dev_quiet.sh" >&2
    echo "" >&2
    echo "  Your .env must have PAYMENT_PROVIDER=mock for local demo loading." >&2
    echo "" >&2
    exit 1
  fi
  echo "[pre-check] API is healthy (HTTP 200). Proceeding."
  echo ""
fi

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

echo ""
echo "=== BUILD DEV DB (target: ${TARGET}) ==="
echo "  step 1: build_kitchen_db.sh (schema + reference + dev fixtures)"
echo "  step 2: load_demo_data.sh   (demo-day data: SQL + Newman + billing)"
echo ""

# ---------------------------------------------------------------------------
# Step 1 — Primitive rebuild: schema + reference data + dev fixtures
# build_kitchen_db.sh picks up DB_HOST / DB_PORT / DB_USER / PGPASSWORD from
# the environment, so no explicit forwarding is needed — CI sets them before
# calling this wrapper.
# ---------------------------------------------------------------------------

echo "--- Step 1/2: build_kitchen_db.sh ---"
bash app/db/build_kitchen_db.sh
echo ""
echo "--- Step 1/2 complete ---"
echo ""

# ---------------------------------------------------------------------------
# Step 2 — Demo-day data: demo_baseline.sql + Newman 900 + billing backfill
# ---------------------------------------------------------------------------

echo "--- Step 2/2: load_demo_data.sh --target=${TARGET} ---"
bash scripts/load_demo_data.sh --target="${TARGET}"
echo ""
echo "--- Step 2/2 complete ---"
echo ""

# ---------------------------------------------------------------------------
# Final message
# ---------------------------------------------------------------------------

echo "======================================================================"
echo "Dev DB ready (target=${TARGET})."
echo "Schema + reference + dev fixtures + demo-day data all loaded."
echo ""
if [ "${TARGET}" = "local" ]; then
  echo "Credentials printed above and written to .demo_credentials.local"
  echo "(gitignored — do not commit)."
else
  echo "Credentials printed above (also written to .demo_credentials.local"
  echo "in the CI runner workspace — not persisted after the run)."
fi
echo "======================================================================"
