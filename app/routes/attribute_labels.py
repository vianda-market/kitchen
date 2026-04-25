"""
Attribute Labels Routes

API endpoint for retrieving per-schema DB column display labels.
Mirrors the /enums endpoint shape but returns a schema-filtered slice
of the attribute labels catalog instead of enum values.

Contract summary
----------------
- GET /api/v1/attribute-labels?language={locale}&schema={schema}
- `schema` is required (no all-schemas variant — see parent plan
  "Caching and load strategy" section).
- `language` defaults to "en"; validates against SUPPORTED_LOCALES.
  Unknown locale → 400.
- Unknown `schema` → 400.
- Response: { "<table>": { "<column>": "<label>" } } — NOT wrapped in
  the enum-style {values, labels} envelope.
- Auth: requires `current_user` (mirrors /enums per Q-S9 in design doc).

Rename-at-API note (Q-S11)
--------------------------
The endpoint is keyed by DB path.  When a DB column ships in an API
response under a renamed field name, the hook call site uses the DB
path, not the response field name.  Three known renames today:
  external.iso4217_currency.{code,name}  → response fields currency_code / currency_name
  billing.supplier_invoice.document_storage_path → response field document_url
  billing.supplier_w9.document_storage_path      → response field document_url

See docs/api/i18n.md §4 (attribute-labels section) and the K-attr1 PR
description for the full rationale.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.config.settings import settings
from app.i18n.attribute_labels import ATTRIBUTE_LABELS
from app.utils.log import log_info

router = APIRouter(prefix="/attribute-labels", tags=["Attribute Labels"])

# ---------------------------------------------------------------------------
# In-memory per-schema cache — (locale, schema) → {table: {column: label}}
# Rebuilt once per process start; ATTRIBUTE_LABELS is immutable at runtime.
# ---------------------------------------------------------------------------
_CACHE: dict[tuple[str, str], dict[str, dict[str, str]]] = {}


def _populate_cache() -> None:
    """Pre-compute all (locale, schema) slices from ATTRIBUTE_LABELS."""
    for locale, schemas in ATTRIBUTE_LABELS.items():
        for schema, tables in schemas.items():
            _CACHE[(locale, schema)] = tables


_populate_cache()

# Derived at module load so 400-validation is O(1).
_KNOWN_SCHEMAS: frozenset[str] = frozenset(schema for schemas in ATTRIBUTE_LABELS.values() for schema in schemas)


@router.get("")
async def get_attribute_labels(
    language: str = Query(
        "en",
        description=("Locale for column display labels (en, es, pt). Must be one of the supported locales."),
    ),
    schema: str = Query(
        ...,
        description=(
            "Database schema to fetch labels for (e.g. 'core', 'billing'). Required — no all-schemas variant."
        ),
    ),
    current_user: dict = Depends(get_current_user),
) -> dict[str, dict[str, str]]:
    """
    Get column display labels for a specific DB schema and locale.

    **Authorization**: All authenticated users (Internal, Supplier, Customer, Employer)

    **Query Parameters**:
    - `language`: Locale code (`en`, `es`, `pt`). Defaults to `en`.
      Returns 400 for unsupported locales.
    - `schema`: DB schema name (`external`, `core`, `customer`, `billing`, `ops`).
      Required. Returns 400 for unknown schemas.

    **Response**: `{ "<table>": { "<column>": "<label>" } }` for the requested
    schema and locale. Not paginated — small, static datasets.

    **Caching**: Client-side cache key: `attribute-labels:${locale}:${schema}`.
    Labels are stable between deploys; session-long caching is appropriate.

    **Example** (schema=core, language=en):
    ```json
    {
        "user_info": {
            "first_name": "First Name",
            "last_name": "Last Name"
        }
    }
    ```

    **Error Responses**:
    - 400: Unsupported language or unknown schema
    - 401: Not authenticated
    """
    if language not in settings.SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=400,
            detail=(f"Unsupported language '{language}'. Supported: {', '.join(settings.SUPPORTED_LOCALES)}."),
        )

    if schema not in _KNOWN_SCHEMAS:
        raise HTTPException(
            status_code=400,
            detail=(f"Unknown schema '{schema}'. Known schemas: {', '.join(sorted(_KNOWN_SCHEMAS))}."),
        )

    log_info(f"User {current_user.get('user_id')} fetching attribute labels (language={language} schema={schema})")

    slice_ = _CACHE.get((language, schema))
    if slice_ is None:
        # The schema exists in _KNOWN_SCHEMAS but has no entry for this locale.
        # This is a catalog parity gap; surface it loudly (empty dict so
        # test_attribute_labels_coverage.py will catch it as a missing entry).
        log_info(
            f"No attribute labels found for (language={language}, schema={schema}); "
            "returning empty dict. Check test_attribute_labels_coverage.py for parity gaps."
        )
        return {}

    return slice_
