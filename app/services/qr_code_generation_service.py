"""
QR Code Generation Service

This service handles QR code image generation and storage management.
Supports both local development storage and S3 cloud storage.
"""

import qrcode
import os
from datetime import datetime
from uuid import UUID
from typing import Tuple, Optional
from fastapi import HTTPException
from io import BytesIO
import hashlib
from app.utils.log import log_info, log_error

class QRCodeGenerationService:
    """Service for generating QR code images and managing storage"""
    
    def __init__(self):
        # Configuration for QR code generation
        self.image_size = 200
        self.image_format = "PNG"
        
        # Storage configuration
        self.storage_mode = os.getenv("QR_STORAGE_MODE", "local")  # "local" or "s3"
        self.local_storage_path = "static/qr_codes"
        self.base_url = os.getenv("QR_BASE_URL", "http://localhost:8000/static/qr_codes")
        
        # S3 configuration (for future deployment)
        self.s3_bucket = os.getenv("QR_S3_BUCKET", "")
        self.s3_region = os.getenv("QR_S3_REGION", "us-east-1")
    
    def generate_qr_code_image(
        self,
        qr_code_id: UUID,
        restaurant_id: UUID,
        payload: str
    ) -> Tuple[str, str, str]:
        """
        Generate QR code image and return (storage_path, url_path, checksum)
        
        Args:
            qr_code_id: Unique QR code identifier
            restaurant_id: Restaurant identifier
            payload: QR code data to encode
            
        Returns:
            Tuple[str, str, str]: (storage_path, url_path, checksum)
            
        Raises:
            HTTPException: If image generation fails
        """
        try:
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(payload)
            qr.make(fit=True)

            # Create image
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to bytes for storage/checksum
            buffer = BytesIO()
            img.save(buffer, format=self.image_format)
            image_bytes = buffer.getvalue()
            checksum = hashlib.sha256(image_bytes).hexdigest()

            # Generate file paths
            now = datetime.now()
            year_month = f"{now.year}/{now.month:02d}"
            filename = f"{qr_code_id}.{self.image_format.lower()}"

            if self.storage_mode == "local":
                storage_path, url_path = self._generate_local_storage(year_month, filename, image_bytes)
            else:
                storage_path, url_path = self._generate_s3_storage(year_month, filename, image_bytes)

            return storage_path, url_path, checksum

        except Exception as e:
            log_error(f"Failed to generate QR code image for {qr_code_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate QR code image"
            )
    
    def _generate_local_storage(self, year_month: str, filename: str, image_bytes: bytes) -> Tuple[str, str]:
        """Generate QR code image for local storage"""
        # Create local file path
        file_path = os.path.join(self.local_storage_path, year_month, filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save image
        with open(file_path, "wb") as file:
            file.write(image_bytes)
        
        # Generate URL path
        url_path = f"{self.base_url}/{year_month}/{filename}"
        
        log_info(f"QR code image saved locally: {file_path}")
        return file_path, url_path
    
    def _generate_s3_storage(self, year_month: str, filename: str, image_bytes: bytes) -> Tuple[str, str]:
        """Generate QR code image for S3 storage (future implementation)"""
        # TODO: Implement S3 upload when deploying to AWS
        # For now, fall back to local storage
        log_info("S3 storage not yet implemented, using local storage")
        return self._generate_local_storage(year_month, filename, image_bytes)
    
    def delete_qr_code_image(self, storage_path: str) -> bool:
        """
        Delete QR code image from storage
        
        Args:
            storage_path: Path to the image file
            
        Returns:
            bool: True if deletion successful, False otherwise
        """
        try:
            if self.storage_mode == "local":
                return self._delete_local_image(storage_path)
            else:
                return self._delete_s3_image(storage_path)
        except Exception as e:
            log_error(f"Failed to delete QR code image {storage_path}: {e}")
            return False
    
    def _delete_local_image(self, storage_path: str) -> bool:
        """Delete QR code image from local storage"""
        try:
            if os.path.exists(storage_path):
                os.remove(storage_path)
                log_info(f"QR code image deleted: {storage_path}")
                return True
            else:
                log_info(f"QR code image not found: {storage_path}")
                return True  # Consider it successful if file doesn't exist
        except Exception as e:
            log_error(f"Failed to delete local QR code image {storage_path}: {e}")
            return False
    
    def _delete_s3_image(self, storage_path: str) -> bool:
        """Delete QR code image from S3 storage (future implementation)"""
        # TODO: Implement S3 deletion when deploying to AWS
        log_info("S3 deletion not yet implemented")
        return True
