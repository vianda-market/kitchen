#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Run all Postman collections (000–016) sequentially via Newman.
# Collections are self-contained — no environment file needed.
# Requires: Node.js + newman (installed automatically if missing).
#
# Usage:
#   bash app/tests/run_postman_collections.sh              # stop on first failure
#   bash app/tests/run_postman_collections.sh --continue   # run all, report at end
#   bash app/tests/run_postman_collections.sh --from 005   # start from collection 005
# =============================================================================

COLLECTIONS_DIR="$(cd "$(dirname "$0")/../../docs/postman/collections" && pwd)"
BASE_URL="${BASE_URL:-http://localhost:8000}"

# Parse flags
CONTINUE_ON_FAIL=false
START_FROM=""
for arg in "$@"; do
  case "$arg" in
    --continue) CONTINUE_ON_FAIL=true ;;
    --from)     shift; START_FROM="$1" ;;
    --from=*)   START_FROM="${arg#--from=}" ;;
  esac
done

# Ensure newman is available
if ! command -v newman &>/dev/null; then
  echo "newman not found. Installing globally via npm..."
  npm install -g newman
  if ! command -v newman &>/dev/null; then
    echo "ERROR: newman installation failed. Install manually: npm install -g newman"
    exit 1
  fi
fi

echo "========================================="
echo "Postman Collection Runner"
echo "========================================="
echo "Base URL:    $BASE_URL"
echo "Collections: $COLLECTIONS_DIR"
echo "Mode:        $([ "$CONTINUE_ON_FAIL" = true ] && echo 'run all (--continue)' || echo 'stop on first failure')"
[ -n "$START_FROM" ] && echo "Start from:  $START_FROM"
echo "========================================="
echo ""

# Ordered list of collections (filename sort = numeric order 000–016)
PASSED=0
FAILED=0
SKIPPED=0
FAILURES=""
STARTED=false

if [ -z "$START_FROM" ]; then
  STARTED=true
fi

for collection in "$COLLECTIONS_DIR"/*.json; do
  filename="$(basename "$collection")"
  # Extract collection number (first 3 chars)
  num="${filename:0:3}"

  # --from: skip until we reach the target
  if [ "$STARTED" = false ]; then
    if [[ "$filename" == *"$START_FROM"* ]] || [[ "$num" == "$START_FROM" ]]; then
      STARTED=true
    else
      SKIPPED=$((SKIPPED + 1))
      continue
    fi
  fi

  echo "─────────────────────────────────────────"
  echo "▶ $filename"
  echo "─────────────────────────────────────────"

  if newman run "$collection" \
    --env-var "baseUrl=$BASE_URL" \
    --timeout-request 30000 \
    --color on \
    --reporters cli; then
    echo "✅ PASSED: $filename"
    PASSED=$((PASSED + 1))
  else
    echo "❌ FAILED: $filename"
    FAILED=$((FAILED + 1))
    FAILURES="$FAILURES\n  ❌ $filename"
    if [ "$CONTINUE_ON_FAIL" = false ]; then
      echo ""
      echo "Stopping on first failure. Use --continue to run all."
      break
    fi
  fi
  echo ""
done

# Summary
echo ""
echo "========================================="
echo "SUMMARY"
echo "========================================="
echo "  ✅ Passed:  $PASSED"
echo "  ❌ Failed:  $FAILED"
[ "$SKIPPED" -gt 0 ] && echo "  ⏭  Skipped: $SKIPPED"
if [ -n "$FAILURES" ]; then
  echo ""
  echo "Failed collections:"
  echo -e "$FAILURES"
fi
echo "========================================="

# Exit code: 0 if all passed, 1 if any failed
[ "$FAILED" -eq 0 ]
