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
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID
import psycopg2.extensions
import psycopg2.extras

from app.services.crud_service import user_service
from app.services.email_service import email_service
from app.auth.security import hash_password
from app.utils.log import log_info, log_error, log_warning
from app.config import Status


class PasswordRecoveryService:
    def __init__(self):
        self.token_expiry_hours = 24  # Token valid for 24 hours
        self.token_length = 64  # URL-safe token length
    
    def generate_reset_token(self) -> str:
        """Generate a secure random token for password reset."""
        return secrets.token_urlsafe(self.token_length)
    
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
            # Check if user exists
            user = user_service.get_one_by_email(email, db)
            
            if not user:
                # Don't reveal that email doesn't exist (security best practice)
                log_warning(f"Password reset requested for non-existent email: {email}")
                return {
                    "success": True,
                    "message": "If an account with that email exists, a password reset link has been sent."
                }
            
            # Generate reset token
            reset_token = self.generate_reset_token()
            expiry_time = datetime.utcnow() + timedelta(hours=self.token_expiry_hours)
            
            # Store token in database
            with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Invalidate any existing tokens for this user
                cursor.execute(
                    """
                    UPDATE credential_recovery
                    SET is_used = TRUE,
                        is_archived = TRUE
                    WHERE user_id = %s
                      AND is_used = FALSE
                      AND is_archived = FALSE
                    """,
                    (user.user_id,)
                )
                
                # Insert new token
                cursor.execute(
                    """
                    INSERT INTO credential_recovery (
                        user_id,
                        recovery_token,
                        token_expiry,
                        is_used,
                        status,
                        is_archived
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING credential_recovery_id
                    """,
                    (
                        user.user_id,
                        reset_token,
                        expiry_time,
                        False,
                        Status.ACTIVE.value,
                        False
                    )
                )
                
                result = cursor.fetchone()
                credential_recovery_id = result['credential_recovery_id']
                db.commit()
            
            # Send password reset email
            email_sent = email_service.send_password_reset_email(
                to_email=email,
                reset_token=reset_token,
                user_first_name=user.first_name,
                expiry_hours=self.token_expiry_hours
            )
            
            if not email_sent:
                log_error(f"Failed to send password reset email to {email}")
                # Don't reveal email sending failure to user (security)
                # But log it for admin investigation
            
            log_info(f"Password reset requested for user {user.user_id}, token ID: {credential_recovery_id}")
            
            return {
                "success": True,
                "message": "If an account with that email exists, a password reset link has been sent."
            }
        
        except Exception as e:
            log_error(f"Error requesting password reset for {email}: {str(e)}")
            db.rollback()
            return {
                "success": False,
                "message": "An error occurred while processing your request. Please try again later."
            }
    
    def validate_reset_token(
        self,
        token: str,
        db: psycopg2.extensions.connection
    ) -> Optional[Dict[str, Any]]:
        """
        Validate a password reset token.
        
        Args:
            token: Reset token from email link
            db: Database connection
        
        Returns:
            dict with user_id if valid, None if invalid
        """
        try:
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
                    WHERE cr.recovery_token = %s
                      AND cr.is_archived = FALSE
                    """,
                    (token,)
                )
                
                result = cursor.fetchone()
                
                if not result:
                    log_warning(f"Invalid reset token attempted")
                    return None
                
                # Check if token is already used
                if result['is_used']:
                    log_warning(f"Already used reset token attempted for user {result['user_id']}")
                    return None
                
                # Check if token is expired
                if datetime.utcnow() > result['token_expiry']:
                    log_warning(f"Expired reset token attempted for user {result['user_id']}")
                    return None
                
                return dict(result)
        
        except Exception as e:
            log_error(f"Error validating reset token: {str(e)}")
            return None
    
    def reset_password(
        self,
        token: str,
        new_password: str,
        db: psycopg2.extensions.connection
    ) -> Dict[str, Any]:
        """
        Reset user's password using valid token.
        
        Args:
            token: Reset token from email link
            new_password: New password (plain text, will be hashed)
            db: Database connection
        
        Returns:
            dict: {"success": bool, "message": str}
        """
        try:
            # Validate token
            token_data = self.validate_reset_token(token, db)
            
            if not token_data:
                return {
                    "success": False,
                    "message": "Invalid or expired reset token."
                }
            
            user_id = token_data['user_id']
            credential_recovery_id = token_data['credential_recovery_id']
            
            # Hash new password
            password_hash = hash_password(new_password)
            
            # Update user's password
            with db.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE user_info
                    SET cellphone_password = %s,
                        updated_date = CURRENT_TIMESTAMP
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
            
            log_info(f"Password successfully reset for user {user_id}")
            
            return {
                "success": True,
                "message": "Password reset successful. You can now log in with your new password."
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
