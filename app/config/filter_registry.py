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
        "status": {"col": "status", "alias": "pl", "op": "eq", "cast": "text", "enum": "Status", "context": "plan"},
        "currency_code": {"col": "currency_code", "alias": "cc", "op": "eq", "cast": "upper"},
        # Pass 5 register-adds:
        # price: range-bound (float -- plan price is stored as float in the DB schema)
        "price_from": {"col": "price", "alias": "pl", "op": "gte", "cast": "float"},
        "price_to": {"col": "price", "alias": "pl", "op": "lte", "cast": "float"},
        # credit: range-bound (int)
        "credit_from": {"col": "credit", "alias": "pl", "op": "gte", "cast": "int"},
        "credit_to": {"col": "credit", "alias": "pl", "op": "lte", "cast": "int"},
        # country_code: multi-select on market_info alias "m"
        "country_code": {"col": "country_code", "alias": "m", "op": "in", "cast": "upper"},
        # rollover: toggle (bool)
        "rollover": {"col": "rollover", "alias": "pl", "op": "bool", "cast": "bool"},
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
        # No Python Cuisine enum exists; cuisines are DB records -- leave enum off.
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
        # Pass 5 register-adds:
        # status: multi-select (restaurant status: active, inactive, pending)
        "status": {"col": "status", "alias": "r", "op": "in", "cast": "text", "enum": "Status"},
        # country_code: multi-select on address_info alias "a"
        "country_code": {"col": "country_code", "alias": "a", "op": "in", "cast": "upper"},
        # institution_id: multi-select on restaurant_info alias "r"
        "institution_id": {"col": "institution_id", "alias": "r", "op": "in", "cast": "uuid"},
        # institution_entity_id: multi-select on restaurant_info alias "r"
        "institution_entity_id": {"col": "institution_entity_id", "alias": "r", "op": "in", "cast": "uuid"},
    },
    "plates": {
        # status is on plate_info, alias "p"
        # context="plate" scopes valid values to catalog visibility subset
        # (active, inactive) -- pickup-lifecycle states do not apply here.
        "status": {"col": "status", "alias": "p", "op": "eq", "cast": "text", "enum": "Status", "context": "plate"},
        # market_id is on market_info, alias "m" (joined via restaurant -> address -> market)
        "market_id": {"col": "market_id", "alias": "m", "op": "eq", "cast": "uuid"},
        # restaurant_id is on plate_info, alias "p"
        "restaurant_id": {"col": "restaurant_id", "alias": "p", "op": "eq", "cast": "uuid"},
        # plate_selection_info.pickup_date is the actual service date (DATE) for a plate reservation.
        # get_enriched_plates joins customer.plate_selection_info (alias "psi") as a filter-only join
        # (psi.pickup_date is not in the SELECT list); distinct=True prevents row inflation from the
        # 1:N plate_info → plate_selection_info relationship.
        "plate_date_from": {"col": "pickup_date", "alias": "psi", "op": "gte", "cast": "date"},
        "plate_date_to": {"col": "pickup_date", "alias": "psi", "op": "lte", "cast": "date"},
        # Pass 5 register-adds:
        # cuisine_id: multi-select on cuisine table alias "cu" (joined via r.cuisine_id = cu.cuisine_id)
        "cuisine_id": {"col": "cuisine_id", "alias": "cu", "op": "in", "cast": "uuid"},
        # dietary: multi-select (DietaryFlag enum) -- pr.dietary is TEXT[] in PostgreSQL.
        # filter_builder "in" op emits col = ANY(%s) which for TEXT[] checks if the whole array
        # equals any value in the list -- NOT element containment. Correct semantics need
        # %s = ANY(col) (reverse ANY). Registered here for schema publication; route wiring
        # uses manual SQL (pr.dietary && %s::text[]) until filter_builder gains "any_in" op.
        # Tracking: kitchen#87.
        "dietary": {"col": "dietary", "alias": "pr", "op": "in", "cast": "text", "enum": "DietaryFlag"},
        # price: range-bound (int)
        "price_from": {"col": "price", "alias": "p", "op": "gte", "cast": "int"},
        "price_to": {"col": "price", "alias": "p", "op": "lte", "cast": "int"},
        # credit: range-bound (int)
        "credit_from": {"col": "credit", "alias": "p", "op": "gte", "cast": "int"},
        "credit_to": {"col": "credit", "alias": "p", "op": "lte", "cast": "int"},
        # has_image: toggle (bool) -- has_image in SELECT is a CASE expression on pr.image_storage_path.
        # Registered for schema publication; route wiring uses a manual SQL condition until
        # filter_builder supports CASE-derived columns. Tracking: kitchen#87.
        "has_image": {"col": "image_storage_path", "alias": "pr", "op": "bool", "cast": "bool"},
        # portion_size: multi-select -- entirely computed in Python (bucket_portion_size()); no DB column.
        # Registered for schema publication only; SQL-layer filtering not wired. Tracking: kitchen#87.
        "portion_size": {
            "col": "portion_size",
            "alias": "p",
            "op": "in",
            "cast": "text",
            "enum": "PortionSizeDisplay",
        },
    },
    "pickups": {
        # status is on plate_pickup_live, alias "ppl"
        # context="plate_pickup" scopes valid values to the pickup lifecycle subset
        # (pending, arrived, handed_out, completed, cancelled) -- not the full Status enum.
        "status": {
            "col": "status",
            "alias": "ppl",
            "op": "eq",
            "cast": "text",
            "enum": "Status",
            "context": "plate_pickup",
        },
        # market_id is on market_info, alias "m" (joined via restaurant -> address -> market)
        "market_id": {"col": "market_id", "alias": "m", "op": "eq", "cast": "uuid"},
        # window_from / window_to filter by expected_completion_time (TIMESTAMPTZ)
        "window_from": {"col": "expected_completion_time", "alias": "ppl", "op": "gte", "cast": "timestamptz"},
        "window_to": {"col": "expected_completion_time", "alias": "ppl", "op": "lte", "cast": "timestamptz"},
        # Pass 5 register-adds:
        # arrival_time: date-range-bound (timestamptz)
        "arrival_time_from": {"col": "arrival_time", "alias": "ppl", "op": "gte", "cast": "timestamptz"},
        "arrival_time_to": {"col": "arrival_time", "alias": "ppl", "op": "lte", "cast": "timestamptz"},
        # completion_time: date-range-bound (timestamptz)
        "completion_time_from": {"col": "completion_time", "alias": "ppl", "op": "gte", "cast": "timestamptz"},
        "completion_time_to": {"col": "completion_time", "alias": "ppl", "op": "lte", "cast": "timestamptz"},
        # was_collected: toggle (bool)
        "was_collected": {"col": "was_collected", "alias": "ppl", "op": "bool", "cast": "bool"},
        # credit: range-bound (int) -- from plate_info alias "p" (joined in get_enriched_plate_pickups)
        "credit_from": {"col": "credit", "alias": "p", "op": "gte", "cast": "int"},
        "credit_to": {"col": "credit", "alias": "p", "op": "lte", "cast": "int"},
        # restaurant_id: multi-select on plate_pickup_live alias "ppl"
        "restaurant_id": {"col": "restaurant_id", "alias": "ppl", "op": "in", "cast": "uuid"},
        # plate_id: multi-select on plate_pickup_live alias "ppl"
        "plate_id": {"col": "plate_id", "alias": "ppl", "op": "in", "cast": "uuid"},
    },
    "national_holidays": {
        # country_code is on national_holidays table, alias "nh".
        # Registered as select (single-value eq) rather than free-text search -- the frontend
        # drives this from the markets/countries reference endpoint, not a text input.
        # No Python enum exists for country codes; values come from the DB reference table.
        # The current frontend already passes ?country_code=AR; this entry registers the param
        # so it flows through filter_builder.py rather than being handled ad-hoc in the route.
        "country_code": {"col": "country_code", "alias": "nh", "op": "eq", "cast": "upper"},
        # Pass 5 register-adds:
        # holiday_date: date-range-bound (date)
        "holiday_date_from": {"col": "holiday_date", "alias": "nh", "op": "gte", "cast": "date"},
        "holiday_date_to": {"col": "holiday_date", "alias": "nh", "op": "lte", "cast": "date"},
        # is_recurring: toggle (bool)
        "is_recurring": {"col": "is_recurring", "alias": "nh", "op": "bool", "cast": "bool"},
        # recurring_month: multi-select (int, values 1-12)
        "recurring_month": {"col": "recurring_month", "alias": "nh", "op": "in", "cast": "int"},
        # source: multi-select (text, values: manual, nager_date) -- no Python enum class exists.
        # Values come from the DB constraint. Leave enum off; accept any string.
        "source": {"col": "source", "alias": "nh", "op": "in", "cast": "text"},
        # status: multi-select (text, Status enum)
        "status": {"col": "status", "alias": "nh", "op": "in", "cast": "text", "enum": "Status"},
    },
}
