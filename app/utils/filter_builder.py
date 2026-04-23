"""
Filter builder utility.

Builds additional_conditions for EnrichedService.get_enriched() and CRUDService
from query params, using the central filter registry.

Each entry in FILTER_REGISTRY uses a per-field dict with an "op" key that
selects the SQL condition to emit. See filter_registry.py for the full shape
and supported ops / cast values.

Multi-column ilike (OR across cols):
  Emits a single tuple with an OR-compound condition and N identical params —
  one placeholder per column, all filled with the same wrapped value.
  Example: {"cols": ["r.name", "r.description"], "op": "ilike"} with value "pizza"
  emits ("(r.name ILIKE %s OR r.description ILIKE %s)", ["%pizza%", "%pizza%"]).
  The enriched_service AND-joins all conditions naturally, so the OR is contained
  within the single tuple.

Enum validation (eq and in ops only):
  When a field dict has an "enum" key, the named enum class is resolved lazily
  and the value is validated against the enum's members before any SQL is
  emitted.  If "context" is also present, valid values are scoped to
  cls.get_by_context(context) instead of the full enum.
  Invalid value → raises ValueError with a descriptive message; callers in
  routes/route_factory translate this to HTTPException(status_code=400).
  Enum-class resolution is cached via functools.lru_cache so repeated calls
  within a request (and across requests) do not re-import.

Geo op (PostGIS):
  Two modes, selected by the "mode" key in the registry entry:
    "bbox"   — four-element list [min_lng, min_lat, max_lng, max_lat].
               Emits: ST_MakeEnvelope(%s, %s, %s, %s, 4326) && alias.col
    "radius" — three-element list [lat, lng, radius_m].
               Emits: ST_DWithin(alias.col::geography,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
  Both modes validate lat ∈ [-90, 90], lng ∈ [-180, 180], radius_m > 0.
  Non-numeric or out-of-range values raise ValueError → HTTP 400.
  The value passed in filters must be a list/tuple of floats (already parsed
  from the query string by the route handler).
"""

import functools
import importlib
from enum import EnumMeta
from typing import Any

from app.config.filter_registry import FILTER_REGISTRY

# ---------------------------------------------------------------------------
# Lazy, cached enum-class resolution (same search order as generate_filter_schema)
# ---------------------------------------------------------------------------
_ENUM_SEARCH_MODULES = ("app.config.enums", "app.dto.models")


@functools.lru_cache(maxsize=64)
def _resolve_enum_class(class_name: str) -> EnumMeta:
    """Locate an enum class by name. Result is cached for the process lifetime."""
    for module_path in _ENUM_SEARCH_MODULES:
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            continue
        cls = getattr(module, class_name, None)
        if cls is not None and isinstance(cls, EnumMeta):
            return cls  # type: ignore[return-value]
    raise ValueError(
        f"Enum class '{class_name}' not found in {list(_ENUM_SEARCH_MODULES)}. "
        "Check the 'enum' key in filter_registry.py."
    )


def _valid_enum_values(class_name: str, context: str | None) -> set[str]:
    """Return the set of valid raw values for an enum, optionally context-scoped."""
    cls = _resolve_enum_class(class_name)
    if context is not None:
        # get_by_context returns list[str] (values, not members)
        values = cls.get_by_context(context)  # type: ignore[attr-defined]
        return set(values)
    return set(cls._value2member_map_.keys())  # type: ignore[attr-defined]


def _validate_enum_value(value: str, class_name: str, context: str | None, param_name: str) -> None:
    """Raise ValueError if value is not in the valid set for this enum/context."""
    valid = _valid_enum_values(class_name, context)
    if value not in valid:
        raise ValueError(f"Invalid value '{value}' for filter '{param_name}' (expected one of: {sorted(valid)})")


_CAST_SQL: dict[str, str] = {
    "uuid": "%s::uuid",
    "upper": "UPPER(%s)",
    "bool": "%s::bool",
    "date": "%s::date",
    "timestamptz": "%s::timestamptz",
    "int": "%s::int",
    "float": "%s::float",
    "text": "%s",
}

