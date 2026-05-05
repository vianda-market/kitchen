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
    _DERIVED_SIZES,
    PROCESSING_VERSION,
    _delete_original_blob,
    _download_original,
    _get_asset_row,
    _json_dumps,
    _likelihood_value,
    _process_with_pyvips,
    _run_safe_search,
    _set_pipeline_status,
    _should_reject,
    _upload_derived_blob,
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


# ─── Helper-level tests (cover internal bodies) ───────────────────────────────


class TestJsonDumps:
    def test_serializes_dict(self) -> None:
        result = _json_dumps({"adult": "LIKELY", "racy": "POSSIBLE"})
        parsed = json.loads(result)
        assert parsed["adult"] == "LIKELY"
        assert parsed["racy"] == "POSSIBLE"

    def test_returns_string(self) -> None:
        assert isinstance(_json_dumps({}), str)


class TestGetAssetRow:
    """Covers _get_asset_row body (import + db_read call path)."""

    def test_returns_row_when_found(self) -> None:
        db = MagicMock()
        expected_row = {**_BASE_ROW}

        # db_read is imported locally inside _get_asset_row; patch at source.
        with patch("app.utils.db.db_read", return_value=expected_row) as mock_read:
            result = _get_asset_row(IMAGE_ASSET_ID, db)

        assert result == expected_row
        mock_read.assert_called_once()
        call_kwargs = mock_read.call_args
        assert call_kwargs.kwargs.get("fetch_one") is True

    def test_returns_none_when_not_found(self) -> None:
        db = MagicMock()

        with patch("app.utils.db.db_read", return_value=None):
            result = _get_asset_row(IMAGE_ASSET_ID, db)

        assert result is None


class TestSetPipelineStatus:
    """Covers _set_pipeline_status body."""

    def test_no_fields_returns_early(self) -> None:
        db = MagicMock()
        _set_pipeline_status(IMAGE_ASSET_ID, db)
        db.cursor.assert_not_called()
        db.commit.assert_not_called()

    def test_executes_update_and_commits(self) -> None:
        db = MagicMock()
        mock_cursor = MagicMock()
        db.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        db.cursor.return_value.__exit__ = MagicMock(return_value=False)

        _set_pipeline_status(IMAGE_ASSET_ID, db, pipeline_status="processing")

        mock_cursor.execute.assert_called_once()
        db.commit.assert_called_once()

    def test_sets_multiple_fields(self) -> None:
        db = MagicMock()
        mock_cursor = MagicMock()
        db.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        db.cursor.return_value.__exit__ = MagicMock(return_value=False)

        _set_pipeline_status(IMAGE_ASSET_ID, db, pipeline_status="ready", processing_version=1)

        sql = mock_cursor.execute.call_args[0][0]
        assert "pipeline_status = %s" in sql
        assert "processing_version = %s" in sql


class TestDownloadOriginal:
    """Covers _download_original body including no-bucket path."""

    def test_raises_when_no_bucket(self) -> None:
        import pytest

        # settings and get_gcs_client are imported locally inside _download_original.
        with (
            patch("app.config.settings.settings") as mock_settings,
            patch("app.utils.gcs.get_gcs_client"),
        ):
            mock_settings.GCS_SUPPLIER_BUCKET = ""
            with pytest.raises(RuntimeError, match="GCS_SUPPLIER_BUCKET"):
                _download_original(INSTITUTION_ID, PRODUCT_ID)

    def test_downloads_from_correct_path(self) -> None:
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"image-data"
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        with (
            patch("app.config.settings.settings") as mock_settings,
            patch("app.utils.gcs.get_gcs_client", return_value=mock_client),
        ):
            mock_settings.GCS_SUPPLIER_BUCKET = "test-bucket"
            result = _download_original(INSTITUTION_ID, PRODUCT_ID)

        assert result == b"image-data"
        expected_blob_name = f"products/{INSTITUTION_ID}/{PRODUCT_ID}/original"
        mock_bucket.blob.assert_called_once_with(expected_blob_name)


class TestDeleteOriginalBlob:
    """Covers _delete_original_blob body including no-bucket and exception paths."""

    def test_no_op_when_no_bucket(self) -> None:
        with patch("app.config.settings.settings") as mock_settings:
            mock_settings.GCS_SUPPLIER_BUCKET = ""
            # Should not raise
            _delete_original_blob(INSTITUTION_ID, PRODUCT_ID)

    def test_deletes_blob_on_success(self) -> None:
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        with (
            patch("app.config.settings.settings") as mock_settings,
            patch("app.utils.gcs.get_gcs_client", return_value=mock_client),
        ):
            mock_settings.GCS_SUPPLIER_BUCKET = "test-bucket"
            _delete_original_blob(INSTITUTION_ID, PRODUCT_ID)

        mock_blob.delete.assert_called_once()

    def test_logs_warning_on_delete_exception(self) -> None:
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.delete.side_effect = Exception("GCS unavailable")
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        with (
            patch("app.config.settings.settings") as mock_settings,
            patch("app.utils.gcs.get_gcs_client", return_value=mock_client),
            patch("app.workers.image_pipeline.processing.logger") as mock_logger,
        ):
            mock_settings.GCS_SUPPLIER_BUCKET = "test-bucket"
            _delete_original_blob(INSTITUTION_ID, PRODUCT_ID)

        mock_logger.warning.assert_called_once()


