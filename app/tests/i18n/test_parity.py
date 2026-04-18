"""Locale key parity: every locale must carry the same keys as English.

English is the reference. When a new key lands in `en` without its translation,
`get_message`/`get_label` silently fall back to English — non-en users see mixed
content. These tests fail that drift loudly at CI time.
"""

import pytest

from app.i18n.enum_labels import ENUM_LABELS
from app.i18n.messages import MESSAGES

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


@pytest.mark.parametrize("locale", _non_reference_locales(ENUM_LABELS))
def test_enum_labels_top_level_keys_match_reference(locale: str) -> None:
    reference = set(ENUM_LABELS[REFERENCE_LOCALE].keys())
    actual = set(ENUM_LABELS[locale].keys())

    missing = sorted(reference - actual)
    extra = sorted(actual - reference)

    assert not missing and not extra, (
        f"ENUM_LABELS['{locale}'] top-level drift vs '{REFERENCE_LOCALE}': "
        f"missing enum types={missing}, extra enum types={extra}"
    )


@pytest.mark.parametrize("locale", _non_reference_locales(ENUM_LABELS))
def test_enum_labels_codes_match_reference(locale: str) -> None:
    drift: list[str] = []
    for enum_type, reference_codes in ENUM_LABELS[REFERENCE_LOCALE].items():
        reference = set(reference_codes.keys())
        actual = set(ENUM_LABELS[locale].get(enum_type, {}).keys())
        missing = sorted(reference - actual)
        extra = sorted(actual - reference)
        if missing or extra:
            drift.append(f"{enum_type}: missing={missing}, extra={extra}")

    assert not drift, f"ENUM_LABELS['{locale}'] code drift vs '{REFERENCE_LOCALE}':\n  " + "\n  ".join(drift)
