"""
Unit tests for app/workers/image_pipeline/processing.py

All GCS, Cloud Vision, pyvips, and DB calls are fully mocked.
No real network, no real filesystem.
"""

import json
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.workers.image_pipeline.processing import (
    PROCESSING_VERSION,
    _likelihood_value,
    _should_reject,
    process_image,
)

INSTITUTION_ID = str(uuid4())
PRODUCT_ID = str(uuid4())
IMAGE_ASSET_ID = uuid4()

# Minimal image_asset row returned by _get_asset_row
_BASE_ROW: dict[str, Any] = {
    "image_asset_id": str(IMAGE_ASSET_ID),
    "product_id": PRODUCT_ID,
    "institution_id": INSTITUTION_ID,
    "original_storage_path": f"products/{INSTITUTION_ID}/{PRODUCT_ID}/original",
    "pipeline_status": "pending",
    "moderation_status": "pending",
    "processing_version": 0,
    "failure_count": 0,
}

_SAFE_SIGNALS_ALL_VERY_UNLIKELY = {
    "adult": "VERY_UNLIKELY",
    "violence": "VERY_UNLIKELY",
    "racy": "VERY_UNLIKELY",
    "medical": "VERY_UNLIKELY",
    "spoof": "VERY_UNLIKELY",
}

_SAFE_SIGNALS_ADULT_LIKELY = {
    "adult": "LIKELY",
    "violence": "VERY_UNLIKELY",
    "racy": "VERY_UNLIKELY",
    "medical": "VERY_UNLIKELY",
    "spoof": "VERY_UNLIKELY",
}


# ─── Unit helpers ────────────────────────────────────────────────────────────


class TestLikelihoodOrdering:
    def test_ordering_is_correct(self) -> None:
        assert _likelihood_value("VERY_UNLIKELY") < _likelihood_value("UNLIKELY")
        assert _likelihood_value("UNLIKELY") < _likelihood_value("POSSIBLE")
        assert _likelihood_value("POSSIBLE") < _likelihood_value("LIKELY")
        assert _likelihood_value("LIKELY") < _likelihood_value("VERY_LIKELY")

    def test_unknown_maps_to_zero(self) -> None:
        assert _likelihood_value("UNKNOWN") == 0

    def test_case_insensitive(self) -> None:
        assert _likelihood_value("likely") == _likelihood_value("LIKELY")


class TestShouldReject:
    def test_adult_at_threshold_rejects(self) -> None:
        signals = {**_SAFE_SIGNALS_ALL_VERY_UNLIKELY, "adult": "LIKELY"}
        assert _should_reject(signals, "LIKELY") is True

    def test_violence_at_threshold_rejects(self) -> None:
        signals = {**_SAFE_SIGNALS_ALL_VERY_UNLIKELY, "violence": "LIKELY"}
        assert _should_reject(signals, "LIKELY") is True

    def test_racy_at_threshold_rejects(self) -> None:
        signals = {**_SAFE_SIGNALS_ALL_VERY_UNLIKELY, "racy": "LIKELY"}
        assert _should_reject(signals, "LIKELY") is True

    def test_below_threshold_passes(self) -> None:
        signals = {**_SAFE_SIGNALS_ALL_VERY_UNLIKELY, "adult": "POSSIBLE"}
        assert _should_reject(signals, "LIKELY") is False

    def test_very_likely_rejects_at_likely_threshold(self) -> None:
        signals = {**_SAFE_SIGNALS_ALL_VERY_UNLIKELY, "adult": "VERY_LIKELY"}
        assert _should_reject(signals, "LIKELY") is True

    def test_possible_rejects_at_possible_threshold(self) -> None:
        signals = {**_SAFE_SIGNALS_ALL_VERY_UNLIKELY, "adult": "POSSIBLE"}
        assert _should_reject(signals, "POSSIBLE") is True

    def test_medical_and_spoof_never_cause_rejection(self) -> None:
        # medical and spoof are not in the rejection set
        signals = {**_SAFE_SIGNALS_ALL_VERY_UNLIKELY, "medical": "VERY_LIKELY", "spoof": "VERY_LIKELY"}
        assert _should_reject(signals, "LIKELY") is False


