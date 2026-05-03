#!/usr/bin/env bash
# scripts/entrypoint.sh — Cloud Run container entrypoint.
#
# RUN_MODE controls which process starts:
#   unset / "api"        → uvicorn (FastAPI API server, default)
#   "image_event"        → Pub/Sub image-event listener (stub)
#   "image_backfill"     → image backfill worker (stub)
#   anything else        → logs a warning, falls through to API mode
#
# Design doc: ~/learn/vianda/docs/plans/image-processing-pipeline.md

set -euo pipefail

RUN_MODE="${RUN_MODE:-api}"

case "$RUN_MODE" in
    api)
        exec uvicorn application:app --host 0.0.0.0 --port 8080
        ;;
    image_event)
        exec python -c "from app.workers.image_pipeline import run_image_event_listener; run_image_event_listener()"
        ;;
    image_backfill)
        exec python -c "from app.workers.image_pipeline import run_image_backfill; run_image_backfill()"
        ;;
    *)
        echo "WARNING: unknown RUN_MODE='${RUN_MODE}', falling through to API mode" >&2
        exec uvicorn application:app --host 0.0.0.0 --port 8080
        ;;
esac
