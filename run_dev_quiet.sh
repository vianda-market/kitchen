#!/usr/bin/env bash
set -euo pipefail

# Quiet dev server: suppresses uvicorn access logs and per-request noise
# but keeps app-level INFO/WARNING/ERROR so you can see business logic logs.
# Use this for day-to-day development.
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

# Silence Python warnings (e.g. PyJWT's InsecureKeyLengthWarning on short dev secrets).
export PYTHONWARNINGS=ignore

KITCHEN_API_PORT="${KITCHEN_API_PORT:-8000}"
export DB_NAME="${DB_NAME:-${KITCHEN_DB_NAME:-kitchen}}"

# uvicorn --log-level warning: suppresses per-request access log lines
# but app logger (my_app) still emits INFO/WARNING/ERROR via app.utils.log
exec uvicorn application:app --host 0.0.0.0 --port "${KITCHEN_API_PORT}" --reload --log-level warning
