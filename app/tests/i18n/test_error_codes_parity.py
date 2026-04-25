"""
Parity test: every ErrorCode enum value must have en, es, and pt entries in
MESSAGES. Fails loudly at CI time so code+message always ship together.

Pattern mirrors test_parity.py::test_messages_keys_match_reference; scoped
to the ErrorCode registry so failures are immediately actionable.
"""

import pytest

from app.i18n.error_codes import ErrorCode
from app.i18n.messages import MESSAGES

REQUIRED_LOCALES = ("en", "es", "pt")

pytestmark = pytest.mark.parity


@pytest.mark.parametrize("locale", REQUIRED_LOCALES)
def test_error_codes_have_messages(locale: str) -> None:
    """Every ErrorCode value must have a message entry in the given locale."""
    catalog = MESSAGES.get(locale, {})
    missing = [code.value for code in ErrorCode if code.value not in catalog]
    assert not missing, (
        f"MESSAGES['{locale}'] is missing entries for ErrorCode values: {missing}\n"
        "Add en/es/pt rows to app/i18n/messages.py for each missing code."
    )
