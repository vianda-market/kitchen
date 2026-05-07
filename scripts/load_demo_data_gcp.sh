#!/usr/bin/env bash
# =============================================================================
# load_demo_data_gcp.sh — Convenience wrapper that loads demo data against the
# deployed GCP dev environment, fetching everything from gcloud + Secret Manager
# so you don't have to assemble env vars by hand.
#
# Usage (from kitchen repo root):
#
#   bash scripts/load_demo_data_gcp.sh             # load demo data
#   bash scripts/load_demo_data_gcp.sh --purge     # purge first, then reload
#   bash scripts/load_demo_data_gcp.sh --purge-only
#
# Prerequisites (one-time):
#   1. gcloud SDK installed and authenticated:  gcloud auth login
#   2. cloud-sql-proxy installed:
#        brew install cloud-sql-proxy
#      (or download from https://cloud.google.com/sql/docs/postgres/sql-proxy)
#   3. newman installed:                         npm install -g newman
#
# What this script does:
#   1. Discovers project / region / Cloud Run URL / Cloud SQL instance from gcloud.
#   2. Starts cloud-sql-proxy in the background on 127.0.0.1:5433 (cleaned up on exit).
#   3. Pulls STRIPE_SECRET_KEY (sk_test_…) from Secret Manager.
#   4. Pulls dev DB password by reading the database URL secret and parsing it.
#   5. Execs scripts/load_demo_data.sh --target=gcp-dev with everything pre-set.
#
# Naming conventions are derived from infra-kitchen-gcp (see src/components/
# backend.py and database.py): vianda-${STACK}-api, vianda-${STACK}-postgres,
# vianda-${STACK}-stripe-secret-key, vianda-${STACK}-database-url.
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Defaults — override via env or flags
# -----------------------------------------------------------------------------

STACK="${STACK:-dev}"                                # never set this to staging/prod
PROXY_PORT="${PROXY_PORT:-5433}"                      # local port the proxy binds to
REGION_DEFAULT="us-central1"                          # most common; overridden by gcloud config or --region

DO_PURGE=0
PURGE_ONLY=0
for arg in "$@"; do
  case "${arg}" in
    --purge)       DO_PURGE=1 ;;
    --purge-only)  PURGE_ONLY=1 ;;
    --stack=*)     STACK="${arg#--stack=}" ;;
    --region=*)    REGION_DEFAULT="${arg#--region=}" ;;
    --proxy-port=*) PROXY_PORT="${arg#--proxy-port=}" ;;
    --help|-h)     sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "ERROR: unknown argument: ${arg}"; echo "Run with --help for usage."; exit 1 ;;
  esac
done

case "${STACK}" in
  dev) ;;
  staging|prod)
    echo "ERROR: this wrapper refuses --stack=${STACK}. Demo data is dev-only."
    exit 1
    ;;
  *)
    echo "WARNING: --stack=${STACK} is unusual; expected 'dev'. Continuing."
    ;;
esac

# -----------------------------------------------------------------------------
# Tool checks
# -----------------------------------------------------------------------------

for tool in gcloud cloud-sql-proxy newman psql; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "ERROR: ${tool} not found in PATH. See header for install commands."
    exit 1
  fi
done

# -----------------------------------------------------------------------------
# gcloud discovery
# -----------------------------------------------------------------------------

PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
if [ -z "${PROJECT}" ]; then
  echo "ERROR: no gcloud project configured. Run: gcloud config set project <id>"
  exit 1
fi

# Confirm project name smells like dev
case "${PROJECT}" in
  *prod*|*staging*)
    echo "ERROR: gcloud project=${PROJECT} smells like prod/staging. Refusing."
    exit 1
    ;;
esac

ACCOUNT="$(gcloud config get-value account 2>/dev/null || echo unknown)"

echo "=== gcloud context ==="
echo "  account: ${ACCOUNT}"
echo "  project: ${PROJECT}"
echo "  stack:   ${STACK}"
echo ""

# Region: resolve from the kitchen Cloud Run service. Prefer scanning all
# regions over guessing (Cloud Run regional descriptions only work if you
# already know the region).
echo "Discovering Cloud Run region for vianda-${STACK}-api..."
REGION="$(
  gcloud run services list \
    --project="${PROJECT}" \
    --filter="metadata.name=vianda-${STACK}-api" \
    --format="value(metadata.namespace,REGION)" 2>/dev/null \
  | awk 'NR==1 {print $NF}'
)"
if [ -z "${REGION}" ]; then
  REGION="${REGION_DEFAULT}"
  echo "  fallback region: ${REGION}"
fi

# Cloud Run URL
KITCHEN_API_BASE="$(
  gcloud run services describe "vianda-${STACK}-api" \
    --project="${PROJECT}" \
    --region="${REGION}" \
    --format='value(status.url)' 2>/dev/null
)"
if [ -z "${KITCHEN_API_BASE}" ]; then
  echo "ERROR: could not resolve Cloud Run URL for vianda-${STACK}-api in ${REGION}."
  echo "       Override with --region=<region>, or check 'gcloud run services list --project=${PROJECT}'."
  exit 1
fi
case "${KITCHEN_API_BASE}" in https://*) ;; *) echo "ERROR: API URL is not https: ${KITCHEN_API_BASE}"; exit 1 ;; esac

