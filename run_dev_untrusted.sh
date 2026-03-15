#!/usr/bin/env bash
set -euo pipefail

# Uses uvicorn defaults: host 127.0.0.1, port 8000 (localhost only, no LAN exposure).
# Use on untrusted networks (plane, cafe, airport).
# For trusted networks (home, office), use run_dev_trusted.sh for physical device testing.

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

exec uvicorn application:app --reload
