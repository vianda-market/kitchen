"""
Smoke tests for image-pipeline entrypoint imports.

The entrypoints (run_image_event_listener, run_image_backfill) are importable
and properly wired — they no longer write stub markers since the real
implementation has landed in this slice.
"""

from app.workers import image_pipeline


def test_run_image_event_listener_is_callable() -> None:
    assert callable(image_pipeline.run_image_event_listener)


def test_run_image_backfill_is_callable() -> None:
    assert callable(image_pipeline.run_image_backfill)
