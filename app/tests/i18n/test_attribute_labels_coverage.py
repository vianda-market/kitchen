"""
100% parity lint: every column in attribute_ui_usage.INVENTORY must have a
label for each supported locale in attribute_labels.ATTRIBUTE_LABELS.

Expected baseline: 313 entries × 3 locales = 939 checks (all pass after
Phase 1 PRs #64, #70, #71, #75, #76, #77 are merged).

Failure output lists exact missing entries so a reviewer can act immediately:
    Missing entries (3):
      locale=es schema=core table=user_info column=email
      locale=pt schema=core table=user_info column=email
      locale=pt schema=billing table=supplier_w9 column=status

Each inventory key has format: <schema>.<table>.<column>
"""

import pytest

from app.config.settings import settings
from app.i18n.attribute_labels import ATTRIBUTE_LABELS
from app.i18n.attribute_ui_usage import INVENTORY

pytestmark = pytest.mark.parity

REQUIRED_LOCALES: tuple[str, ...] = tuple(settings.SUPPORTED_LOCALES)


def _missing_entries() -> list[str]:
    """
    Return a list of descriptive strings for every (locale, schema, table, column)
    combination that is in INVENTORY but absent from ATTRIBUTE_LABELS.
    """
    missing: list[str] = []
    for key in INVENTORY:
        parts = key.split(".", 2)
        if len(parts) != 3:
            missing.append(f"malformed inventory key={key!r} (expected <schema>.<table>.<column>)")
            continue
        schema, table, column = parts
        for locale in REQUIRED_LOCALES:
            label = ATTRIBUTE_LABELS.get(locale, {}).get(schema, {}).get(table, {}).get(column)
            if not label:
                missing.append(f"locale={locale} schema={schema} table={table} column={column}")
    return missing


def test_inventory_coverage_100_percent() -> None:
    """
    Every column in INVENTORY must have a non-empty label for each locale.

    Coverage denominator: len(INVENTORY) × len(REQUIRED_LOCALES).
    Expected: 313 × 3 = 939 after Phase 1 fully merged.
    """
    missing = _missing_entries()
    total_checks = len(INVENTORY) * len(REQUIRED_LOCALES)
    assert not missing, (
        f"Attribute label coverage is not 100%.\n"
        f"Total checks: {total_checks} ({len(INVENTORY)} entries × {len(REQUIRED_LOCALES)} locales)\n"
        f"Missing entries ({len(missing)}):\n"
        + "\n".join(f"  {m}" for m in missing)
        + "\n\nAdd en/es/pt rows to app/i18n/attribute_labels.py for each missing entry."
    )
