"""Stub-coverage tests for the image-pipeline entrypoints.

The real processor (libvips, SafeSearch, GCS upload) lands in a later slice.
For now we just prove the entrypoint stubs are importable and emit their
expected one-line marker on stdout, satisfying the diff-coverage gate while
the module is still a placeholder.
"""

from app.workers import image_pipeline


def test_run_image_event_listener_stub_writes_marker(capsys) -> None:
    image_pipeline.run_image_event_listener()
    out = capsys.readouterr().out
    assert "image_event entrypoint stub" in out


def test_run_image_backfill_stub_writes_marker(capsys) -> None:
    image_pipeline.run_image_backfill()
    out = capsys.readouterr().out
    assert "image_backfill entrypoint stub" in out
