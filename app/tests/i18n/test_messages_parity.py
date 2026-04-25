"""Locale key parity for MESSAGES: every locale must carry the same keys as English.

English is the reference. When a new key lands in `en` without its translation,
`get_message` silently falls back to English — non-en users see mixed content.
These tests fail that drift loudly at CI time.

Split from test_parity.py in K3 (see docs/plans/translation-phase-2-kitchen.md).
"""

import pytest

from app.i18n.messages import MESSAGES

pytestmark = pytest.mark.parity

REFERENCE_LOCALE = "en"


def _non_reference_locales(catalog: dict[str, dict]) -> list[str]:
    return sorted(loc for loc in catalog if loc != REFERENCE_LOCALE)


@pytest.mark.parametrize("locale", _non_reference_locales(MESSAGES))
def test_messages_keys_match_reference(locale: str) -> None:
    reference = set(MESSAGES[REFERENCE_LOCALE].keys())
    actual = set(MESSAGES[locale].keys())

    missing = sorted(reference - actual)
    extra = sorted(actual - reference)

    assert not missing and not extra, (
        f"MESSAGES['{locale}'] drift vs '{REFERENCE_LOCALE}': missing={missing}, extra={extra}"
    )
