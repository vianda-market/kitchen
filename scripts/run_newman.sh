#!/usr/bin/env bash
# Run Postman collections via newman against a live server.
#
# Usage:
#   ./scripts/run_newman.sh                     # run all collections
#   ./scripts/run_newman.sh 003 006             # run only matching collections
#   NEWMAN_BASE_URL=http://host:8000 ./scripts/run_newman.sh
#
# Requires: newman (npm install -g newman)
# The server must already be running (or use CI workflow which starts it).

set -euo pipefail

COLLECTIONS_DIR="docs/postman/collections"
ENV_FILE="docs/postman/environments/ci.postman_environment.json"
BASE_URL="${NEWMAN_BASE_URL:-http://localhost:8000}"

# Override baseUrl in environment if provided
export NEWMAN_BASE_URL="$BASE_URL"

if ! command -v newman &>/dev/null; then
    echo "ERROR: newman not found. Install with: npm install -g newman" >&2
    exit 1
fi

# Collect target collections
collections=()
if [ $# -gt 0 ]; then
    # Filter by prefix arguments (e.g., "003" "006")
    for prefix in "$@"; do
        for f in "$COLLECTIONS_DIR"/${prefix}*; do
            [ -f "$f" ] && collections+=("$f")
        done
    done
else
    for f in "$COLLECTIONS_DIR"/*.json; do
        [ -f "$f" ] && collections+=("$f")
    done
fi

if [ ${#collections[@]} -eq 0 ]; then
    echo "No collections found." >&2
    exit 1
fi

echo "Running ${#collections[@]} collection(s) against $BASE_URL"
echo "---"

failed=0
passed=0
failed_names=()
passed_names=()

for collection in "${collections[@]}"; do
    name=$(basename "$collection" .json | sed 's/.postman_collection//')
    echo ""
    echo "=== $name ==="

    if newman run "$collection" \
        --environment "$ENV_FILE" \
        --env-var "baseUrl=$BASE_URL" \
        --bail \
        --color on \
        --reporters cli \
        --timeout-request 10000; then
        passed=$((passed + 1))
        passed_names+=("$name")
    else
        failed=$((failed + 1))
        failed_names+=("$name")
        echo "FAILED: $name"
    fi
done

echo ""
echo "============================================"
echo "  NEWMAN SUMMARY"
echo "============================================"
echo "  Total: ${#collections[@]} | Passed: $passed | Failed: $failed"
echo ""

if [ "$passed" -gt 0 ]; then
    echo "  ✅ Passed:"
    for n in "${passed_names[@]}"; do
        echo "     $n"
    done
fi

if [ "$failed" -gt 0 ]; then
    echo ""
    echo "  ❌ Failed:"
    for n in "${failed_names[@]}"; do
        echo "     $n"
    done
fi

echo "============================================"

[ "$failed" -eq 0 ]
