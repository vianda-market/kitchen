#!/bin/bash
# postman_import.sh — Push local Postman collection files to Christian's Workspace
# Usage: bash scripts/postman_import.sh -all
#        bash scripts/postman_import.sh 002 003 010

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COLLECTIONS_DIR="$PROJECT_DIR/docs/postman/collections"
WORKSPACE_ID="9f0af08e-1d55-4a46-8ee2-9e8a8101260c"
API_BASE="https://api.getpostman.com"

# Load API key from .env
if [ -f "$PROJECT_DIR/.env" ]; then
    POSTMAN_API_KEY=$(grep -E '^POSTMAN_API_KEY=' "$PROJECT_DIR/.env" | cut -d'=' -f2-)
fi

if [ -z "$POSTMAN_API_KEY" ]; then
    echo "Error: POSTMAN_API_KEY not found in .env"
    exit 1
fi

# Parse arguments
if [ $# -eq 0 ]; then
    echo "Usage: bash scripts/postman_import.sh -all"
    echo "       bash scripts/postman_import.sh 002 003 010"
    exit 1
fi

if [ "$1" = "-all" ]; then
    PREFIXES=$(ls "$COLLECTIONS_DIR"/*.json 2>/dev/null | sed 's/.*\///' | grep -oE '^[0-9]+' | sort -u)
else
    PREFIXES="$@"
fi

# Fetch remote collections in workspace (once)
echo "Fetching remote collections from Christian's Workspace..."
REMOTE_JSON=$(curl -s -H "X-Api-Key: $POSTMAN_API_KEY" "$API_BASE/collections?workspace=$WORKSPACE_ID")

find_collection_uid() {
    local prefix="$1"
    echo "$REMOTE_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for c in data.get('collections', []):
    if c['name'].startswith('$prefix'):
        print(c['uid'])
        break
" 2>/dev/null
}

find_local_file() {
    local prefix="$1"
    ls "$COLLECTIONS_DIR"/${prefix}*.json 2>/dev/null | head -1
}

create_collection() {
    local file="$1"
    local name
    name=$(basename "$file")

    echo "  Creating: $name"

    local tmpfile
    tmpfile=$(mktemp)

    python3 -c "
import json
with open('$file') as f:
    coll = json.load(f)
if 'info' in coll:
    coll['info']['schema'] = 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'
with open('$tmpfile', 'w') as f:
    json.dump({'collection': coll}, f)
"

    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST \
        -H "X-Api-Key: $POSTMAN_API_KEY" \
        -H "Content-Type: application/json" \
        -d @"$tmpfile" \
        "$API_BASE/collections?workspace=$WORKSPACE_ID")

    rm -f "$tmpfile"

    if [ "$http_code" = "200" ]; then
        echo "    OK (created)"
    else
        echo "    FAILED (HTTP $http_code)"
        return 1
    fi
}

push_collection() {
    local uid="$1"
    local file="$2"
    local name
    name=$(basename "$file")

    echo "  Pushing: $name"

    local tmpfile
    tmpfile=$(mktemp)

    # Wrap in API format and ensure v2.1.0 schema
    python3 -c "
import json
with open('$file') as f:
    coll = json.load(f)
if 'info' in coll:
    coll['info']['schema'] = 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'
with open('$tmpfile', 'w') as f:
    json.dump({'collection': coll}, f)
"

    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -X PUT \
        -H "X-Api-Key: $POSTMAN_API_KEY" \
        -H "Content-Type: application/json" \
        -d @"$tmpfile" \
        "$API_BASE/collections/$uid")

    rm -f "$tmpfile"

    if [ "$http_code" = "200" ]; then
        echo "    OK (HTTP 200)"
    else
        echo "    FAILED (HTTP $http_code)"
        return 1
    fi
}

# Process each prefix
FAILED=0
PUSHED=0

for prefix in $PREFIXES; do
    local_file=$(find_local_file "$prefix")
    if [ -z "$local_file" ]; then
        echo "  Skip: no local file for prefix $prefix"
        continue
    fi

    uid=$(find_collection_uid "$prefix")
    if [ -z "$uid" ]; then
        echo "  Creating new collection for prefix $prefix..."
        if create_collection "$local_file"; then
            PUSHED=$((PUSHED + 1))
        else
            FAILED=$((FAILED + 1))
        fi
        continue
    fi

    if push_collection "$uid" "$local_file"; then
        PUSHED=$((PUSHED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "Done: $PUSHED pushed, $FAILED failed."
