"""
Email Service - Gmail SMTP for MVP

This service handles email sending using Gmail SMTP.
Post-UAT: Migrate to AWS SES for production.

Setup Instructions:
1. Create Gmail account (e.g., kitchen-backend@gmail.com)
2. Enable 2FA on Gmail account
3. Generate App-Specific Password:
   - Go to Google Account > Security > 2-Step Verification > App passwords
   - Generate password for "Mail" on "Other (Custom name)"
4. Add credentials to .env:
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=your-app-specific-password
   FROM_EMAIL=your-email@gmail.com
   FROM_NAME=Kitchen Backend

Rate Limits:
- Gmail Free: 500 emails/day
- For production: Migrate to AWS SES (50,000 emails/day free tier)

Debugging (optional, off by default):
- Set LOG_EMAIL_TRACKING=1 (or true/yes) in .env to enable SMTP/email logs.
- When enabled: config status at startup, each send attempt, success/failure, and errors.
- Leave unset or set to 0/false in production to avoid noisy logs.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import os
from datetime import datetime, timezone

from app.utils.log import log_email_tracking
from app.config.settings import get_settings


class EmailService:
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.from_email = os.getenv('FROM_EMAIL', self.smtp_username)
        self.from_name = os.getenv('FROM_NAME', 'Vianda')
        
        # Validate configuration (only log when LOG_EMAIL_TRACKING=1 in .env)
        if not self.smtp_username or not self.smtp_password:
            log_email_tracking("Email service not configured. Set SMTP_USERNAME and SMTP_PASSWORD in .env", level="warning")
        else:
            log_email_tracking(
                f"Email service configured: SMTP_HOST={self.smtp_host}, SMTP_PORT={self.smtp_port}, "
                f"FROM_EMAIL={self.from_email}, FROM_NAME={self.from_name}"
            )
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> bool:
        """
        Send email via Gmail SMTP.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body_text: Plain text body (required)
            body_html: HTML body (optional, falls back to text)
            cc: List of CC email addresses
            bcc: List of BCC email addresses
        
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.smtp_username or not self.smtp_password:
            log_email_tracking("Cannot send email: SMTP credentials not configured", level="error")
            return False

        log_email_tracking(f"Attempting to send email to {to_email}, subject: {subject!r}")
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Date'] = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            if bcc:
                msg['Bcc'] = ', '.join(bcc)
            
            # Attach plain text part
            part_text = MIMEText(body_text, 'plain')
            msg.attach(part_text)
            
            # Attach HTML part if provided
            if body_html:
                part_html = MIMEText(body_html, 'html')
                msg.attach(part_html)
            
            # Prepare recipient list
            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
            
            # Connect to SMTP server
            log_email_tracking(f"Connecting to {self.smtp_host}:{self.smtp_port}")
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()  # Upgrade to secure connection
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg, from_addr=self.from_email, to_addrs=recipients)
            
            log_email_tracking(f"Email sent successfully to {to_email} - Subject: {subject}")
            return True
        
        except smtplib.SMTPAuthenticationError as e:
            log_email_tracking(f"SMTP authentication failed: {str(e)}. Check SMTP_USERNAME and SMTP_PASSWORD.", level="error")
            return False
        except smtplib.SMTPException as e:
            log_email_tracking(f"SMTP error sending email to {to_email}: {str(e)}", level="error")
            return False
        except Exception as e:
            log_email_tracking(f"Unexpected error sending email to {to_email}: {str(e)}", level="error")
            return False
    
    def send_password_reset_email(
        self,
        to_email: str,
        reset_code: str,
        user_first_name: str,
        expiry_hours: int = 24
    ) -> bool:
        """
        Send password reset email with 6-digit code only (no link).

        Args:
            to_email: User's email address
            reset_code: 6-digit password reset code
            user_first_name: User's first name for personalization
            expiry_hours: Code expiry time in hours

        Returns:
            bool: True if sent successfully
        """
        subject = "Reset Your Vianda Password"

        # Plain text version
        body_text = f"""
Hi {user_first_name},

You requested to reset your password for your Vianda account.

Your reset code is:

{reset_code}

Enter this code with your new password to reset. It will expire in {expiry_hours} hours.

If you didn't request this password reset, please ignore this email.

Thanks,
The Vianda Team
        """.strip()

        # HTML version
        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px;">
        <h1 style="color: #2c3e50; margin-bottom: 20px;">Reset Your Password</h1>
        <p>Hi {user_first_name},</p>
        <p>You requested to reset your password for your Vianda account.</p>
        <p>Your reset code is:</p>
        <p style="font-size: 24px; font-weight: bold; letter-spacing: 4px; margin: 20px 0;">{reset_code}</p>
        <p style="font-size: 14px; color: #7f8c8d;">Enter this code with your new password to reset. It will expire in {expiry_hours} hours.</p>
        <p style="font-size: 14px; color: #7f8c8d;">If you didn't request this password reset, please ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 30px 0;">
        <p style="font-size: 12px; color: #95a5a6;">Thanks,<br>The Vianda Team</p>
    </div>
