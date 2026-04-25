"""
Tests for scripts/lint_filter_inventory.py.

Verifies that:
1. The inventory script runs without error (exits 0 in informational mode).
2. Both artifact files are created and parse correctly.
3. Every row in the JSON has the required fields.
4. The Markdown artifact has at least one section header per registered entity.
"""

import importlib.util
import json
import sys
from importlib.abc import Loader
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so scripts.* imports work from the test runner.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_JSON_ARTIFACT = _REPO_ROOT / "docs" / "api" / "filters_inventory.json"
_MD_ARTIFACT = _REPO_ROOT / "docs" / "api" / "filters_inventory.md"

_EXPECTED_ENTITIES = {"national_holidays", "pickups", "plates", "plans", "restaurants"}
_REQUIRED_ROW_KEYS = {"entity", "endpoint", "model", "field", "status"}
_VALID_STATUSES = {"unfiltered", "exempt"}


@pytest.fixture(scope="module")
def inventory_rows() -> list:
    """Run the lint script's main function and return the parsed JSON artifact."""
    # Import the module (not __main__ block) so we get the functions directly.
    spec = importlib.util.spec_from_file_location(
        "lint_filter_inventory",
        _REPO_ROOT / "scripts" / "lint_filter_inventory.py",
    )
    assert spec is not None
    loader: Loader | None = spec.loader
    assert loader is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)

    # Call main() — it writes artifacts and exits 0.
    # We capture the SystemExit to verify exit code.
    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 0, f"lint_filter_inventory.main() exited with code {exc_info.value.code}, expected 0"

    # Parse and return the JSON artifact.
    assert _JSON_ARTIFACT.exists(), f"JSON artifact not written: {_JSON_ARTIFACT}"
    raw: list = json.loads(_JSON_ARTIFACT.read_text(encoding="utf-8"))
    return raw


def test_json_artifact_exists(inventory_rows):
    """JSON artifact file is present after running main()."""
    assert _JSON_ARTIFACT.exists()


def test_md_artifact_exists(inventory_rows):
    """Markdown artifact file is present after running main()."""
    assert _MD_ARTIFACT.exists()


def test_json_parses_as_list(inventory_rows):
    """JSON artifact is a list."""
    assert isinstance(inventory_rows, list)


def test_each_row_has_required_keys(inventory_rows):
    """Every row in the JSON has entity, endpoint, model, field, and status."""
    for row in inventory_rows:
        missing = _REQUIRED_ROW_KEYS - set(row.keys())
        assert not missing, f"Row missing keys {missing}: {row}"


def test_all_statuses_are_valid(inventory_rows):
    """Every status value is 'unfiltered' or 'exempt'."""
    for row in inventory_rows:
        assert row["status"] in _VALID_STATUSES, f"Unexpected status '{row['status']}' in row: {row}"


def test_all_expected_entities_present(inventory_rows):
    """All five registered entities appear in the inventory rows."""
    found_entities = {row["entity"] for row in inventory_rows}
    # Each entity should have at least one unfiltered field.
    for entity in _EXPECTED_ENTITIES:
        assert entity in found_entities, (
            f"Entity '{entity}' not found in inventory rows. Check the hardcoded map in lint_filter_inventory.py."
        )


def test_md_has_section_per_entity(inventory_rows):
    """The Markdown artifact has a section header (## `entity`) for each entity."""
    md_text = _MD_ARTIFACT.read_text(encoding="utf-8")
    for entity in _EXPECTED_ENTITIES:
        assert f"## `{entity}`" in md_text, f"Markdown missing section for entity '{entity}'"


def test_exempt_rows_have_reason(inventory_rows):
    """Rows with status 'exempt' include an exempt_reason key."""
    for row in inventory_rows:
        if row["status"] == "exempt":
            assert "exempt_reason" in row, f"Exempt row missing 'exempt_reason': {row}"
            assert row["exempt_reason"], "exempt_reason must not be empty"
