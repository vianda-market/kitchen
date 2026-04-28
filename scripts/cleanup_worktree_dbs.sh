#!/usr/bin/env bash
# scripts/cleanup_worktree_dbs.sh — drop per-worktree Postgres databases whose
# worktree no longer exists.
#
# Run this periodically when worktrees pile up (e.g. after closing a wave of
# parallel agent sessions). Not automatic on session end — that would require
# a Git Stop hook wired per worktree; run manually or on a schedule instead.
#
# USAGE
#   bash scripts/cleanup_worktree_dbs.sh           # dry-run: list orphans
#   bash scripts/cleanup_worktree_dbs.sh --execute  # drop orphan DBs
#
# SAFE TO RUN ANY TIME — idempotent. Only drops DBs of the pattern
# kitchen_<6hex> where no matching worktree path exists. The main `kitchen`
# database and `kitchen_template` are never touched.
#
# REFERENCES
#   Issue #199 — Postgres TEMPLATE-clone pattern for per-worktree DB cold-start.
#   Issue #197 — KITCHEN_DB_NAME derivation (worktree_env.sh).

set -euo pipefail

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-cdeachaval}"
EXECUTE=0

for arg in "$@"; do
  case "$arg" in
    --execute) EXECUTE=1 ;;
    *) echo "cleanup_worktree_dbs: unknown argument '$arg'" >&2; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Collect active worktree hashes
# ---------------------------------------------------------------------------
# git worktree list outputs lines like:
#   /path/to/worktree  <sha>  [branch]
# Extract just the paths, then compute the same 6-char hash that
# worktree_env.sh would produce, and collect into a set.
declare -A ACTIVE_HASHES
while IFS= read -r wt_line; do
  wt_path=$(echo "${wt_line}" | awk '{print $1}')
  hash=$(printf '%s' "${wt_path}" | shasum | cut -c1-6)
  ACTIVE_HASHES["${hash}"]=1
done < <(git worktree list 2>/dev/null || true)

# ---------------------------------------------------------------------------
# Collect kitchen_* clone DBs (exclude kitchen and kitchen_template)
# ---------------------------------------------------------------------------
CLONE_DBS=$(psql \
  -h "${DB_HOST}" \
  -p "${DB_PORT}" \
  -U "${DB_USER}" \
  -d postgres \
  -tAX \
  -c "SELECT datname FROM pg_database
      WHERE datname ~ '^kitchen_[0-9a-f]{6}$';" 2>/dev/null || true)

if [ -z "${CLONE_DBS}" ]; then
  echo "cleanup_worktree_dbs: no kitchen_<hash> clone DBs found."
  exit 0
fi

ORPHAN_COUNT=0
for db in ${CLONE_DBS}; do
  # Extract the 6-char hash from the DB name (kitchen_<hash>).
  hash="${db#kitchen_}"
  if [ "${ACTIVE_HASHES[${hash}]+_}" ]; then
    echo "  KEEP  ${db}  (active worktree)"
  else
    ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
    if [ "${EXECUTE}" -eq 1 ]; then
      echo "  DROP  ${db}  (no matching worktree)"
      psql \
        -h "${DB_HOST}" \
        -p "${DB_PORT}" \
        -U "${DB_USER}" \
        -d postgres \
        -q -X \
        -c "DROP DATABASE IF EXISTS \"${db}\";" || {
          echo "  WARNING: could not drop ${db} (connections open?)" >&2
        }
    else
      echo "  ORPHAN  ${db}  (no matching worktree — would be dropped with --execute)"
    fi
  fi
done

if [ "${ORPHAN_COUNT}" -eq 0 ]; then
  echo "cleanup_worktree_dbs: no orphan DBs found."
elif [ "${EXECUTE}" -eq 0 ]; then
  echo ""
  echo "cleanup_worktree_dbs: ${ORPHAN_COUNT} orphan(s) found."
  echo "  Rerun with --execute to drop them."
else
  echo ""
  echo "cleanup_worktree_dbs: dropped ${ORPHAN_COUNT} orphan DB(s)."
fi
