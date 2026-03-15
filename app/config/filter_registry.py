"""
Central filter registry for list/filter endpoints.

Defines allowed query filters per entity. Each filter maps to a DB column
and SQL condition. Used by filter_builder to produce additional_conditions
for EnrichedService / CRUDService.

Format: param_name -> (column, table_alias, cast_type)
- column: DB column name
- table_alias: Alias used in the enriched query (e.g. pl for plan_info)
- cast_type: "uuid" | "text" | "upper" (how to cast/transform the param for SQL)
"""

FILTER_REGISTRY = {
    "plans": {
        "market_id": ("market_id", "pl", "uuid"),
        "status": ("status", "pl", "text"),
        "currency_code": ("currency_code", "cc", "upper"),
    },
    # Future entities:
    # "subscriptions": {...},
    # "markets": {...},
}
