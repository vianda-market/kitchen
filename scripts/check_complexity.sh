#!/usr/bin/env bash
# Check cyclomatic complexity of changed Python files.
#
# In CI (PR context): checks only files changed vs. base branch.
# Locally / push to main: checks all files.
#
# Fails if any function exceeds the threshold (default: 25, grade D).
# Existing high-complexity functions are listed in .complexity-baseline.txt
# and excluded from failure.
#
# Usage:
#   ./scripts/check_complexity.sh              # auto-detect mode
#   MAX_COMPLEXITY=15 ./scripts/check_complexity.sh  # custom threshold

set -euo pipefail

MAX_CC="${MAX_COMPLEXITY:-25}"
BASELINE_FILE=".complexity-baseline.txt"

# Determine which files to check
if [ -n "${GITHUB_BASE_REF:-}" ]; then
    # CI pull request — check changed files only
    files=$(git diff --name-only --diff-filter=ACMR "origin/${GITHUB_BASE_REF}...HEAD" -- '*.py' | grep -v '^app/tests/' || true)
    mode="PR (changed files vs ${GITHUB_BASE_REF})"
else
    # Local or push — check all
    files=$(find app/ -name '*.py' -not -path 'app/tests/*' | sort)
    mode="all files"
fi

if [ -z "$files" ]; then
    echo "No Python files to check ($mode)"
    exit 0
fi

echo "Complexity check ($mode), max allowed: $MAX_CC"
echo "---"

# Run radon on the files, show only functions exceeding threshold
violations=$(echo "$files" | xargs radon cc -s -n E 2>/dev/null || true)

if [ -z "$violations" ]; then
    echo "All functions within complexity limit."
    exit 0
fi

# Filter out baselined entries
new_violations=""
while IFS= read -r line; do
    # Skip empty lines and file headers (no leading spaces)
    if [ -z "$line" ]; then continue; fi
    if [[ ! "$line" =~ ^[[:space:]] ]]; then
        current_file="$line"
        continue
    fi

    # Extract function signature for baseline matching: "file:function_name"
    func_name=$(echo "$line" | sed -E 's/^[[:space:]]+[A-Z] [0-9]+:[0-9]+ ([^ ]+).*/\1/')
    baseline_key="${current_file}:${func_name}"

    if [ -f "$BASELINE_FILE" ] && grep -qF "$baseline_key" "$BASELINE_FILE"; then
        continue  # baselined, skip
    fi

    new_violations+="${current_file}"$'\n'"${line}"$'\n'
done <<< "$violations"

if [ -z "$new_violations" ]; then
    echo "All high-complexity functions are baselined."
    exit 0
fi

echo ""
echo "NEW high-complexity functions (not in baseline):"
echo "$new_violations"
echo ""
echo "To fix: refactor to reduce complexity below $MAX_CC."
echo "To baseline (temporary): add 'file.py:function_name' to $BASELINE_FILE"
exit 1
