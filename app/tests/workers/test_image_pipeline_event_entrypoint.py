"""
Unit tests for app/workers/image_pipeline/event_entrypoint.py

Tests the FastAPI sub-app handler and helper parse functions.
All DB, GCS, and process_image calls are fully mocked.
No real network, no real DB.
"""

import base64
import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.workers.image_pipeline.event_entrypoint import (
    _extract_object_name,
    _lookup_image_asset_by_product_id,
    _make_app,
    _parse_gcs_notification,
    _parse_product_id_from_path,
    run_image_event_listener,
)

INSTITUTION_ID = str(uuid4())
PRODUCT_ID = str(uuid4())
IMAGE_ASSET_ID = uuid4()

_VALID_OBJECT_NAME = f"products/{INSTITUTION_ID}/{PRODUCT_ID}/original"


def _make_pubsub_body(notification: dict, *, data_b64: str | None = None) -> dict:
    """Build a Pub/Sub push envelope wrapping a GCS notification dict."""
    if data_b64 is None:
        data_b64 = base64.b64encode(json.dumps(notification).encode()).decode()
    return {"message": {"data": data_b64, "messageId": "123"}}


def _make_ctx(db: object):
    @contextmanager
    def _ctx():
        yield db

    return _ctx()


def _ctx_factory(db: object):
    def factory():
        return _make_ctx(db)

    return factory


# ─── Helper function tests ────────────────────────────────────────────────────


class TestParseGcsNotification:
    def test_decodes_valid_base64_json(self) -> None:
        payload = {"bucket": "test-bucket", "name": _VALID_OBJECT_NAME}
        b64 = base64.b64encode(json.dumps(payload).encode()).decode()
        result = _parse_gcs_notification(b64)
        assert result["name"] == _VALID_OBJECT_NAME

    def test_raises_on_invalid_base64(self) -> None:
        with pytest.raises(ValueError, match="Cannot decode"):
            _parse_gcs_notification("!!! not base64 !!!")

    def test_raises_on_non_json_data(self) -> None:
        b64 = base64.b64encode(b"not-json").decode()
        with pytest.raises(ValueError, match="Cannot decode"):
            _parse_gcs_notification(b64)


class TestExtractObjectName:
    def test_returns_name_field(self) -> None:
        notification: dict[str, object] = {"name": _VALID_OBJECT_NAME, "bucket": "x"}
        assert _extract_object_name(notification) == _VALID_OBJECT_NAME

    def test_raises_when_name_missing(self) -> None:
        with pytest.raises(ValueError, match="missing 'name'"):
            _extract_object_name({"bucket": "x"})

    def test_raises_when_name_empty(self) -> None:
        with pytest.raises(ValueError, match="missing 'name'"):
            _extract_object_name({"name": "", "bucket": "x"})


class TestParseProductIdFromPath:
    def test_extracts_product_id(self) -> None:
        result = _parse_product_id_from_path(_VALID_OBJECT_NAME)
        assert result == PRODUCT_ID

    def test_raises_on_non_original_suffix(self) -> None:
        with pytest.raises(ValueError, match="not a product original"):
            _parse_product_id_from_path(f"products/{INSTITUTION_ID}/{PRODUCT_ID}/hero")

    def test_raises_on_wrong_prefix(self) -> None:
        with pytest.raises(ValueError, match="not a product original"):
            _parse_product_id_from_path(f"other/{INSTITUTION_ID}/{PRODUCT_ID}/original")

    def test_raises_on_short_path(self) -> None:
        with pytest.raises(ValueError, match="not a product original"):
            _parse_product_id_from_path("products/original")

    def test_raises_on_extra_segments(self) -> None:
        with pytest.raises(ValueError, match="not a product original"):
            _parse_product_id_from_path(f"products/{INSTITUTION_ID}/{PRODUCT_ID}/original/extra")


# ─── FastAPI sub-app handler tests ───────────────────────────────────────────


def _make_client() -> TestClient:
    app = _make_app()
    return TestClient(app, raise_server_exceptions=False)


class TestHandlePubSubPushBadRequests:
    """4xx responses for malformed or unprocessable messages."""

    def test_non_json_body_returns_400(self) -> None:
        client = _make_client()
        resp = client.post("/", content=b"not-json", headers={"Content-Type": "text/plain"})
        assert resp.status_code == 400

    def test_missing_data_field_returns_400(self) -> None:
        client = _make_client()
        body = {"message": {"messageId": "123"}}  # no 'data'
        resp = client.post("/", json=body)
        assert resp.status_code == 400

    def test_empty_data_field_returns_400(self) -> None:
        client = _make_client()
        body = {"message": {"data": "", "messageId": "123"}}
        resp = client.post("/", json=body)
        assert resp.status_code == 400

    def test_invalid_base64_data_returns_400(self) -> None:
        client = _make_client()
        body = {"message": {"data": "!!!invalid-base64!!!", "messageId": "123"}}
        resp = client.post("/", json=body)
        assert resp.status_code == 400

    def test_notification_missing_name_returns_400(self) -> None:
        client = _make_client()
        notification = {"bucket": "test-bucket"}  # no 'name'
        body = _make_pubsub_body(notification)
        resp = client.post("/", json=body)
        assert resp.status_code == 400

    def test_non_original_object_silently_acked_204(self) -> None:
        """GCS events for non-original blobs (hero, card, etc.) are silently acked."""
        client = _make_client()
        notification = {"bucket": "test-bucket", "name": f"products/{INSTITUTION_ID}/{PRODUCT_ID}/hero"}
        body = _make_pubsub_body(notification)
        resp = client.post("/", json=body)
        assert resp.status_code == 204

    def test_image_asset_not_found_returns_404(self) -> None:
        client = _make_client()
        notification = {"bucket": "test-bucket", "name": _VALID_OBJECT_NAME}
        body = _make_pubsub_body(notification)

        mock_db = MagicMock()

        with (
            # get_db_connection_context imported locally inside the handler
            patch("app.utils.db_pool.get_db_connection_context", side_effect=_ctx_factory(mock_db)),
            patch(
                "app.workers.image_pipeline.event_entrypoint._lookup_image_asset_by_product_id",
                return_value=None,
            ),
        ):
            resp = client.post("/", json=body)

        assert resp.status_code == 404


