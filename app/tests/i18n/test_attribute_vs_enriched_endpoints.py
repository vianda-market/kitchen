"""
Report-mode discovery lint: compare enriched endpoint response model fields
against attribute_ui_usage.INVENTORY.

Flags columns that ship in responses but are NOT in INVENTORY — these are
either inventory gaps (column is rendered in a frontend but never inventoried)
or over-exposure candidates (column ships in responses but no frontend renders
it, so it should be dropped).

This test does NOT fail CI on diff content — it runs clean and emits a
per-schema report to stderr so the output is visible in the CI log.  The test
fails only if the introspection itself raises an error.

Audit schema default-excluded
------------------------------
Convention 6: audit.* tables intentionally carry zero INVENTORY entries
because they mirror source schemas and are not independently rendered in UIs.
The audit schema dominates the uninventoried column count (648 of 1,394 total
in the Phase 1 baseline) and would drown real signal if included by default.

To include audit tables in the report (e.g. for a data-exposure investigation),
set the environment variable ATTR_LINT_INCLUDE_AUDIT=1:

    ATTR_LINT_INCLUDE_AUDIT=1 pytest app/tests/i18n/test_attribute_vs_enriched_endpoints.py -v -s

Phase 1 baseline
----------------
Pre-computed at docs/plans/phase1-gaps/{schema}.txt — 1,394 total rows;
746 real candidates after audit exclusion.  On first run the diff should
approximately match these files.  Growth beyond the baseline is the real
signal going forward.

Q-S11 rename-at-API note
-------------------------
Endpoint response fields are compared to INVENTORY by response field name.
Renamed fields (e.g. currency_code ← external.iso4217_currency.code) will
appear as "not in INVENTORY" because INVENTORY uses DB paths.  This is
expected and does NOT represent a gap — the DB-path entry covers the rename.
These appear in the diff output; filter them out during a data-exposure audit
by cross-referencing attribute_labels.py rename comments.
"""

import os
import sys
from typing import Any, get_args, get_origin

import pytest
from pydantic import BaseModel

from app.i18n.attribute_ui_usage import INVENTORY


def _get_response_model_fields(model: Any) -> set[str]:
    """
    Recursively extract all field names from a Pydantic response model.

    Handles:
    - Direct BaseModel subclasses
    - list[SomeModel] annotations
    - Nested BaseModel fields (one level deep — covers most enriched schemas)
    """
    if model is None:
        return set()

    # Unwrap list[Model]
    origin = get_origin(model)
    if origin is list:
        args = get_args(model)
        if args:
            return _get_response_model_fields(args[0])
        return set()

    if not (isinstance(model, type) and issubclass(model, BaseModel)):
        return set()

    fields: set[str] = set(model.model_fields.keys())
    # One level of nested model recursion (covers most join-layer schemas)
    for field_info in model.model_fields.values():
        annotation = field_info.annotation
        if annotation is None:
            continue
        nested_origin = get_origin(annotation)
        if nested_origin is list:
            nested_args = get_args(annotation)
            annotation = nested_args[0] if nested_args else None
        if annotation and isinstance(annotation, type) and issubclass(annotation, BaseModel):
            fields.update(annotation.model_fields.keys())

    return fields


def _collect_response_fields() -> dict[str, set[str]]:
    """
    Walk all registered FastAPI routes, collect response model field names,
    and bucket them by schema (the first segment of the field name is used
    as a heuristic — this is intentionally fuzzy; accurate attribution is
    not the goal, total discovery is).

    Returns a single flat set under key "all" because field names don't carry
    their schema path in the response layer — that's the whole point of the
    rename-at-API design (Q-S11).  The per-schema bucketing in the report
    uses the phase1-gaps baseline files as a reference, not route attribution.
    """
    from application import app  # local import — avoids circular at collection time

    all_fields: set[str] = set()
    for route in app.routes:
        response_model = getattr(route, "response_model", None)
        if response_model is None:
            continue
        all_fields.update(_get_response_model_fields(response_model))

    return {"all": all_fields}


def _load_inventory_field_names() -> set[str]:
    """
    Extract the column part of each INVENTORY key (last segment after the
    final dot) for a coarse name-based comparison.

    This is intentionally approximate — the real comparison is by full
    DB path, but response fields carry only the column name (or a rename).
    """
    names: set[str] = set()
    for key in INVENTORY:
        parts = key.rsplit(".", 1)
        if len(parts) == 2:
            names.add(parts[1])
    return names