_CAST_COERCE: dict[str, Any] = {
    "uuid": str,
    "upper": lambda v: (v if isinstance(v, str) else str(v)).upper(),
    "bool": bool,
    "date": str,
    "timestamptz": str,
    "int": int,
    "float": float,
    "text": lambda v: v if isinstance(v, str) else str(v),
}


def _placeholder(cast: str) -> str:
    return _CAST_SQL.get(cast, "%s")


def _coerce(value: Any, cast: str) -> Any:
    fn = _CAST_COERCE.get(cast, lambda v: v if isinstance(v, str) else str(v))
    return fn(value)


def _col_ref(field: dict) -> str:
    """Return fully-qualified column reference: alias.col"""
    return f"{field['alias']}.{field['col']}"


# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------


def _to_float(raw: Any, label: str) -> float:
    """Coerce raw to float, raise ValueError with descriptive message on failure."""
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"Geo filter param '{label}' must be a number, got {raw!r}") from None


def _validate_lat(lat: float, label: str) -> None:
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"Geo filter param '{label}' latitude {lat} is out of range [-90, 90]")


def _validate_lng(lng: float, label: str) -> None:
    if not -180.0 <= lng <= 180.0:
        raise ValueError(f"Geo filter param '{label}' longitude {lng} is out of range [-180, 180]")


def _build_geo_bbox(col: str, value: Any, param_name: str) -> tuple[str, list]:
    """
    Build bbox condition.

    value must be a 4-element sequence [min_lng, min_lat, max_lng, max_lat].
    """
    try:
        items = list(value)
    except TypeError:
        raise ValueError(
            f"Geo bbox filter '{param_name}' expects a 4-element sequence "
            f"[min_lng, min_lat, max_lng, max_lat], got {value!r}"
        ) from None
    if len(items) != 4:
        raise ValueError(
            f"Geo bbox filter '{param_name}' requires exactly 4 values "
            f"[min_lng, min_lat, max_lng, max_lat], got {len(items)}"
        )
    min_lng = _to_float(items[0], f"{param_name}[min_lng]")
    min_lat = _to_float(items[1], f"{param_name}[min_lat]")
    max_lng = _to_float(items[2], f"{param_name}[max_lng]")
    max_lat = _to_float(items[3], f"{param_name}[max_lat]")
    _validate_lng(min_lng, f"{param_name}[min_lng]")
    _validate_lat(min_lat, f"{param_name}[min_lat]")
    _validate_lng(max_lng, f"{param_name}[max_lng]")
    _validate_lat(max_lat, f"{param_name}[max_lat]")
    condition = f"ST_MakeEnvelope(%s, %s, %s, %s, 4326) && {col}"
    return condition, [min_lng, min_lat, max_lng, max_lat]


def _build_geo_radius(col: str, value: Any, param_name: str) -> tuple[str, list]:
    """
    Build radius condition.

    value must be a 3-element sequence [lat, lng, radius_m].
    """
    try:
        items = list(value)
    except TypeError:
        raise ValueError(
            f"Geo radius filter '{param_name}' expects a 3-element sequence [lat, lng, radius_m], got {value!r}"
        ) from None
    if len(items) != 3:
        raise ValueError(
            f"Geo radius filter '{param_name}' requires exactly 3 values [lat, lng, radius_m], got {len(items)}"
        )
    lat = _to_float(items[0], f"{param_name}[lat]")
    lng = _to_float(items[1], f"{param_name}[lng]")
    radius_m = _to_float(items[2], f"{param_name}[radius_m]")
    _validate_lat(lat, f"{param_name}[lat]")
    _validate_lng(lng, f"{param_name}[lng]")
    if radius_m <= 0:
        raise ValueError(f"Geo filter param '{param_name}[radius_m]' must be > 0, got {radius_m}")
    # ST_SetSRID(ST_MakePoint(lng, lat), 4326) — PostGIS takes lng first, lat second.
    condition = f"ST_DWithin({col}::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)"
    return condition, [lng, lat, radius_m]


# ---------------------------------------------------------------------------
# Per-op builders (dispatch table below). Each returns (condition, param_list),
# or None if the field's shape means it should be silently skipped (e.g. ilike
# with no cols declared). Unknown ops are handled at the dispatcher — these
# helpers trust their op.
# ---------------------------------------------------------------------------


