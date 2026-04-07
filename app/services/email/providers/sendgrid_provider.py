"""SendGrid email provider — production email transport."""

from typing import List, Optional

from app.services.email.providers.base import EmailProvider
from app.utils.log import log_email_tracking


class SendGridEmailProvider(EmailProvider):
    """Send email via SendGrid REST API."""

    def __init__(
        self,
        api_key: str,
        from_email: str,
        from_name: str,
        reply_to: Optional[str] = None,
    ):
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name
        self.default_reply_to = reply_to

    def is_configured(self) -> bool:
        return bool(self.api_key and self.from_email)

    def send(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        category: Optional[str] = None,
    ) -> bool:
        if not self.is_configured():
            log_email_tracking("Cannot send email: SendGrid API key or from_email not configured", level="error")
            return False

        log_email_tracking(f"SendGrid: sending to {to_email}, subject: {subject!r}")

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import (
                Bcc,
                Category,
                Cc,
                Content,
                Email,
                Mail,
                ReplyTo,
                To,
            )

            from_addr = Email(self.from_email, self.from_name)
            to_addr = To(to_email)
            plain_content = Content("text/plain", body_text)

            mail = Mail(from_email=from_addr, to_emails=to_addr, subject=subject, plain_text_content=plain_content)

            if body_html:
                mail.add_content(Content("text/html", body_html))

            effective_reply_to = reply_to or self.default_reply_to
            if effective_reply_to:
                mail.reply_to = ReplyTo(effective_reply_to)

            if cc:
                for addr in cc:
                    mail.add_cc(Cc(addr))
            if bcc:
                for addr in bcc:
                    mail.add_bcc(Bcc(addr))

            if category:
                mail.add_category(Category(category))

            sg = SendGridAPIClient(self.api_key)
            response = sg.client.mail.send.post(request_body=mail.get())

            if response.status_code in (200, 201, 202):
                log_email_tracking(f"SendGrid: sent successfully to {to_email} (status {response.status_code})")
                return True

            log_email_tracking(
                f"SendGrid: unexpected status {response.status_code} for {to_email}: {response.body}",
                level="error",
            )
            return False

        except Exception as e:
            log_email_tracking(f"SendGrid: error sending to {to_email}: {e}", level="error")
            return False
