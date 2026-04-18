#!/usr/bin/env bash
# Strict complexity check on files CHANGED vs origin/main.
#
# Fails if any function in a changed file has CC > 15 (grade D or worse)
# unless that function is already baselined in .complexity-baseline.txt.
#
# This is a tighter gate than check_complexity.sh (CC ≤ 25 repo-wide).
# The idea: existing complexity is tracked via baseline, but NEW or MODIFIED
# code must stay below CC 15.
#
# Usage:
#   bash scripts/check_complexity_strict.sh
#
# Local equivalent (same thing CI runs):
#   bash scripts/check_complexity_strict.sh
#
# Requires: radon (pip install radon>=5.1.0)

set -euo pipefail

STRICT_CC=15
BASELINE_FILE=".complexity-baseline.txt"

# Determine compare branch
if [ -n "${GITHUB_BASE_REF:-}" ]; then
    compare="origin/${GITHUB_BASE_REF}"
else
    compare="origin/main"
fi

# Get changed Python files (excluding tests)
files=$(git diff --name-only --diff-filter=ACMR "${compare}...HEAD" -- '*.py' 2>/dev/null \
    | grep -v '^app/tests/' || true)

if [ -z "$files" ]; then
    echo "✔ No changed Python files to check (strict CC ≤ ${STRICT_CC})"
    exit 0
fi

file_count=$(echo "$files" | wc -l | tr -d ' ')
echo "Strict complexity check (CC ≤ ${STRICT_CC}) on ${file_count} changed file(s) vs ${compare}"
echo "---"

# Run radon — show grade D (16-20), E (21-25), F (26+)
violations=$(echo "$files" | xargs radon cc -s -n D 2>/dev/null || true)

if [ -z "$violations" ]; then
    echo "✔ All functions in changed files are CC ≤ ${STRICT_CC}"
    exit 0
fi

# Filter out baselined entries (same format as check_complexity.sh)
new_violations=""
current_file=""
while IFS= read -r line; do
    if [ -z "$line" ]; then continue; fi
    if [[ ! "$line" =~ ^[[:space:]] ]]; then
        current_file="$line"
        continue
    fi

    # Extract function name for baseline matching: "file:function_name"
    func_name=$(echo "$line" | sed -E 's/^[[:space:]]+[A-Z] [0-9]+:[0-9]+ ([^ ]+).*/\1/')
    baseline_key="${current_file}:${func_name}"

    if [ -f "$BASELINE_FILE" ] && grep -qF "$baseline_key" "$BASELINE_FILE"; then
        continue  # baselined, skip
    fi

    new_violations+="${current_file}"$'\n'"${line}"$'\n'
done <<< "$violations"

if [ -z "$new_violations" ]; then
    echo "✔ All high-complexity functions in changed files are baselined."
    exit 0
fi

echo ""
echo "✘ Functions in changed files exceed CC ${STRICT_CC} (not baselined):"
echo "$new_violations"
echo ""
echo "To fix: refactor to reduce complexity to ${STRICT_CC} or below."
echo "If this is pre-existing complexity you didn't introduce, add"
echo "'file.py:function_name' to ${BASELINE_FILE} (keep sorted)."
exit 1
