"""
Product Image Management Service

Handles product image uploads, resizing, checksum calculation, storage, and cleanup.
Supports local storage (dev) and GCS (Cloud Run).
"""

import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional
from uuid import UUID
import hashlib

from fastapi import HTTPException
from PIL import Image

from app.config.settings import settings
from app.utils.log import log_error, log_info, log_warning

# Local dev only — in GCS mode (GCS_SUPPLIER_BUCKET set), files go to GCS instead
STATIC_PRODUCT_DIR = "static/product_images"


class ProductImageService:
    """Service responsible for storing and maintaining product images."""

    PLACEHOLDER_CHECKSUM = "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c"

    def __init__(self) -> None:
        self._gcs_mode = bool(settings.GCS_SUPPLIER_BUCKET)
        self.local_storage_path = os.getenv("PRODUCT_IMAGE_LOCAL_PATH", STATIC_PRODUCT_DIR)
        self.base_url = os.getenv("PRODUCT_IMAGE_BASE_URL", "http://localhost:8000/static/product_images")

        # Image processing configuration
        self.max_dimension = int(os.getenv("PRODUCT_IMAGE_MAX_DIMENSION", "1024"))
        self.thumbnail_dimension = int(os.getenv("PRODUCT_IMAGE_THUMBNAIL_DIMENSION", "300"))
        self.output_format = os.getenv("PRODUCT_IMAGE_FORMAT", "PNG").upper()
        self.allowed_content_types = {"image/png", "image/jpeg", "image/webp"}

    def save_image(
        self,
        product_id: UUID,
        institution_id: UUID,
        *,
        image_bytes: bytes,
        content_type: str,
        expected_checksum: Optional[str] = None,
    ) -> tuple[str, str, str, str, str]:
        """
        Persist an uploaded image (full-size + thumbnail) and return storage metadata.

        Args:
            product_id: Product identifier to namespace the image.
            institution_id: Institution identifier (for GCS path).
            image_bytes: Raw uploaded bytes.
            content_type: Original content type for validation.

        Returns:
            Tuple of (storage_path, url_path, thumbnail_storage_path, thumbnail_url_path, checksum).
        """
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Uploaded image is empty")

        if content_type not in self.allowed_content_types:
            raise HTTPException(
                status_code=400,
                detail="Unsupported image type. Allowed types: PNG, JPEG, WEBP",
            )

        # Compute checksum from ORIGINAL bytes FIRST (before any processing)
        original_checksum = hashlib.sha256(image_bytes).hexdigest()

        # Validate checksum of the uploaded payload if provided
        if expected_checksum:
            normalized_expected = expected_checksum.strip().lower()
            if len(normalized_expected) != 64:
                raise HTTPException(
                    status_code=400,
                    detail="Provided checksum must be a 64-character SHA-256 hex string",
                )
            try:
                int(normalized_expected, 16)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Provided checksum must contain only hexadecimal characters",
                )
            if original_checksum != normalized_expected:
                raise HTTPException(
                    status_code=400, detail="Image checksum mismatch. Please re-upload the file."
                )

        # Process image AFTER checksum computation
        try:
            image = Image.open(BytesIO(image_bytes))
        except Exception:
            raise HTTPException(status_code=400, detail="Unable to read image file")

        image = image.convert("RGB")
        image_full = image.copy()
        if max(image_full.size) > self.max_dimension:
            image_full.thumbnail((self.max_dimension, self.max_dimension), Image.LANCZOS)
        image_thumb = image.copy()
        if max(image_thumb.size) > self.thumbnail_dimension:
            image_thumb.thumbnail(
                (self.thumbnail_dimension, self.thumbnail_dimension), Image.LANCZOS
            )

        buffer_full = BytesIO()
        image_full.save(buffer_full, format=self.output_format, optimize=True)
        full_bytes = buffer_full.getvalue()
        buffer_thumb = BytesIO()
        image_thumb.save(buffer_thumb, format=self.output_format, optimize=True)
        thumb_bytes = buffer_thumb.getvalue()

        if self._gcs_mode:
            from app.utils.gcs import upload_product_image

            blob_full, blob_thumb = upload_product_image(
                product_id, institution_id, full_bytes, thumb_bytes, content_type
            )
            # Store blob paths; API resolution injects signed URLs at read time
            return blob_full, blob_full, blob_thumb, blob_thumb, original_checksum

        # Local mode
        now = datetime.now(timezone.utc)
        year_month = f"{now.year}/{now.month:02d}"
        ext = self.output_format.lower()
        filename = f"{product_id}.{ext}"
        thumb_filename = f"{product_id}_thumb.{ext}"
        storage_dir = os.path.join(self.local_storage_path, year_month)
        os.makedirs(storage_dir, exist_ok=True)
        absolute_path_full = os.path.join(storage_dir, filename)
        with open(absolute_path_full, "wb") as f:
            f.write(full_bytes)
        absolute_path_thumb = os.path.join(storage_dir, thumb_filename)
        with open(absolute_path_thumb, "wb") as f:
            f.write(thumb_bytes)
        storage_path = os.path.join(self.local_storage_path, year_month, filename).replace(
            "\\", "/"
        )
        url_path = f"{self.base_url}/{year_month}/{filename}"
        thumbnail_storage_path = os.path.join(
            self.local_storage_path, year_month, thumb_filename
        ).replace("\\", "/")
        thumbnail_url_path = f"{self.base_url}/{year_month}/{thumb_filename}"
        log_info(f"Product image saved: {storage_path}, thumbnail: {thumbnail_storage_path}")
        return storage_path, url_path, thumbnail_storage_path, thumbnail_url_path, original_checksum

    def delete_image(
        self,
        storage_path: str,
        thumbnail_storage_path: Optional[str] = None,
    ) -> None:
        """Remove an image (and optionally its thumbnail) from storage (ignoring placeholder)."""
        if not storage_path or self.is_placeholder(storage_path):
            return
        if self._gcs_mode and storage_path.startswith("products/"):
            # Parse products/{institution_id}/{product_id}/image or /thumbnail
            parts = storage_path.split("/")
            if len(parts) >= 4:
                from app.utils.gcs import delete_product_image

                try:
                    delete_product_image(UUID(parts[2]), UUID(parts[1]))
                    log_info(f"Product image deleted from GCS: {storage_path}")
                except Exception as exc:
                    log_error(f"Failed to delete product image from GCS {storage_path}: {exc}")
            return
        # Local mode
        for p in (storage_path, thumbnail_storage_path):
            if not p or self.is_placeholder(p):
                continue
            try:
                absolute_path = p if os.path.isabs(p) else os.path.abspath(p)
                if os.path.exists(absolute_path):
                    os.remove(absolute_path)
                    log_info(f"Product image deleted: {absolute_path}")
            except Exception as exc:
                log_error(f"Failed to delete product image {p}: {exc}")

    def is_placeholder(self, storage_path: str) -> bool:
        """Check whether the provided storage path points to the placeholder image."""
        return storage_path in (
            "placeholder/product_default.png",
            "static/placeholders/product_default.png",
        )

    def get_default_storage_path(self) -> str:
        """Return default storage path based on environment (GCS or local)."""
        if settings.GCS_INTERNAL_BUCKET:
            return "placeholder/product_default.png"
        return "static/placeholders/product_default.png"

    def placeholder_metadata(self) -> dict:
        """Return placeholder metadata (storage_path, image_url, thumbnail_*, checksum)."""
        from app.utils.gcs import get_placeholder_signed_url

        if settings.GCS_INTERNAL_BUCKET:
            url = get_placeholder_signed_url()
            return {
                "storage_path": "placeholder/product_default.png",
                "image_url": url,
                "thumbnail_storage_path": "placeholder/product_default.png",
                "thumbnail_url": url,
                "checksum": self.PLACEHOLDER_CHECKSUM,
            }
        return {
            "storage_path": "static/placeholders/product_default.png",
            "image_url": "/static/placeholders/product_default.png",
            "thumbnail_storage_path": "static/placeholders/product_default.png",
            "thumbnail_url": "/static/placeholders/product_default.png",
            "checksum": self.PLACEHOLDER_CHECKSUM,
        }

    def validate_placeholder_exists(self) -> bool:
        """Check if the placeholder image file exists (local mode only)."""
        if settings.GCS_INTERNAL_BUCKET:
            return True
        path = os.path.abspath("static/placeholders/product_default.png")
        return os.path.exists(path)

    def ensure_placeholder_exists(self) -> None:
        """
        Ensure the placeholder exists. In GCS mode, no-op (placeholder in GCS).
        In local mode, create if missing.
        """
        if settings.GCS_INTERNAL_BUCKET:
            return
        if self.validate_placeholder_exists():
            return
        log_warning("Placeholder image missing, attempting to create...")
        try:
            import shutil

            placeholder_path = "static/placeholders/product_default.png"
            os.makedirs(os.path.dirname(placeholder_path), exist_ok=True)
            for loc in [
                "static/placeholders/product_default.png",
                os.path.join(os.path.dirname(__file__), "..", "..", "static", "placeholders", "product_default.png"),
            ]:
                abs_loc = os.path.abspath(loc)
                if os.path.exists(abs_loc):
                    shutil.copy2(abs_loc, os.path.abspath(placeholder_path))
                    return
            placeholder_img = Image.new("RGB", (100, 100), color="#CCCCCC")
            placeholder_img.save(os.path.abspath(placeholder_path), "PNG")
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Cannot create product without valid placeholder: {exc}",
            )

    def validate_product_image_at_creation(
        self,
        image_storage_path: Optional[str] = None,
        image_url: Optional[str] = None,
        image_checksum: Optional[str] = None,
    ) -> dict:
        """
        Validate and ensure product has valid image at creation time.

        Returns:
            Dict with storage_path, image_url, thumbnail_storage_path, thumbnail_url, checksum.
        """
        if not image_storage_path or self.is_placeholder(image_storage_path):
            log_info("No custom image provided for product, using placeholder")
            self.ensure_placeholder_exists()
            return self.placeholder_metadata()
        if not settings.GCS_INTERNAL_BUCKET:
            abs_custom_path = (
                os.path.abspath(image_storage_path)
                if not os.path.isabs(image_storage_path)
                else image_storage_path
            )
            if not os.path.exists(abs_custom_path):
                raise HTTPException(
                    status_code=400,
                    detail=f"Custom image file not found at {image_storage_path}",
                )
        meta = self.placeholder_metadata()
        return {
            "storage_path": image_storage_path,
            "image_url": image_url or meta["image_url"],
            "thumbnail_storage_path": image_storage_path,
            "thumbnail_url": image_url or meta["thumbnail_url"],
            "checksum": image_checksum or meta["checksum"],
        }