class TestRunSafeSearch:
    """Covers _run_safe_search body."""

    def test_returns_signal_dict(self) -> None:
        # Build mock Vision annotation
        mock_ann = MagicMock()
        mock_ann.adult.name = "VERY_UNLIKELY"
        mock_ann.violence.name = "VERY_UNLIKELY"
        mock_ann.racy.name = "VERY_UNLIKELY"
        mock_ann.medical.name = "VERY_UNLIKELY"
        mock_ann.spoof.name = "VERY_UNLIKELY"

        mock_response = MagicMock()
        mock_response.safe_search_annotation = mock_ann

        mock_annotator_client = MagicMock()
        mock_annotator_client.safe_search_detection.return_value = mock_response

        mock_vision_module = MagicMock()
        mock_vision_module.ImageAnnotatorClient.return_value = mock_annotator_client

        # _run_safe_search does `from google.cloud import vision` locally.
        # Patch via sys.modules so the local import resolves to our mock.

        fake_google = MagicMock()
        fake_google.cloud.vision = mock_vision_module

        with patch.dict(
            "sys.modules",
            {
                "google": fake_google,
                "google.cloud": fake_google.cloud,
                "google.cloud.vision": mock_vision_module,
            },
        ):
            result = _run_safe_search(b"fake-image")

        assert "adult" in result
        assert "violence" in result
        assert "racy" in result
        assert "medical" in result
        assert "spoof" in result


class TestUploadDerivedBlob:
    """Covers _upload_derived_blob body including no-bucket path."""

    def test_raises_when_no_bucket(self) -> None:
        import pytest

        with patch("app.config.settings.settings") as mock_settings:
            mock_settings.GCS_SUPPLIER_BUCKET = ""
            with pytest.raises(RuntimeError, match="GCS_SUPPLIER_BUCKET"):
                _upload_derived_blob(INSTITUTION_ID, PRODUCT_ID, "hero", b"data", "image/webp")

    def test_uploads_to_correct_path(self) -> None:
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        with (
            patch("app.config.settings.settings") as mock_settings,
            patch("app.utils.gcs.get_gcs_client", return_value=mock_client),
        ):
            mock_settings.GCS_SUPPLIER_BUCKET = "test-bucket"
            _upload_derived_blob(INSTITUTION_ID, PRODUCT_ID, "hero", b"webp-data", "image/webp")

        expected_blob_name = f"products/{INSTITUTION_ID}/{PRODUCT_ID}/hero"
        mock_bucket.blob.assert_called_once_with(expected_blob_name)
        mock_blob.upload_from_string.assert_called_once_with(b"webp-data", content_type="image/webp")


def _make_pyvips_mock() -> MagicMock:
    """Build a pyvips module mock with a realistic Image chain."""
    mock_resized = MagicMock()
    mock_resized.webpsave_buffer.return_value = b"webp"
    mock_resized.jpegsave_buffer.return_value = b"jpeg"

    mock_img = MagicMock()
    mock_img.thumbnail_image.return_value = mock_resized

    mock_pyvips = MagicMock()
    mock_pyvips.Image.new_from_buffer.return_value = mock_img
    return mock_pyvips


class TestProcessWithPyvips:
    """Covers _process_with_pyvips body — iterates all three derived sizes."""

    def test_produces_all_three_derived_sizes(self) -> None:
        upload_calls: list[tuple[str, str, str, bytes, str]] = []

        def fake_upload(institution_id: str, product_id: str, key: str, data: bytes, content_type: str) -> None:
            upload_calls.append((institution_id, product_id, key, data, content_type))

        mock_pyvips = _make_pyvips_mock()

        with (
            patch.dict("sys.modules", {"pyvips": mock_pyvips}),
            patch("app.workers.image_pipeline.processing._upload_derived_blob", side_effect=fake_upload),
        ):
            _process_with_pyvips(b"fake-image", INSTITUTION_ID, PRODUCT_ID)

        # 3 sizes × 2 formats = 6 uploads
        assert len(upload_calls) == 6

        keys_uploaded = [c[2] for c in upload_calls]
        assert "hero" in keys_uploaded
        assert "card" in keys_uploaded
        assert "thumbnail" in keys_uploaded
        assert "hero.jpg" in keys_uploaded
        assert "card.jpg" in keys_uploaded
        assert "thumbnail.jpg" in keys_uploaded

    def test_webp_and_jpeg_content_types(self) -> None:
        upload_calls: list[tuple] = []
        mock_pyvips = _make_pyvips_mock()

        with (
            patch.dict("sys.modules", {"pyvips": mock_pyvips}),
            patch(
                "app.workers.image_pipeline.processing._upload_derived_blob",
                side_effect=lambda *a: upload_calls.append(a),
            ),
        ):
            _process_with_pyvips(b"fake-image", INSTITUTION_ID, PRODUCT_ID)

        webp_calls = [c for c in upload_calls if c[4] == "image/webp"]
        jpeg_calls = [c for c in upload_calls if c[4] == "image/jpeg"]
        assert len(webp_calls) == len(_DERIVED_SIZES)
        assert len(jpeg_calls) == len(_DERIVED_SIZES)

    def test_derived_sizes_dimensions_passed(self) -> None:
        """thumbnail_image is called with the correct width/height for each size."""
        mock_pyvips = _make_pyvips_mock()

        with (
            patch.dict("sys.modules", {"pyvips": mock_pyvips}),
            patch("app.workers.image_pipeline.processing._upload_derived_blob"),
        ):
            _process_with_pyvips(b"fake-image", INSTITUTION_ID, PRODUCT_ID)

        mock_img = mock_pyvips.Image.new_from_buffer.return_value
        calls = mock_img.thumbnail_image.call_args_list
        assert len(calls) == len(_DERIVED_SIZES)
        widths = [c[0][0] for c in calls]
        assert 1600 in widths
        assert 600 in widths
        assert 200 in widths