# ─── process_image integration scenarios ─────────────────────────────────────


def _make_db_mock(row_override: dict | None = None) -> MagicMock:
    """Return a mock DB connection pre-configured with _get_asset_row returning a row."""
    db = MagicMock()
    db.cursor.return_value.__enter__ = MagicMock(return_value=MagicMock())
    db.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return db


def _patch_get_asset_row(row: dict | None):
    return patch("app.workers.image_pipeline.processing._get_asset_row", return_value=row)


def _patch_set_pipeline_status():
    return patch("app.workers.image_pipeline.processing._set_pipeline_status")


def _patch_download_original(image_bytes: bytes = b"fake-image-data"):
    return patch("app.workers.image_pipeline.processing._download_original", return_value=image_bytes)


def _patch_run_safe_search(signals: dict):
    return patch("app.workers.image_pipeline.processing._run_safe_search", return_value=signals)


def _patch_delete_original():
    return patch("app.workers.image_pipeline.processing._delete_original_blob")


def _patch_pyvips():
    return patch("app.workers.image_pipeline.processing._process_with_pyvips")


class TestProcessImageIdempotent:
    """Row already ready at current version → no-op (no GCS, no DB writes)."""

    def test_no_op_when_already_ready(self) -> None:
        ready_row = {**_BASE_ROW, "pipeline_status": "ready", "processing_version": PROCESSING_VERSION}
        db = _make_db_mock()

        with (
            _patch_get_asset_row(ready_row),
            _patch_set_pipeline_status() as mock_set,
            _patch_download_original() as mock_dl,
            _patch_run_safe_search(_SAFE_SIGNALS_ALL_VERY_UNLIKELY) as mock_ss,
            _patch_pyvips() as mock_pv,
        ):
            process_image(IMAGE_ASSET_ID, db)

        mock_set.assert_not_called()
        mock_dl.assert_not_called()
        mock_ss.assert_not_called()
        mock_pv.assert_not_called()


class TestProcessImageForceRerun:
    """force=True re-processes even when already ready at current version."""

    def test_force_reprocesses(self) -> None:
        ready_row = {**_BASE_ROW, "pipeline_status": "ready", "processing_version": PROCESSING_VERSION}
        db = _make_db_mock()

        with (
            _patch_get_asset_row(ready_row),
            _patch_set_pipeline_status(),
            _patch_download_original(),
            _patch_run_safe_search(_SAFE_SIGNALS_ALL_VERY_UNLIKELY),
            _patch_delete_original(),
            _patch_pyvips() as mock_pv,
        ):
            process_image(IMAGE_ASSET_ID, db, force=True)

        mock_pv.assert_called_once()


class TestProcessImageMissingRow:
    """Row not found → log and return silently."""

    def test_missing_row_is_noop(self) -> None:
        db = _make_db_mock()

        with (
            _patch_get_asset_row(None),
            _patch_set_pipeline_status() as mock_set,
        ):
            process_image(IMAGE_ASSET_ID, db)

        mock_set.assert_not_called()