</body>
</html>
        """.strip()
        
        return self.send_email(
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )

    def send_b2b_invite_email(
        self,
        to_email: str,
        reset_code: str,
        user_first_name: Optional[str],
        expiry_hours: int = 24,
        *,
        set_password_url_template: Optional[str] = None,
    ) -> bool:
        """
        Send B2B invite email with link to set password.
        Used when an admin creates a user without a password; user clicks link to set their own.

        Args:
            to_email: User's email address
            reset_code: 6-digit code (included in link)
            user_first_name: User's first name for personalization (optional)
            expiry_hours: Code expiry time in hours
            set_password_url_template: Optional. Default uses B2B_INVITE_SET_PASSWORD_URL env.
                Template: {url} with {code} placeholder. E.g. "https://app.example.com/set-password?code={code}"

        Returns:
            bool: True if sent successfully
        """
        template = set_password_url_template or get_settings().B2B_INVITE_SET_PASSWORD_URL or os.getenv("B2B_INVITE_SET_PASSWORD_URL", "")
        if template:
            set_password_url = template.replace("{code}", reset_code)
        else:
            # Fallback: B2B_FRONTEND_URL (e.g. http://localhost:5173) for invite links; prod should set B2B_INVITE_SET_PASSWORD_URL
            b2b_url = (get_settings().B2B_FRONTEND_URL or os.getenv("B2B_FRONTEND_URL", "")).rstrip("/")
            if b2b_url:
                set_password_url = f"{b2b_url}/set-password?code={reset_code}"
            else:
                set_password_url = f"https://app.vianda.com/set-password?code={reset_code}"
        first_name = user_first_name or "there"
        subject = "You've been invited to Vianda – Set your password"
        body_text = f"""
Hi {first_name},

You've been invited to join Vianda. Click the link below to set your password and access your account:

{set_password_url}

This link will expire in {expiry_hours} hours.

If you didn't expect this invitation, please ignore this email.

Thanks,
The Vianda Team
        """.strip()
        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px;">
        <h1 style="color: #2c3e50; margin-bottom: 20px;">You've been invited to Vianda</h1>
        <p>Hi {first_name},</p>
        <p>You've been invited to join Vianda. Click the link below to set your password and access your account:</p>
        <p style="margin: 25px 0;"><a href="{set_password_url}" style="background-color: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px;">Set your password</a></p>
        <p style="font-size: 14px; color: #7f8c8d;">Or copy this link: {set_password_url}</p>
        <p style="font-size: 14px; color: #7f8c8d;">This link will expire in {expiry_hours} hours.</p>
        <p style="font-size: 14px; color: #7f8c8d;">If you didn't expect this invitation, please ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 30px 0;">
        <p style="font-size: 12px; color: #95a5a6;">Thanks,<br>The Vianda Team</p>
    </div>
</body>
</html>
        """.strip()
        return self.send_email(
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )

    def send_username_recovery_email(
        self,
        to_email: str,
        username: str,
        user_first_name: Optional[str] = None
    ) -> bool:
        """
        Send username recovery email (forgot username flow).
        Contains the username only; no password or reset link.

        Args:
            to_email: User's email address
            username: The account username to include in the email
            user_first_name: User's first name for personalization (optional)

        Returns:
            bool: True if sent successfully
        """
        first_name = user_first_name or "there"
        subject = "Your Vianda username"
        body_text = f"""
Hi {first_name},

You requested your username for your Vianda account.

Your username is: {username}

Use this username to sign in. If you need to reset your password, use the "Forgot password?" link on the sign-in page.

If you didn't request this, please ignore this email.

Thanks,
The Vianda Team
        """.strip()
        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px;">
        <h1 style="color: #2c3e50; margin-bottom: 20px;">Your Vianda username</h1>
        <p>Hi {first_name},</p>
        <p>You requested your username for your Vianda account.</p>
        <p style="font-weight: bold;">Your username is: {username}</p>
        <p>Use this username to sign in. If you need to reset your password, use the "Forgot password?" link on the sign-in page.</p>
        <p style="font-size: 14px; color: #7f8c8d;">If you didn't request this, please ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 30px 0;">
        <p style="font-size: 12px; color: #95a5a6;">Thanks,<br>The Vianda Team</p>
    </div>
