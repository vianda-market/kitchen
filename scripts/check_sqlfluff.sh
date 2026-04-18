#!/usr/bin/env bash
# SQL lint gate — enforces sqlfluff on new migration files only.
#
# Existing files are baselined in .sqlfluff-baseline.txt (one path per line).
# New migrations not in the baseline must pass sqlfluff lint.
# schema.sql is baselined (170KB, too large to retroactively clean).
#
# Usage:
#   bash scripts/check_sqlfluff.sh
#
# Requires: sqlfluff (pip install sqlfluff)

set -euo pipefail

BASELINE=".sqlfluff-baseline.txt"
MIGRATIONS_DIR="app/db/migrations"
SCHEMA_FILE="app/db/schema.sql"

# Collect all SQL files to check
files=()
for f in "$MIGRATIONS_DIR"/*.sql "$SCHEMA_FILE"; do
    [ -f "$f" ] || continue
    # Skip baselined files
    if [ -f "$BASELINE" ] && grep -qxF "$f" "$BASELINE"; then
        continue
    fi
    files+=("$f")
done

if [ ${#files[@]} -eq 0 ]; then
    echo "✔ No new SQL files to lint (all baselined or no migrations)"
    exit 0
fi

echo "Linting ${#files[@]} new SQL file(s) with sqlfluff..."
echo "---"

failed=0
for f in "${files[@]}"; do
    echo "  → $f"
    if ! sqlfluff lint "$f" --dialect postgres 2>&1; then
        ((failed++))
    fi
done

if [ "$failed" -gt 0 ]; then
    echo ""
    echo "✘ $failed file(s) have sqlfluff violations."
    echo "Fix with: sqlfluff fix <file> --dialect postgres"
    echo "Or baseline: add the file path to $BASELINE"
    exit 1
else
    echo ""
    echo "✔ All new SQL files pass sqlfluff."
    exit 0
fi
