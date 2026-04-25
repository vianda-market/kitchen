"""
Filter inventory lint script.

For each registered entity, compares the filterable keys in FILTER_REGISTRY against
the response-model fields exposed by the enriched endpoint.  Reports every field
that is NOT covered by a filter ("unfiltered") and every field that has been
deliberately exempted via a source-level comment ("exempt").

Exemption syntax (add on the line immediately above the field declaration in the
model class):
    # filter-registry:exempt reason=<reason>

Artifacts produced (always):
    kitchen/docs/api/filters_inventory.json  — structured rows
    kitchen/docs/api/filters_inventory.md    — human-readable table per entity

Strict mode (since Pass 5b, 2026-04-25):
    - Exits 0 when every enriched-response field is either filterable or exempt.
    - Exits 1 when any field is unfiltered (i.e. exposed but neither registered
      nor explicitly exempted via `# filter-registry:exempt reason="..."`).

The previous informational-only mode was retired once Pass 5 brought the
unfiltered count to 0 across all 5 entities. From now on, any new enriched
field added to a Pydantic response model must be either registered as a
filter in `app/config/filter_registry.py` or carry an exempt comment, or
this lint fails CI.

Usage:
    python3 scripts/lint_filter_inventory.py            # run from repo root
    python3 -m scripts.lint_filter_inventory           # alternative
"""

import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Repo root on sys.path so app.* imports work.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Hardcoded entity → response-model mapping (v1).
# AST-based discovery is deferred until the registry grows past ~10 entities
# (see §10, 2026-04-24 decision log in the cross-repo filters plan).
# ---------------------------------------------------------------------------
def _load_entity_models() -> dict[str, type]:
    """Return the hardcoded entity → Pydantic model class map."""
    from app.schemas.consolidated_schemas import (  # noqa: PLC0415
        NationalHolidayResponseSchema,  # noqa: PLC0415
        PlanEnrichedResponseSchema,
        PlateEnrichedResponseSchema,
        PlatePickupEnrichedResponseSchema,
        RestaurantEnrichedResponseSchema,
    )

    return {
        "national_holidays": NationalHolidayResponseSchema,
        "pickups": PlatePickupEnrichedResponseSchema,
        "plates": PlateEnrichedResponseSchema,
        "plans": PlanEnrichedResponseSchema,
        "restaurants": RestaurantEnrichedResponseSchema,
    }


# ---------------------------------------------------------------------------
# Endpoint mapping (for the inventory output — documentation only).
# ---------------------------------------------------------------------------
_ENTITY_ENDPOINTS: dict[str, str] = {
    "national_holidays": "/api/v1/national-holidays",
    "pickups": "/api/v1/plate-pickup/enriched",
    "plates": "/api/v1/plates/enriched",
    "plans": "/api/v1/plans/enriched",
    "restaurants": "/api/v1/restaurants/enriched",
}

# ---------------------------------------------------------------------------
# Exempt-comment detection.
# ---------------------------------------------------------------------------
_EXEMPT_PATTERN = re.compile(r"#\s*filter-registry:exempt\s+reason=(.+)$")


def _find_exempt_fields(model_cls: type) -> dict[str, str]:
    """
    Scan the source file of model_cls for exemption comments.

    Returns a dict of {field_name: reason_string} for each field that has a
    ``# filter-registry:exempt reason=...`` comment on the line immediately
    above its declaration.

    Falls back gracefully if the source is unavailable (e.g. frozen module).
    """
    exempt: dict[str, str] = {}
    try:
        source_lines = inspect.getsource(model_cls).splitlines()
    except (OSError, TypeError):
        return exempt

    for i, line in enumerate(source_lines):
        # Detect a field declaration line (simplified: contains ": " after identifier).
        # We look for the preceding line for the exempt comment.
        stripped = line.strip()
        if i == 0 or not stripped or stripped.startswith("#"):
            continue
        # Check if line looks like a field declaration (field_name: ...)
        field_match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", line)
        if field_match:
            field_name = field_match.group(1)
            # Skip class-level keywords and common non-field lines.
            if field_name in ("class", "def", "return", "model_config", "self"):
                continue
            prev_line = source_lines[i - 1].strip() if i > 0 else ""
            m = _EXEMPT_PATTERN.search(prev_line)
            if m:
                exempt[field_name] = m.group(1).strip()
    return exempt


