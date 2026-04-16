from abc import ABC, abstractmethod


class EmailProvider(ABC):
    """Abstract base for email transport providers (SMTP, SendGrid, etc.)."""

    @abstractmethod
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
        """Send an email. Returns True on success."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider has valid credentials."""
        ...
