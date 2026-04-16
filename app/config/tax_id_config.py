# app/config/tax_id_config.py
"""
Country-specific tax ID configuration.

Maps country_code → label, mask, regex, example for tax_id validation and
frontend form hints. Used by:
  - entity create/update validation (route_factory._before_create / _before_update)
  - market response enrichment (_serialize_market / _enrich_market_row_with_tax_id)

Convention: backend stores and validates **raw digits only** (no dashes or
separators). The `mask` field tells the frontend how to display the value
(e.g. "##-#######" → auto-insert dash after 2nd digit). The frontend must
strip non-digit characters before sending the API payload.
"""

import re

from fastapi import HTTPException

TAX_ID_CONFIG = {
    "AR": {
        "label": "CUIT",
        "mask": "##-########-#",
        "regex": r"^\d{11}$",
        "example": "30123456789",
    },
    "PE": {
        "label": "RUC",
        "mask": "###########",
        "regex": r"^\d{11}$",
        "example": "20123456789",
    },
    "US": {
        "label": "EIN",
        "mask": "##-#######",
        "regex": r"^\d{9}$",
        "example": "123456789",
    },
}


def get_tax_id_config(country_code: str) -> dict | None:
    """Return tax ID config for a country, or None if no rules defined."""
    return TAX_ID_CONFIG.get(country_code.upper())


def validate_tax_id_for_country(tax_id: str, country_code: str) -> None:
    """Validate tax_id format against country rules. Raises HTTPException on mismatch.

    Expects raw digits only (no dashes or separators). The frontend is
    responsible for stripping display formatting before submission.
    """
    config = get_tax_id_config(country_code)
    if config is None:
        return  # no rules for this country — accept any format
    if not re.match(config["regex"], tax_id):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid {config['label']} format for {country_code}. "
                f"Expected {len(config['example'])} digits (e.g. {config['example']})"
            ),
        )
