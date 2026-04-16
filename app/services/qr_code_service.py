"""
Atomic QR Code Service

This service provides atomic QR code creation and deletion operations.
Ensures data consistency between database records and image files.
"""

from uuid import UUID

import psycopg2.extensions
from fastapi import HTTPException

from app.dto.models import QRCodeDTO
from app.security.institution_scope import InstitutionScope
from app.services.crud_service import qr_code_service
from app.services.qr_code_generation_service import QRCodeGenerationService
from app.utils.log import log_error, log_info


class AtomicQRCodeService:
    """Service for atomic QR code operations"""

    def __init__(self):
        self.generation_service = QRCodeGenerationService()

    def create_qr_code_atomic(
        self,
        restaurant_id: UUID,
        current_user: UUID,
        db: psycopg2.extensions.connection,
        scope: InstitutionScope | None = None,
    ) -> QRCodeDTO:
        """
        Atomically create QR code with image generation.
        If image generation fails, QR code creation is rolled back.

        Args:
            restaurant_id: Restaurant identifier
            current_user: User creating the QR code
            db: Database connection

        Returns:
            QRCodeDTO: Complete QR code record with image

        Raises:
            HTTPException: If creation fails
        """
        try:
            from app.utils.qr_hmac import build_signed_qr_url

            # Start transaction
            with db.cursor() as cursor:
                # 1. Insert QR code with placeholder payload and paths
                cursor.execute(
                    """
                    INSERT INTO qr_code
                    (restaurant_id, qr_code_payload, qr_code_image_url, image_storage_path, modified_by)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING qr_code_id
                """,
                    (
                        str(restaurant_id),
                        "",  # Placeholder — signed URL computed after we get qr_code_id
                        "",
                        "",
                        str(current_user),
                    ),
                )

                qr_code_id = cursor.fetchone()[0]

                # 2. Build signed QR URL payload from the generated qr_code_id
                payload = build_signed_qr_url(str(qr_code_id))

                # 3. Generate QR code image encoding the signed URL
                storage_path, url_path, checksum = self.generation_service.generate_qr_code_image(
                    qr_code_id, restaurant_id, payload
                )

                # 4. Update QR code with signed payload and image paths
                cursor.execute(
                    """
                    UPDATE qr_code
                    SET qr_code_payload = %s, qr_code_image_url = %s,
                        image_storage_path = %s, qr_code_checksum = %s
                    WHERE qr_code_id = %s
                """,
                    (payload, url_path, storage_path, checksum, qr_code_id),
                )

                # Commit transaction
                db.commit()

                log_info(f"QR code created atomically: {qr_code_id} for restaurant {restaurant_id}")

                # Return complete QR code
                return qr_code_service.get_by_id(qr_code_id, db, scope=scope)

        except Exception as e:
            # Rollback on any error
            db.rollback()
            log_error(f"Failed to create QR code atomically: {e}")
            raise HTTPException(status_code=500, detail="Failed to create QR code with image") from None

    def delete_qr_code_atomic(
        self, qr_code_id: UUID, db: psycopg2.extensions.connection, scope: InstitutionScope | None = None
    ) -> bool:
        """
        Atomically delete QR code and its image.
        If image deletion fails, database deletion is still performed.

        Args:
            qr_code_id: QR code identifier
            db: Database connection

        Returns:
            bool: True if deletion successful, False otherwise
        """
        try:
            # Get QR code record first to get image path
            qr_code = qr_code_service.get_by_id(qr_code_id, db, scope=scope)
            if not qr_code:
                log_info(f"QR code {qr_code_id} not found for deletion")
                return True  # Consider it successful if not found

            # Start transaction
            with db.cursor() as cursor:
                # 1. Delete QR code from database
                cursor.execute(
                    """
                    DELETE FROM qr_code
                    WHERE qr_code_id = %s
                """,
                    (str(qr_code_id),),
                )

                if cursor.rowcount == 0:
                    log_info(f"QR code {qr_code_id} not found in database")
                    return True

                # Commit database deletion first
                db.commit()

                # 2. Delete image file (non-critical operation)
                image_deleted = self.generation_service.delete_qr_code_image(qr_code.image_storage_path)

                if not image_deleted:
                    log_error(f"Failed to delete image for QR code {qr_code_id}, but database record was deleted")

                log_info(f"QR code deleted atomically: {qr_code_id}")
                return True

        except Exception as e:
            # Rollback database changes if they haven't been committed
            try:
                db.rollback()
            except Exception:
                pass  # Ignore rollback errors

            log_error(f"Failed to delete QR code atomically: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete QR code") from None

    def update_qr_code_status(
        self,
        qr_code_id: UUID,
        status: str,
        current_user: UUID,
        db: psycopg2.extensions.connection,
        scope: InstitutionScope | None = None,
    ) -> QRCodeDTO | None:
        """
        Update QR code status (Active/Inactive)

        Args:
            qr_code_id: QR code identifier
            status: New status
            current_user: User making the change
            db: Database connection

        Returns:
            QRCodeDTO: Updated QR code record
        """
        try:
            update_data = {"status": status, "modified_by": str(current_user)}

            result = qr_code_service.update(qr_code_id, update_data, db, scope=scope)
            if result:
                log_info(f"QR code {qr_code_id} status updated to {status}")

            return result

        except Exception as e:
            log_error(f"Failed to update QR code status: {e}")
            raise HTTPException(status_code=500, detail="Failed to update QR code status") from None
