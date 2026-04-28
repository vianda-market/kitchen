#!/usr/bin/env bash
# scripts/worktree_env.sh — derive a unique API port + DB name from $PWD.
#
# PURPOSE
#   When two kitchen agents run in parallel (each in a separate git worktree),
#   they share the same host Postgres instance and network stack. Without unique
#   port + DB per worktree, both APIs bind :8000 and both operate on the same
#   "kitchen" database, causing port conflicts and DB cross-contamination.
#
#   Sourcing this script before starting uvicorn / building the DB sets unique
#   env vars derived deterministically from $PWD so each worktree claims its
#   own slice of the host resources.
#
# USAGE
#   # Option A — source manually before starting the API or building the DB:
#   source scripts/worktree_env.sh
#   bash app/db/build_kitchen_db.sh
#   bash run_dev_quiet.sh
#   ./scripts/run_newman.sh 000
#
#   # Option B — scripts/verify.sh auto-sources this file when $PWD matches
#   # */.claude/worktrees/* so no manual step is needed for agent dispatches.
#
# DERIVATION CONTRACT
#   1. SHA1-hash $PWD, take first 6 hex chars → WORKTREE_HASH
#   2. First 4 hex chars as a number mod 1000 → PORT_OFFSET (0–999)
#   3. KITCHEN_API_PORT = 8000 + PORT_OFFSET  (range: 8000–8999)
#   4. KITCHEN_DB_NAME  = "kitchen_${WORKTREE_HASH}"
#   5. NEWMAN_BASE_URL  = "http://localhost:${KITCHEN_API_PORT}"
#
#   The main working tree (no worktree) never sources this script; its values
#   stay at the defaults (port 8000, DB "kitchen") — human dev unchanged.
#
# POSTGRES PREREQUISITE
#   Creating a new DB per worktree requires the dev Postgres user to have
#   CREATEDB privilege. One-time grant (run as superuser):
#     ALTER USER <your_db_user> CREATEDB;
#   If the user lacks CREATEDB, build_kitchen_db.sh will fail with:
#     "ERROR: permission denied to create database"
#   Fix: run the ALTER USER above once, then retry.
#
# COLLISION PROBABILITY
#   6 hex chars = 16,777,216 distinct hashes. Two worktrees with the same
#   6-char prefix collide on port and DB; probability with N worktrees is
#   N*(N-1)/2 / 16M. For N=10 that is ~3-in-a-million. Acceptable.

WORKTREE_HASH=$(printf '%s' "$PWD" | shasum | cut -c1-6)
PORT_OFFSET=$(( 16#${WORKTREE_HASH:0:4} % 1000 ))

export KITCHEN_API_PORT=$(( 8000 + PORT_OFFSET ))
export KITCHEN_DB_NAME="kitchen_${WORKTREE_HASH}"
export NEWMAN_BASE_URL="http://localhost:${KITCHEN_API_PORT}"

echo "worktree_env: port=${KITCHEN_API_PORT}  db=${KITCHEN_DB_NAME}  base_url=${NEWMAN_BASE_URL}"

# Ensure kitchen_template is current before any worktree DB clone.
# This is a no-op when the migration + seed fingerprint is unchanged (~0.1s).
# When migrations or seed change, it rebuilds the template (~30s) so the next
# clone reflects the new schema — downstream API syncs run ONCE here, not
# per worktree.
#
# To force a refresh (e.g. after upstream currency rates change):
#   bash scripts/refresh_db_template.sh --force
#
# Reference: issue #199
if [ -f "scripts/refresh_db_template.sh" ]; then
  bash scripts/refresh_db_template.sh
fi
