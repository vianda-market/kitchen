"""
Pub/Sub push subscription HTTP listener for image-processing events.

Cloud Run boots this with RUN_MODE=image_event.  The Pub/Sub push
subscription POSTs a JSON envelope to POST / on PORT (default 8080).

GCS notification payload (base64-decoded `data` field):
  {
    "bucket": "vianda-dev-supplier",
    "name": "products/{institution_id}/{product_id}/original",
    ...
  }

We extract (product_id, original_storage_path) and look up the
image_asset row, then delegate to process_image().

Return contract:
  204 — success; Pub/Sub considers the message acknowledged.
  4xx — permanent failure (bad payload, product not found); Pub/Sub
         drops the message (no retry).
  5xx — transient failure; Pub/Sub redelivers.
"""

import base64
import json
import logging
import os

import uvicorn
from fastapi import FastAPI, Request, Response

from app.workers.image_pipeline.processing import process_image

logger = logging.getLogger(__name__)


def _parse_gcs_notification(data_b64: str) -> dict[str, object]:
    """Decode and parse the GCS notification JSON from the Pub/Sub data field."""
    try:
        decoded = base64.b64decode(data_b64).decode("utf-8")
        result: dict[str, object] = json.loads(decoded)
        return result
    except Exception as exc:
        raise ValueError(f"Cannot decode Pub/Sub data field: {exc}") from exc


def _extract_object_name(notification: dict[str, object]) -> str:
    """Return the GCS object name from a GCS notification dict."""
    name = str(notification.get("name", ""))
    if not name:
        raise ValueError("GCS notification missing 'name' field")
    return name


def _parse_product_id_from_path(object_name: str) -> str:
    """
    Extract product_id from a path like:
      products/{institution_id}/{product_id}/original
    Returns product_id string.
    Raises ValueError for non-matching paths.
    """
    parts = object_name.split("/")
    # Expected: ['products', institution_id, product_id, 'original']
    if len(parts) != 4 or parts[0] != "products" or parts[3] != "original":
        raise ValueError(f"Unexpected object path (not a product original): {object_name!r}")
    return parts[2]


def _lookup_image_asset_by_product_id(product_id: str, storage_path: str, db: object) -> dict[str, object] | None:
    """Find the image_asset row by product_id + original_storage_path."""
    from app.utils.db import db_read

    row = db_read(
        """
        SELECT image_asset_id
        FROM ops.image_asset
        WHERE product_id = %s
          AND original_storage_path = %s
        """,
        (product_id, storage_path),
        connection=db,
        fetch_one=True,
    )
    return row  # type: ignore[return-value]


def _make_app() -> FastAPI:
    """Build the minimal FastAPI sub-app for Pub/Sub push delivery."""
    sub_app = FastAPI(title="Image Event Listener", docs_url=None, redoc_url=None)

    @sub_app.post("/")
    async def handle_pubsub_push(request: Request) -> Response:
        """
        Handle a Pub/Sub push POST.
        Returns 204 on success, 4xx for permanent errors, 5xx for transient.
        """
        from uuid import UUID

        from app.utils.db_pool import get_db_connection_context

        try:
            body = await request.json()
        except Exception:
            logger.warning("Received non-JSON Pub/Sub push body — dropping (400)")
            return Response(status_code=400, content="Invalid JSON body")

        message = body.get("message", {})
        data_b64 = message.get("data", "")
        if not data_b64:
            logger.warning("Pub/Sub message has no data field — dropping (400)")
            return Response(status_code=400, content="Empty Pub/Sub message data")

        try:
            notification = _parse_gcs_notification(data_b64)
        except ValueError as exc:
            logger.warning("Cannot parse GCS notification: %s — dropping (400)", exc)
            return Response(status_code=400, content=str(exc))

        try:
            object_name = _extract_object_name(notification)
        except ValueError as exc:
            logger.warning("GCS notification missing name: %s — dropping (400)", exc)
            return Response(status_code=400, content=str(exc))

        # Only process 'original' uploads; silently ack anything else.
        try:
            product_id_str = _parse_product_id_from_path(object_name)
        except ValueError:
            logger.info("Ignoring non-original GCS event for %s", object_name)
            return Response(status_code=204)

        storage_path = object_name  # same as what the route stored

        try:
            with get_db_connection_context() as db:
                row = _lookup_image_asset_by_product_id(product_id_str, storage_path, db)
                if row is None:
                    logger.warning(
                        "No image_asset row for product_id=%s path=%s — dropping (404)",
                        product_id_str,
                        storage_path,
                    )
                    return Response(status_code=404, content="image_asset not found")

                image_asset_id = UUID(str(row["image_asset_id"]))
                process_image(image_asset_id, db)

        except Exception:
            logger.exception("Transient error processing image_asset for product %s", product_id_str)
            return Response(status_code=500, content="Transient processing error — will retry")

        return Response(status_code=204)

    return sub_app


def run_image_event_listener() -> None:
    """Boot the Pub/Sub HTTP listener. Called by scripts/entrypoint.sh."""
    import logging as _logging

    _logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    port = int(os.environ.get("PORT", "8080"))
    logger.info("Starting image event listener on port %d", port)

    app = _make_app()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
