"""SMTP email provider — wraps current Gmail SMTP logic."""

import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.services.email.providers.base import EmailProvider
from app.utils.log import log_email_tracking


class SmtpEmailProvider(EmailProvider):
    """Send email via SMTP (Gmail or any SMTP relay)."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        from_email: str,
        from_name: str,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.from_name = from_name

    def is_configured(self) -> bool:
        return bool(self.smtp_username and self.smtp_password)

    def send(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to: str | None = None,
        category: str | None = None,
    ) -> bool:
        if not self.is_configured():
            log_email_tracking("Cannot send email: SMTP credentials not configured", level="error")
            return False

        log_email_tracking(f"Attempting to send email to {to_email}, subject: {subject!r}")

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg["Date"] = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")

            if cc:
                msg["Cc"] = ", ".join(cc)
            if bcc:
                msg["Bcc"] = ", ".join(bcc)
            if reply_to:
                msg["Reply-To"] = reply_to

            msg.attach(MIMEText(body_text, "plain"))
            if body_html:
                msg.attach(MIMEText(body_html, "html"))

            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)

            log_email_tracking(f"Connecting to {self.smtp_host}:{self.smtp_port}")
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg, from_addr=self.from_email, to_addrs=recipients)

            log_email_tracking(f"Email sent successfully to {to_email} - Subject: {subject}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            log_email_tracking(
                f"SMTP authentication failed: {e}. Check SMTP_USERNAME and SMTP_PASSWORD.", level="error"
            )
            return False
        except smtplib.SMTPException as e:
            log_email_tracking(f"SMTP error sending email to {to_email}: {e}", level="error")
            return False
        except Exception as e:
            log_email_tracking(f"Unexpected error sending email to {to_email}: {e}", level="error")
            return False
