# app/workers/image_pipeline/__init__.py
# Stub module for the async image-processing pipeline.
# Real implementation (libvips resizing, Cloud Vision SafeSearch, GCS upload)
# will be added in a later slice.
# Design doc: ~/learn/vianda/docs/plans/image-processing-pipeline.md

import sys


def run_image_event_listener() -> None:
    """Pub/Sub image-event listener entry point. Stub — not yet implemented."""
    sys.stdout.write("image_event entrypoint stub — not yet implemented\n")


def run_image_backfill() -> None:
    """Backfill worker that re-processes existing product images. Stub — not yet implemented."""
    sys.stdout.write("image_backfill entrypoint stub — not yet implemented\n")
