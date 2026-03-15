"""
Product Image Management Service

Handles product image uploads, resizing, checksum calculation, storage, and cleanup.
Designed to mirror the QR code service structure for easy migration to S3 later.
"""

import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Tuple, Optional
from uuid import UUID
import hashlib

from fastapi import HTTPException
from PIL import Image

from app.utils.log import log_error, log_info, log_warning


class ProductImageService:
    """Service responsible for storing and maintaining product images."""

    def __init__(self) -> None:
        self.storage_mode = os.getenv("PRODUCT_IMAGE_STORAGE_MODE", "local")  # Future S3 support
        self.local_storage_path = os.getenv("PRODUCT_IMAGE_LOCAL_PATH", "static/product_images")
        self.base_url = os.getenv("PRODUCT_IMAGE_BASE_URL", "http://localhost:8000/static/product_images")

        # Placeholder configuration
        self.placeholder_storage_path = os.getenv(
            "PRODUCT_IMAGE_PLACEHOLDER_PATH", "static/placeholders/product_default.png"
        )
        self.placeholder_url = os.getenv(
            "PRODUCT_IMAGE_PLACEHOLDER_URL", "http://localhost:8000/static/placeholders/product_default.png"
        )
        self.placeholder_checksum = os.getenv(
            "PRODUCT_IMAGE_PLACEHOLDER_CHECKSUM",
            "7d959ae9353a02d3707dbeefe68f0af43e35d3ff8b479e8a9b16121d90ce947c",
        )

        # Image processing configuration
        self.max_dimension = int(os.getenv("PRODUCT_IMAGE_MAX_DIMENSION", "1024"))
        self.thumbnail_dimension = int(os.getenv("PRODUCT_IMAGE_THUMBNAIL_DIMENSION", "300"))
        self.output_format = os.getenv("PRODUCT_IMAGE_FORMAT", "PNG").upper()
        self.allowed_content_types = {"image/png", "image/jpeg", "image/webp"}

    def save_image(
        self,
        product_id: UUID,
        *,
        image_bytes: bytes,
        content_type: str,
        expected_checksum: Optional[str] = None,
    ) -> Tuple[str, str, str, str, str]:
        """
        Persist an uploaded image (full-size + thumbnail) and return storage metadata.

        Args:
            product_id: Product identifier to namespace the image.
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
        # This ensures the checksum matches what the client sent
        original_checksum = hashlib.sha256(image_bytes).hexdigest()

        # Validate checksum of the uploaded payload if provided
        if expected_checksum:
            normalized_expected = expected_checksum.strip().lower()
            if len(normalized_expected) != 64:
                raise HTTPException(status_code=400, detail="Provided checksum must be a 64-character SHA-256 hex string")
            try:
                int(normalized_expected, 16)
            except ValueError:
                raise HTTPException(status_code=400, detail="Provided checksum must contain only hexadecimal characters")
            if original_checksum != normalized_expected:
                raise HTTPException(status_code=400, detail="Image checksum mismatch. Please re-upload the file.")

        # Process image AFTER checksum computation
        try:
            image = Image.open(BytesIO(image_bytes))
        except Exception:
            raise HTTPException(status_code=400, detail="Unable to read image file")

        # Normalize image to RGB
        image = image.convert("RGB")

        # Full-size: resize to max_dimension (1024) if larger
        image_full = image.copy()
        if max(image_full.size) > self.max_dimension:
            image_full.thumbnail((self.max_dimension, self.max_dimension), Image.LANCZOS)

        # Thumbnail: resize to thumbnail_dimension (e.g. 300x300)
        image_thumb = image.copy()
        if max(image_thumb.size) > self.thumbnail_dimension:
            image_thumb.thumbnail((self.thumbnail_dimension, self.thumbnail_dimension), Image.LANCZOS)

        now = datetime.now(timezone.utc)
        year_month = f"{now.year}/{now.month:02d}"
        ext = self.output_format.lower()
        filename = f"{product_id}.{ext}"
        thumb_filename = f"{product_id}_thumb.{ext}"

        if self.storage_mode != "local":
            log_error("Only local storage mode is implemented for product images")
            raise HTTPException(
                status_code=500,
                detail="Product image storage is not configured for non-local environments",
            )

        storage_dir = os.path.join(self.local_storage_path, year_month)
        os.makedirs(storage_dir, exist_ok=True)

        # Save full-size
        buffer_full = BytesIO()
        image_full.save(buffer_full, format=self.output_format, optimize=True)
        absolute_path_full = os.path.join(storage_dir, filename)
        with open(absolute_path_full, "wb") as file:
            file.write(buffer_full.getvalue())

        # Save thumbnail
        buffer_thumb = BytesIO()
        image_thumb.save(buffer_thumb, format=self.output_format, optimize=True)
        absolute_path_thumb = os.path.join(storage_dir, thumb_filename)
        with open(absolute_path_thumb, "wb") as file:
            file.write(buffer_thumb.getvalue())

        # Normalize paths with forward slashes for DB storage
        storage_path = os.path.join(self.local_storage_path, year_month, filename).replace("\\", "/")
        url_path = f"{self.base_url}/{year_month}/{filename}"
        thumbnail_storage_path = os.path.join(self.local_storage_path, year_month, thumb_filename).replace("\\", "/")
        thumbnail_url_path = f"{self.base_url}/{year_month}/{thumb_filename}"

        log_info(f"Product image saved: {storage_path}, thumbnail: {thumbnail_storage_path}")
        return storage_path, url_path, thumbnail_storage_path, thumbnail_url_path, original_checksum

    def delete_image(self, storage_path: str, thumbnail_storage_path: Optional[str] = None) -> None:
        """Remove an image (and optionally its thumbnail) from storage (ignoring placeholder)."""
        paths_to_delete = [p for p in (storage_path, thumbnail_storage_path) if p and not self.is_placeholder(p)]
        for p in paths_to_delete:
            try:
                absolute_path = p if os.path.isabs(p) else os.path.abspath(p)
                if os.path.exists(absolute_path):
                    os.remove(absolute_path)
                    log_info(f"Product image deleted: {absolute_path}")
            except Exception as exc:
                log_error(f"Failed to delete product image {p}: {exc}")

    def is_placeholder(self, storage_path: str) -> bool:
        """Check whether the provided storage path points to the placeholder image."""
        return storage_path == self.placeholder_storage_path

    def placeholder_metadata(self) -> Tuple[str, str, str]:
        """Return (storage_path, url, checksum) for the placeholder asset."""
        return self.placeholder_storage_path, self.placeholder_url, self.placeholder_checksum

    def validate_placeholder_exists(self) -> bool:
        """Check if the placeholder image file exists on disk."""
        placeholder_path = self.placeholder_storage_path
        if not os.path.isabs(placeholder_path):
            placeholder_path = os.path.abspath(placeholder_path)
        return os.path.exists(placeholder_path)

    def ensure_placeholder_exists(self) -> None:
        """
        Ensure the placeholder image file exists. Create it if missing.
        
        Raises:
            HTTPException: If placeholder cannot be created
        """
        if self.validate_placeholder_exists():
            log_info("Placeholder image exists and is accessible")
            return

        log_warning(f"Placeholder image missing at {self.placeholder_storage_path}, attempting to create...")

        try:
            # Create directory if it doesn't exist
            placeholder_dir = os.path.dirname(self.placeholder_storage_path)
            if placeholder_dir and not os.path.exists(placeholder_dir):
                os.makedirs(placeholder_dir, exist_ok=True)
                log_info(f"Created placeholder directory: {placeholder_dir}")

            # Try to find placeholder in alternate locations (for deployment scenarios)
            possible_locations = [
                self.placeholder_storage_path,
                os.path.join("app", "static", "placeholders", "product_default.png"),
                os.path.join("static", "placeholders", "product_default.png"),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "static", "placeholders", "product_default.png")),
            ]

            # Try to copy from alternate location
            for location in possible_locations:
                abs_location = os.path.abspath(location) if not os.path.isabs(location) else location
                if os.path.exists(abs_location) and abs_location != os.path.abspath(self.placeholder_storage_path):
                    import shutil
                    shutil.copy2(abs_location, os.path.abspath(self.placeholder_storage_path))
                    log_info(f"Copied placeholder from {abs_location} to {self.placeholder_storage_path}")
                    return

            # If placeholder doesn't exist anywhere, create a minimal placeholder
            # This creates a simple grey 1x1 PNG as a fallback
            placeholder_img = Image.new('RGB', (100, 100), color='#CCCCCC')
            abs_placeholder_path = os.path.abspath(self.placeholder_storage_path)
            placeholder_img.save(abs_placeholder_path, 'PNG')
            log_warning(f"Created minimal placeholder image at {abs_placeholder_path}")

        except Exception as exc:
            error_msg = f"Cannot create product without valid placeholder image. Placeholder missing at {self.placeholder_storage_path} and could not be created: {exc}"
            log_error(error_msg)
            raise HTTPException(
                status_code=500,
                detail=error_msg
            )

    def validate_product_image_at_creation(
        self,
        image_storage_path: Optional[str] = None,
        image_url: Optional[str] = None,
        image_checksum: Optional[str] = None
    ) -> Tuple[str, str, str]:
        """
        Validate and ensure product has valid image at creation time.
        
        Args:
            image_storage_path: Optional custom image storage path
            image_url: Optional custom image URL
            image_checksum: Optional custom image checksum
            
        Returns:
            Tuple of (storage_path, url, checksum) - either custom or placeholder values
            
        Raises:
            HTTPException: If image validation fails
        """
        # If no custom image provided, use placeholder
        if not image_storage_path or self.is_placeholder(image_storage_path):
            log_info("No custom image provided for product, using placeholder")
            self.ensure_placeholder_exists()
            return self.placeholder_metadata()

        # If custom image provided, validate it exists
        abs_custom_path = os.path.abspath(image_storage_path) if not os.path.isabs(image_storage_path) else image_storage_path
        if not os.path.exists(abs_custom_path):
            error_msg = f"Custom image file not found at {image_storage_path}. Cannot create product without valid image."
            log_error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        log_info(f"Custom image validated: {image_storage_path}")
        # Return custom image values (URL and checksum should be provided)
        return (
            image_storage_path,
            image_url or self.placeholder_url,  # Fallback to placeholder URL if not provided
            image_checksum or self.placeholder_checksum  # Fallback to placeholder checksum if not provided
        )