class TestProcessImageHappyPath:
    """
    SafeSearch returns all VERY_UNLIKELY → pyvips called, row flipped to ready
    with processing_version=PROCESSING_VERSION.
    """

    def test_happy_path(self) -> None:
        db = _make_db_mock()

        with (
            _patch_get_asset_row(_BASE_ROW),
            _patch_set_pipeline_status() as mock_set,
            _patch_download_original(),
            _patch_run_safe_search(_SAFE_SIGNALS_ALL_VERY_UNLIKELY),
            _patch_delete_original(),
            _patch_pyvips() as mock_pv,
            patch.object(
                __import__("app.config.settings", fromlist=["settings"]).settings,
                "MODERATION_REJECT_LIKELIHOOD",
                "LIKELY",
            ),
        ):
            process_image(IMAGE_ASSET_ID, db)

        mock_pv.assert_called_once()

        # Check the final set_pipeline_status call includes pipeline_status='ready'
        calls_kwargs = [c.kwargs for c in mock_set.call_args_list]
        final = calls_kwargs[-1]
        assert final.get("pipeline_status") == "ready"
        assert final.get("processing_version") == PROCESSING_VERSION

    def test_moderation_status_passed_recorded(self) -> None:
        db = _make_db_mock()

        with (
            _patch_get_asset_row(_BASE_ROW),
            _patch_set_pipeline_status() as mock_set,
            _patch_download_original(),
            _patch_run_safe_search(_SAFE_SIGNALS_ALL_VERY_UNLIKELY),
            _patch_delete_original(),
            _patch_pyvips(),
            patch.object(
                __import__("app.config.settings", fromlist=["settings"]).settings,
                "MODERATION_REJECT_LIKELIHOOD",
                "LIKELY",
            ),
        ):
            process_image(IMAGE_ASSET_ID, db)

        all_kwargs = [c.kwargs for c in mock_set.call_args_list]
        moderation_calls = [k for k in all_kwargs if "moderation_status" in k]
        assert any(k.get("moderation_status") == "passed" for k in moderation_calls)


class TestProcessImageModerationRejection:
    """SafeSearch adult=LIKELY → original deleted, row→rejected, no derived sizes written."""

    def test_rejected_on_adult_likely(self) -> None:
        db = _make_db_mock()

        with (
            _patch_get_asset_row(_BASE_ROW),
            _patch_set_pipeline_status() as mock_set,
            _patch_download_original(),
            _patch_run_safe_search(_SAFE_SIGNALS_ADULT_LIKELY),
            _patch_delete_original() as mock_del,
            _patch_pyvips() as mock_pv,
            patch.object(
                __import__("app.config.settings", fromlist=["settings"]).settings,
                "MODERATION_REJECT_LIKELIHOOD",
                "LIKELY",
            ),
        ):
            process_image(IMAGE_ASSET_ID, db)

        # original must be deleted
        mock_del.assert_called_once()
        # pyvips must NOT be called
        mock_pv.assert_not_called()

        # final status update must be 'rejected'
        all_kwargs = [c.kwargs for c in mock_set.call_args_list]
        assert any(k.get("pipeline_status") == "rejected" for k in all_kwargs)
        assert any(k.get("moderation_status") == "rejected" for k in all_kwargs)

    def test_moderation_signals_captured_on_rejection(self) -> None:
        db = _make_db_mock()

        with (
            _patch_get_asset_row(_BASE_ROW),
            _patch_set_pipeline_status() as mock_set,
            _patch_download_original(),
            _patch_run_safe_search(_SAFE_SIGNALS_ADULT_LIKELY),
            _patch_delete_original(),
            _patch_pyvips(),
            patch.object(
                __import__("app.config.settings", fromlist=["settings"]).settings,
                "MODERATION_REJECT_LIKELIHOOD",
                "LIKELY",
            ),
        ):
            process_image(IMAGE_ASSET_ID, db)

        all_kwargs = [c.kwargs for c in mock_set.call_args_list]
        signal_calls = [k for k in all_kwargs if "moderation_signals" in k]
        assert signal_calls, "moderation_signals should be persisted on rejection"
        captured = json.loads(signal_calls[-1]["moderation_signals"])
        assert captured["adult"] == "LIKELY"