# ---------------------------------------------------------------------------
# Core inventory builder.
# ---------------------------------------------------------------------------
def build_inventory() -> list[dict[str, Any]]:
    """
    Build the full inventory rows.

    Returns a list of dicts:
        {entity, endpoint, model, field, status: "unfiltered" | "exempt"}
    """
    from app.config.filter_registry import FILTER_REGISTRY  # noqa: PLC0415

    entity_models = _load_entity_models()
    rows: list[dict[str, Any]] = []

    for entity, model_cls in sorted(entity_models.items()):
        filterable_keys: set[str] = set(FILTER_REGISTRY.get(entity, {}).keys())
        model_fields: set[str] = set(model_cls.model_fields.keys())
        endpoint = _ENTITY_ENDPOINTS.get(entity, "unknown")
        model_name = model_cls.__name__
        exempt_fields = _find_exempt_fields(model_cls)

        for field in sorted(model_fields):
            if field in filterable_keys:
                # Covered by the registry — not reported.
                continue
            if field in exempt_fields:
                rows.append(
                    {
                        "entity": entity,
                        "endpoint": endpoint,
                        "model": model_name,
                        "field": field,
                        "status": "exempt",
                        "exempt_reason": exempt_fields[field],
                    }
                )
            else:
                rows.append(
                    {
                        "entity": entity,
                        "endpoint": endpoint,
                        "model": model_name,
                        "field": field,
                        "status": "unfiltered",
                    }
                )

    return rows


# ---------------------------------------------------------------------------
# Artifact writers.
# ---------------------------------------------------------------------------


def _write_json(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Emit a subset of keys for JSON (drop exempt_reason into its own key).
    path.write_text(json.dumps(rows, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_md(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    # Group by entity.
    by_entity: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_entity.setdefault(row["entity"], []).append(row)

    lines = [
        "# Filter Inventory",
        "",
        "Auto-generated by `scripts/lint_filter_inventory.py`. Do not hand-edit.",
        "",
        "Status legend:",
        "- **unfiltered** — field exists on the response model but has no entry in `FILTER_REGISTRY`.",
        "- **exempt** — field has a `# filter-registry:exempt reason=...` comment and is intentionally unregistered.",
        "",
    ]

    for entity in sorted(by_entity.keys()):
        entity_rows = by_entity[entity]
        if not entity_rows:
            continue
        model_name = entity_rows[0]["model"]
        endpoint = entity_rows[0]["endpoint"]
        lines += [
            f"## `{entity}`",
            "",
            f"**Endpoint:** `{endpoint}`  ",
            f"**Response model:** `{model_name}`",
            "",
            "| Field | Status | Exempt reason |",
            "|-------|--------|---------------|",
        ]
        for row in sorted(entity_rows, key=lambda r: r["field"]):
            reason = row.get("exempt_reason", "")
            lines.append(f"| `{row['field']}` | {row['status']} | {reason} |")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Summary line.
# ---------------------------------------------------------------------------


def _summary_line(rows: list[dict[str, Any]], entity_models: dict) -> str:
    n_entities = len(entity_models)
    total_fields = sum(len(model_cls.model_fields) for model_cls in entity_models.values())
    n_unfiltered = sum(1 for r in rows if r["status"] == "unfiltered")
    n_exempt = sum(1 for r in rows if r["status"] == "exempt")
    return f"{n_entities} entities, {total_fields} enriched fields, {n_unfiltered} unfiltered, {n_exempt} exempt"


# ---------------------------------------------------------------------------
# Main entry point.
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the inventory, write artifacts, print summary.

    Exits 0 when no fields are unfiltered; exits 1 otherwise.
    """
    rows = build_inventory()
    entity_models = _load_entity_models()

    json_path = _REPO_ROOT / "docs" / "api" / "filters_inventory.json"
    md_path = _REPO_ROOT / "docs" / "api" / "filters_inventory.md"

    _write_json(rows, json_path)
    _write_md(rows, md_path)

    summary = _summary_line(rows, entity_models)
    print(summary)
    print(f"  Written {json_path}")
    print(f"  Written {md_path}")

    # Informational: print a breakdown per entity.

    for entity, model_cls in sorted(entity_models.items()):
        total = len(model_cls.model_fields)
        entity_rows = [r for r in rows if r["entity"] == entity]
        unfiltered = sum(1 for r in entity_rows if r["status"] == "unfiltered")
        exempt = sum(1 for r in entity_rows if r["status"] == "exempt")
        covered = total - unfiltered - exempt
        print(f"  {entity}: {total} fields total, {covered} filterable, {unfiltered} unfiltered, {exempt} exempt")

    # Strict mode (Pass 5b): fail CI if any field is exposed but neither
    # filterable nor exempt. Pass 5 brought the count to 0; the gate now
    # ratchets that and prevents drift.
    n_unfiltered = sum(1 for r in rows if r["status"] == "unfiltered")
    if n_unfiltered > 0:
        print(
            f"\n✘ {n_unfiltered} enriched field(s) exposed but not filterable.\n"
            "  Either register the field in app/config/filter_registry.py, or\n"
            '  add `# filter-registry:exempt reason="..."` next to the field\n'
            "  in its Pydantic response schema.",
            file=sys.stderr,
        )
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
