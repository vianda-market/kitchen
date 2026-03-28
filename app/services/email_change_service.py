"""
Email change verification: pending row + 6-digit code to new address, confirm via POST /users/me/verify-email-change.
Mirrors credential_recovery / password_recovery_service patterns.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import psycopg2
import psycopg2.errors
import psycopg2.extras
import psycopg2.extensions
from fastapi import HTTPException, status

from app.config import Status
from app.services.email_service import email_service
from app.services.entity_service import get_user_by_email
from app.services.crud_service import user_service
from app.utils.log import log_info, log_error, log_warning


class EmailChangeService:
    """Request and verify email changes with codes stored in email_change_request."""

    token_expiry_hours = 24
    _code_insert_max_attempts = 8

    def generate_verification_code(self) -> str:
        return str(secrets.randbelow(1_000_000)).zfill(6)

    def request_email_change(
        self,
        user_id: UUID,
        new_email: str,
        db: psycopg2.extensions.connection,
    ) -> None:
        """
        Invalidate prior pending rows for user, insert new request, send code to new_email.
        Rolls back if SMTP send fails. Raises HTTPException on validation/conflict.
        """
        normalized = (new_email or "").strip().lower()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required",
            )

        user = user_service.get_by_id(user_id, db, scope=None)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        current_email = (user.email or "").strip().lower()
        if normalized == current_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New email must differ from your current email",
            )

        other = get_user_by_email(normalized, db)
        if other and str(other.user_id) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already registered to another account",
            )

        user_id_str = str(user_id)
        with db.cursor() as dup_cur:
            dup_cur.execute(
                """
                SELECT 1 FROM email_change_request
                WHERE new_email = %s
                  AND is_used = FALSE
                  AND is_archived = FALSE
                  AND user_id <> %s::uuid
                """,
                (normalized, user_id_str),
            )
            if dup_cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This email is already pending verification for another account",
                )
        expiry_time = datetime.now(timezone.utc) + timedelta(hours=self.token_expiry_hours)
        last_error: Optional[Exception] = None

        for _attempt in range(self._code_insert_max_attempts):
            verification_code = self.generate_verification_code()
            try:
                with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        UPDATE email_change_request
                        SET is_used = TRUE,
                            is_archived = TRUE
                        WHERE user_id = %s
                          AND is_used = FALSE
                          AND is_archived = FALSE
                        """,
                        (user_id_str,),
                    )
                    cursor.execute(
                        """
                        INSERT INTO email_change_request (
                            user_id,
                            new_email,
                            verification_code,
                            token_expiry,
                            is_used,
                            status,
                            is_archived
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            user_id_str,
                            normalized,
                            verification_code,
                            expiry_time,
                            False,
                            Status.ACTIVE.value,
                            False,
                        ),
                    )
                db.commit()
            except psycopg2.errors.UniqueViolation as e:
                db.rollback()
                last_error = e
                # Retry only for rare 6-digit code collision; other violations should surface
                continue
            except Exception as e:
                db.rollback()
                log_error(f"request_email_change DB error for user_id={user_id_str}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not start email change request",
                ) from e

            sent = email_service.send_email_change_verification_email(
                to_email=normalized,
                verification_code=verification_code,
                user_first_name=user.first_name,
                expiry_hours=self.token_expiry_hours,
            )
            if not sent:
                try:
                    with db.cursor() as cursor:
                        cursor.execute(
                            """
                            DELETE FROM email_change_request
                            WHERE user_id = %s
                              AND verification_code = %s
                              AND is_used = FALSE
                              AND is_archived = FALSE
                            """,
                            (user_id_str, verification_code),
                        )
                    db.commit()
                except Exception as cleanup_err:
                    db.rollback()
                    log_error(f"request_email_change: failed to rollback row after SMTP failure: {cleanup_err}")
                log_error(f"request_email_change: failed to send verification email to {normalized}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Could not send verification email. Please try again later.",
                )

            log_info(f"Email change request created for user_id={user_id_str}, pending new_email={normalized}")
            return

        log_error(f"request_email_change: exhausted code retries for user_id={user_id_str}: {last_error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate a unique verification code. Please try again.",
        )

    def verify_email_change(
        self,
        user_id: UUID,
        code: str,
        db: psycopg2.extensions.connection,
    ) -> None:
        raw = (code or "").strip()
        if not raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code",
            )

        user_id_str = str(user_id)
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT email_change_request_id, new_email, token_expiry, is_used, is_archived
                FROM email_change_request
                WHERE user_id = %s
                  AND verification_code = %s
                  AND is_archived = FALSE
                """,
                (user_id_str, raw),
            )
            row = cursor.fetchone()

        if not row:
            log_warning(f"verify_email_change: no row for user_id={user_id_str}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code",
            )

        if row["is_used"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has already been used",
            )

        token_expiry = row["token_expiry"]
        now = datetime.now(timezone.utc)
        if token_expiry and token_expiry.tzinfo is None:
            token_expiry = token_expiry.replace(tzinfo=timezone.utc)
        if (token_expiry or now) <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code",
            )

        new_email = row["new_email"]
        if hasattr(new_email, "lower"):
            new_email = str(new_email).strip().lower()
        else:
            new_email = str(new_email).strip().lower()

        request_id = str(row["email_change_request_id"])

        try:
            with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT email, first_name FROM user_info WHERE user_id = %s",
                    (user_id_str,),
                )
                before = cursor.fetchone()
            if not before:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

            old_email = before["email"]
            first_name = before["first_name"]
            old_email_str = str(old_email) if old_email is not None else ""

            with db.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE user_info
                    SET email = %s,
                        email_verified = TRUE,
                        email_verified_at = CURRENT_TIMESTAMP,
                        modified_by = %s,
                        modified_date = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                    """,
                    (new_email, user_id_str, user_id_str),
                )
                cursor.execute(
                    """
                    UPDATE email_change_request
                    SET is_used = TRUE,
                        used_date = CURRENT_TIMESTAMP,
                        is_archived = TRUE
                    WHERE email_change_request_id = %s
                    """,
                    (request_id,),
                )
                cursor.execute(
                    """
                    UPDATE email_change_request
                    SET is_used = TRUE,
                        is_archived = TRUE
                    WHERE user_id = %s
                      AND is_used = FALSE
                      AND is_archived = FALSE
                      AND email_change_request_id <> %s::uuid
                    """,
                    (user_id_str, request_id),
                )
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            log_error(f"verify_email_change failed for user_id={user_id_str}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not update email",
            ) from e

        if old_email_str.strip():
            sent = email_service.send_email_change_confirmation_email(
                to_email=old_email_str.strip(),
                user_first_name=first_name,
                new_email=new_email,
            )
            if not sent:
                log_warning(
                    f"verify_email_change: confirmation email failed for old address user_id={user_id_str}"
                )

        log_info(f"Email change verified for user_id={user_id_str}")

    def cleanup_expired_requests(self, db: psycopg2.extensions.connection) -> int:
        """Archive expired unused email change requests (for cron)."""
        try:
            with db.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE email_change_request
                    SET is_archived = TRUE
                    WHERE token_expiry < CURRENT_TIMESTAMP
                      AND is_used = FALSE
                      AND is_archived = FALSE
                    """,
                )
                count = cursor.rowcount
            db.commit()
            log_info(f"Archived {count} expired email_change_request rows")
            return count
        except Exception as e:
            log_error(f"cleanup_expired_requests: {e}")
            db.rollback()
            return 0


email_change_service = EmailChangeService()
