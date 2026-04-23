"""
Generate docs/api/filters.json from FILTER_REGISTRY.

This script is intentionally side-effect free on import. File I/O only happens
when run as __main__. Callers that need the data without writing can:

    from scripts.generate_filter_schema import build_schema
    schema = build_schema()

Output contract:
  A JSON array of entity objects:
    [
      {
        "entity": "<name>",
        "fields": [
          {
            "key": "<param_name>",
            "kind": "select" | "multi-select" | "range-bound" | "search" | "toggle",
            "cast": "<cast_type>",           // omitted for ilike fields (no cast)
            "enum_ref": "<ClassName>",        // only when enum is declared
            "values": ["<slug>", ...]         // only when enum is declared
          },
          ...
        ]
      },
      ...
    ]

op → kind mapping:
  eq        → "select"        (single-value exact match)
  in        → "multi-select"  (list membership, repeated params)
  gte / lte → "range-bound"   (one bound; frontends pair by naming convention)
  ilike     → "search"        (case-insensitive substring)
  bool      → "toggle"        (boolean on/off)

No SQL fragments, column names, table aliases, or internal implementation
details are emitted. The output is a pure frontend contract.

Enum resolution order:
  1. app.config.enums  (primary — most Python enums live here)
  2. app.dto.models    (secondary — any enums defined alongside DTOs)

If an enum class named in the registry is not found in either module,
a ValueError is raised at generation time so the contract gap is caught early.
"""

import importlib
import json
import sys
from enum import EnumMeta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Repo root must be on sys.path so we can import app.* modules.
# When run as __main__ from the repo root (python scripts/generate_filter_schema.py)
# this is usually already the case, but we ensure it explicitly.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Lazy import of FILTER_REGISTRY so that import of this module is cheap.
# Do NOT move these imports to module level — keep the file side-effect free.
_ENUM_SEARCH_MODULES = ["app.config.enums", "app.dto.models"]

_OP_TO_KIND: dict[str, str] = {
    "eq": "select",
    "in": "multi-select",
    "gte": "range-bound",
    "lte": "range-bound",
    "ilike": "search",
    "bool": "toggle",
    "geo": "geo",  # kind is further qualified by "mode" field (geo-bbox / geo-radius)
}


def _resolve_enum_class(class_name: str) -> EnumMeta:
    """
    Locate an enum class by name across the known search modules.

    Raises ValueError if the class is not found or is not an Enum.
    """
    for module_path in _ENUM_SEARCH_MODULES:
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            continue
        cls = getattr(module, class_name, None)
        if cls is not None:
            if not isinstance(cls, EnumMeta):
                raise ValueError(
                    f"'{class_name}' found in '{module_path}' but is not an Enum class "
                    f"(got {type(cls).__name__!r}). Check the registry entry."
                )
            return cls
    raise ValueError(
        f"Enum class '{class_name}' not found in any of: {_ENUM_SEARCH_MODULES}. "
        "Add the correct import path or fix the 'enum' key in filter_registry.py."
    )


def _build_field_entry(param_name: str, field_def: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a single registry field definition into its schema representation.

    Omits internal keys (col, cols, alias) entirely — the output is a pure
    frontend contract with no SQL fragments.
    """
    op: str = field_def.get("op", "eq")
    kind = _OP_TO_KIND.get(op)
    if kind is None:
        raise ValueError(f"Unknown op '{op}' on field '{param_name}'. Supported ops: {sorted(_OP_TO_KIND.keys())}.")

    # For geo op, qualify kind with mode to give frontends an unambiguous signal.
    if op == "geo":
        mode = field_def.get("mode")
        if not mode:
            raise ValueError(f"Geo field '{param_name}' is missing required 'mode' key (bbox or radius).")
        kind = f"geo-{mode}"

    entry: dict[str, Any] = {"key": param_name, "kind": kind}

    # cast is meaningful for all ops except ilike (which has no per-value cast)
    # and geo (which manages its own types internally).
    cast = field_def.get("cast")
    if cast is not None:
        entry["cast"] = cast

    # For geo, emit the mode so frontends know which params to send.
    if op == "geo":
        entry["mode"] = field_def["mode"]

    # Enum: resolve class, emit ref name + value slugs
    enum_class_name = field_def.get("enum")
    if enum_class_name:
        enum_cls = _resolve_enum_class(enum_class_name)
        entry["enum_ref"] = enum_class_name
        context = field_def.get("context")
        if context is not None:
            # Use context-scoped values; get_by_context returns list[str]
            values = enum_cls.get_by_context(context)  # type: ignore[attr-defined]
            if not values:
                raise ValueError(
                    f"Status.get_by_context('{context}') returned an empty list for "
                    f"field '{param_name}'. This is a bug — check STATUS_CONTEXTS in status.py."
                )
            entry["values"] = values
            entry["context"] = context
        else:
            entry["values"] = [e.value for e in enum_cls]  # type: ignore[attr-defined]

    return entry


def build_schema() -> list[dict[str, Any]]:
    """
    Build the full filter schema from FILTER_REGISTRY.

    Returns a list of entity objects sorted by entity name for deterministic
    output. Field order within each entity mirrors FILTER_REGISTRY insertion
    order (Python 3.7+ dict ordering), which is stable.

    This function is side-effect free — it does not write any files.
    """
    from app.config.filter_registry import FILTER_REGISTRY  # noqa: PLC0415

    result: list[dict[str, Any]] = []

    for entity_name in sorted(FILTER_REGISTRY.keys()):
        fields_def = FILTER_REGISTRY[entity_name]
        fields: list[dict[str, Any]] = []
        for param_name, field_def in fields_def.items():
            fields.append(_build_field_entry(param_name, field_def))
        result.append({"entity": entity_name, "fields": fields})

    return result


def _schema_to_json(schema: list[dict[str, Any]]) -> str:
    """
    Serialize the schema to a pretty-printed, deterministic JSON string.

    Keys within each object are sorted so that diffs are stable regardless of
    dict insertion order in the generator internals. No timestamps, no random
    data.
    """
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    """Write docs/api/filters.json relative to the repo root."""
    output_path = _REPO_ROOT / "docs" / "api" / "filters.json"
    schema = build_schema()
    json_text = _schema_to_json(schema)
    output_path.write_text(json_text, encoding="utf-8")
    print(f"Written {output_path}")
    # Summary for verification
    for entity in schema:
        field_count = len(entity["fields"])
        print(f"  {entity['entity']}: {field_count} field(s)")


if __name__ == "__main__":
    main()
