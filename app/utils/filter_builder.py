"""
Filter builder utility.

Builds additional_conditions for EnrichedService.get_enriched() and CRUDService
from query params, using the central filter registry.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.config.filter_registry import FILTER_REGISTRY


def build_filter_conditions(
    entity_key: str,
    filters: Dict[str, Any],
) -> Optional[List[Tuple[str, Any]]]:
    """
    Build additional_conditions for EnrichedService from filters dict.

    Args:
        entity_key: Key in FILTER_REGISTRY (e.g. "plans")
        filters: Dict of param_name -> value (None values are skipped)

    Returns:
        List of (condition, param) tuples for additional_conditions, or None if empty
    """
    registry = FILTER_REGISTRY.get(entity_key, {})
    conditions: List[Tuple[str, Any]] = []

    for param_name, value in filters.items():
        if value is None:
            continue
        if param_name not in registry:
            continue

        col, alias, cast_type = registry[param_name]

        if cast_type == "uuid":
            condition = f"{alias}.{col} = %s::uuid"
            param: Any = str(value)
        elif cast_type == "text":
            condition = f"{alias}.{col}::text = %s"
            param = value if isinstance(value, str) else str(value)
        elif cast_type == "upper":
            condition = f"{alias}.{col} = UPPER(%s)"
            param = value if isinstance(value, str) else str(value)
        else:
            condition = f"{alias}.{col} = %s"
            param = value

        conditions.append((condition, param))

    return conditions if conditions else None