def _op_eq(field: dict, value: Any, param_name: str) -> tuple[str, list]:
    cast = field.get("cast", "text")
    enum_name = field.get("enum")
    if enum_name:
        # For upper cast the DB column stores upper-cased values; validate the
        # upper-cased form so the check matches what is stored.
        check_value = value.upper() if cast == "upper" else value
        _validate_enum_value(check_value, enum_name, field.get("context"), param_name)
    return (f"{_col_ref(field)} = {_placeholder(cast)}", [_coerce(value, cast)])


def _op_in(field: dict, value: Any, param_name: str) -> tuple[str, list]:
    cast = field.get("cast", "text")
    items = list(value) if isinstance(value, (list, tuple)) else [value]
    enum_name = field.get("enum")
    if enum_name:
        context = field.get("context")
        for item in items:
            check_item = item.upper() if cast == "upper" else item
            _validate_enum_value(check_item, enum_name, context, param_name)
    coerced = [_coerce(i, cast) for i in items]
    # psycopg2 list binding: col = ANY(%s) with a list as the single param
    return (f"{_col_ref(field)} = ANY(%s)", [coerced])


def _op_gte(field: dict, value: Any, param_name: str) -> tuple[str, list]:
    cast = field.get("cast", "text")
    return (f"{_col_ref(field)} >= {_placeholder(cast)}", [_coerce(value, cast)])


def _op_lte(field: dict, value: Any, param_name: str) -> tuple[str, list]:
    cast = field.get("cast", "text")
    return (f"{_col_ref(field)} <= {_placeholder(cast)}", [_coerce(value, cast)])


def _op_ilike(field: dict, value: Any, param_name: str) -> tuple[str, list] | None:
    # Emit a single OR-compound condition with N placeholders and N identical
    # params. AND-join in enriched_service naturally composes with siblings.
    cols = field.get("cols", [])
    if not cols:
        return None
    wrapped = f"%{value}%"
    condition = f"({' OR '.join(f'{col} ILIKE %s' for col in cols)})" if len(cols) > 1 else f"{cols[0]} ILIKE %s"
    return (condition, [wrapped] * len(cols))


def _op_bool(field: dict, value: Any, param_name: str) -> tuple[str, list]:
    return (f"{_col_ref(field)} = %s::bool", [bool(value)])


def _op_geo(field: dict, value: Any, param_name: str) -> tuple[str, list]:
    mode = field.get("mode")
    col = _col_ref(field)
    if mode == "bbox":
        return _build_geo_bbox(col, value, param_name)
    if mode == "radius":
        return _build_geo_radius(col, value, param_name)
    raise ValueError(f"Geo filter '{param_name}' has unknown mode '{mode}'. Supported modes: 'bbox', 'radius'.")


_OP_BUILDERS = {
    "eq": _op_eq,
    "in": _op_in,
    "gte": _op_gte,
    "lte": _op_lte,
    "ilike": _op_ilike,
    "bool": _op_bool,
    "geo": _op_geo,
}


def build_filter_conditions(
    entity_key: str,
    filters: dict[str, Any],
) -> list[tuple[str, list]] | None:
    """
    Build additional_conditions for EnrichedService from filters dict.

    Args:
        entity_key: Key in FILTER_REGISTRY (e.g. "plans")
        filters: Dict of param_name -> value (None values are skipped)

    Returns:
        List of (condition, list_of_params) tuples for additional_conditions, or None if empty.

        Op semantics live in each _op_* helper; see module docstring for the overview.
        Unknown ops are silently skipped — keeps callers safe from registry drift.
    """
    registry = FILTER_REGISTRY.get(entity_key, {})
    conditions: list[tuple[str, list]] = []

    for param_name, value in filters.items():
        if value is None or param_name not in registry:
            continue
        field = registry[param_name]
        builder = _OP_BUILDERS.get(field.get("op", "eq"))
        if builder is None:
            continue
        result = builder(field, value, param_name)
        if result is not None:
            conditions.append(result)

    return conditions if conditions else None
