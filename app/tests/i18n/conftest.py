"""Shared fixtures and helpers for app/tests/i18n/.

catalog_parity is a reusable helper for parity tests across catalog modules.
It checks that every non-reference locale carries the same flat keys as the
reference locale (default: "en").

Usage in a parity test:
    from app.tests.i18n.conftest import catalog_parity
    assert catalog_parity(MESSAGES) == [], "MESSAGES has locale drift"

Or with a scoped subset:
    subset = {loc: {k: v for k, v in entries.items() if k.startswith("request.")}
              for loc, entries in MESSAGES.items()}
    assert catalog_parity(subset) == []
"""


def catalog_parity(catalog: dict[str, dict], reference_locale: str = "en") -> list[str]:
    """
    Check parity of a flat locale catalog against the reference locale.

    Returns a list of "<locale>=<key>" violation strings; empty list means
    full parity. The catalog is expected to be a dict[locale, dict[key, value]].
    """
    if reference_locale not in catalog:
        return [f"reference locale '{reference_locale}' not in catalog"]

    reference_keys = set(catalog[reference_locale].keys())
    violations: list[str] = []

    for locale, entries in catalog.items():
        if locale == reference_locale:
            continue
        locale_keys = set(entries.keys())
        for key in sorted(reference_keys - locale_keys):
            violations.append(f"locale={locale} missing={key}")
        for key in sorted(locale_keys - reference_keys):
            violations.append(f"locale={locale} extra={key}")

    return violations
