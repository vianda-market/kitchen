#!/usr/bin/env bash
set -euo pipefail

# Same as run_dev_trusted.sh but silences all non-error output:
#   - LOG_LEVEL=ERROR silences the app's "my_app" logger (log_info/log_warning)
#   - uvicorn --log-level error silences uvicorn's startup banner, reload watcher, and per-request access log
# Use this when sharing terminal output alongside Postman runs so logs stay readable.
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

export LOG_LEVEL=ERROR
# Silence Python warnings (e.g. PyJWT's InsecureKeyLengthWarning on short dev secrets).
export PYTHONWARNINGS=ignore

KITCHEN_API_PORT="${KITCHEN_API_PORT:-8000}"
export DB_NAME="${DB_NAME:-${KITCHEN_DB_NAME:-kitchen}}"

exec uvicorn application:app --host 0.0.0.0 --port "${KITCHEN_API_PORT}" --reload --log-level error
