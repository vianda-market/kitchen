#!/usr/bin/env bash
set -euo pipefail

# Bind to all interfaces - devices on LAN can reach the backend.
# Use on trusted networks only (home, office).
# For untrusted networks (plane, cafe, airport), use run_dev_untrusted.sh instead.
#
# Env vars (optional — defaults suit human dev; set for parallel worktree runs):
#   KITCHEN_API_PORT   port uvicorn binds to (default: 8000)
#   KITCHEN_DB_NAME    PostgreSQL database name (default: kitchen)
#   Source scripts/worktree_env.sh to auto-derive unique values in a worktree.

if [ -f "venv/bin/activate" ]; then
  _VENV="venv/bin/activate"
elif [ -f ".venv/bin/activate" ]; then
  _VENV=".venv/bin/activate"
else
  _VENV=""
fi
if [ -n "${_VENV}" ]; then
  source "${_VENV}"
fi

KITCHEN_API_PORT="${KITCHEN_API_PORT:-8000}"
export DB_NAME="${DB_NAME:-${KITCHEN_DB_NAME:-kitchen}}"

exec uvicorn application:app --host 0.0.0.0 --port "${KITCHEN_API_PORT}" --reload
