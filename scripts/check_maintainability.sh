#!/usr/bin/env bash
# Maintainability index gate — fails if MI drops >5% on any changed file.
#
# Compares the maintainability index (radon mi) of changed Python files
# between the current branch and origin/main. Flags files where MI
# drops more than 5 percentage points (e.g., 65 → 59 = 6pt drop = fail).
#
# Usage:
#   bash scripts/check_maintainability.sh
#
# Requires: radon (pip install radon>=5.1.0), python3

set -euo pipefail

MAX_DROP=5  # Percentage points

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
    echo "✔ No changed Python files to check (MI gate)"
    exit 0
fi

file_count=$(echo "$files" | wc -l | tr -d ' ')
echo "Maintainability index check on ${file_count} changed file(s) vs ${compare}"
echo "Max allowed drop: ${MAX_DROP} points"
echo "---"

failed=0
checked=0

while IFS= read -r filepath; do
    [ -z "$filepath" ] && continue

    # Get current MI (radon mi outputs: "file - A (score)")
    current_mi=$(radon mi "$filepath" -s 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)
    if [ -z "$current_mi" ]; then
        continue  # Skip files radon can't parse
    fi

    # Get baseline MI from the compare branch
    baseline_content=$(git show "${compare}:${filepath}" 2>/dev/null || echo "")
    if [ -z "$baseline_content" ]; then
        continue  # New file, no baseline to compare
    fi

    baseline_mi=$(echo "$baseline_content" | radon mi - -s 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)
    if [ -z "$baseline_mi" ]; then
        continue  # Baseline couldn't be parsed
    fi

    # Compare: fail if drop exceeds threshold
    drop=$(python3 -c "
base = float('${baseline_mi}')
curr = float('${current_mi}')
drop = base - curr
print(f'{drop:.1f}')
")

    exceeds=$(python3 -c "print('yes' if float('${drop}') > ${MAX_DROP} else 'no')")

    ((checked++))

    if [ "$exceeds" = "yes" ]; then
        echo "  ✘ ${filepath}: MI ${baseline_mi} → ${current_mi} (dropped ${drop} points)"
        ((failed++))
    fi
done <<< "$files"

echo ""
if [ "$failed" -gt 0 ]; then
    echo "✘ ${failed} file(s) dropped maintainability index by more than ${MAX_DROP} points."
    echo "  Refactor to improve readability/reduce complexity."
    exit 1
else
    echo "✔ ${checked} file(s) checked. No maintainability regression > ${MAX_DROP} points."
    exit 0
fi
