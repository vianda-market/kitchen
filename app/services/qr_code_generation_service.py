"""
QR Code Generation Service

This service handles QR code image generation and storage management.
Supports local development storage and GCS (Cloud Run).
"""

import hashlib
import os
from datetime import datetime
from io import BytesIO
from uuid import UUID

import qrcode
from fastapi import HTTPException

from app.config.settings import settings
from app.utils.log import log_error, log_info

# Local dev only — in GCS mode (GCS_INTERNAL_BUCKET set), files go to GCS instead
STATIC_QR_DIR = "static/qr_codes"


class QRCodeGenerationService:
    """Service for generating QR code images and managing storage."""

    def __init__(self) -> None:
        self.image_format = "PNG"
        self._gcs_mode = bool(settings.GCS_INTERNAL_BUCKET)
        self.local_storage_path = os.getenv("QR_LOCAL_STORAGE_PATH", STATIC_QR_DIR)
        self.base_url = os.getenv("QR_BASE_URL", "http://localhost:8000/static/qr_codes")

    def generate_qr_code_image(
        self,
        qr_code_id: UUID,
        restaurant_id: UUID,
        payload: str,
    ) -> tuple[str, str, str]:
        """
        Generate QR code image and return (storage_path, url_path, checksum).

        Returns:
            Tuple of (storage_path, url_path, checksum).
            In GCS mode, url_path equals storage_path; signed URLs resolved at read time.
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(payload)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format=self.image_format)
            image_bytes = buffer.getvalue()
            checksum = hashlib.sha256(image_bytes).hexdigest()

            if self._gcs_mode:
                storage_path, url_path = self._generate_gcs_storage(qr_code_id, restaurant_id, image_bytes)
            else:
                now = datetime.now()
                year_month = f"{now.year}/{now.month:02d}"
                filename = f"{qr_code_id}.{self.image_format.lower()}"
                storage_path, url_path = self._generate_local_storage(year_month, filename, image_bytes)

            return storage_path, url_path, checksum

        except Exception as e:
            log_error(f"Failed to generate QR code image for {qr_code_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate QR code image") from None

    def _generate_local_storage(self, year_month: str, filename: str, image_bytes: bytes) -> tuple[str, str]:
        """Save QR code image to local storage."""
        file_path = os.path.join(self.local_storage_path, year_month, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        url_path = f"{self.base_url}/{year_month}/{filename}"
        log_info(f"QR code image saved locally: {file_path}")
        return file_path, url_path

    def _generate_gcs_storage(self, qr_code_id: UUID, restaurant_id: UUID, image_bytes: bytes) -> tuple[str, str]:
        """Upload QR code image to GCS internal bucket."""
        from app.utils.gcs import upload_qr_code

        blob_path = upload_qr_code(qr_code_id, restaurant_id, image_bytes)
        log_info(f"QR code image uploaded to GCS: {blob_path}")
        return blob_path, blob_path

    def delete_qr_code_image(self, storage_path: str) -> bool:
        """
        Delete QR code image from storage.
        In GCS mode, storage_path is the blob name (e.g. qrcodes/{restaurant_id}/{qr_code_id}.png).
        """
        try:
            if self._gcs_mode and storage_path.startswith("qrcodes/"):
                from app.utils.gcs import delete_qr_code_blob

                try:
                    delete_qr_code_blob(storage_path)
                    log_info(f"QR code image deleted from GCS: {storage_path}")
                    return True
                except Exception as e:
                    log_error(f"Failed to delete QR code from GCS {storage_path}: {e}")
                    return False
            return self._delete_local_image(storage_path)
        except Exception as e:
            log_error(f"Failed to delete QR code image {storage_path}: {e}")
            return False

    def _delete_local_image(self, storage_path: str) -> bool:
        """Delete QR code image from local storage."""
        try:
            if os.path.exists(storage_path):
                os.remove(storage_path)
                log_info(f"QR code image deleted: {storage_path}")
                return True
            log_info(f"QR code image not found: {storage_path}")
            return True
        except Exception as e:
            log_error(f"Failed to delete local QR code image {storage_path}: {e}")
            return False