</body>
</html>
        """.strip()
        return self.send_email(
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )
    
    def send_signup_verification_email(
        self,
        to_email: str,
        verification_code: str,
        user_first_name: Optional[str] = None,
        expiry_hours: int = 24
    ) -> bool:
        """
        Send signup verification email with 6-digit code only (no link).
        Used for customer self-registration: user enters code to verify email before account is created.

        Args:
            to_email: User's email address
            verification_code: 6-digit verification code
            user_first_name: User's first name for personalization (optional)
            expiry_hours: Code expiry time in hours

        Returns:
            bool: True if sent successfully
        """
        first_name = user_first_name or "there"
        log_email_tracking(
            f"Signup verification: to={to_email}, expiry_hours={expiry_hours}"
        )

        subject = "Verify your email to complete signup"

        body_text = f"""
Hi {first_name},

Thanks for signing up. Your verification code is:

{verification_code}

Enter this code to verify your email. It will expire in {expiry_hours} hours.

If you didn't create an account, please ignore this email.

Thanks,
The Vianda Team
        """.strip()

        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px;">
        <h1 style="color: #2c3e50; margin-bottom: 20px;">Verify your email</h1>
        <p>Hi {first_name},</p>
        <p>Thanks for signing up. Your verification code is:</p>
        <p style="font-size: 24px; font-weight: bold; letter-spacing: 4px; margin: 20px 0;">{verification_code}</p>
        <p style="font-size: 14px; color: #7f8c8d;">Enter this code to verify your email. It will expire in {expiry_hours} hours.</p>
        <p style="font-size: 14px; color: #7f8c8d;">If you didn't create an account, please ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 30px 0;">
        <p style="font-size: 12px; color: #95a5a6;">Thanks,<br>The Vianda Team</p>
    </div>
</body>
</html>
        """.strip()

        return self.send_email(
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )

    def send_welcome_email(
        self,
        to_email: str,
        user_first_name: str
    ) -> bool:
        """
        Send welcome email to new users.
        
        Args:
            to_email: User's email address
            user_first_name: User's first name
        
        Returns:
            bool: True if sent successfully
        """
        subject = "Welcome to Vianda!"
        
        body_text = f"""
Hi {user_first_name},

Welcome to Vianda! We're excited to have you on board.

You can now:
- Browse daily plates from local restaurants
- Select and pick up your meals
- Manage your subscriptions

If you have any questions, feel free to reach out to us.

Thanks,
The Vianda Team
        """.strip()
        
        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px;">
        <h1 style="color: #2c3e50;">Welcome to Vianda! 🍽️</h1>
        
        <p>Hi {user_first_name},</p>
        
        <p>We're excited to have you on board!</p>
        
        <p>You can now:</p>
        <ul>
            <li>Browse daily plates from local restaurants</li>
            <li>Select and pick up your meals</li>
            <li>Manage your subscriptions</li>
        </ul>
        
        <p>If you have any questions, feel free to reach out to us.</p>
        
        <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 30px 0;">
        
        <p style="font-size: 12px; color: #95a5a6;">
            Thanks,<br>
            The Vianda Team
        </p>
    </div>
</body>
</html>
        """.strip()
        
        return self.send_email(
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )
    
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return bool(self.smtp_username and self.smtp_password)


# Singleton instance
email_service = EmailService()
