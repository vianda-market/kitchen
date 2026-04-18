#!/usr/bin/env bash
# Dead-code gate via vulture — no-regression check.
#
# Compares current vulture output against .vulture-baseline.txt.
# Fails if NEW findings appear (lines in current but not in baseline).
# Removing baseline entries (fixing dead code) is always allowed.
#
# Usage:
#   bash scripts/check_vulture.sh              # enforce against baseline
#   bash scripts/check_vulture.sh --update     # regenerate baseline
#
# Requires: vulture (pip install vulture>=2.14)

set -euo pipefail

BASELINE=".vulture-baseline.txt"
MIN_CONFIDENCE=80
EXCLUDE="app/tests"

if [ "${1:-}" = "--update" ]; then
    vulture app/ --min-confidence "$MIN_CONFIDENCE" --exclude "$EXCLUDE" | sort > "$BASELINE"
    count=$(wc -l < "$BASELINE" | tr -d ' ')
    echo "✔ Baseline updated: $count finding(s) in $BASELINE"
    exit 0
fi

if [ ! -f "$BASELINE" ]; then
    echo "ERROR: $BASELINE not found. Run: bash scripts/check_vulture.sh --update"
    exit 1
fi

# Capture current findings
current=$(mktemp)
vulture app/ --min-confidence "$MIN_CONFIDENCE" --exclude "$EXCLUDE" | sort > "$current" || true

# Find NEW findings (in current but not in baseline)
new_findings=$(comm -23 "$current" "$BASELINE")

# Find FIXED findings (in baseline but not in current) — informational only
fixed=$(comm -23 "$BASELINE" "$current")

if [ -n "$fixed" ]; then
    fixed_count=$(echo "$fixed" | wc -l | tr -d ' ')
    echo "ℹ  $fixed_count baseline finding(s) fixed (nice!):"
    echo "$fixed"
    echo ""
fi

current_count=$(wc -l < "$current" | tr -d ' ')
baseline_count=$(wc -l < "$BASELINE" | tr -d ' ')

if [ -n "$new_findings" ]; then
    new_count=$(echo "$new_findings" | wc -l | tr -d ' ')
    echo "✘ $new_count NEW dead-code finding(s) — fix before merging:"
    echo "$new_findings"
    echo ""
    echo "Current: $current_count | Baseline: $baseline_count | New: $new_count"
    echo ""
    echo "If these are false positives, add them to $BASELINE (keep sorted)."
    rm -f "$current"
    exit 1
else
    echo "✔ No new dead code. Current: $current_count | Baseline: $baseline_count"
    rm -f "$current"
    exit 0
fi