class TestHandlePubSubPushHappyPath:
    """Valid payload → process_image called → 204."""

    def test_valid_payload_calls_process_image_and_returns_204(self) -> None:
        client = _make_client()
        notification = {"bucket": "test-bucket", "name": _VALID_OBJECT_NAME}
        body = _make_pubsub_body(notification)

        mock_row = {"image_asset_id": str(IMAGE_ASSET_ID)}
        mock_db = MagicMock()

        with (
            patch("app.utils.db_pool.get_db_connection_context", side_effect=_ctx_factory(mock_db)),
            patch(
                "app.workers.image_pipeline.event_entrypoint._lookup_image_asset_by_product_id",
                return_value=mock_row,
            ),
            patch("app.workers.image_pipeline.event_entrypoint.process_image") as mock_process,
        ):
            resp = client.post("/", json=body)

        assert resp.status_code == 204
        mock_process.assert_called_once()


class TestHandlePubSubPushTransientErrors:
    """process_image raises or DB fails → 5xx (Pub/Sub redelivers)."""

    def test_process_image_exception_returns_500(self) -> None:
        client = _make_client()
        notification = {"bucket": "test-bucket", "name": _VALID_OBJECT_NAME}
        body = _make_pubsub_body(notification)

        mock_row = {"image_asset_id": str(IMAGE_ASSET_ID)}
        mock_db = MagicMock()

        with (
            patch("app.utils.db_pool.get_db_connection_context", side_effect=_ctx_factory(mock_db)),
            patch(
                "app.workers.image_pipeline.event_entrypoint._lookup_image_asset_by_product_id",
                return_value=mock_row,
            ),
            patch(
                "app.workers.image_pipeline.event_entrypoint.process_image",
                side_effect=RuntimeError("GCS timeout"),
            ),
        ):
            resp = client.post("/", json=body)

        assert resp.status_code == 500

    def test_db_connection_failure_returns_500(self) -> None:
        """DB connection context manager raises → 500."""
        client = _make_client()
        notification = {"bucket": "test-bucket", "name": _VALID_OBJECT_NAME}
        body = _make_pubsub_body(notification)

        with patch(
            "app.utils.db_pool.get_db_connection_context",
            side_effect=RuntimeError("DB pool exhausted"),
        ):
            resp = client.post("/", json=body)

        assert resp.status_code == 500


# ─── _lookup_image_asset_by_product_id body tests ────────────────────────────


class TestLookupImageAssetByProductId:
    """Covers the db_read call inside _lookup_image_asset_by_product_id."""

    def test_returns_row_when_found(self) -> None:
        db = MagicMock()
        expected_row = {"image_asset_id": str(IMAGE_ASSET_ID)}

        with patch("app.utils.db.db_read", return_value=expected_row) as mock_read:
            result = _lookup_image_asset_by_product_id(PRODUCT_ID, _VALID_OBJECT_NAME, db)

        assert result == expected_row
        mock_read.assert_called_once()
        assert mock_read.call_args.kwargs.get("fetch_one") is True

    def test_returns_none_when_not_found(self) -> None:
        db = MagicMock()

        with patch("app.utils.db.db_read", return_value=None):
            result = _lookup_image_asset_by_product_id(PRODUCT_ID, _VALID_OBJECT_NAME, db)

        assert result is None


# ─── run_image_event_listener body test ──────────────────────────────────────


class TestRunImageEventListener:
    """Covers the uvicorn boot path in run_image_event_listener."""

    def test_calls_uvicorn_run_with_correct_port(self) -> None:
        import os

        with (
            patch("app.workers.image_pipeline.event_entrypoint.uvicorn") as mock_uvicorn,
            patch.dict(os.environ, {"PORT": "9090"}),
        ):
            run_image_event_listener()

        mock_uvicorn.run.assert_called_once()
        call_kwargs = mock_uvicorn.run.call_args
        assert call_kwargs.kwargs.get("port") == 9090
        assert call_kwargs.kwargs.get("host") == "0.0.0.0"  # noqa: S104

    def test_uses_default_port_8080_when_env_not_set(self) -> None:
        import os

        env = {k: v for k, v in os.environ.items() if k != "PORT"}

        with (
            patch("app.workers.image_pipeline.event_entrypoint.uvicorn") as mock_uvicorn,
            patch.dict(os.environ, env, clear=True),
        ):
            run_image_event_listener()

        call_kwargs = mock_uvicorn.run.call_args
        assert call_kwargs.kwargs.get("port") == 8080