class TestProcessImageThresholdOverride:
    """MODERATION_REJECT_LIKELIHOOD=POSSIBLE → adult=POSSIBLE causes rejection."""

    def test_possible_threshold_rejects_possible_signal(self) -> None:
        db = _make_db_mock()
        signals_possible_adult = {**_SAFE_SIGNALS_ALL_VERY_UNLIKELY, "adult": "POSSIBLE"}

        with (
            _patch_get_asset_row(_BASE_ROW),
            _patch_set_pipeline_status() as mock_set,
            _patch_download_original(),
            _patch_run_safe_search(signals_possible_adult),
            _patch_delete_original() as mock_del,
            _patch_pyvips() as mock_pv,
            patch.object(
                __import__("app.config.settings", fromlist=["settings"]).settings,
                "MODERATION_REJECT_LIKELIHOOD",
                "POSSIBLE",
            ),
        ):
            process_image(IMAGE_ASSET_ID, db)

        mock_del.assert_called_once()
        mock_pv.assert_not_called()
        all_kwargs = [c.kwargs for c in mock_set.call_args_list]
        assert any(k.get("pipeline_status") == "rejected" for k in all_kwargs)


class TestProcessImageFailureRetry:
    """pyvips raises → failure_count increments; on 3rd failure status→failed."""

    def test_first_failure_sets_pending(self) -> None:
        db = _make_db_mock()

        with (
            _patch_get_asset_row(_BASE_ROW),  # failure_count=0
            _patch_set_pipeline_status() as mock_set,
            _patch_download_original(),
            _patch_run_safe_search(_SAFE_SIGNALS_ALL_VERY_UNLIKELY),
            _patch_delete_original(),
            patch("app.workers.image_pipeline.processing._process_with_pyvips", side_effect=RuntimeError("vips crash")),
            patch.object(
                __import__("app.config.settings", fromlist=["settings"]).settings,
                "MODERATION_REJECT_LIKELIHOOD",
                "LIKELY",
            ),
        ):
            process_image(IMAGE_ASSET_ID, db)

        all_kwargs = [c.kwargs for c in mock_set.call_args_list]
        # Last call: status=pending, failure_count=1
        final = all_kwargs[-1]
        assert final.get("pipeline_status") == "pending"
        assert final.get("failure_count") == 1

    def test_third_failure_sets_failed(self) -> None:
        db = _make_db_mock()
        row_at_two_failures = {**_BASE_ROW, "failure_count": 2}

        with (
            _patch_get_asset_row(row_at_two_failures),
            _patch_set_pipeline_status() as mock_set,
            _patch_download_original(),
            _patch_run_safe_search(_SAFE_SIGNALS_ALL_VERY_UNLIKELY),
            _patch_delete_original(),
            patch("app.workers.image_pipeline.processing._process_with_pyvips", side_effect=RuntimeError("vips crash")),
            patch.object(
                __import__("app.config.settings", fromlist=["settings"]).settings,
                "MODERATION_REJECT_LIKELIHOOD",
                "LIKELY",
            ),
        ):
            process_image(IMAGE_ASSET_ID, db)

        all_kwargs = [c.kwargs for c in mock_set.call_args_list]
        final = all_kwargs[-1]
        assert final.get("pipeline_status") == "failed"
        assert final.get("failure_count") == 3

    def test_second_failure_still_pending(self) -> None:
        db = _make_db_mock()
        row_at_one_failure = {**_BASE_ROW, "failure_count": 1}

        with (
            _patch_get_asset_row(row_at_one_failure),
            _patch_set_pipeline_status() as mock_set,
            _patch_download_original(),
            _patch_run_safe_search(_SAFE_SIGNALS_ALL_VERY_UNLIKELY),
            _patch_delete_original(),
            patch("app.workers.image_pipeline.processing._process_with_pyvips", side_effect=RuntimeError("vips crash")),
            patch.object(
                __import__("app.config.settings", fromlist=["settings"]).settings,
                "MODERATION_REJECT_LIKELIHOOD",
                "LIKELY",
            ),
        ):
            process_image(IMAGE_ASSET_ID, db)

        all_kwargs = [c.kwargs for c in mock_set.call_args_list]
        final = all_kwargs[-1]
        assert final.get("pipeline_status") == "pending"
        assert final.get("failure_count") == 2
