#!/usr/bin/env bash
set -euo pipefail

# Bind to all interfaces - devices on LAN can reach the backend.
# Use on trusted networks only (home, office).
# For untrusted networks (plane, cafe, airport), use run_dev_untrusted.sh instead.

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

exec uvicorn application:app --host 0.0.0.0 --reload
