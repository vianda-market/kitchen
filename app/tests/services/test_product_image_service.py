"""
Unit tests for ProductImageService path-confine guard in delete_image.

Tests the Path.resolve() + base-dir-confine hardening added in kitchen#91 PR-B.
Only covers the new security guard; other service behaviour (GCS mode, image
processing) is tested via Postman collections per the repo testing convention.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.services.product_image_service import ProductImageService


class TestDeleteImagePathConfineGuard:
    """Tests for the path-traversal confine guard in delete_image (local mode)."""

    def _make_service(self, local_path: str) -> ProductImageService:
        svc = ProductImageService.__new__(ProductImageService)
        svc._gcs_mode = False
        svc.local_storage_path = local_path
        svc.base_url = "http://localhost:8000/static/product_images"
        svc.max_dimension = 1024
        svc.thumbnail_dimension = 300
        svc.output_format = "PNG"
        svc.allowed_content_types = {"image/png", "image/jpeg", "image/webp"}
        return svc

    def test_delete_image_normal_path_removes_file(self, tmp_path: Path) -> None:
        """delete_image with a valid in-base path deletes the file."""
        # Arrange
        svc = self._make_service(str(tmp_path))
        image_file = tmp_path / "2024" / "01" / "some_product.png"
        image_file.parent.mkdir(parents=True)
        image_file.write_bytes(b"fake-image-data")
        relative_path = str(image_file.relative_to(tmp_path))

        # Act — no exception should be raised
        svc.delete_image(relative_path)

        # Assert — file was deleted
        assert not image_file.exists()

    def test_delete_image_escape_attempt_raises_http_exception(self, tmp_path: Path) -> None:
        """delete_image with a path-traversal sequence raises HTTPException 500."""
        # Arrange
        svc = self._make_service(str(tmp_path))
        # Classic ../.. escape — resolves outside tmp_path
        escape_path = "../../etc/passwd"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            svc.delete_image(escape_path)

        assert exc_info.value.status_code == 500

    def test_delete_image_absolute_escape_raises_http_exception(self, tmp_path: Path) -> None:
        """delete_image with an absolute path outside base dir raises HTTPException 500."""
        # Arrange
        svc = self._make_service(str(tmp_path))
        # An absolute path that points somewhere outside tmp_path
        outside_path = "/tmp/some_other_file.png"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            svc.delete_image(outside_path)

        assert exc_info.value.status_code == 500

    def test_delete_image_nonexistent_in_base_path_does_not_raise(self, tmp_path: Path) -> None:
        """delete_image with a valid in-base path that does not exist silently passes."""
        # Arrange
        svc = self._make_service(str(tmp_path))
        relative_path = "2024/01/missing_product.png"

        # Act — should not raise (file simply does not exist)
        svc.delete_image(relative_path)

    def test_delete_image_placeholder_is_skipped(self, tmp_path: Path) -> None:
        """delete_image skips placeholder paths without touching the filesystem."""
        svc = self._make_service(str(tmp_path))
        with patch.object(Path, "exists") as mock_exists:
            svc.delete_image("placeholder/product_default.png")
            mock_exists.assert_not_called()

    def test_delete_image_empty_path_is_skipped(self, tmp_path: Path) -> None:
        """delete_image silently returns when storage_path is empty."""
        svc = self._make_service(str(tmp_path))
        svc.delete_image("")  # Should not raise
