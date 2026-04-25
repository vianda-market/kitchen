"""
Parity test: every push.* key in MESSAGES["en"] must have en, es, and pt entries,
all non-empty strings.

Mirrors the pattern in test_error_codes_parity.py. Fails loudly at CI time so
push copy and its translations always ship together.

K4 (kitchen#68).
"""

import pytest

from app.i18n.messages import MESSAGES

REQUIRED_LOCALES = ("en", "es", "pt")

pytestmark = pytest.mark.parity


def _push_keys() -> list[str]:
    return [k for k in MESSAGES["en"] if k.startswith("push.")]


@pytest.mark.parametrize("locale", REQUIRED_LOCALES)
def test_push_keys_present_and_non_empty(locale: str) -> None:
    """Every push.* key from the English catalog must exist and be non-empty in each locale."""
    catalog = MESSAGES.get(locale, {})
    push_keys = _push_keys()

    missing = [k for k in push_keys if k not in catalog]
    empty = [k for k in push_keys if k in catalog and not catalog[k].strip()]

    assert not missing, (
        f"MESSAGES['{locale}'] is missing push.* keys: {missing}\n"
        "Add en/es/pt rows to app/i18n/messages.py for each missing key."
    )
    assert not empty, f"MESSAGES['{locale}'] has empty push.* values for keys: {empty}"


def test_push_keys_exist_in_english() -> None:
    """Sanity check: the push.* namespace is non-empty in the English catalog."""
    push_keys = _push_keys()
    assert push_keys, (
        "No push.* keys found in MESSAGES['en']. Expected at least push.pickup_ready_title and push.pickup_ready_body."
    )
