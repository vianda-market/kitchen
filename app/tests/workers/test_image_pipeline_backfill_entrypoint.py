"""
Unit tests for app/workers/image_pipeline/backfill_entrypoint.py

Tests the batch-iteration logic: zero rows → no-op; N rows → process_image
called N times with force=True; one row raising → continues, exits cleanly.
All DB and process_image calls are fully mocked.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.workers.image_pipeline.backfill_entrypoint import _BATCH_SIZE, run_image_backfill

_ID_1 = str(uuid4())
_ID_2 = str(uuid4())
_ID_3 = str(uuid4())


def _make_ctx(db: object):
    """Return a fresh context manager that yields `db`."""

    @contextmanager
    def _ctx():
        yield db

    return _ctx()


def _ctx_factory(db: object):
    """Side-effect callable: each call returns a fresh ctx manager for `db`."""

    def factory():
        return _make_ctx(db)

    return factory


# ─── Core iteration tests ─────────────────────────────────────────────────────


class TestRunImageBackfillZeroRows:
    """When no stale rows exist, process_image is never called."""

    def test_zero_rows_no_process_calls(self) -> None:
        mock_db = MagicMock()

        with (
            # get_db_connection_context is imported locally inside run_image_backfill
            patch("app.utils.db_pool.get_db_connection_context", side_effect=_ctx_factory(mock_db)),
            # db_read is imported locally as well
            patch("app.utils.db.db_read", return_value=[]),
            patch("app.workers.image_pipeline.backfill_entrypoint.process_image") as mock_process,
        ):
            run_image_backfill()

        mock_process.assert_not_called()


class TestRunImageBackfillSingleBatch:
    """Three rows in a single batch → process_image called 3 times with force=True."""

    def test_three_rows_processed(self) -> None:
        rows = [
            {"image_asset_id": _ID_1},
            {"image_asset_id": _ID_2},
            {"image_asset_id": _ID_3},
        ]
        # First call returns rows; second call returns [] to stop
        db_read_results = [rows, []]
        mock_db = MagicMock()

        with (
            patch("app.utils.db_pool.get_db_connection_context", side_effect=_ctx_factory(mock_db)),
            patch("app.utils.db.db_read", side_effect=db_read_results),
            patch("app.workers.image_pipeline.backfill_entrypoint.process_image") as mock_process,
        ):
            run_image_backfill()

        assert mock_process.call_count == 3
        for c in mock_process.call_args_list:
            assert c.kwargs.get("force") is True

    def test_force_true_passed_for_each_row(self) -> None:
        rows = [{"image_asset_id": _ID_1}]
        db_read_results = [rows, []]
        mock_db = MagicMock()

        with (
            patch("app.utils.db_pool.get_db_connection_context", side_effect=_ctx_factory(mock_db)),
            patch("app.utils.db.db_read", side_effect=db_read_results),
            patch("app.workers.image_pipeline.backfill_entrypoint.process_image") as mock_process,
        ):
            run_image_backfill()

        assert mock_process.call_count == 1
        assert mock_process.call_args.kwargs["force"] is True


class TestRunImageBackfillContinuesOnError:
    """One row raises → remaining rows are still processed; function exits normally."""

    def test_error_in_one_row_continues_others(self) -> None:
        rows = [
            {"image_asset_id": _ID_1},
            {"image_asset_id": _ID_2},
            {"image_asset_id": _ID_3},
        ]
        db_read_results = [rows, []]
        mock_db = MagicMock()
        call_count = 0

        def process_side_effect(image_asset_id, db, *, force=False):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("GCS read error on row 2")

        with (
            patch("app.utils.db_pool.get_db_connection_context", side_effect=_ctx_factory(mock_db)),
            patch("app.utils.db.db_read", side_effect=db_read_results),
            patch(
                "app.workers.image_pipeline.backfill_entrypoint.process_image",
                side_effect=process_side_effect,
            ),
        ):
            # Must not raise even though one row failed
            run_image_backfill()

        assert call_count == 3


class TestRunImageBackfillMultiBatch:
    """Two batches then empty → offset advances per batch."""

    def test_offset_advances_per_batch(self) -> None:
        batch = [{"image_asset_id": str(uuid4())} for _ in range(3)]
        # Return non-empty twice then empty to stop
        db_read_results = [batch, batch, []]
        mock_db = MagicMock()

        with (
            patch("app.utils.db_pool.get_db_connection_context", side_effect=_ctx_factory(mock_db)),
            patch("app.utils.db.db_read", side_effect=db_read_results) as mock_db_read,
            patch("app.workers.image_pipeline.backfill_entrypoint.process_image"),
        ):
            run_image_backfill()

        # Three db_read calls: batch 1, batch 2, empty stop
        assert mock_db_read.call_count == 3

        # Offsets are positional arg [2] in the params tuple (index 2 → OFFSET)
        offsets = [c[0][1][2] for c in mock_db_read.call_args_list]
        assert offsets[0] == 0
        assert offsets[1] == _BATCH_SIZE


class TestRunImageBackfillCompletionLog:
    """run_image_backfill logs summary and exits without raising."""

    def test_completes_without_exception(self) -> None:
        mock_db = MagicMock()

        with (
            patch("app.utils.db_pool.get_db_connection_context", side_effect=_ctx_factory(mock_db)),
            patch("app.utils.db.db_read", return_value=[]),
        ):
            # Must not raise
            run_image_backfill()
