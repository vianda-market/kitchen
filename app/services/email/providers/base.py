from abc import ABC, abstractmethod
from typing import List, Optional


class EmailProvider(ABC):
    """Abstract base for email transport providers (SMTP, SendGrid, etc.)."""

    @abstractmethod
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
        """Send an email. Returns True on success."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider has valid credentials."""
        ...
