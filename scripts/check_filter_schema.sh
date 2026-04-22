#!/usr/bin/env bash
# Verify that docs/api/filters.json is in sync with the current FILTER_REGISTRY.
#
# Runs the generator into a temp file and diffs against the committed JSON.
# Exits 1 if the files differ, so CI fails and contributors know to re-run
# the generator before pushing.
#
# Usage (local):
#   bash scripts/check_filter_schema.sh
#
# Usage (CI):
#   bash scripts/check_filter_schema.sh
#
# To regenerate:
#   python3 scripts/generate_filter_schema.py

set -euo pipefail

COMMITTED="docs/api/filters.json"
TMPFILE=$(mktemp /tmp/filters_generated_XXXXXX.json)

cleanup() {
    rm -f "$TMPFILE"
}
trap cleanup EXIT

echo "Generating filter schema into temp file..."
python3 - <<'PYEOF' > "$TMPFILE"
import sys, json
sys.path.insert(0, '.')
from scripts.generate_filter_schema import build_schema, _schema_to_json
sys.stdout.write(_schema_to_json(build_schema()))
PYEOF

if diff -u "$COMMITTED" "$TMPFILE"; then
    echo ""
    echo "docs/api/filters.json is up to date."
    exit 0
else
    echo ""
    echo "ERROR: docs/api/filters.json is out of sync with FILTER_REGISTRY."
    echo "Run: python3 scripts/generate_filter_schema.py"
    echo "Then stage the updated filters.json before committing."
    exit 1
fi
