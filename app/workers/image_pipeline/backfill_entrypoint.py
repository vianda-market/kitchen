"""
Backfill worker — re-processes all image_asset rows with processing_version < PROCESSING_VERSION.

Cloud Run jobs run to completion; this exits 0 when all rows are processed.
Called by scripts/entrypoint.sh when RUN_MODE=image_backfill.
"""

import logging
from uuid import UUID

from app.workers.image_pipeline.processing import PROCESSING_VERSION, process_image

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


def run_image_backfill() -> None:
    """Iterate stale image_asset rows in batches and re-process each one."""
    import logging as _logging

    _logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    logger.info("image_backfill starting — target processing_version=%d", PROCESSING_VERSION)

    from app.utils.db import db_read
    from app.utils.db_pool import get_db_connection_context

    processed = 0
    failed = 0
    offset = 0

    while True:
        with get_db_connection_context() as db:
            rows = db_read(
                """
                SELECT image_asset_id
                FROM ops.image_asset
                WHERE processing_version < %s
                ORDER BY created_date
                LIMIT %s OFFSET %s
                """,
                (PROCESSING_VERSION, _BATCH_SIZE, offset),
                connection=db,
                fetch_one=False,
            )

        if not rows:
            break

        logger.info("Backfill batch: %d rows at offset %d", len(rows), offset)

        for row in rows:
            row_dict: dict[str, object] = row  # type: ignore[assignment]
            image_asset_id = UUID(str(row_dict["image_asset_id"]))
            try:
                with get_db_connection_context() as db:
                    process_image(image_asset_id, db, force=True)
                processed += 1
            except Exception:
                logger.exception("Backfill failed for image_asset %s", image_asset_id)
                failed += 1

        offset += _BATCH_SIZE

    logger.info(
        "image_backfill complete — processed=%d failed=%d",
        processed,
        failed,
    )
