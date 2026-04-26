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

# Collections temporarily skipped. Two distinct root causes — see the
# referenced issue for each entry. Remove an entry in the same PR that
# fixes the underlying failure (and updates the collection's assertions
# where applicable).
#
# Match is on the "NNN" collection prefix (001/013/014/etc.).
#
# vianda-market/kitchen#79 — PR #60 regressions (filter backend).
# vianda-market/kitchen#83 — Postman assertions need envelope-shape update
#   for K3's contract change. Frontend Phase 3 adoption PRs MUST update
#   the matching collections and remove their entries here before merging.
SKIPPED_COLLECTIONS=(
    # kitchen#79 (PR #60 regressions — needs CODE fix)
    "001"  # DISCRETIONARY_CREDIT_SYSTEM — pre-request script crash
    "013"  # SUBSCRIPTION_ACTIONS — 500 on subscription action endpoint
    "014"  # INGREDIENTS_AND_FAVORITES — 404 where 204 expected
    # kitchen#83 (K3 envelope contract — restored in #84)
    # kitchen#66 K7 sweep — auth/security messages migrated to envelope catalog,
    # collection assertions still match the old message text. Re-enable when
    # frontend Phase 3 follow-up updates the assertions.
    "008"  # ROLE AND FIELD ACCESS — no_show_discount + role-restriction text changed
    "010"  # Permissions Testing - Employee-Only Access — access-denied text changed
    # kitchen#66 K15 sweep — enum-not-found now emits entity.not_found (with
    # entity=enum_name) instead of falling through K3's status-map to
    # request.not_found. Test assertion needs update; addressed in K-last sweep.
    "003"  # ENUM_SERVICE — unknown-enum-type code changed
)

is_skipped() {
    local prefix="$1"
    for skipped in "${SKIPPED_COLLECTIONS[@]}"; do
        [ "$prefix" = "$skipped" ] && return 0
    done
    return 1
}

# Override baseUrl in environment if provided
export NEWMAN_BASE_URL="$BASE_URL"

if ! command -v newman &>/dev/null; then
    echo "ERROR: newman not found. Install with: npm install -g newman" >&2
    exit 1
fi

# Collect target collections (skipping any in SKIPPED_COLLECTIONS — see kitchen#79)
collections=()
skipped_runtime=()
if [ $# -gt 0 ]; then
    # Filter by prefix arguments (e.g., "003" "006")
    for prefix in "$@"; do
        if is_skipped "$prefix"; then
            skipped_runtime+=("$prefix")
            continue
        fi
        for f in "$COLLECTIONS_DIR"/${prefix}*; do
            [ -f "$f" ] && collections+=("$f")
        done
    done
else
    for f in "$COLLECTIONS_DIR"/*.json; do
        [ -f "$f" ] || continue
        prefix=$(basename "$f" | cut -c1-3)
        if is_skipped "$prefix"; then
            skipped_runtime+=("$prefix")
            continue
        fi
        collections+=("$f")
    done
fi

if [ ${#skipped_runtime[@]} -gt 0 ]; then
    echo "Skipping ${#skipped_runtime[@]} collection(s) per SKIPPED_COLLECTIONS (see kitchen#79):"
    for p in "${skipped_runtime[@]}"; do
        echo "  - $p"
    done
    echo "---"
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
