"""
Image processing core — libvips resizing + Cloud Vision SafeSearch moderation.

Entry point: process_image(image_asset_id, db, *, force=False)

Processing version is bumped here when processing standards change.
Backfill iterates rows with processing_version < PROCESSING_VERSION.
"""

import logging
from uuid import UUID

import psycopg2.extensions

logger = logging.getLogger(__name__)

PROCESSING_VERSION: int = 1

# SafeSearch likelihood ordinal map (matches Cloud Vision proto ordering).
_LIKELIHOOD_ORDER = {
    "UNKNOWN": 0,
    "VERY_UNLIKELY": 1,
    "UNLIKELY": 2,
    "POSSIBLE": 3,
    "LIKELY": 4,
    "VERY_LIKELY": 5,
}

# Derived sizes: (key, width, height)
_DERIVED_SIZES = [
    ("hero", 1600, 1066),
    ("card", 600, 400),
    ("thumbnail", 200, 200),
]


def _likelihood_value(name: str) -> int:
    return _LIKELIHOOD_ORDER.get(name.upper(), 0)


def _get_asset_row(image_asset_id: UUID, db: psycopg2.extensions.connection) -> dict | None:
    from app.utils.db import db_read

    row = db_read(
        """
        SELECT image_asset_id, product_id, institution_id,
               original_storage_path, pipeline_status, moderation_status,
               processing_version, failure_count
        FROM ops.image_asset
        WHERE image_asset_id = %s
        """,
        (str(image_asset_id),),
        connection=db,
        fetch_one=True,
    )
    return row  # type: ignore[return-value]


def _set_pipeline_status(image_asset_id: UUID, db: psycopg2.extensions.connection, **fields: object) -> None:
    """Update ops.image_asset with arbitrary keyword columns, then commit."""
    if not fields:
        return
    set_clauses = ", ".join(f"{col} = %s" for col in fields)
    values = list(fields.values()) + [str(image_asset_id)]
    with db.cursor() as cur:
        cur.execute(
            f"UPDATE ops.image_asset SET {set_clauses} WHERE image_asset_id = %s",  # noqa: S608
            values,
        )
    db.commit()


def _download_original(institution_id: str, product_id: str) -> bytes:
    """Download the original blob from GCS and return its bytes."""
    from app.config.settings import settings
    from app.utils.gcs import get_gcs_client

    bucket_name = settings.GCS_SUPPLIER_BUCKET
    if not bucket_name:
        raise RuntimeError("GCS_SUPPLIER_BUCKET is not configured")

    blob_name = f"products/{institution_id}/{product_id}/original"
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    data: bytes = blob.download_as_bytes()
    return data


def _delete_original_blob(institution_id: str, product_id: str) -> None:
    """Delete the original blob from GCS (best-effort)."""
    from app.config.settings import settings
    from app.utils.gcs import get_gcs_client

    bucket_name = settings.GCS_SUPPLIER_BUCKET
    if not bucket_name:
        return
    blob_name = f"products/{institution_id}/{product_id}/original"
    try:
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        bucket.blob(blob_name).delete()
    except Exception:
        logger.warning("Failed to delete original blob %s", blob_name, exc_info=True)


def _run_safe_search(image_bytes: bytes) -> dict[str, str]:
    """
    Call Cloud Vision SafeSearch on raw image bytes.
    Returns a dict mapping signal name -> likelihood string.
    """
    from google.cloud import vision  # type: ignore[attr-defined]

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.safe_search_detection(image=image)
    ann = response.safe_search_annotation

    return {
        "adult": ann.adult.name,
        "violence": ann.violence.name,
        "racy": ann.racy.name,
        "medical": ann.medical.name,
        "spoof": ann.spoof.name,
    }


def _should_reject(signals: dict[str, str], threshold: str) -> bool:
    """Return True if any of adult/violence/racy meets or exceeds the threshold likelihood."""
    threshold_val = _likelihood_value(threshold)
    return any(_likelihood_value(signals.get(key, "UNKNOWN")) >= threshold_val for key in ("adult", "violence", "racy"))


def _upload_derived_blob(institution_id: str, product_id: str, key: str, data: bytes, content_type: str) -> None:
    """Upload a derived image blob to GCS."""
    from app.config.settings import settings
    from app.utils.gcs import get_gcs_client

    bucket_name = settings.GCS_SUPPLIER_BUCKET
    if not bucket_name:
        raise RuntimeError("GCS_SUPPLIER_BUCKET is not configured")

    blob_name = f"products/{institution_id}/{product_id}/{key}"
    client = get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type=content_type)


