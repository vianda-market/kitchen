#!/usr/bin/env bash
set -euo pipefail

# Same as run_dev_trusted.sh but silences all non-error output:
#   - LOG_LEVEL=ERROR silences the app's "my_app" logger (log_info/log_warning)
#   - uvicorn --log-level error silences uvicorn's startup banner, reload watcher, and per-request access log
# Use this when sharing terminal output alongside Postman runs so logs stay readable.

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

exec uvicorn application:app --host 0.0.0.0 --reload --log-level error
