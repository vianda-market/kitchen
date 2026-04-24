"""Attribute display labels by locale; keys mirror the DB schema.

Structure: ATTRIBUTE_LABELS[locale][schema][table][column] = "Label"

Locales: "en", "es", "pt" (matching SUPPORTED_LOCALES).
Coverage: every column present in attribute_ui_usage.INVENTORY must have
  a label for all three locales — 100% parity required per Phase 1 spec.

Note on renamed columns: where a DB column surfaces in API responses under
a different field name, the label describes the user-facing concept (e.g.
iso4217_currency.code ships as "currency_code"; the label is "Currency").
"""

ATTRIBUTE_LABELS: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "en": {
        "external": {
            "iso4217_currency": {
                "code": "Currency",
                "name": "Currency Name",
            },
        },
    },
    "es": {
        "external": {
            "iso4217_currency": {
                "code": "Moneda",
                "name": "Nombre de moneda",
            },
        },
    },
    "pt": {
        "external": {
            "iso4217_currency": {
                "code": "Moeda",
                "name": "Nome da moeda",
            },
        },
    },
}