def _process_with_pyvips(image_bytes: bytes, institution_id: str, product_id: str) -> None:
    """
    Produce three derived sizes (hero, card, thumbnail) as WebP + JPEG fallback.
    Uses pyvips smartcrop for cover-crop, strips EXIF metadata.
    """
    import pyvips

    for key, width, height in _DERIVED_SIZES:
        # Load from memory; access=sequential avoids full decode for large images.
        img = pyvips.Image.new_from_buffer(image_bytes, "", access="sequential")

        # thumbnail_image: smartcrop='attention' picks the most interesting region.
        # size=pyvips.enums.Size.FORCE ensures we always scale to exactly (width, height).
        resized = img.thumbnail_image(
            width,
            height=height,
            crop=pyvips.enums.Interesting.ATTENTION,
            size=pyvips.enums.Size.FORCE,
        )

        # Strip EXIF + ICC by saving without any metadata.
        webp_bytes = resized.webpsave_buffer(strip=True, Q=85)
        jpeg_bytes = resized.jpegsave_buffer(strip=True, Q=85)

        _upload_derived_blob(institution_id, product_id, key, webp_bytes, "image/webp")
        _upload_derived_blob(institution_id, product_id, f"{key}.jpg", jpeg_bytes, "image/jpeg")

        logger.info("Uploaded %s (webp + jpg) for product %s", key, product_id)


def process_image(image_asset_id: UUID, db: psycopg2.extensions.connection, *, force: bool = False) -> None:
    """
    Core image processing function. Idempotent.

    Steps:
      1. Load image_asset row; bail if missing.
      2. Skip if already at PROCESSING_VERSION + ready, unless force=True.
      3. Flip to pipeline_status='processing'.
      4. Download original from GCS.
      5. Run Cloud Vision SafeSearch.
      6. Reject or pass based on moderation threshold.
      7. On pass: run pyvips, upload derived sizes, flip to 'ready'.
      8. On any error: increment failure_count; flip to 'failed' after 3 attempts.
    """
    from app.config.settings import settings

    row = _get_asset_row(image_asset_id, db)
    if row is None:
        logger.info("image_asset %s not found — likely already deleted, skipping", image_asset_id)
        return

    # Idempotency check.
    if not force and row["processing_version"] == PROCESSING_VERSION and row["pipeline_status"] == "ready":
        logger.info("image_asset %s already at version %s/ready — skipping", image_asset_id, PROCESSING_VERSION)
        return

    institution_id = str(row["institution_id"])
    product_id = str(row["product_id"])
    failure_count = int(row["failure_count"])

    _set_pipeline_status(image_asset_id, db, pipeline_status="processing")

    try:
        # Step 4: download original.
        image_bytes = _download_original(institution_id, product_id)

        # Step 5: SafeSearch moderation.
        signals = _run_safe_search(image_bytes)

        threshold = getattr(settings, "MODERATION_REJECT_LIKELIHOOD", "LIKELY")

        if _should_reject(signals, threshold):
            logger.warning("image_asset %s rejected by SafeSearch (threshold=%s)", image_asset_id, threshold)
            _delete_original_blob(institution_id, product_id)
            _set_pipeline_status(
                image_asset_id,
                db,
                pipeline_status="rejected",
                moderation_status="rejected",
                moderation_signals=_json_dumps(signals),
            )
            return

        # Step 6: moderation passed.
        _set_pipeline_status(
            image_asset_id,
            db,
            moderation_status="passed",
            moderation_signals=_json_dumps(signals),
        )

        # Step 7: pyvips resizing + upload.
        _process_with_pyvips(image_bytes, institution_id, product_id)

        _set_pipeline_status(
            image_asset_id,
            db,
            pipeline_status="ready",
            processing_version=PROCESSING_VERSION,
        )
        logger.info("image_asset %s processing complete (version %s)", image_asset_id, PROCESSING_VERSION)

    except Exception:
        logger.exception("image_asset %s processing failed", image_asset_id)
        failure_count += 1
        new_status = "failed" if failure_count >= 3 else "pending"
        _set_pipeline_status(image_asset_id, db, pipeline_status=new_status, failure_count=failure_count)


def _json_dumps(obj: object) -> str:
    """JSON-serialize a dict for JSONB columns."""
    import json

    return json.dumps(obj)
