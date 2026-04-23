"""
Central filter registry for list/filter endpoints.

Defines allowed query filters per entity. Each filter maps to a DB column
and SQL condition. Used by filter_builder to produce additional_conditions
for EnrichedService / CRUDService.

Per-field dict shape:
  For single-column ops (eq, in, gte, lte, bool):
    { "col": str, "alias": str, "op": str, "cast": str, "enum"?: str }
  For multi-column search (ilike):
    { "cols": list[str], "op": "ilike" }
  For geo ops (PostGIS):
    { "col": str, "alias": str, "op": "geo", "mode": "bbox" | "radius" }
    bbox   value shape: [min_lng, min_lat, max_lng, max_lat]
    radius value shape: [lat, lng, radius_m]

Supported ops:
  "eq"    — equality: alias.col = %s (with cast)
  "in"    — set membership: alias.col = ANY(%s) (psycopg2 list binding)
  "gte"   — lower bound: alias.col >= %s (with cast)
  "lte"   — upper bound: alias.col <= %s (with cast)
  "ilike" — case-insensitive substring: col ILIKE %value% OR col2 ILIKE %value%
  "bool"  — boolean equality: alias.col = %s::bool
  "geo"   — spatial filter via PostGIS; mode selects the SQL pattern:
              bbox:   ST_MakeEnvelope(min_lng, min_lat, max_lng, max_lat, 4326) && col
              radius: ST_DWithin(col::geography, ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography, radius_m)

Note: when a filter targets a column on a 1:N joined table (e.g. pkd.kitchen_day), the join
must be added to the relevant get_enriched_* function and distinct=True must be passed to
EnrichedService.get_enriched() to prevent row inflation. The registry entry itself is a
plain "eq" (or other scalar op) — SQL fragments do not belong in the registry.

Supported cast values (for eq, in, gte, lte):
  "uuid", "text", "upper", "bool", "date", "int", "float"

The optional "enum" key holds the enum class name (e.g. "Status"). The schema
generator uses it to emit valid values; display labels are resolved by frontends
through app/i18n/enum_labels.py and are never duplicated here.
"""

FILTER_REGISTRY: dict[str, dict[str, dict]] = {
    "plans": {
        "market_id": {"col": "market_id", "alias": "pl", "op": "eq", "cast": "uuid"},
        "status": {"col": "status", "alias": "pl", "op": "eq", "cast": "text", "enum": "Status"},
        "currency_code": {"col": "currency_code", "alias": "cc", "op": "eq", "cast": "upper"},
    },
    "restaurants": {
        # city is on address_info, alias "a" in the enriched restaurant query
        "city": {"col": "city", "alias": "a", "op": "eq", "cast": "text"},
        # market_id is on market_info, alias "m" (joined via address.country_code = market.country_code)
        "market_id": {"col": "market_id", "alias": "m", "op": "eq", "cast": "uuid"},
        # kitchen_day lives on ops.plate_kitchen_days (alias "pkd"), which is joined via
        # ops.plate_info (alias "pi") in get_enriched_restaurants. The join is filter-only
        # (pkd.kitchen_day is not in the SELECT list); duplicate rows are eliminated by
        # distinct=True in the enriched service call.
        "kitchen_day": {"col": "kitchen_day", "alias": "pkd", "op": "eq", "cast": "text", "enum": "KitchenDay"},
        # cuisine is filtered by cuisine_name on the joined cuisine table, alias "cu"
        # No Python Cuisine enum exists; cuisines are DB records — leave enum off.
        "cuisine": {"col": "cuisine_name", "alias": "cu", "op": "in", "cast": "text"},
        # search across restaurant name and description (tagline is the public description)
        "search": {"cols": ["r.name", "r.tagline"], "op": "ilike"},
        # geo bbox: bounding box [min_lng, min_lat, max_lng, max_lat].
        # Route handler parses ?bbox=min_lng,min_lat,max_lng,max_lat into a 4-float list.
        # Requires PostGIS (geometry(Point,4326) column on ops.restaurant_info).
        "bbox": {"col": "location", "alias": "r", "op": "geo", "mode": "bbox"},
        # geo radius: proximity filter [lat, lng, radius_m].
        # Route handler parses ?center=lat,lng&radius_m=<meters> into a 3-float list.
        # Requires PostGIS.
        "radius": {"col": "location", "alias": "r", "op": "geo", "mode": "radius"},
    },
    "plates": {
        # status is on plate_info, alias "p"
        "status": {"col": "status", "alias": "p", "op": "eq", "cast": "text", "enum": "Status"},
        # market_id is on market_info, alias "m" (joined via restaurant → address → market)
        "market_id": {"col": "market_id", "alias": "m", "op": "eq", "cast": "uuid"},
        # restaurant_id is on plate_info, alias "p"
        "restaurant_id": {"col": "restaurant_id", "alias": "p", "op": "eq", "cast": "uuid"},
        # plate_info has no plate_date column; created_date is the closest proxy.
        # plate_selection_info.pickup_date is the actual pickup date but is on a different table.
        # Using p.created_date for date-range filtering on the plate's creation date.
        "plate_date_from": {"col": "created_date", "alias": "p", "op": "gte", "cast": "date"},
        "plate_date_to": {"col": "created_date", "alias": "p", "op": "lte", "cast": "date"},
    },
    "pickups": {
        # status is on plate_pickup_live, alias "ppl"
        # context="plate_pickup" scopes valid values to the pickup lifecycle subset
        # (pending, arrived, handed_out, completed, cancelled) — not the full Status enum.
        "status": {"col": "status", "alias": "ppl", "op": "eq", "cast": "text", "enum": "Status", "context": "plate_pickup"},
        # market_id is on market_info, alias "m" (joined via restaurant → address → market)
        "market_id": {"col": "market_id", "alias": "m", "op": "eq", "cast": "uuid"},
        # window_from / window_to filter by expected_completion_time (TIMESTAMPTZ)
        "window_from": {"col": "expected_completion_time", "alias": "ppl", "op": "gte", "cast": "timestamptz"},
        "window_to": {"col": "expected_completion_time", "alias": "ppl", "op": "lte", "cast": "timestamptz"},
    },
}
