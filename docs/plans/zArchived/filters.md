# Filters — Kitchen Slice

**Status:** Draft. Not scheduled.
**Parent plan:** `~/learn/vianda/docs/plans/filters.md` (cross-repo).
**Scope of this slice:** Step 1 of the parent rollout — extend the filter registry, extend the builder to cover the vocabulary the frontends need, publish a machine-readable schema, and write the permanent contract doc.

This is the ephemeral rollout checklist. Durable contracts graduate to `docs/api/filters.md` at the end.

---

## 1. Existing state (verified)

- `app/config/filter_registry.py` — `FILTER_REGISTRY` dict: `entity → { param_name: (column, table_alias, cast_type) }`. Only `plans` is registered. Cast types: `"uuid" | "text" | "upper"`.
- `app/utils/filter_builder.py` — `build_filter_conditions(entity_key, filters)` emits `list[(condition, param)]` for `EnrichedService.get_enriched()` / `CRUDService`. Equality-only.
- `app/routes/route_factory.py` — consumes the builder for `/api/v1/plans/enriched` via the `paginatable` / enriched path.

The shape is right. The vocabulary is narrow.

---

## 2. Vocabulary gaps to close

Parent plan §2.2 defines the filter kinds the frontends will express. Today only `select` (equality) is supported. Extend the builder to cover:

| FilterField kind | Backend support needed |
|---|---|
| `select` | ✅ already works (`uuid` / `text` / `upper`) |
| `multi-select` | New: `IN (%s, %s, ...)` with list-valued params. Add `cast_type` semantics for lists, or a new `op` field. |
| `toggle` (boolean) | New cast type `bool` → `col = %s::bool`. |
| `range` (numeric) | Two params per field (`<key>_min`, `<key>_max`) → `col >= %s AND col <= %s`. Decide encoding convention (hyphen vs underscore vs bracketed). |
| `date-range` | Two params (`<key>_from`, `<key>_to`) → `col >= %s::date AND col <= %s::date`. Timezone policy: ISO dates interpreted in the market's timezone, not server local. |
| `search` (free-text) | `ILIKE %s` with `%…%` wrapping. Registry entry needs to declare which column(s) to search; consider trigram index for hot paths. |
| `geo` | Deferred to rollout step §3.4 (PostGIS). Flagged, not blocking on v1 of this slice. |

**Registry shape upgrade:** the 3-tuple `(column, alias, cast_type)` can't express multi-column search or range pairs. Move to a per-field dict:

```python
"restaurants": {
    "city":         {"col": "city",         "alias": "r", "op": "eq",    "cast": "text"},
    "market_id":    {"col": "market_id",    "alias": "r", "op": "eq",    "cast": "uuid"},
    "kitchen_day":  {"col": "kitchen_day",  "alias": "r", "op": "eq",    "cast": "text", "enum": "KitchenDay"},
    "cuisine":      {"col": "cuisine",      "alias": "r", "op": "in",    "cast": "text", "enum": "Cuisine"},
    "search":       {"cols": ["r.name", "r.description"], "op": "ilike"},
    "opened_from":  {"col": "opened_at",    "alias": "r", "op": "gte",   "cast": "date"},
    "opened_to":    {"col": "opened_at",    "alias": "r", "op": "lte",   "cast": "date"},
}
```

An `"enum"` key references the enum class name (from `app/dto/models.py` or wherever it lives). The schema generator uses it to emit valid values; frontends resolve display labels through the existing i18n channel (`app/i18n/enum_labels.py`), never from `filters.json`.

Migrate the `plans` entry to the new shape at the same time; keep tuple-form support **only if** any other caller depends on the old shape (check with `rg` before deleting).

---

## 3. Rollout — ordered checklist

### 3.1 Registry + builder upgrade

1. Rewrite `filter_registry.py` to per-field dict shape.
2. Extend `filter_builder.py`:
   - Dispatch on `op` (`eq` / `in` / `gte` / `lte` / `ilike` / `bool`).
   - Keep existing cast semantics (`uuid`, `text`, `upper`, plus new `bool`, `date`, `int`, `float`).
   - Safe list-param expansion for `in` (no string interpolation of values — psycopg2 list binding).
3. Migrate `plans` registry entry to the new shape. Verify `/api/v1/plans/enriched` still returns the same results.
4. pytest coverage for `build_filter_conditions` across all ops (this is `app/utils/`, so it gets unit tests per CLAUDE.md testing matrix).

### 3.2 Register new entities

Register, in this order (each can be a separate PR once 3.1 lands):

- **`restaurants`** — keys: `city`, `kitchen_day`, `market_id`, `cuisine` (multi-select), `search` (name + description). Drives vianda-app Explore list + map.
- **`viandas`** — keys: `status`, `market_id`, `restaurant_id`, `vianda_date_from`, `vianda_date_to`. Drives vianda-platform CRUD.
- **`pickups`** — keys: `status`, `market_id`, `window_from`, `window_to`. Drives vianda-platform Kiosk (static filters only; live/stream is parent plan §9.2 follow-up).

