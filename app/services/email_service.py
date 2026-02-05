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
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import os
from datetime import datetime

from app.utils.log import log_info, log_error, log_warning


class EmailService:
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.from_email = os.getenv('FROM_EMAIL', self.smtp_username)
        self.from_name = os.getenv('FROM_NAME', 'Kitchen Backend')
        
        # Validate configuration
        if not self.smtp_username or not self.smtp_password:
            log_warning("Email service not configured. Set SMTP_USERNAME and SMTP_PASSWORD in .env")
    
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
            log_error("Cannot send email: SMTP credentials not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
            
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
            log_info(f"Connecting to {self.smtp_host}:{self.smtp_port}")
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()  # Upgrade to secure connection
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg, from_addr=self.from_email, to_addrs=recipients)
            
            log_info(f"Email sent successfully to {to_email} - Subject: {subject}")
            return True
        
        except smtplib.SMTPAuthenticationError as e:
            log_error(f"SMTP authentication failed: {str(e)}. Check SMTP_USERNAME and SMTP_PASSWORD.")
            return False
        except smtplib.SMTPException as e:
            log_error(f"SMTP error sending email to {to_email}: {str(e)}")
            return False
        except Exception as e:
            log_error(f"Unexpected error sending email to {to_email}: {str(e)}")
            return False
    
    def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        user_first_name: str,
        expiry_hours: int = 24
    ) -> bool:
        """
        Send password reset email with reset link.
        
        Args:
            to_email: User's email address
            reset_token: Password reset token
            user_first_name: User's first name for personalization
            expiry_hours: Token expiry time in hours
        
        Returns:
            bool: True if sent successfully
        """
        # Frontend URL (adjust for your environment)
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        reset_link = f"{frontend_url}/reset-password?token={reset_token}"
        
        subject = "Reset Your Kitchen Password"
        
        # Plain text version
        body_text = f"""
Hi {user_first_name},

You requested to reset your password for your Kitchen account.

Please click the link below to reset your password:
{reset_link}

This link will expire in {expiry_hours} hours.

If you didn't request this password reset, please ignore this email.

Thanks,
The Kitchen Team
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
        
        <p>You requested to reset your password for your Kitchen account.</p>
        
        <div style="margin: 30px 0;">
            <a href="{reset_link}" 
               style="background-color: #3498db; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                Reset Password
            </a>
        </div>
        
        <p style="font-size: 14px; color: #7f8c8d;">
            This link will expire in {expiry_hours} hours.
        </p>
        
        <p style="font-size: 14px; color: #7f8c8d;">
            If you didn't request this password reset, please ignore this email.
        </p>
        
        <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 30px 0;">
        
        <p style="font-size: 12px; color: #95a5a6;">
            Thanks,<br>
            The Kitchen Team
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
        subject = "Welcome to Kitchen!"
        
        body_text = f"""
Hi {user_first_name},

Welcome to Kitchen! We're excited to have you on board.

You can now:
- Browse daily plates from local restaurants
- Select and pick up your meals
- Manage your subscriptions

If you have any questions, feel free to reach out to us.

Thanks,
The Kitchen Team
        """.strip()
        
        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px;">
        <h1 style="color: #2c3e50;">Welcome to Kitchen! 🍽️</h1>
        
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
            The Kitchen Team
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
