"""
Password Recovery Service

Handles password reset flow:
1. User requests password reset (forgot password)
2. Generate secure token, store in credential_recovery table
3. Send email with reset link
4. User clicks link, submits new password
5. Validate token, update password, mark token as used
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import UUID
import psycopg2.extensions
import psycopg2.extras

from app.services.crud_service import user_service
from app.services.email_service import email_service
from app.auth.security import hash_password
from app.utils.log import log_info, log_error, log_warning, log_password_recovery_debug
from app.config import Status


class PasswordRecoveryService:
    def __init__(self):
        self.token_expiry_hours = 24  # Code valid for 24 hours

    def generate_reset_code(self) -> str:
        """Generate a 6-digit reset code for password reset."""
        return str(secrets.randbelow(1_000_000)).zfill(6)
    
    def request_password_reset(
        self,
        email: str,
        db: psycopg2.extensions.connection
    ) -> Dict[str, Any]:
        """
        Handle password reset request.
        
        Args:
            email: User's email address
            db: Database connection
        
        Returns:
            dict: {"success": bool, "message": str}
        
        Note: For security, always return success even if email doesn't exist.
        This prevents email enumeration attacks.
        """
        try:
            log_password_recovery_debug(f"request_password_reset called for email={email!r}")
            email_normalized = (email or "").strip().lower()
            # Check if user exists
            user = user_service.get_by_field("email", email_normalized, db)

            if not user:
                log_password_recovery_debug("user not found for email; returning generic success")
                # Don't reveal that email doesn't exist (security best practice)
                log_warning(f"Password reset requested for non-existent email: {email_normalized}")
                return {
                    "success": True,
                    "message": "If an account with that email exists, a password reset link has been sent."
                }

            log_password_recovery_debug(f"user found user_id={user.user_id}; generating reset code")
            reset_code = self.generate_reset_code()
            expiry_time = datetime.now(timezone.utc) + timedelta(hours=self.token_expiry_hours)

            # Store code in database (str(user_id) for psycopg2 UUID adaptation)
            user_id_val = str(user.user_id)
            with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Invalidate any existing codes for this user
                cursor.execute(
                    """
                    UPDATE credential_recovery
                    SET is_used = TRUE,
                        is_archived = TRUE
                    WHERE user_id = %s
                      AND is_used = FALSE
                      AND is_archived = FALSE
                    """,
                    (user_id_val,)
                )

                cursor.execute(
                    """
                    INSERT INTO credential_recovery (
                        user_id,
                        recovery_code,
                        token_expiry,
                        is_used,
                        status,
                        is_archived
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING credential_recovery_id
                    """,
                    (
                        user_id_val,
                        reset_code,
                        expiry_time,
                        False,
                        Status.ACTIVE.value,
                        False
                    )
                )
                result = cursor.fetchone()
                credential_recovery_id = result['credential_recovery_id']
                db.commit()

            log_password_recovery_debug(f"reset code stored credential_recovery_id={credential_recovery_id}; sending email")
            email_sent = email_service.send_password_reset_email(
                to_email=email_normalized,
                reset_code=reset_code,
                user_first_name=user.first_name,
                expiry_hours=self.token_expiry_hours
            )
            
            if not email_sent:
                log_password_recovery_debug("send_password_reset_email returned False")
                log_error(f"Failed to send password reset email to {email_normalized}")
                # Don't reveal email sending failure to user (security)
                # But log it for admin investigation
            else:
                log_password_recovery_debug("password reset email sent successfully")

            log_info(f"Password reset requested for user {user.user_id}, token ID: {credential_recovery_id}")
            
            return {
                "success": True,
                "message": "If an account with that email exists, a password reset code has been sent."
            }
        
        except Exception as e:
            log_error(f"Error requesting password reset for {email}: {str(e)}")
            db.rollback()
            return {
                "success": False,
                "message": "An error occurred while processing your request. Please try again later."
            }

    def request_username_recovery(
        self,
        email: str,
        send_password_reset: bool,
        db: psycopg2.extensions.connection
    ) -> Dict[str, Any]:
        """
        Handle username recovery (forgot username). Send email with username; optionally
        also send password reset link (second email). Always return generic success to avoid enumeration.

        Args:
            email: User's email address (will be normalized lowercase)
            send_password_reset: If True, also trigger password reset email
            db: Database connection

        Returns:
            dict: {"success": True, "message": str} with generic message
        """
        try:
            log_password_recovery_debug(f"request_username_recovery called email={email!r} send_password_reset={send_password_reset}")
            email_normalized = (email or "").strip().lower()
            if not email_normalized:
                return {
                    "success": True,
                    "message": "If an account exists for this email, we have sent your username to it."
                }
            user = user_service.get_by_field("email", email_normalized, db)
            if not user:
                log_password_recovery_debug("username recovery: user not found; returning generic success")
                log_warning(f"Username recovery requested for non-existent email: {email_normalized}")
                return {
                    "success": True,
                    "message": "If an account exists for this email, we have sent your username to it."
                }
            log_password_recovery_debug(f"username recovery: user found user_id={user.user_id}; sending username email")
            username_sent = email_service.send_username_recovery_email(
                to_email=email_normalized,
                username=user.username,
                user_first_name=user.first_name
            )
            if not username_sent:
                log_password_recovery_debug("username recovery: send_username_recovery_email returned False")
                log_error(f"Failed to send username recovery email to {email_normalized}")
            else:
                log_password_recovery_debug("username recovery: username email sent")
            if send_password_reset:
                log_password_recovery_debug("username recovery: triggering password reset as requested")
                self.request_password_reset(email_normalized, db)
            log_info(f"Username recovery sent for user {user.user_id}")
            return {
                "success": True,
                "message": "If an account exists for this email, we have sent your username to it."
            }
        except Exception as e:
            log_error(f"Error requesting username recovery for {email}: {str(e)}")
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            return {
                "success": True,
                "message": "If an account exists for this email, we have sent your username to it."
            }

    def validate_reset_code(
        self,
        code: str,
        db: psycopg2.extensions.connection
    ) -> Optional[Dict[str, Any]]:
        """
        Validate a password reset code (6-digit or legacy token for compat).

        Args:
            code: Reset code from email (or legacy token)
            db: Database connection

        Returns:
            dict with user_id if valid, None if invalid
        """
        try:
            raw = (code or "").strip()
            if not raw:
                return None
            log_password_recovery_debug("validate_reset_code called")
            with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        cr.credential_recovery_id,
                        cr.user_id,
                        cr.token_expiry,
                        cr.is_used,
                        u.email,
                        u.first_name
                    FROM credential_recovery cr
                    INNER JOIN user_info u ON cr.user_id = u.user_id
                    WHERE cr.recovery_code = %s
                      AND cr.is_archived = FALSE
                    """,
                    (raw,)
                )
                result = cursor.fetchone()

            if not result:
                log_password_recovery_debug("validate_reset_code: no row found (invalid code)")
                log_warning("Invalid reset code attempted")
                return None

            if result['is_used']:
                log_password_recovery_debug(f"validate_reset_code: code already used user_id={result['user_id']}")
                log_warning(f"Already used reset code attempted for user {result['user_id']}")
                return None

            now = datetime.now(timezone.utc)
            if result['token_expiry'].tzinfo is None:
                result['token_expiry'] = result['token_expiry'].replace(tzinfo=timezone.utc)
            if now > result['token_expiry']:
                log_password_recovery_debug(f"validate_reset_code: code expired user_id={result['user_id']}")
                log_warning(f"Expired reset code attempted for user {result['user_id']}")
                return None

            log_password_recovery_debug(f"validate_reset_code: valid user_id={result['user_id']}")
            return dict(result)

        except Exception as e:
            log_error(f"Error validating reset code: {str(e)}")
            return None
    
    def reset_password(
        self,
        code: str,
        new_password: str,
        db: psycopg2.extensions.connection
    ) -> Dict[str, Any]:
        """
        Reset user's password using valid reset code (6-digit or legacy token).

        Args:
            code: Reset code from email (or legacy token)
            new_password: New password (plain text, will be hashed)
            db: Database connection

        Returns:
            dict: {"success": bool, "message": str}
        """
        try:
            log_password_recovery_debug("reset_password called; validating code")
            token_data = self.validate_reset_code(code, db)

            if not token_data:
                log_password_recovery_debug("reset_password: code invalid or expired; returning 400")
                return {
                    "success": False,
                    "message": "Invalid or expired reset code."
                }
            
            user_id = str(token_data['user_id'])
            credential_recovery_id = str(token_data['credential_recovery_id'])
            
            # Hash new password
            password_hash = hash_password(new_password)
            
            # Update user's password and set status = Active (invite flow or password recovery)
            with db.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE user_info
                    SET hashed_password = %s,
                        modified_date = CURRENT_TIMESTAMP,
                        status = 'Active',
                        email_verified = TRUE,
                        email_verified_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                    """,
                    (password_hash, user_id)
                )
                
                # Mark token as used
                cursor.execute(
                    """
                    UPDATE credential_recovery
                    SET is_used = TRUE,
                        used_date = CURRENT_TIMESTAMP,
                        is_archived = TRUE
                    WHERE credential_recovery_id = %s
                    """,
                    (credential_recovery_id,)
                )
                
                db.commit()

            log_password_recovery_debug(f"reset_password: password updated and code marked used for user_id={user_id}")
            log_info(f"Password successfully reset for user {user_id}")

            refreshed = user_service.get_by_id(UUID(user_id), db, scope=None)
            return {
                "success": True,
                "message": "Password reset successful. You can now log in with your new password.",
                "user": refreshed,
            }
        
        except Exception as e:
            log_error(f"Error resetting password: {str(e)}")
            db.rollback()
            return {
                "success": False,
                "message": "An error occurred while resetting your password. Please try again."
            }
    
    def cleanup_expired_tokens(self, db: psycopg2.extensions.connection) -> int:
        """
        Archive expired password reset tokens.
        Should be run periodically (e.g., daily cron job).
        
        Returns:
            int: Number of tokens archived
        """
        try:
            with db.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE credential_recovery
                    SET is_archived = TRUE
                    WHERE token_expiry < CURRENT_TIMESTAMP
                      AND is_archived = FALSE
                    """,
                )
                
                archived_count = cursor.rowcount
                db.commit()
            
            log_info(f"Archived {archived_count} expired password reset tokens")
            return archived_count
        
        except Exception as e:
            log_error(f"Error cleaning up expired tokens: {str(e)}")
            db.rollback()
            return 0


# Singleton instance
password_recovery_service = PasswordRecoveryService()
