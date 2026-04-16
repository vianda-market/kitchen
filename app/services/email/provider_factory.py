"""Email provider factory — returns the configured provider singleton."""

import os

from app.services.email.providers.base import EmailProvider
from app.utils.log import log_email_tracking

_provider: EmailProvider | None = None


def get_email_provider() -> EmailProvider:
    """Return the email provider based on EMAIL_PROVIDER setting. Cached after first call."""
    global _provider
    if _provider is not None:
        return _provider

    from app.config.settings import get_settings

    settings = get_settings()

    provider_name = settings.EMAIL_PROVIDER.lower()

    if provider_name == "sendgrid":
        from app.services.email.providers.sendgrid_provider import SendGridEmailProvider

        from_email = settings.EMAIL_FROM_ADDRESS or os.getenv("FROM_EMAIL", "")
        from_name = settings.EMAIL_FROM_NAME or os.getenv("FROM_NAME", "Vianda")

        _provider = SendGridEmailProvider(
            api_key=settings.SENDGRID_API_KEY,
            from_email=from_email,
            from_name=from_name,
            reply_to=settings.EMAIL_REPLY_TO or None,
        )
        log_email_tracking(f"Email provider: SendGrid (from={from_email})")

    elif provider_name == "smtp":
        from app.services.email.providers.smtp_provider import SmtpEmailProvider

        _provider = SmtpEmailProvider(
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            from_email=settings.EMAIL_FROM_ADDRESS or os.getenv("FROM_EMAIL", os.getenv("SMTP_USERNAME", "")),
            from_name=settings.EMAIL_FROM_NAME or os.getenv("FROM_NAME", "Vianda"),
        )
        log_email_tracking(f"Email provider: SMTP ({_provider.smtp_host}:{_provider.smtp_port})")

    else:
        raise ValueError(f"Unknown EMAIL_PROVIDER: {provider_name!r}. Use 'smtp' or 'sendgrid'.")

    return _provider