# Cloud SQL connection name (project:region:instance)
SQL_CONNECTION_NAME="$(
  gcloud sql instances describe "vianda-${STACK}-postgres" \
    --project="${PROJECT}" \
    --format='value(connectionName)' 2>/dev/null
)"
if [ -z "${SQL_CONNECTION_NAME}" ]; then
  echo "ERROR: could not resolve Cloud SQL instance vianda-${STACK}-postgres."
  exit 1
fi

echo "  cloud run URL:        ${KITCHEN_API_BASE}"
echo "  cloud sql instance:   ${SQL_CONNECTION_NAME}"
echo "  proxy port:           127.0.0.1:${PROXY_PORT}"
echo ""

# -----------------------------------------------------------------------------
# Pull secrets
# -----------------------------------------------------------------------------

echo "Pulling secrets from Secret Manager..."

STRIPE_SECRET_KEY="$(
  gcloud secrets versions access latest \
    --project="${PROJECT}" \
    --secret="vianda-${STACK}-stripe-secret-key" 2>/dev/null
)"
if [ -z "${STRIPE_SECRET_KEY}" ]; then
  echo "ERROR: could not read vianda-${STACK}-stripe-secret-key. Check IAM."
  exit 1
fi
case "${STRIPE_SECRET_KEY}" in
  sk_test_*) ;;
  sk_live_*) echo "ERROR: vianda-${STACK}-stripe-secret-key is a LIVE key. Refusing — demo seeding must use sandbox."; exit 1 ;;
  *) echo "WARNING: stripe key doesn't look like sk_test_…; continuing." ;;
esac

# DB URL secret holds postgresql://kitchen_app:<password>@<private-ip>/kitchen.
# We only need the password — the proxy gives us host/port, the DB name and
# user are constants from infra (see database.py: db_name='kitchen', db_user='kitchen_app').
DB_URL="$(
  gcloud secrets versions access latest \
    --project="${PROJECT}" \
    --secret="vianda-${STACK}-database-url" 2>/dev/null
)"
if [ -z "${DB_URL}" ]; then
  echo "ERROR: could not read vianda-${STACK}-database-url. Check IAM."
  exit 1
fi
# Parse password between : and @ in postgresql://user:password@host/db
PGPASSWORD="$(
  printf '%s' "${DB_URL}" | sed -E 's|^postgresql://[^:]+:([^@]+)@.*$|\1|'
)"
if [ -z "${PGPASSWORD}" ] || [ "${PGPASSWORD}" = "${DB_URL}" ]; then
  echo "ERROR: could not parse password from vianda-${STACK}-database-url."
  exit 1
fi
export PGPASSWORD

DB_NAME="kitchen"
DB_USER="kitchen_app"

echo "  stripe secret:        sk_test_… (loaded)"
echo "  db credentials:       loaded for ${DB_USER}@${DB_NAME}"
echo ""

# -----------------------------------------------------------------------------
# Start cloud-sql-proxy in background (trap to clean up on any exit)
# -----------------------------------------------------------------------------

PROXY_LOG="$(mktemp -t cloud-sql-proxy.XXXXXX.log)"
echo "Starting cloud-sql-proxy → 127.0.0.1:${PROXY_PORT} (log: ${PROXY_LOG})..."

cloud-sql-proxy "${SQL_CONNECTION_NAME}" \
  --port="${PROXY_PORT}" \
  > "${PROXY_LOG}" 2>&1 &
PROXY_PID=$!

cleanup() {
  if kill -0 "${PROXY_PID}" 2>/dev/null; then
    kill "${PROXY_PID}" 2>/dev/null || true
    wait "${PROXY_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Wait up to 15s for proxy to be ready
for _ in $(seq 1 30); do
  if pg_isready -h 127.0.0.1 -p "${PROXY_PORT}" -U "${DB_USER}" >/dev/null 2>&1; then
    echo "  proxy ready."
    break
  fi
  sleep 0.5
done
if ! pg_isready -h 127.0.0.1 -p "${PROXY_PORT}" -U "${DB_USER}" >/dev/null 2>&1; then
  echo "ERROR: cloud-sql-proxy did not become ready. Tail of log:"
  tail -20 "${PROXY_LOG}"
  exit 1
fi
echo ""

# -----------------------------------------------------------------------------
# Optional purge first
# -----------------------------------------------------------------------------

if [ "${DO_PURGE}" -eq 1 ] || [ "${PURGE_ONLY}" -eq 1 ]; then
  echo "=== Purging demo data on ${PROJECT} ==="
  ENV=dev \
  DB_HOST=127.0.0.1 DB_PORT="${PROXY_PORT}" \
  DB_NAME="${DB_NAME}" DB_USER="${DB_USER}" \
  bash scripts/purge_demo_data.sh
  echo ""
fi

if [ "${PURGE_ONLY}" -eq 1 ]; then
  echo "Purge-only mode complete. Exiting."
  exit 0
fi

# -----------------------------------------------------------------------------
# Hand off to load_demo_data.sh --target=gcp-dev
# -----------------------------------------------------------------------------

echo "=== Loading demo data on ${PROJECT} ==="
ENV=dev \
KITCHEN_API_BASE="${KITCHEN_API_BASE}" \
STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY}" \
DB_HOST=127.0.0.1 DB_PORT="${PROXY_PORT}" \
DB_NAME="${DB_NAME}" DB_USER="${DB_USER}" \
bash scripts/load_demo_data.sh --target=gcp-dev