For each: wire through the relevant list endpoint (enriched or CRUD) in `route_factory.py` or the route module; confirm `X-Total-Count` still sets correctly with pagination; add a Postman collection case per entity under `docs/postman/collections/`.

### 3.3 Publish the schema

Parent plan §5.2 picked **generated `filters.json` shipped with API docs** over a runtime `/_meta` endpoint. Implementation:

1. Add a script `scripts/generate_filter_schema.py` that imports `FILTER_REGISTRY` and emits `docs/api/filters.json` (JSON-serializable, no SQL fragments — frontends get `{ entity, fields: [{ key, kind, enum_ref?, values?, ... }] }`).
2. Run it in pre-commit (or at least in CI) so the JSON can't drift from the Python registry.
3. Commit `docs/api/filters.json` — this is what vianda-hooks / frontends anchor on.

**Enum handling (locked):** when a registry entry has an `"enum"` key, the generator imports that enum class and emits `enum_ref: "<ClassName>"` + `values: [<slug>, ...]` (lowercase slugs, matching DB). **Never emit display labels into `filters.json`.** Labels are resolved by each frontend through the existing i18n channel backed by `app/i18n/enum_labels.py` — the single source of truth for enum display across every repo. Duplicating labels into `filters.json` would fork the multinational language management strategy and is forbidden.

### 3.4 Geo filter extension (restaurants)

- Add PostGIS column / index to `restaurants.location` if not already present. If it is: confirm SRID 4326 and a GIST index.
- New builder op: `geo_bbox` (params: `min_lng`, `min_lat`, `max_lng`, `max_lat` → `ST_MakeEnvelope` + `&&`) and/or `geo_radius` (params: `lat`, `lng`, `radius_m` → `ST_DWithin`).
- Register on `restaurants` entity.

**DB changes (policy override for this feature):** The user has explicitly marked current DB data as disposable for this rollout. Normal rule ("never edit an already-applied migration; never use `build_kitchen_db.sh` to apply incremental changes" — `kitchen/CLAUDE.md`) is **waived for this slice only**. Edit `app/db/schema.sql`, `app/db/index.sql`, and `app/db/trigger.sql` directly for any PostGIS column, spatial index, or `search`-supporting index (e.g. `pg_trgm` for ILIKE hot paths), then run `bash app/db/build_kitchen_db.sh` to rebuild. Do **not** write migration files for this slice. Record the rebuild as the deploy step in the rollout notes. Revert to the standard migration policy for all work outside this slice.

### 3.5 Permanent doc

Write `docs/api/filters.md` covering:

- The registry model (per-field dict shape, supported `op` values, cast semantics).
- How to add a filter to an existing entity.
- How to add a new filterable entity.
- URL param encoding conventions (range suffixes, multi-select repetition vs comma, ILIKE wildcard policy, date timezone policy).
- The `filters.json` schema contract frontends consume.
- Pagination interaction (filters apply before `X-Total-Count` is computed).
- Gotchas: how `search` interacts with enriched joins, why `in` needs list binding not string concat, timezone handling for date ranges.

Index it in `docs/api/AGENT_INDEX.md`.

---

## 4. Acceptance criteria

- [ ] All three new entities (`restaurants`, `viandas`, `pickups`) are filterable through their list endpoints with the keys listed in §3.2.
- [ ] `plans/enriched` still passes its existing Postman tests (no regression from registry shape change).
- [ ] `filters.json` exists, is generated from the registry, and matches the live behavior for at least one key per op type.
- [ ] pytest unit coverage on `build_filter_conditions` for every op.
- [ ] `docs/api/filters.md` written and indexed.
- [ ] Geo filter works on `restaurants` (at minimum `geo_bbox`).

---

## 5. Out of scope for this slice

- Live/stream filtering for Kiosk (parent plan §9.2 — separate follow-up plan).
- `useQueryFilters` hook in vianda-hooks (parent plan step 2).
- Any frontend work (parent plan steps 3–4).
- Saved filter presets, user-default filters (parent plan §7 non-goals).
- Auth-scoped filtering (e.g. restricting a Supplier's view of pickups) — that belongs in the existing `InstitutionScope` layer, not the filter registry. If conflicts surface during §3.2, note and defer to a separate plan.

---

## 6. Permanent doc produced

- `docs/api/filters.md` — see §3.5.
- `docs/api/filters.json` — generated schema, committed.
- `CLAUDE_ARCHITECTURE.MD` — add a line pointing to the filter subsystem.

## 7. Consumers to notify on completion

Per the cross-repo doc protocol in `kitchen/CLAUDE.md`:

- **vianda-hooks work** (parent plan step 2): consumes `docs/api/filters.json` and `docs/api/filters.md` to build `useQueryFilters` + `FilterSpec`.
- **vianda-platform agent**: will consume `filters.json` for CRUD table + Kiosk filters.
- **vianda-app agent**: will consume `filters.json` for Explore list + map filters.
- **infra-kitchen-gcp agent**: no action unless PostGIS extension requires a Cloud SQL flag change — flag that during §3.4 if so.