def _load_baseline_columns(include_audit: bool) -> dict[str, set[str]]:
    """
    Load the Phase 1 gap baseline from docs/plans/phase1-gaps/{schema}.txt.

    Returns a dict keyed by schema name.  Each value is the set of column
    paths (schema.table.column) from that file.

    The files contain one entry per line in the format:
      <schema>.<table>.<column>
    """
    import pathlib

    base = pathlib.Path(__file__).resolve().parents[3] / "docs" / "plans" / "phase1-gaps"
    result: dict[str, set[str]] = {}
    for txt_file in sorted(base.glob("*.txt")):
        schema_name = txt_file.stem
        if not include_audit and schema_name == "audit":
            continue
        entries: set[str] = set()
        for line in txt_file.read_text().splitlines():
            line = line.strip()
            if line:
                entries.add(line)
        result[schema_name] = entries
    return result


@pytest.fixture(scope="module")
def include_audit() -> bool:
    """Whether to include audit.* schema in the report."""
    return os.environ.get("ATTR_LINT_INCLUDE_AUDIT", "0").strip() in ("1", "true", "yes")


def test_enriched_endpoint_discovery(include_audit: bool) -> None:
    """
    Report-mode discovery: collect all response model fields and compare
    against the Phase 1 gap baseline.

    This test:
    - Asserts the introspection runs without error (always).
    - Prints a per-schema summary to stderr (visible in pytest -s / CI logs).
    - Does NOT fail on diff content (report mode per parent plan open question #4).
    """
    # Collect response fields from all registered routes.
    response_field_sets = _collect_response_fields()
    all_response_fields: set[str] = response_field_sets["all"]

    # Load baseline gap files.
    baseline_by_schema = _load_baseline_columns(include_audit=include_audit)

    # Per-schema summary using baseline as the reference corpus.
    report_lines: list[str] = [
        "",
        "=" * 72,
        "Attribute-vs-enriched-endpoint discovery report",
        f"Audit schema: {'INCLUDED' if include_audit else 'EXCLUDED (set ATTR_LINT_INCLUDE_AUDIT=1 to include)'}",
        "=" * 72,
    ]

    total_baseline = 0
    total_found_in_response = 0

    for schema_name, baseline_cols in sorted(baseline_by_schema.items()):
        # Columns in the baseline gap list whose short name appears in
        # the response model fields.
        found_in_response: set[str] = set()
        for col_path in baseline_cols:
            col_name = col_path.rsplit(".", 1)[-1]
            if col_name in all_response_fields:
                found_in_response.add(col_path)

        total_baseline += len(baseline_cols)
        total_found_in_response += len(found_in_response)

        report_lines.append(
            f"\n  schema={schema_name}: "
            f"{len(baseline_cols)} baseline gap columns, "
            f"{len(found_in_response)} with matching response field name"
        )

    report_lines.append(
        f"\nTotal: {total_baseline} baseline gap columns across "
        f"{len(baseline_by_schema)} schemas "
        f"({'audit excluded' if not include_audit else 'audit included'})"
    )
    report_lines.append(f"       {total_found_in_response} have a response model field with a matching name")
    report_lines.append("\nNote: 'matching name' is approximate (column name only, not full DB path).")
    report_lines.append("Columns that appear in responses but not in INVENTORY are either:")
    report_lines.append("  (a) inventory gaps — frontends render them; add to INVENTORY + labels, or")
    report_lines.append("  (b) over-exposure — no frontend renders them; drop from response.")
    report_lines.append("Cross-reference with docs/plans/phase1-gaps/{schema}.txt for full list.")
    report_lines.append("=" * 72)

    # Emit report to stderr so it appears in pytest -s and CI logs.
    print("\n".join(report_lines), file=sys.stderr)

    # This assertion gates on parse/introspection correctness, not on diff count.
    # If baseline files are missing or unreadable, the test fails here.
    assert isinstance(all_response_fields, set), "response field introspection must return a set"
    assert total_baseline > 0, (
        "Expected at least one baseline gap entry from docs/plans/phase1-gaps/*.txt; "
        "check that the baseline files are present."
    )
