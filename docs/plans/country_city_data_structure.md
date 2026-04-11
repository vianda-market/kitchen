# Country & City Data Structure — Raw Ingest + Metadata Layer

## Context

Several overlapping pressures want the same thing: a single, authoritative source for country and city nomenclature, with a clean place to attach Vianda-specific metadata.

1. **Marketing-site supplier bug** (see `marketing_audience_supplier.md`) — `/leads/cities` can't serve suppliers in unserved markets because `core.city_info` is a curated handful (~22 rows across 6 countries), not a reference dataset.
2. **Country names are not normalized.** Country names and codes live inline on `core.market_info` (`country_name`, `country_code`) and are duplicated as free-text elsewhere. There is no canonical country table. If someone wants "Brasil" localized to "Brazil" or to add Colombia without yet running operations there, there's no single place to set that.
3. **`core.city_info` is overloaded.** It mixes three jobs in one table:
   - Operational FK target for `user_info.city_id`
   - Curated list of cities Vianda formally supports for signup
   - Would-be reference dataset (which it isn't, but downstream code treats it like one)
4. **Free-text city on addresses.** `core.address_info.city` is `VARCHAR(50)` free-text, meaning two rows can refer to the same physical city via different strings ("São Paulo" vs "Sao Paulo" vs "SP"), and there's no link from an address to any canonical city record. We have structured data available; we should use it.
5. **Adding a new market is a manual, bespoke task.** Ops currently has to hand-seed cities for every new country. Fine at one market per quarter; brittle as we scale.

The user's request: centralize nomenclature to an external source (GeoNames), store the raw external data as-is, then attach Vianda-specific metadata in a separate layer (flags like "show in signup picker", "show in supplier form", "is served"). Retire `core.city_info` and wire `market_info` + `address_info` to the new structure via FKs so the entire system derives country/city facts from one place.

## Goals

1. **One source of truth for nomenclature.** GeoNames-authored country and city rows. Every country/city reference in the system traces back to a single row in `external.geonames_country` or `external.geonames_city`.
2. **Clean separation of raw vs. metadata.** Raw = "what the world calls this place"; metadata = "what Vianda does with this place". Raw is re-importable without touching metadata.
3. **Explicit flags instead of implicit roles.** Every dropdown / picker / filter that needs "cities for X" is a boolean flag on `city_metadata`, not a bespoke query.
4. **Wire operational tables to the new structure via FK.** `market_info.country_code` becomes a FK to the canonical country table. `address_info.city` stops being free-text and becomes a FK to `city_metadata`. `user_info.city_id` moves from `city_info` to `city_metadata`. This makes the metadata layer structurally load-bearing rather than advisory.
5. **Unblock marketing-site supplier flow** in the same work. The `/leads/cities?audience=supplier` fix rides on top of Phase 2 and does not ship as an independent `reference_city` one-off.
6. **Tear down, rebuild.** No valuable manually-entered data exists right now — seeded rows only. We can drop `city_info` outright and rebuild signup/address paths against the new FKs without a dual-write transition. This drastically simplifies the migration.

## Non-Goals

- **Not replacing `core.market_info`.** Market remains the operational row. It gains a FK to `external.geonames_country`, and pure-display fields (`country_name`) are stripped in favor of deriving from source, but operational fields (`timezone`, `phone_dial_code`, `language`, `credit_currency_id`, `kitchen_close_time`, `phone_local_digits`) are **owned by market_info** and **copied from source at market-create time**, not referenced live. Rationale in the "Copy vs Reference — Principle" section below.
- ~~**Not supporting fully localized city/country names in v1.**~~ **Superseded — localization is now in v1 scope.** See the Localization section below. Localized names are imported from GeoNames `alternateNamesV2.zip` into `external.geonames_alternate_name` at ingest time, and a `resolve_place_name(geonames_id, locale)` service helper serves them with a fallback chain.
- **Not building runtime calls to any external API.** All data is bulk-loaded and stored in our DB. A future refresh mechanism — a script that downloads the latest GeoNames dump, diffs against `external.geonames_*`, and upserts new/changed rows — is a **backlog item**, not v1 work.
- **Not geocoding existing free-text addresses.** There are no real addresses in the current seed that need geocoding, and the tear-down approach lets us start fresh. Any future import of real addresses (when we go live) will be written directly through the new FK-based path.

---

## Copy vs Reference — Principle

The raw `external.geonames_*` tables are always authoritative for nomenclature. Everywhere else in the system, the question is: **do we store a copy of a field from the source, or do we look it up via FK join at read time?** The answer depends on who owns the value.

### Rule 1 — Metadata tables reference source. No copying.

`core.country_metadata` and `core.city_metadata` are thin Vianda-flag layers on top of the raw source. They do **not** duplicate any field that exists upstream (name, population, timezone, currency, admin codes, etc.). Every query that needs a display name joins through `geonames_id → external.geonames_city.name` (or `country_iso → external.geonames_country.name`).

The only exceptions are:
- `country_iso` denormalized onto `city_metadata` for index-friendly country-scoped queries (derivable, but worth the cost).
- `display_name_override VARCHAR(200) NULL` + `display_name_i18n JSONB NULL` — set only when Vianda **explicitly disagrees** with GeoNames for a specific row (e.g. we want "México DF" instead of GeoNames' "Ciudad de México"). Null otherwise, meaning "use source as-is".

If we later want a city name in Spanish for an Argentinian user's receipt, that lookup goes through `external.geonames_alternate_name` (when we add it), **not** through a copy on `city_metadata`.

### Rule 2 — Operational tables copy at create time, own the value thereafter.

`core.market_info` drives live business logic: payout cutoffs use the market's `timezone`, billing uses `credit_currency_id`, user phone validation uses `phone_dial_code`. Having these silently change because GeoNames updated a country entry would be a nasty operational surprise.

So for operational fields, the rule is: **at market-create time, service code copies defaults from `external.geonames_country` into the new `market_info` row, and thereafter market_info owns the value**. The refresh-from-source backlog item is responsible for flagging diffs (source changed, our copy didn't) for manual review, never auto-applying.

### Rule 3 — Pure-display fields on operational tables get stripped, not copied.

`market_info.country_name` is a display field. It's not load-bearing for any business logic — the `country_code` FK is. Strip it from the schema and derive via join with `external.geonames_country.name` wherever the display name is needed. A service helper `get_market_enriched()` centralizes the join so the rest of the code doesn't have to.

### Applying the rules to `market_info`

| Column | Decision | Rationale |
|---|---|---|
| `country_name VARCHAR` | **Strip** | Pure display. Derive via join through `country_code → external.geonames_country.name`. |
| `country_code VARCHAR(2)` | **Keep, now FK-bound** | Load-bearing — every FK chain from address/user eventually traces to it. Gains FK constraint to `external.geonames_country(iso_alpha2)`. |
| `credit_currency_id UUID` | **Keep, copy-defaulted at create** | Operational billing policy. Default on create by mapping `geonames_country.currency_code` → existing row in `credit_currency_info`. Ops can override. |
| `timezone VARCHAR(50)` | **DROP** | Per "Multi-Timezone Restaurant Support" below, there is no meaningful single timezone for a country-scoped market. Timezone is resolved per-restaurant via `restaurant → address → external.geonames_city.timezone`. Market-wide analytics that want a reference tz compute it on demand from the country's capital city row. |
| `kitchen_close_time TIME` | **Keep** | Entirely Vianda-specific policy. Not in source. |
| `language VARCHAR(2)` | **Keep, copy-defaulted at create** | UI default. Default on create by taking the first 2-letter language code from `geonames_country.languages`. Ops can override. |
| `phone_dial_code VARCHAR(5)` | **Keep, copy-defaulted at create** | Used in phone validation regex. Default on create from `geonames_country.phone_prefix`. Ops can override. |
| `phone_local_digits INTEGER` | **Keep** | Vianda-specific phone validation rule. Not in source. |
| `is_archived`, `status`, audit fields | **Keep** | Standard. |

The net effect: two columns are dropped (`country_name`, `timezone`), no columns are added to `market_info`, and four columns get their defaults auto-populated from GeoNames at create time instead of being hand-typed. See "Multi-Timezone Restaurant Support" below for the full story on the `timezone` drop and where operational timezone now lives.

### Market creation UX (vianda-platform form)

To eliminate the mismatch risk on the new FK, the "Create Market" form in vianda-platform **must pick the country from `external.geonames_country`**, not accept free-text. The form calls a new `GET /admin/countries` (or reuses `/leads/markets?audience=...` if admins don't need the extra fields) that returns `[{iso_alpha2, name, suggested_timezone, suggested_currency_code, suggested_language, suggested_phone_prefix}]`, and the submit handler passes the `iso_alpha2` to `POST /markets`. Backend `create_market` then:
1. Looks up the `external.geonames_country` row by `iso_alpha2` — if missing, 422.
2. Populates `market_info.country_code` with the `iso_alpha2`.
3. Populates the operational fields from source as defaults, with any explicit overrides from the form body winning.
4. Creates the corresponding `core.country_metadata` row if not already present.

This makes the form a declarative picker instead of a source of string typos.

### Refresh mechanism implications (backlog)

When we eventually build the GeoNames diff-refresh, it has to:
1. Upsert new/changed rows in `external.geonames_*` (authoritative, no review needed).
2. **Diff against `market_info` copies.** If GeoNames changed `phone_prefix` for a country where we have a market, flag it in a review report rather than auto-updating `market_info.phone_dial_code`. Ops decides whether to promote the change.
3. Eager-create `city_metadata` rows for newly-added `external.geonames_city` rows.
4. Never auto-update metadata override columns (`display_name_override`, flags).

Captured in the Backlog section at the bottom.

---

## Multi-Timezone Restaurant Support

### Problem

`market_info.timezone VARCHAR(50) NOT NULL` is today a single value per market. Since markets are country-scoped, this breaks immediately for any country that spans multiple timezones:

- A US market with one `market_id` and two restaurants — one in New York, one in Los Angeles — would close both kitchens on the same wall-clock moment (tied to the market's chosen tz). A 13:30 EST cutoff fires at 10:30 PST, which is nowhere near lunchtime for the LA kitchen. The LA kitchen gets torn down mid-day.
- The same problem breaks billing. If an institution entity (which owns bank + tax identity and sits above restaurants) has restaurants across timezones, its monthly billing closeout can't sensibly use a single market timezone — some restaurants' local days end before, some after.

The tear-down-rebuild window is the right moment to fix this cleanly, because we're already rewiring the country/city layer to GeoNames.

### What's already correct in the current code

Exploration revealed the current architecture is closer to right than I expected:

- **`core.address_info.timezone VARCHAR(50) NOT NULL` already exists** (`app/db/schema.sql:524`). Addresses already carry their own timezone.
- **`ops.institution_entity_info.address_id UUID NOT NULL FK` already exists** (`app/db/schema.sql:1183`). The entity that owns billing already has its own home address — no schema addition needed to give billing a proper timezone.
- **Runtime consumers already read `address_info.timezone`**, not `market_info.timezone`: `app/services/plate_pickup_service.py`, `app/services/cron/kitchen_start_promotion.py`, and `app/services/cron/billing_events.py` all reach through to address-level timezone.
- `market_info.timezone` is consumed in only **4 files**: `app/routes/admin/markets.py`, `app/config/market_config.py`, `app/services/plate_selection_service.py`, `app/services/timezone_service.py`.

### What's broken

**`app/services/timezone_service.py` is the ugly part.** It contains a hardcoded Python dictionary `PROVINCE_TIMEZONE_MAPPING` mapping province/state codes to IANA timezones for US / BR / CA / MX — roughly 200 lines of `"California": "America/Los_Angeles", "CA": "America/Los_Angeles", ...`. This dict is the source of truth for timezone resolution when an address is created in a multi-timezone country. Today's flow:

```
create_address(country_code, province, ...) →
    TimezoneService.deduce_timezone(country_code, province) →
        if country not in PROVINCE_TIMEZONE_MAPPING → market_info.timezone
        else → PROVINCE_TIMEZONE_MAPPING[country][province]
    → stored in address_info.timezone
```

This is exactly the kind of Vianda-maintained nomenclature that should come from GeoNames instead.

### New architecture

**Source of truth: `external.geonames_city.timezone`.** Every GeoNames city row carries its own IANA timezone. When an address is created, the user (or admin form) picks a `city_metadata_id` from the structured dropdown — so we already know the exact city, and can look up the exact timezone in one query. No province-to-timezone guessing. No single-timezone-per-country fallback.

**Runtime flow after this change:**

```
create_address(country_code, city_metadata_id, street, ...) →
    SELECT gc.timezone
    FROM core.city_metadata cm
    JOIN external.geonames_city gc ON gc.geonames_id = cm.geonames_id
    WHERE cm.city_metadata_id = %(city_metadata_id)s
    → stored in address_info.timezone (copy-on-write, per the Copy principle)
```

Everything downstream — kitchen close, billing cutoff, pickup windows, analytics — reads `address_info.timezone` for the relevant address (restaurant address for restaurant ops, institution entity address for billing ops, user address for user-facing "today").

### Schema changes

In the tear-down-rebuild schema:

- **`core.market_info.timezone` — DROP.** No longer load-bearing. Analytics that need a per-market reference timezone should anchor on an **institution entity** (`institution_entity_info.address_id → address.timezone`) — e.g. roll up the market's suppliers grouped by their own local day — or use UTC for tz-neutral reports. There is deliberately **no** "country capital tz" shortcut; anchoring on a real supplier's address is more meaningful and avoids inventing fictional market-wide wall clocks.
- **`core.market_info.kitchen_close_time` and `core.market_info.kitchen_open_time` — KEEP as market-level *onboarding templates*, not runtime policy.** Both are Postgres `TIME` values, which are deliberately **naive wall-clock times with no timezone attached**. "13:30" means "1:30 in whatever local timezone applies when the value is interpreted." At the market level the value is interpreted nowhere — it's just a placeholder that gets copied into new restaurant rows. "Every Argentinian kitchen defaults to 09:00 open and 13:30 close" is the intent, where "09:00" means "09:00 local for whichever specific city the restaurant lives in."
- **`ops.restaurant_info.kitchen_open_time TIME NOT NULL` and `ops.restaurant_info.kitchen_close_time TIME NOT NULL` — NEW.** Both are copied from the market row at restaurant-create time (same naive `TIME` values). `restaurant_info` owns the values thereafter. Matches the Copy-vs-Reference principle exactly: operational policy is copied once from a template, then owned. No runtime fallback lookup through the market row, no `COALESCE` chain, no per-restaurant-override flag. Changing the market template does **not** affect existing restaurants; it only affects the defaults applied to future restaurant creation. Supports earlier-plate restaurants (open at 07:00) without any special casing.

**Concretely, the "abstract wall clock" resolution flow:**

1. Superadmin sets market `AR` with `kitchen_open_time = 09:00` and `kitchen_close_time = 13:30`. These are naive — no timezone, just wall-clock times of day.
2. A supplier in Argentina registers a restaurant in Buenos Aires. The restaurant-create form **pre-fills** `kitchen_open_time = 09:00` and `kitchen_close_time = 13:30` from the market template. The supplier can edit before submitting.
3. On submit, `restaurant_info.kitchen_open_time = 09:00` and `kitchen_close_time = 13:30` are stored — also naive, no timezone.
4. The restaurant has an `address_id` pointing at an `address_info` row whose `timezone = America/Argentina/Buenos_Aires` (copied at address-create time from `external.geonames_city.timezone` via `city_metadata_id`).
5. At runtime: `is_kitchen_open(restaurant_id)` computes `now()` in the restaurant's address timezone, extracts the time-of-day, and compares it against the naive `restaurant.kitchen_open_time`/`kitchen_close_time`. Tuesday at 11:30 America/New_York and Tuesday at 11:30 America/Los_Angeles are **different UTC moments** but **the same wall-clock time**, so both NY and LA restaurants with `kitchen_open_time=09:00` and `kitchen_close_time=13:30` fire their open/close events at their own 09:00 and 13:30 local.
6. Same pattern for institution_entity billing closeouts: `institution_entity_info.address_id → address.timezone` provides the tz, and any naive time-of-day policy is interpreted in that tz.

So "the market timezone" never exists as a thing — the market template is a pair of **timezone-free wall-clock times** that inherit timezone from whichever downstream row interprets them. This is exactly the abstraction you described, and Postgres `TIME` (not `TIMETZ`, not `TIMESTAMP`) is the right type for it.
- **`core.address_info.timezone VARCHAR(50) NOT NULL` — KEEP.** Already exists. Populated at write time by the new `city_metadata → geonames_city.timezone` lookup, not by the province mapping.

### Service changes

- **`app/services/timezone_service.py` — DELETE** (or reduce to a one-function stub that calls the new resolver). The entire `PROVINCE_TIMEZONE_MAPPING` dict goes away. `TimezoneService.deduce_timezone(country_code, province, db)` is replaced by `resolve_address_timezone(city_metadata_id, db)` living in `app/services/address_service.py`.
- **`app/services/address_service.create_address`** — no longer takes `province` for timezone purposes. Looks up `city_metadata_id → geonames_city.timezone` and stores it in `address_info.timezone`. Province is still stored on the address (it's a real address field) but is no longer load-bearing for timezone.
- **`app/services/kitchen_day_service._get_kitchen_close_time`** — current signature is `(country_code, day_name)`. New signature: `(restaurant_id, day_name)` or `(market_id, restaurant_override_time, day_name)`, implementing the `COALESCE(override, market)` fallback. The three-tier fallback (DB → `MarketConfiguration` → hardcoded `time(13, 30)`) stays for safety but the top tier becomes restaurant-scoped.
- **`app/services/kitchen_day_service.get_effective_current_day`** — currently takes `(timezone_str, country_code)`. New signature: `(address_id, db)` or `(restaurant_id, db)`, resolving the tz + close time internally. Callers pass the restaurant/address they're computing for, not a raw tz string — removes a class of "passed the wrong timezone" bugs.
- **`app/services/cron/kitchen_start_promotion.py`** — already iterates per-restaurant with address tz per the current grep. Verify during implementation that no residual `market.timezone` reads remain; delete them if found.
- **`app/services/cron/billing_events.py`** — already uses address tz per the current grep. Verify that the address it uses is the **institution_entity's** address (for billing period boundaries), not a restaurant address or a market-level default. If not, fix.
- **`app/services/plate_selection_service.py`** — flagged as a current `market.timezone` reader. Needs audit during implementation: figure out what it's using timezone for, and route it through either the restaurant's address tz (if it's doing restaurant-scoped work) or the capital-city lookup helper (if it's doing market-wide analytics).
- **`app/routes/admin/markets.py`** — admin Create/Edit Market form loses the `timezone` field. Replaced by the GeoNames country picker which already makes tz-per-market moot.
- **`app/config/market_config.py`** — currently holds per-country configuration including kitchen_close hints. Audit for any timezone constants and remove; any useful per-market defaults migrate to the DB column.

### Billing closeout, explicitly

Three-layer rule:

| Operation | Whose timezone? | Via which FK chain |
|---|---|---|
| Kitchen-day open / close | Restaurant's own | `restaurant_info.address_id → address_info.timezone` |
| Plate pickup windows, order cutoffs | Restaurant's own | same |
| Per-restaurant daily balance closeout | Restaurant's own | same |
| Monthly billing period boundary (institution-entity-scoped) | Institution entity's home address | `institution_entity_info.address_id → address_info.timezone` |
| Institution-level payout aggregation | Institution entity's home address | same |
| Market-wide analytics rollups | UTC (tz-neutral) or anchored on a specific institution entity | `institution_entity_info.address_id → address.timezone` for entity-scoped rollups; UTC otherwise. **No** country-capital anchor. |
| User-facing "today" in the app | User's primary address | `user_info.city_metadata_id → geonames_city.timezone`, or via the user's selected delivery address |

A transaction's `event_time_utc` is stored canonically in UTC. Which billing period it falls into is determined by converting to the institution entity's tz and checking whether it's on or before/after the period boundary in that tz. Restaurants in timezones that trail the entity's tz (e.g. LA restaurants under an entity in New York) will have transactions near month-end that "cross" the boundary in one direction or the other — that's normal and correct; the period-assignment rule is based on the entity tz.

### Edge cases

- **DST:** pytz/zoneinfo handle DST transitions automatically. Already handled.
- **A restaurant moves to a new address in a different timezone:** updating `restaurant_info.address_id` (or the linked address's `city_metadata_id`) recomputes `address_info.timezone`. In-flight kitchen days at the moment of the move are a rare operational edge case — document as "don't move restaurants mid-day."
- **Cross-midnight kitchen close** (e.g. `kitchen_close_time = 02:00`): the resolver interprets the time in the restaurant's local tz. Same logic as today, nothing timezone-specific breaks.
- **Institution entity with a home address in a country with no active market:** billing still works — `address_info.timezone` is independent of any `market_info` row. The address's country_iso FKs `external.geonames_country` directly.
- **GeoNames timezone data for a city is wrong or stale:** rare in practice. Fallback is to set `address_info.timezone` manually via a service operation. Long-term, the refresh mechanism's diff report flags any changes in `geonames_city.timezone` for review.

### Decisions locked in for this section

1. **Kitchen hours on restaurant_info** — both `kitchen_open_time` and `kitchen_close_time` live on `restaurant_info` as NOT NULL columns, copied from the market template at restaurant-create time. No `_override` suffix, no runtime fallback through market. Market columns become pure onboarding templates. Earlier-opening plates supported out of the box (any restaurant can have `kitchen_open_time = 07:00`).
2. **`get_effective_current_day` signature** — changes to `(restaurant_id, db)` (or the lower-level `(address_id, db)`). Resolution happens inside the service, callers can't pass the wrong timezone.
3. **`plate_selection_service` market.timezone usage** — TBD until a code read during implementation. Once we see what it's actually computing, route it through either the restaurant's address tz or UTC.
4. **`timezone_service.py`** — **deleted entirely** during the rebuild. `PROVINCE_TIMEZONE_MAPPING` gone. Failing call sites surface during E2E testing and get migrated to the new resolver.
5. **`app/config/market_config.py` `MarketConfiguration.kitchen_day_config`** — deleted. Any service that was relying on it gets migrated to the new `restaurant_info.kitchen_open_time`/`kitchen_close_time` columns.

---

## Localization

Localized country and city names are **in v1 scope**. Two use cases must be served simultaneously by every place-name response:

1. **Display name** — shown to human users, varies by locale. "Brazil" for `en`, "Brasil" for `pt`, "Brasil" for `es`.
2. **Canonical name** — sent to Mapbox, Google Maps, Google Ads, Meta Ads, and any external system that has its own place gazetteer. Matches GeoNames `name` / `ascii_name`. Stable across locales.

Both values ride together in API responses so a frontend can render one and forward the other.

### Source

GeoNames' `alternateNamesV2.zip` — a TSV of ~13 M rows globally, each mapping a `geonameid` to one alternate name in one language. Columns: `alternateNameId, geonameid, isolanguage, alternate_name, isPreferredName, isShortName, isColloquial, isHistoric, from, to`.

Filtered to our cities/countries and to locales `{en, es, pt}` at ingest time, the committed TSV drops to roughly 1–3 MB / ~200–400k rows. Re-run the filter when we add a new locale.

### Resolver

One service helper `resolve_place_name(geonames_id, locale, db) -> { display_name, canonical_name }` is the single entry point. Fallback chain:

1. **Metadata override** — if `city_metadata.display_name_override` or `display_name_i18n->>'locale'` is set for this row, use it. Per the Copy-vs-Reference principle, this column is only populated for explicit disagreements with source (rare).
2. **Alternate name in requested locale** — `SELECT alternate_name FROM external.geonames_alternate_name WHERE geonames_id = ? AND iso_language = ? AND is_preferred = TRUE AND is_historic = FALSE LIMIT 1`. If no preferred row, any non-historic row in that locale.
3. **Canonical name** — `external.geonames_city.name` / `external.geonames_country.name`.

Canonical name is always: `external.geonames_city.name` (or `.ascii_name` if the caller explicitly asks for ASCII-only — Mapbox sometimes prefers ASCII for query stability).

The resolver is the only piece of code that needs to know about the fallback chain. Everything else calls it.

### API response shape changes

Endpoints that return place names gain a `display_name` + `canonical_name` split when the caller sends `Accept-Language`:

```
GET /leads/cities?country_code=AR&audience=supplier
Accept-Language: en

{
  "cities": [
    { "city_metadata_id": "uuid-1", "display_name": "Buenos Aires", "canonical_name": "Buenos Aires" },
    { "city_metadata_id": "uuid-2", "display_name": "Córdoba",      "canonical_name": "Córdoba" },
    ...
  ]
}
```

Frontend renders `display_name` and forwards `canonical_name` to Mapbox / ad platforms / geocoding. Mono-language callers ignore the second field.

### Caching

The `(geonames_id, locale) → {display, canonical}` resolution is deterministic and rarely changes, so the resolver caches results in-process with a 1-hour TTL. Cache invalidation on refresh (backlog) is a post-write hook on `external.geonames_*`.

### Edge cases

- **Locale has no alternate name for this place** (e.g. `pt` for a small US town): fallback to canonical name. User sees the English spelling; acceptable degradation.
- **Ambiguous locale** (e.g. `pt-BR` vs `pt-PT` — GeoNames uses language, not country subtag): for v1, map regional codes to their base language (`pt-BR` → `pt`). Good enough for display purposes.
- **User sets UI locale to `en` but wants to see Spanish names for a Mexico trip**: not a case we support in v1. One locale per request.
- **Refresh delivers a newer preferred-name flag**: refresh runs through the normal `external.*` upsert, resolver cache TTL expires, UI reflects the change within the hour. Metadata overrides are untouched.

### Files (localization-specific)

- `app/db/schema.sql` — add `external.geonames_alternate_name` table + indexes (already listed in main schema section)
- `app/db/seed/external/geonames_alternate_names.tsv` — committed, pre-filtered (~1–3 MB)
- `app/scripts/import_geonames.py` — adds the alternate-names filter step before the `COPY`
- `app/services/place_name_resolver.py` — new, single `resolve_place_name()` entry point, in-process cache
- Any route/service returning place names — calls the resolver instead of joining `geonames_city.name` directly

---

## Design Overview — Two Layers

### Layer 1: `external` schema — raw ingest, read-only from application code

A new Postgres schema `external` holds verbatim mirrors of external reference datasets. One table per source file, columns matching the source as closely as Postgres types allow. Never written to by the application — populated only by ingest scripts/migrations.

v1 tables (all ingested in this plan):
- `external.geonames_country` — mirror of GeoNames `countryInfo.txt`
- `external.geonames_admin1` — mirror of GeoNames `admin1CodesASCII.txt` (~200 KB, a few thousand rows). Maps admin1 codes (state/province identifiers) to their display names, so the superadmin city picker can show "Springfield (Illinois)" vs "Springfield (Massachusetts)" instead of three identical "Springfield" entries.
- `external.geonames_city` — mirror of GeoNames `cities5000.txt` (~53k rows, ~5 MB). Each city row carries its `admin1_code` referencing the admin1 table.
- `external.geonames_alternate_name` — mirror of GeoNames `alternateNamesV2.txt`, **filtered** to the geonames_ids present in our country + admin1 + city tables and to the locales we care about (`en, es, pt` initially). Powers the localization resolver for all three entity types.
- `external.iso4217_currency` — raw ISO 4217 currency list (code, name, numeric code, minor-unit precision). Small static file (~180 rows, ~10 KB). Replaces the hand-typed `currency_name` / `currency_code` fields currently on `core.credit_currency_info`. Vianda-owned pricing policy (credit values, USD conversion) moves to a new `core.currency_metadata` layer on top — see "Currency rewire" under Implementation Ordering.

**Other external sources should live here too, eventually.** The kitchen codebase currently has a few reference datasets populated from external or semi-external sources (`core.credit_currency_info` for ISO 4217 currencies, `ops.cuisine` for the curated cuisines list, possibly others). Per the single-home principle, they all belong in the `external` schema with a thin `core.*_metadata` layer on top for any Vianda-owned flags. In v1 we only actually migrate the GeoNames ingests into `external.*`; refactoring currency and cuisine into the same two-tier model is a follow-up captured in the Backlog section. The important point is that the `external` schema is the **one** grep-obvious home for raw external reference data going forward — no more currency-seeded-in-reference_data, cuisines-seeded-in-reference_data, and then GeoNames-over-here.

Why a dedicated schema: so it's grep-obvious which tables are "raw external, do not write here" vs. which are "application state, writable". Similar to how `audit.*` is used for history tables in this codebase.

Why raw-as-is: if we want to re-import with a newer snapshot or cross-check a row against GeoNames debug tools, the data matches 1:1. Any transformation happens in the metadata layer.

### Layer 2: `core` metadata tables — writable, application-specific, **superadmin-promoted**

- `core.country_metadata` — one row per country Vianda has explicitly promoted for **any** downstream use (interest forms, signup, supplier audience, customer audience). Has FK to `external.geonames_country`, audience flags, and a `status` field that distinguishes `pending` (flagged for inclusion in an interest form but no suppliers registered yet) from `active` (at least one supplier has registered in this country).
- `core.city_metadata` — one row per city that a superadmin has **explicitly promoted**. Not 1:1 with `external.geonames_city`. If a row doesn't exist for a given city, that city is not available in any dropdown, not a valid destination for an address, and not in any audience. Promotion happens via the vianda-platform admin UI.

**Superadmin-driven promotion flow** (vianda-platform):

The promotion UI is a **cascading filtered picker** on vianda-platform's market management screen. The gate for "what shows up anywhere in Vianda" is: it must exist in `core.country_metadata` or `core.city_metadata`. The superadmin form is the only way to create rows in those tables.

1. **Country picker.** Superadmin opens "Add Market" in vianda-platform. The form calls `GET /admin/external/countries` which returns the full list from `external.geonames_country` (with localized name via the place-name resolver). Superadmin picks `CO`.
2. **Country metadata row created.** vianda-platform calls the backend, which upserts `country_metadata(country_iso='CO', is_supplier_audience=TRUE, status='pending')`. Also optionally creates a `market_info` row if ops is ready to operate there; if not, `country_metadata.market_id` stays `NULL` until later.
3. **Province filter (optional).** Form now shows a province dropdown populated by `GET /admin/external/provinces?country_iso=CO` → `SELECT * FROM external.geonames_admin1 WHERE country_iso = 'CO'`. Superadmin can either leave it blank (show all cities in the country) or pick one province to narrow the city list. Useful for the US, BR, MX, AR where a single country has thousands of cities.
4. **City picker.** Form shows a filtered city list via `GET /admin/external/cities?country_iso=CO&admin1_code=CUN&q=type-ahead` → uses the `(country_iso, admin1_code)` + trigram indexes on `external.geonames_city`. Each option shows `"{city.name}, {admin1.name}"` — "Cartagena, Bolívar" not just "Cartagena" — so the superadmin can disambiguate same-named cities across provinces (the classic "Springfield, IL" vs "Springfield, MA" case). Sorted by population descending within the filtered set.
5. **City metadata rows created.** For each picked city, backend upserts `city_metadata(geonames_id, country_iso='CO', show_in_supplier_form=TRUE, status='pending')`.
6. **Downstream exposure.** The supplier interest form (`/leads/cities?country_code=CO&audience=supplier`) now returns exactly those promoted cities. Any user-facing dropdown that asks "which cities in Colombia?" reads from `city_metadata` filtered by the relevant flag — never from the raw `external.geonames_city` table. The raw table is only consulted by the superadmin picker above and by the refresh script.
7. **Auto-flip on real supplier activity.** When a real supplier registers in `CO` (first `restaurant_lead` accepted → institution_entity + restaurant created), a service hook **auto-flips** `country_metadata.status` from `pending` to `active`. When the first restaurant is created in a specific promoted city, that `city_metadata.status` flips from `pending` to `active` too. The flip happens via explicit service code (`country_metadata_service.promote_to_active(country_iso)` called from the registration path), not a DB trigger — easier to reason about and unit-test.

**Province data stays on the raw side.** The plan does *not* add a FK from `city_metadata` to `geonames_admin1`. Reason: the city's `admin1_code` is already authoritative on the raw row, and the cascading picker uses it to filter. Promoting a city doesn't need a metadata copy of its province. If anything downstream needs "what province is this city in?" it joins through `city_metadata.geonames_id → geonames_city.admin1_code → geonames_admin1.name` — one extra join, cached by the place-name resolver.

**Optional follow-up for `core.address_info.province`:** currently `VARCHAR(50) NOT NULL` free-text. With admin1 data ingested, this column is technically redundant — it's derivable via `address.city_metadata_id → geonames_city.admin1_code → geonames_admin1.name`. Not proposing to drop it in this plan because postal-format addresses typically want the province printed on a line (receipts, shipping labels), and having it on the row avoids a join on every address read. Revisit after the cutover if/when the copy-vs-reference tradeoff tips.

**What "not in metadata" means:**

| Presence | Supplier interest form? | User signup? | Address create? |
|---|---|---|---|
| Country row missing | Country not listed | Can't pick | Can't use |
| Country present, no cities promoted | Country listed, empty cities dropdown (rare — should promote at least one before exposing) | Can't pick | Can't use |
| Country present, cities promoted, status='pending' | Visible, labeled as "coming soon" or similar | Usually no (unless flag allows) | Only if address is for a supplier lead conversion |
| Country present, cities promoted, status='active' | Visible, live | Yes | Yes |

**Why superadmin-driven, not eager 1:1 ingest:**

Previous draft proposed eager creation — one `city_metadata` row per `external.geonames_city` row (~53k rows), all flags `FALSE` by default. That bloats the metadata table with rows nobody cares about, makes audit history triggers fire on ingest, makes "what's in the dropdown?" a flag-scanning query rather than a table-membership query, and loses the clean "metadata = intentional Vianda decisions" mental model. On-demand promotion aligns with the user's stated goal: "the superadmin will be in control of exposing countries and cities into each metadata table".

**Writable via services + CRUD patterns.** Has `modified_by` + history table per CLAUDE.md conventions. **History triggers fire only on updates to existing metadata rows**, never on raw `external.*` ingest (which is append/upsert-only and doesn't need audit history — the raw tables are reproducible from source).

Why a separate schema from `external.*`: the raw tables get wiped and re-imported. Metadata is ours and must not be destroyed by a re-import. The FK on `geonames_id` (for cities) or `iso_alpha2` (for countries) gives us the join back.

### Layer 3: operational tables — `market_info`, `address_info`, `user_info`

Existing tables get new FKs into the metadata/raw layers. See "Copy vs Reference — Principle" above for the per-column decision matrix.

- **`market_info.country_code`** — already `VARCHAR(2)`, gains FK constraint `REFERENCES external.geonames_country(iso_alpha2)`. The vianda-platform "Create Market" form picks from this list at submit time, so there is no way to get a mismatch.
- **`market_info.country_name`** — **dropped**. Pure display, derived via join with `external.geonames_country.name` through the new FK. A service helper `get_market_enriched()` centralizes the join.
- **`market_info` operational defaults** — `language`, `phone_dial_code`, `credit_currency_id` are **copied at create time** from `external.geonames_country`. Ops can override via the form. After create, `market_info` owns these values; the future GeoNames refresh mechanism flags diffs for manual review rather than auto-applying.
- **`market_info.timezone`** — **dropped entirely.** Operational timezone is resolved per-restaurant via the restaurant's address (for kitchen-day ops) or per-institution-entity via the entity's address (for billing closeout). See the "Multi-Timezone Restaurant Support" section above for the full architecture.
- **`core.market_info.kitchen_open_time TIME NOT NULL`** — new column alongside the existing `kitchen_close_time`. Both market-level columns become **onboarding templates** that get copied into new restaurants at restaurant-create time.
- **`ops.restaurant_info.kitchen_open_time TIME NOT NULL`** and **`ops.restaurant_info.kitchen_close_time TIME NOT NULL`** — new columns. Copied from the market template at restaurant-create time, owned by `restaurant_info` thereafter. No runtime fallback through market row.
- **`address_info.city`** — currently `VARCHAR(50)` free-text. **Replaced** by `address_info.city_metadata_id UUID NOT NULL REFERENCES core.city_metadata(city_metadata_id)`. No more string matching. The display name for an address is resolved via `city_metadata → external.geonames_city.name` (with `display_name_override` taking precedence if set).
- **`address_info.country_code`** — gains FK constraint `REFERENCES external.geonames_country(iso_alpha2)`. Redundant-but-fast: already derivable from `city_metadata_id`, but denormalized so country-scoped queries don't need a 3-table join. Service layer must keep the two consistent (enforced by a CHECK or by trusting the writer path — see open decisions).
- **`user_info.city_id`** — renamed to `user_info.city_metadata_id UUID NOT NULL REFERENCES core.city_metadata(city_metadata_id)`. Previous FK to `city_info` is gone.
- **`customer.pending_customer_signup.city_id`** — same rename + repoint.

---

## Schemas

### `external.geonames_country`

Direct mirror of [`countryInfo.txt`](https://download.geonames.org/export/dump/countryInfo.txt). Tab-separated with comment-prefixed header.

```sql
CREATE SCHEMA IF NOT EXISTS external;

CREATE TABLE IF NOT EXISTS external.geonames_country (
    iso_alpha2        VARCHAR(2)  PRIMARY KEY,          -- 'US'
    iso_alpha3        VARCHAR(3)  NOT NULL,             -- 'USA'
    iso_numeric       INTEGER     NOT NULL,             -- 840
    fips              VARCHAR(2),                       -- 'US'
    name              VARCHAR(200) NOT NULL,            -- 'United States'
    capital           VARCHAR(200),
    area_sq_km        NUMERIC,
    population        BIGINT,
    continent         VARCHAR(2),                       -- 'NA'
    tld               VARCHAR(10),                      -- '.us'
    currency_code     VARCHAR(3),                       -- 'USD'
    currency_name     VARCHAR(100),
    phone_prefix      VARCHAR(20),                      -- '1'
    postal_format     VARCHAR(200),
    postal_regex      TEXT,
    languages         TEXT,                             -- 'en-US,es-US,haw,fr'
    geonames_id       INTEGER,
    neighbours        TEXT,                             -- 'CA,MX'
    equivalent_fips   VARCHAR(5),
    imported_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### `external.geonames_admin1`

Direct mirror of [`admin1CodesASCII.txt`](https://download.geonames.org/export/dump/admin1CodesASCII.txt). Tiny file (~200 KB), one row per state/province/region globally.

```sql
CREATE TABLE IF NOT EXISTS external.geonames_admin1 (
    admin1_full_code  VARCHAR(20) PRIMARY KEY,           -- 'US.CA', 'BR.SP', 'AR.07' — country_iso + '.' + admin1_code
    country_iso       VARCHAR(2)  NOT NULL
                      REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT,
    admin1_code       VARCHAR(20) NOT NULL,              -- 'CA', 'SP', '07' — the part after the dot
    name              VARCHAR(200) NOT NULL,             -- 'California', 'São Paulo', 'Ciudad Autónoma de Buenos Aires'
    ascii_name        VARCHAR(200) NOT NULL,             -- 'California', 'Sao Paulo', 'Ciudad Autonoma de Buenos Aires'
    geonames_id       INTEGER,                           -- GeoNames' own ID for the admin1 entity (used by alternate_name lookups)
    imported_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_geonames_admin1_country
    ON external.geonames_admin1 (country_iso);
CREATE INDEX IF NOT EXISTS idx_geonames_admin1_country_code
    ON external.geonames_admin1 (country_iso, admin1_code);
```

**Joining from a city to its admin1:** `external.geonames_city` rows store the `admin1_code` (the part after the dot). Join via `(city.country_iso, city.admin1_code) → (admin1.country_iso, admin1.admin1_code)`. The composite natural key is cheap to index and avoids computing `country_iso || '.' || admin1_code` on every join.

### `external.geonames_city`

Direct mirror of [`cities5000.txt`](https://download.geonames.org/export/dump/cities5000.zip). Header columns per [readme.txt](https://download.geonames.org/export/dump/readme.txt).

```sql
CREATE TABLE IF NOT EXISTS external.geonames_city (
    geonames_id       INTEGER     PRIMARY KEY,
    name              VARCHAR(200) NOT NULL,            -- 'São Paulo'
    ascii_name        VARCHAR(200) NOT NULL,            -- 'Sao Paulo'
    alternate_names   TEXT,                             -- comma-separated shortlist
    latitude          NUMERIC(10, 7),
    longitude         NUMERIC(11, 7),
    feature_class     CHAR(1),                          -- 'P' for populated places
    feature_code      VARCHAR(10),                      -- 'PPL', 'PPLC' (capital), 'PPLA' (admin center)
    country_iso       VARCHAR(2) NOT NULL REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT,
    cc2               TEXT,                             -- alternate country codes for disputed territory
    admin1_code       VARCHAR(20),                      -- state/province code (FIPS or ISO)
    admin2_code       VARCHAR(80),                      -- county
    admin3_code       VARCHAR(20),
    admin4_code       VARCHAR(20),
    population        BIGINT,
    elevation         INTEGER,
    dem               INTEGER,                          -- digital elevation model
    timezone          VARCHAR(50),                      -- 'America/Sao_Paulo'
    modification_date DATE,                             -- GeoNames' own last-modified date
    imported_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_geonames_city_country_pop
    ON external.geonames_city (country_iso, population DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_geonames_city_country_ascii
    ON external.geonames_city (country_iso, LOWER(ascii_name));
CREATE INDEX IF NOT EXISTS idx_geonames_city_ascii_trgm
    ON external.geonames_city USING GIN (ascii_name gin_trgm_ops);  -- superadmin type-ahead picker
```

### `external.geonames_alternate_name`

Direct mirror of [`alternateNamesV2.txt`](https://download.geonames.org/export/dump/alternateNamesV2.zip), filtered at ingest time to the `geonames_id`s we actually use and the locales we care about.

```sql
CREATE TABLE IF NOT EXISTS external.geonames_alternate_name (
    alternate_name_id  INTEGER     PRIMARY KEY,       -- GeoNames' own alternateNameId
    geonames_id        INTEGER     NOT NULL,          -- refers to either geonames_country.geonames_id or geonames_city.geonames_id
    iso_language       VARCHAR(7)  NOT NULL,          -- ISO 639-1 2-letter, or 3-letter, or 'post' / 'link' / 'iata' etc.
    alternate_name     VARCHAR(400) NOT NULL,         -- 'Brasil', 'Ciudad de México', 'São Paulo'
    is_preferred       BOOLEAN     NOT NULL DEFAULT FALSE,   -- GeoNames-flagged preferred name for this lang
    is_short           BOOLEAN     NOT NULL DEFAULT FALSE,
    is_colloquial      BOOLEAN     NOT NULL DEFAULT FALSE,
    is_historic        BOOLEAN     NOT NULL DEFAULT FALSE,
    imported_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_geonames_alt_name_geonames_lang
    ON external.geonames_alternate_name (geonames_id, iso_language)
    WHERE is_historic = FALSE AND is_colloquial = FALSE;
```

**Ingest filter:** we only load rows where `iso_language IN ('en', 'es', 'pt')` (or whatever locales we support at the time) AND `geonames_id` is in the set we imported into `geonames_country` or `geonames_city`. This cuts the raw file from ~500 MB / ~13 M rows to ~1–3 MB / ~200–400k rows. The filter runs in the import script, not in the COPY step, so the committed TSV is already trimmed.

**Polymorphic geonames_id:** the column refers to either a country row or a city row. We don't add a FK constraint because GeoNames itself uses one `geonamesId` namespace for both. The resolver service looks up cities by city geonames_id and countries by country geonames_id — distinct call paths, no ambiguity in practice.

### `core.country_metadata`

```sql
CREATE TABLE IF NOT EXISTS core.country_metadata (
    country_metadata_id   UUID PRIMARY KEY DEFAULT uuidv7(),
    country_iso           VARCHAR(2) NOT NULL UNIQUE
                          REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT,
    market_id             UUID NULL
                          REFERENCES core.market_info(market_id) ON DELETE SET NULL,  -- NULL = country we expose but don't operate in
    display_name_i18n     JSONB NULL,                                                 -- { "en": "United States", "es": "Estados Unidos" }
    is_customer_audience  BOOLEAN NOT NULL DEFAULT FALSE,                             -- appears in /leads/markets default
    is_supplier_audience  BOOLEAN NOT NULL DEFAULT FALSE,                             -- appears in /leads/markets?audience=supplier
    is_employer_audience  BOOLEAN NOT NULL DEFAULT FALSE,                             -- reserved for employer flow
    is_archived           BOOLEAN NOT NULL DEFAULT FALSE,
    status                status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by            UUID NULL,
    modified_by           UUID NOT NULL REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    modified_date         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_country_metadata_market ON core.country_metadata(market_id) WHERE market_id IS NOT NULL;
```

History table `audit.country_metadata_history` per CLAUDE.md conventions.

### `core.city_metadata`

```sql
CREATE TABLE IF NOT EXISTS core.city_metadata (
    city_metadata_id      UUID PRIMARY KEY DEFAULT uuidv7(),
    geonames_id           INTEGER NOT NULL UNIQUE
                          REFERENCES external.geonames_city(geonames_id) ON DELETE RESTRICT,
    country_iso           VARCHAR(2) NOT NULL
                          REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT,
    display_name_override VARCHAR(200) NULL,            -- NULL = use raw geonames_city.name
    display_name_i18n     JSONB NULL,
    -- Flags: "should this city appear in {view}?"
    show_in_signup_picker BOOLEAN NOT NULL DEFAULT FALSE,  -- replaces city_info's canonical role
    show_in_supplier_form BOOLEAN NOT NULL DEFAULT FALSE,
    show_in_customer_form BOOLEAN NOT NULL DEFAULT FALSE,
    is_served             BOOLEAN NOT NULL DEFAULT FALSE,  -- derived: ≥1 active restaurant w/ plates + QR
    is_archived           BOOLEAN NOT NULL DEFAULT FALSE,
    status                status_enum NOT NULL DEFAULT 'active'::status_enum,
    created_date          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by            UUID NULL,
    modified_by           UUID NOT NULL REFERENCES core.user_info(user_id) ON DELETE RESTRICT,
    modified_date         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_city_metadata_country
    ON core.city_metadata (country_iso) WHERE is_archived = FALSE;
CREATE INDEX IF NOT EXISTS idx_city_metadata_country_supplier
    ON core.city_metadata (country_iso) WHERE show_in_supplier_form = TRUE AND is_archived = FALSE;
CREATE INDEX IF NOT EXISTS idx_city_metadata_country_signup
    ON core.city_metadata (country_iso) WHERE show_in_signup_picker = TRUE AND is_archived = FALSE;
```

History table `audit.city_metadata_history`.

**Eager creation at ingest time:** every `external.geonames_city` row gets exactly one `core.city_metadata` row at ingest (all flags `FALSE` by default). This keeps the 1:1 invariant so that any address can FK into `city_metadata` without needing a "lazy create" service wrapper. Post-ingest, flags are toggled via seed or admin action to promote cities into dropdowns.

**Denormalized `country_iso`:** technically derivable via `geonames_id → geonames_city.country_iso` but denormalized onto `city_metadata` so the overwhelmingly common "give me all metadata-flagged cities in country X" query is a single-table scan + index seek, not a join.

### Operational table changes

```sql
-- market_info: gain FK to canonical country, drop display-only country_name, drop now-meaningless timezone
ALTER TABLE core.market_info DROP COLUMN country_name;
ALTER TABLE core.market_info DROP COLUMN timezone;   -- per "Multi-Timezone Restaurant Support"
ALTER TABLE core.market_info
    ADD CONSTRAINT fk_market_info_country_iso
    FOREIGN KEY (country_code) REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT;
-- (country_code stays as the natural-key-shaped column, now strictly FK-bound.
--  language / phone_dial_code / credit_currency_id remain owned columns;
--  service layer copies defaults from GeoNames at create time — see market_service.create_market below.)

-- market_info: add kitchen_open_time alongside kitchen_close_time (both become onboarding templates)
ALTER TABLE core.market_info ADD COLUMN kitchen_open_time TIME NOT NULL DEFAULT '09:00'::TIME;

-- restaurant_info: own its own kitchen hours; values are copied from the market template at restaurant-create time
ALTER TABLE ops.restaurant_info ADD COLUMN kitchen_open_time  TIME NOT NULL;
ALTER TABLE ops.restaurant_info ADD COLUMN kitchen_close_time TIME NOT NULL;

-- address_info: drop free-text city, add FK to city_metadata
ALTER TABLE core.address_info DROP COLUMN city;
ALTER TABLE core.address_info
    ADD COLUMN city_metadata_id UUID NOT NULL REFERENCES core.city_metadata(city_metadata_id) ON DELETE RESTRICT;
ALTER TABLE core.address_info
    ADD CONSTRAINT fk_address_info_country_iso
    FOREIGN KEY (country_code) REFERENCES external.geonames_country(iso_alpha2) ON DELETE RESTRICT;

-- user_info: repoint primary city FK
ALTER TABLE core.user_info DROP COLUMN city_id;
ALTER TABLE core.user_info
    ADD COLUMN city_metadata_id UUID NOT NULL REFERENCES core.city_metadata(city_metadata_id) ON DELETE RESTRICT;

-- pending_customer_signup: same
ALTER TABLE customer.pending_customer_signup DROP COLUMN city_id;
ALTER TABLE customer.pending_customer_signup
    ADD COLUMN city_metadata_id UUID NOT NULL REFERENCES core.city_metadata(city_metadata_id) ON DELETE RESTRICT;

-- city_info: retire entirely
DROP TABLE core.city_info CASCADE;
```

(In practice the rebuild happens via `build_kitchen_db.sh` — `schema.sql` is rewritten to the new shape and the `ALTER`s above show the delta. See Migration section below.)

---

## Ingest Mechanism

### What's committed to the repo

- `app/db/seed/external/geonames_countryInfo.tsv` — raw `countryInfo.txt` (~30 KB), committed as-is.
- `app/db/seed/external/geonames_admin1_codes.tsv` — raw `admin1CodesASCII.txt` (~200 KB), committed as-is. Provides state/province names for the superadmin city picker.
- `app/db/seed/external/geonames_cities5000.tsv` — raw `cities5000.txt`, imported globally (~5 MB committed once).
- `app/db/seed/external/geonames_alternate_names.tsv` — pre-filtered `alternateNamesV2.txt`, restricted to `iso_language IN ('en', 'es', 'pt')` and to the `geonames_id`s that exist in our country + admin1 + city files (~1–3 MB committed). The filter is applied by the import script; the committed TSV is already trimmed.
- `app/db/seed/external/README.md` — notes GeoNames source URLs, CC-BY 4.0 attribution, refresh command, GL synthetic-country exception.
- `docs/licenses/THIRD_PARTY_ATTRIBUTIONS.md` — GeoNames CC-BY 4.0 attribution.

### Loader

Called from `build_kitchen_db.sh` and from a one-shot migration for any existing-but-stale environment. Uses `COPY` into staging + upsert:

```sql
CREATE TEMP TABLE _staging_geonames_country (LIKE external.geonames_country INCLUDING DEFAULTS);
\copy _staging_geonames_country FROM 'app/db/seed/external/geonames_countryInfo.tsv' WITH (FORMAT csv, DELIMITER E'\t', HEADER false, NULL '');

INSERT INTO external.geonames_country SELECT * FROM _staging_geonames_country
ON CONFLICT (iso_alpha2) DO UPDATE SET
    iso_alpha3 = EXCLUDED.iso_alpha3,
    name = EXCLUDED.name,
    -- ... refresh every column except imported_at
    imported_at = CURRENT_TIMESTAMP;
```

Same pattern for `geonames_city` and `geonames_alternate_name` (the last one powers localized display — see the Localization section). **No eager `city_metadata` backfill** — metadata rows are created only when a superadmin explicitly promotes a city through vianda-platform.

`COPY` handles the ~53k-row city file in a couple of seconds. `geonames_alternate_name` after filtering to `{en, es, pt}` and only the cities/countries we've imported is on the order of ~1–3 MB and a few hundred thousand rows.

### Indexing for efficient lookups

`external.geonames_city` must be indexed for fast superadmin city-picker queries across the full 53k-row (or larger) dataset:

```sql
CREATE INDEX idx_geonames_city_country_name   ON external.geonames_city (country_iso, LOWER(ascii_name));
CREATE INDEX idx_geonames_city_country_pop    ON external.geonames_city (country_iso, population DESC NULLS LAST);
CREATE INDEX idx_geonames_city_name_trgm      ON external.geonames_city USING GIN (ascii_name gin_trgm_ops);  -- for "type-ahead" search
```

This keeps the "show me cities in country X ranked by population" query (what vianda-platform's city promotion UI needs) cheap even if we later bump to cities1000 or cities500 when we hit coverage gaps.

### Backlog: diff-based refresh

Future ops capability, **not v1**:

1. Download latest `countryInfo.txt` + `cities5000.txt` from GeoNames.
2. Load into temp staging tables.
3. Diff against `external.geonames_*`: new rows, changed rows, rows present locally but missing from source (potential deletions — handle manually, never auto-delete).
4. Insert new rows + upsert changed rows. Does **not** auto-create corresponding `city_metadata` rows — metadata is always superadmin-driven.
5. Emit a report of changes so ops can review. Specifically diffs any GeoNames-sourced column against the copies on `core.market_info` so ops can decide whether to promote the change.

This becomes valuable once we're operating in multiple markets and GeoNames ships updates for new cities or renamed places. Until then, re-running the initial loader with a fresh TSV is sufficient. Captured as `backlog/geonames_diff_refresh.md` (to be created when promoted).

### Python tooling

`app/scripts/import_geonames.py` — simple helper that:
1. (Optional) downloads the latest zip from GeoNames
2. Unzips into a temp dir
3. Runs the staging + upsert SQL

Not a web endpoint. Not on a cron. Just a tool ops runs when refreshing the committed TSVs.

---

## Migration — Tear Down and Rebuild

Since there's no valuable manually-entered data, we take the simple path. The entire change ships in **one coordinated migration + schema rewrite**, exercised via `build_kitchen_db.sh`. Two migration files accommodate the (rare) environments where someone is running `migrate.sh` against a long-lived database, but the default deployment is a full rebuild.

### Single atomic change

1. **Add `external` schema + raw tables + loader.** `schema.sql` gets `external.geonames_country`, `external.geonames_city`, `external.geonames_alternate_name`. `reference_data.sql` gets the `\copy` + upsert blocks and the indexing statements. Loader runs before any `core` metadata table is created.
2. **Add `core.country_metadata` + `core.city_metadata` + history triggers.** History triggers fire on `core.*_metadata` modifications only, never on raw `external.*` ingest.
3. **No eager metadata backfill.** `core.city_metadata` and `core.country_metadata` are populated only by explicit promotion — either by the seed data for the bootstrap markets (step 5) or by superadmin action via vianda-platform.
4. **Rewrite operational table schemas** in `schema.sql`:
   - Drop `city_info` (and `audit.city_info_history`).
   - `market_info` — add FK on `country_code → external.geonames_country(iso_alpha2)`; drop `country_name`; drop `timezone`; add `kitchen_open_time TIME NOT NULL` (template).
   - `restaurant_info` — add `kitchen_open_time TIME NOT NULL` + `kitchen_close_time TIME NOT NULL` (copied from market template at create time).
   - `address_info` — drop `city VARCHAR(50)`, add `city_metadata_id UUID NOT NULL FK city_metadata`. Add FK constraint on `country_code → external.geonames_country`. Add composite FK `(city_metadata_id, country_code) → (city_metadata_id, country_iso)`.
   - `user_info` — drop `city_id`, add `city_metadata_id UUID NOT NULL FK city_metadata`.
   - `pending_customer_signup` — same rename.
5. **Seed data for bootstrap markets:**
   - For each of the 6 existing markets (AR, BR, CL, MX, PE, US), insert a `country_metadata` row with `is_customer_audience = is_supplier_audience = TRUE`, `status = 'active'`, `market_id` set. GL (Global Marketplace) is handled as a synthetic row in `external.geonames_country` (iso_alpha2='GL', name='Global', other fields NULL — documented as a Vianda-specific exception).
   - Promote the 22 legacy cities from the old `city_info` into `city_metadata` rows. For each, resolve `(country_iso, LOWER(unaccent(ascii_name)))` → `external.geonames_city.geonames_id`, then insert `city_metadata` with `show_in_signup_picker = TRUE`, `show_in_customer_form = TRUE`, `show_in_supplier_form = TRUE`, `is_served = TRUE`, `status = 'active'`. Any legacy city that can't be resolved gets logged and resolved manually (only 22 rows — tractable).
   - System bot + super-admin `user_info` rows point at the "Global" `city_metadata` row (created as a synthetic entry matching the GL country exception).
6. **Rewrite the affected services + routes in one go:**
   - `/leads/cities` route takes `audience=supplier`, returns `{cities: [{city_metadata_id, display_name}]}` (shape change — see below).
   - `/leads/markets` reads from `country_metadata` instead of the current in-memory-cached `market_service.get_all` path.
   - Signup flow (`pending_customer_signup`, user creation) accepts `city_metadata_id` from the frontend instead of looking up city by name.
   - `city_info`-referencing imports / queries are deleted.
   - Rate-limit 429 handler and `Cache-Control` header from `marketing_audience_supplier.md` are included here.
7. **Rewrite the tests + Postman collections** that depended on `city_info` or the old `city_name` response shape.

Because the rebuild path (`build_kitchen_db.sh`) drops and recreates the entire DB, everything above collapses into a single schema + seed revision. No dual-write, no phased cutover.

### For any database that must be migrated in place

Ship two migration files for any environment that can't afford a full rebuild:

- `app/db/migrations/NNNN_add_external_and_metadata.sql` — creates `external` + metadata tables, loads GeoNames, eager-creates `city_metadata`. Additive.
- `app/db/migrations/NNNN_rewire_operational_tables.sql` — drops `city_info`, repoints FKs on `user_info` / `pending_customer_signup` / `address_info`, adds FK constraints on `market_info` / `address_info`. Destructive.

The second migration assumes the only pre-existing rows are seeded ones. If there's any user-created data, the migration has to either refuse or delete it. Document this clearly in the migration file.

### API shape changes (breaking)

The `/leads/cities` response changes from `{cities: ["Austin", "Miami"]}` to `{cities: [{city_metadata_id: "uuid", display_name: "Austin"}, ...]}`. This is a breaking change for vianda-home, vianda-app, and any admin UI consuming the endpoint. Coordinate the backend deploy with the frontend updates (hard-land + frontend PRs ready simultaneously).

Same shape change applies to any endpoint that previously returned a raw `city_name` string. Audit list (to confirm during implementation):
- `/leads/cities`
- `/restaurants/cities` (auth)
- Any signup schema that accepted `city_name` as input — change to `city_metadata_id`
- Any read endpoint that returned `city` as a string on an address — change to nested `{city_metadata_id, display_name, country_iso}` or equivalent

---

## How This Unblocks `marketing_audience_supplier.md`

That plan's technical dependency was "a table that returns a usable list of cities for any country including unserved markets." This plan delivers that as a side-effect of the metadata layer. `GET /leads/cities?country_code=X&audience=supplier` is implemented as:

```sql
SELECT city_metadata_id, COALESCE(display_name_override, gc.name) AS display_name
FROM core.city_metadata cm
INNER JOIN external.geonames_city gc ON gc.geonames_id = cm.geonames_id
WHERE cm.country_iso = %(country)s
  AND cm.is_archived = FALSE
  AND cm.show_in_supplier_form = TRUE
ORDER BY LOWER(COALESCE(display_name_override, gc.name))
LIMIT 1000
```

For a country like Colombia where Vianda hasn't operated yet, ops pre-promotes a sensible set of cities by running a one-line UPDATE:

```sql
UPDATE core.city_metadata
SET show_in_supplier_form = TRUE
WHERE country_iso = 'CO' AND geonames_id IN (
    SELECT geonames_id FROM external.geonames_city
    WHERE country_iso = 'CO' AND population >= 50000
    ORDER BY population DESC LIMIT 200
);
```

Or we bake a default-promotion rule into the seed: "when country_metadata.is_supplier_audience flips to TRUE, promote the top 200 cities by population in that country to `show_in_supplier_form = TRUE`." Implementable as a trigger or service helper. **Open decision** — see below.

All the ancillary improvements from `marketing_audience_supplier.md` (structured 429, `Cache-Control: public, max-age=3600`, `/leads/cities` route docs, GeoNames attribution) fold into this work. That plan can be closed out once Phase 2 of this one ships.

---

## Decisions Locked In

1. **Cities dump size: cities5000** (~53k rows, ~5 MB).
2. **Global, not filtered by market.** Import the whole cities5000 file. Superadmin-driven promotion determines what actually gets used; the raw table can afford to be complete.
3. **"Global Marketplace" (`GL`) pseudo-country: synthetic row in `external.geonames_country`.** `iso_alpha2 = 'GL'`, `name = 'Global'`, other fields NULL. Documented in `app/db/seed/external/README.md` as the one Vianda-specific exception to "raw is verbatim". Rejected alternatives: partial FK (b, "nullify-to-bypass" is an injection vector worth avoiding), and drop-GL-entirely with nullable market_id (c, cleanest in principle but the same null-opens-gates concern applies across the institution tree).
4. **Custom cities not in GeoNames: switch dump size, don't pollute.** If cities5000 has a coverage gap, re-import with cities1000 (or cities500 for that country only). The raw table is properly indexed by country (see the Indexing subsection in the Ingest Mechanism section) so cross-country search stays cheap even at cities500. Neither synthetic rows in the raw table nor polymorphic references in metadata.
5. **Auto-promotion of top-N cities when a new supplier-audience country is added: yes, via an explicit service helper** `promote_supplier_cities(country_iso, top_n=200)`. Called from the superadmin country-promotion flow in vianda-platform. Not a trigger.
6. **`address_info` city/country consistency: composite FK at the DB level.** `FOREIGN KEY (city_metadata_id, country_code) REFERENCES city_metadata(city_metadata_id, country_iso)`.
7. **Re-import cadence: no cron.** Manual ops-run refresh when needed. Diff-based refresh lives in the backlog.
8. **Localized city/country names: IN v1 scope** (moved from backlog). See the new "Localization" section for the full rule. Summary: metadata tables do not copy names from source; every display path resolves through `external.geonames_alternate_name` for locale-specific names and falls back to `external.geonames_country.name` / `external.geonames_city.name`. `display_name_i18n` on metadata tables exists only as a per-row override hatch.
9. **`/leads/cities` response shape changes** from `string[]` to `{city_metadata_id, display_name}[]` in the same cutover. Breaking for vianda-home/vianda-app; deploy coordinated.

### Why localization is in v1 (and the display-vs-canonical split)

The business case — higher Google/Meta ad CTR with locale-matched geo targets, user-facing UX that shows "Brazil" to English speakers and "Brasil" to Portuguese speakers, canonical names for Mapbox / Google Maps geocoding — is strong enough that deferring it creates rework. Since the ingest story (a new `external.geonames_alternate_name` table + a TSV filter step) and the resolution story (a thin service helper) are small compared to the payoff, it lands in v1.

**The display-vs-canonical split:**

There are two distinct uses for a city/country name, and they **cannot** be served by the same value:

| Use case | Which name? | Source |
|---|---|---|
| User-facing UX in locale `L` | Localized (alt name in `L`, or canonical if no alt exists) | `external.geonames_alternate_name WHERE language = L`, fallback to `external.geonames_{city,country}.name` |
| Mapbox / Google Maps geocoding input | Canonical (GeoNames `name` or `ascii_name`) | `external.geonames_{city,country}.name` / `.ascii_name` |
| Google Ads / Meta Ads targeting | Locale-specific for the campaign's target language | Alt name in the campaign's target locale |
| Receipts, invoices, legal docs | Canonical English (or the entity's registered locale) | Canonical, or user's preferred locale |
| API `/leads/cities` response to a locale-aware caller | Localized per request header | Alt name, with fallback |

Both values travel together in the API response where it matters: `{city_metadata_id, display_name, canonical_name}` is returned by `/leads/cities` when the caller sends `Accept-Language`, so frontend can show `display_name` in the UI and send `canonical_name` to Mapbox. Single-language clients ignore `canonical_name`.

### Pros/cons: reference-from-source vs copy-on-metadata for localized names

Since this is the specific question you raised:

**Option A — Reference source; metadata only overrides when we explicitly disagree** (recommended, matches principle)
- Pros: No duplication. The raw table stays the single source of truth. Adding a new locale is just ingesting more alt-names into `external.geonames_alternate_name` — no metadata migration. Refresh is safe: new alt-names propagate immediately because they're read live. Metadata rows stay tiny.
- Cons: Every display path joins at least one extra table (`alternate_name` → fallback). Query complexity is real. Mitigated by caching the resolution in-memory at the service layer (a dictionary keyed by `(geonames_id, locale)` with TTL). Also: if GeoNames ships a bad alt-name, the bad value is live everywhere until we add an override row.

**Option B — Copy locale-specific names into `city_metadata.display_name_i18n` JSONB at metadata-create time**
- Pros: Single-table lookup, simpler query. Metadata row is self-contained — a `city_metadata` row carries its own locale map.
- Cons: Duplication. Adding a locale means rewriting metadata rows. Refresh is risky: new GeoNames alt-names don't propagate unless we also run a metadata-refresh pass, which itself would need a "don't clobber manual overrides" gate. The metadata table gets heavier per-row, particularly if we support 5+ locales. The copy window introduces a "metadata was created before GeoNames added Swedish, so the Swedish name is missing" class of bugs.

**Option C — Hybrid**: metadata stores nothing by default, `display_name_i18n` JSONB populated only for manual overrides (per-row). Live resolution: metadata override → alternate_name table → canonical.
- This is Option A with an escape hatch, which is what the plan recommends.

**Recommendation: Option C** (= Option A + override column). Matches the principle ("reference source, copy only what you own"), minimizes refresh risk, and the override column is there for the genuinely rare cases where ops says "GeoNames is wrong about this city name, use ours."

---

## Risks

| Risk | Mitigation |
|---|---|
| `GL` Global market doesn't map cleanly to GeoNames | Synthetic row with `iso_alpha2 = 'GL'` + documented exception. Locked in under Decisions Locked In #3. |
| Bootstrap backfill can't match one of the 22 seeded `city_info` rows to a `geonames_city` row (e.g. "Tierra del Fuego" is a province) | Log mismatches loudly. Manually resolve by finding the right `geonames_id` for each orphan and updating the bootstrap promotion script. Acceptable since there are only 22. |
| Superadmin forgets to promote cities for a country before opening it for interest | Interest form shows the country with an empty cities dropdown, user can't complete the form. Mitigation: the superadmin "Open country" action in vianda-platform requires at least one city promotion in the same transaction, or explicitly calls `promote_supplier_cities(country_iso, top_n=200)` before flipping the audience flag. Enforced in the service, not the DB. |
| API shape change (`string[]` → `{id, name}[]`) breaks vianda-home + vianda-app simultaneously | Coordinate deploy. Backend PR merged only after frontend PRs are staged + ready. |
| `external` schema ingest blows up in an unexpected environment | Loader is idempotent (upsert on stable keys), schema creation is `IF NOT EXISTS`. `build_kitchen_db.sh` is the default path; incremental migration is the fallback. |
| Composite FK `(city_metadata_id, country_code) → (city_metadata_id, country_iso)` isn't a standard pattern in this repo | Single example in this change, documented inline. Or punt to trust-the-writer with a CHECK via trigger. |
| GeoNames schema changes between imports | Loader uses COPY + upsert on stable PKs. If GeoNames adds a column, existing rows keep working; we update `schema.sql` in a follow-up. |

---

## Critical files to create / modify

### Raw ingest + metadata
- `app/db/schema.sql` — add `CREATE SCHEMA external`, `external.geonames_country`, `external.geonames_admin1`, `external.geonames_city`, `external.geonames_alternate_name`, `core.country_metadata`, `core.city_metadata`
- `app/db/trigger.sql` — history triggers for `country_metadata` and `city_metadata` **only**. No triggers on `external.*` — raw ingest is reproducible from source, no audit history needed.
- `app/db/schema.sql` (audit section) — `audit.country_metadata_history`, `audit.city_metadata_history`
- `app/db/migrations/NNNN_add_external_and_metadata.sql` — additive migration for in-place environments
- `app/db/seed/external/geonames_countryInfo.tsv` — committed raw data
- `app/db/seed/external/geonames_cities5000.tsv` — committed raw data (global, ~5 MB)
- `app/db/seed/external/geonames_alternate_names.tsv` — committed, pre-filtered to `{en, es, pt}` and to imported geonames_ids (~1–3 MB)
- `app/db/seed/external/README.md` — source URLs, CC-BY 4.0, refresh instructions, GL exception, filter rules
- `app/db/seed/reference_data.sql` — external loader (geonames_country + geonames_city + geonames_alternate_name) + bootstrap `country_metadata` rows for the 6 existing markets + bootstrap `city_metadata` rows for the 22 legacy signup cities (status='active', all relevant flags TRUE). No eager 53k-row backfill.
- `docs/licenses/THIRD_PARTY_ATTRIBUTIONS.md` — new file, GeoNames CC-BY 4.0 attribution
- `app/scripts/import_geonames.py` — ops helper: downloads GeoNames zips, runs the alt-names filter step (keeps only in-scope geonames_ids and locales), produces the committed TSVs
- `app/services/place_name_resolver.py` — new. `resolve_place_name(geonames_id, locale, db) → {display_name, canonical_name}` with metadata-override → alternate_name → canonical fallback chain, 1-hour in-process TTL cache
- `app/services/country_metadata_service.py` — new. `promote_country(iso_alpha2, audience_flags)`, `promote_to_active(country_iso)`, `promote_supplier_cities(country_iso, top_n)` helpers for the superadmin promotion flow
- `app/services/city_metadata_service.py` — new. `promote_city(geonames_id, flags)`, `promote_to_active(city_metadata_id)` helpers

### Operational table rewire
- `app/db/schema.sql` — drop `core.city_info`; drop `core.market_info.country_name`; drop `core.market_info.timezone`; add `core.market_info.kitchen_open_time TIME NOT NULL` (template); add `ops.restaurant_info.kitchen_open_time TIME NOT NULL` + `ops.restaurant_info.kitchen_close_time TIME NOT NULL` (copied from market at create time); repoint `user_info.city_id` → `city_metadata_id`; drop `address_info.city`, add `address_info.city_metadata_id`; add FK on `market_info.country_code` + `address_info.country_code` + composite FK on `(city_metadata_id, country_code)`
- `app/db/migrations/NNNN_rewire_operational_tables.sql` — destructive migration
- `app/dto/models.py` — update `UserInfo`, `AddressInfo`, `PendingCustomerSignup`, add `CountryMetadata`, `CityMetadata`
- `app/schemas/consolidated_schemas.py` — update schemas: `/leads/cities` response, address response, signup request
- Pydantic schemas for `CountryMetadata` / `CityMetadata`

### Routes + services
- `app/routes/leads.py` — `/leads/cities` gains `audience=supplier` branch, response shape updated; `/leads/markets` reads from `country_metadata`
- `app/services/city_metrics_service.py` — rewrite around `city_metadata` flags; drop `city_info` references
- `app/services/country_service.py` — new, reads from `country_metadata`
- `app/services/market_service.py` — `create_market` looks up the picked `iso_alpha2` in `external.geonames_country`, copies defaults into the new `market_info` row (`phone_dial_code` ← `phone_prefix`, `language` ← first code from `languages`, `credit_currency_id` ← lookup in `credit_currency_info` by `currency_code`), and accepts explicit overrides from the form body. Does **not** populate a `timezone` column (dropped). `get_market_enriched()` joins `external.geonames_country` for display fields (replaces references to the dropped `country_name` column). Creates the corresponding `core.country_metadata` row if absent.
- `app/services/timezone_service.py` — **deleted** (or reduced to a stub that raises on call). `PROVINCE_TIMEZONE_MAPPING` dict retired entirely; replaced by the `city_metadata → geonames_city.timezone` lookup in `address_service.resolve_address_timezone(city_metadata_id, db)`.
- `app/services/address_service.py` — `create_address` / `update_address` look up timezone via `city_metadata_id → external.geonames_city.timezone` and store on `address_info.timezone`. No more province-based deduction.
- `app/services/kitchen_day_service.py` — `_get_kitchen_close_time` signature changes from `(country_code, day_name)` to a restaurant-scoped lookup with `COALESCE(restaurant.kitchen_close_time_override, market.kitchen_close_time)` fallback. `get_effective_current_day` takes a restaurant/address identifier instead of a raw tz string.
- `app/services/cron/kitchen_start_promotion.py` — audit for residual `market.timezone` reads; expected to already iterate per-restaurant via address tz, so the diff should be small.
- `app/services/cron/billing_events.py` — verify that billing closeout uses `institution_entity.address.timezone` (via `institution_entity_info.address_id → address_info.timezone`), not restaurant address or market default.
- `app/services/plate_selection_service.py` — currently reads `market.timezone`; audit what it uses it for and route through either restaurant address tz or the capital-city helper.
- `app/routes/admin/markets.py` — admin Create/Edit Market form drops the `timezone` field (and `country_name`, which is now derived).
- `app/config/market_config.py` — audit for timezone-related constants (`MarketConfiguration.kitchen_day_config`); delete anything now redundant with the DB + per-restaurant override.
- `app/services/user_service.py`, signup / pending-signup services — accept `city_metadata_id` from frontend; drop city_name string lookup
- `app/services/address_service.py` (or wherever address is created) — accept `city_metadata_id` from frontend
- `application.py` — custom slowapi `RateLimitExceeded` handler (from `marketing_audience_supplier.md`)

### Docs
- `docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md` — update §2 for new audience param + new response shape
- `docs/api/internal/COUNTRY_CITY_DATA_STRUCTURE.md` — new, authoritative doc explaining the two-layer model and flag taxonomy; referenced from `AGENT_INDEX.md`
- `CLAUDE_ARCHITECTURE.md` — add section on country/city data flow, note `city_info` retired
- `docs/api/AGENT_INDEX.md` — index the new doc
- `docs/plans/marketing_audience_supplier.md` — mark as absorbed / obsolete

### Tests
- `app/tests/` — update any fixture that builds a `user_info` / `address_info` row to supply `city_metadata_id` instead of `city_id` / `city` string
- `docs/postman/collections/` — `/leads/cities` tests updated for new shape; `/leads/markets` tests if response shape shifts

---

## Verification

1. **DB rebuild:** `bash app/db/build_kitchen_db.sh` — confirms schema + seed load cleanly.
2. **Row counts:**
   - `SELECT count(*) FROM external.geonames_country` → 250+
   - `SELECT count(*) FROM external.geonames_city` → ~53k
   - `SELECT count(*) FROM core.city_metadata` → matches `geonames_city` count (1:1 invariant)
   - `SELECT count(*) FROM core.city_metadata WHERE show_in_signup_picker = TRUE` → 22 (legacy migration preserved)
   - `SELECT count(*) FROM core.country_metadata WHERE is_customer_audience = TRUE` → 6 (matches seeded markets)
3. **Import check:** `python3 -c "from application import app; print('OK')"`.
4. **Composite FK sanity:** try inserting an `address_info` row with `country_code='US'` but `city_metadata_id` pointing at a Mexican city → FK violation as expected.
5. **Curl smoke tests:**
   - `GET /leads/cities?country_code=AR` → default-flag cities only (same as before for customer coverage)
   - `GET /leads/cities?country_code=AR&audience=supplier` → broader supplier list, response shape `[{city_metadata_id, display_name}]`
   - `GET /leads/cities?country_code=CO&audience=supplier` → non-empty (after running the supplier promotion rule for CO)
   - `GET /leads/cities?country_code=ZZ&audience=supplier` → empty (unknown country)
   - `GET /leads/markets?audience=supplier` → reads from `country_metadata`, returns the same payload shape
   - Burst 25 req/min on `/leads/cities` → structured 429 `{detail: "rate_limited", retry_after_seconds: 60}` + `Retry-After: 60`
   - Verify `Cache-Control: public, max-age=3600` on cities + markets responses
6. **End-to-end signup smoke:** run the B2C signup flow using the new `city_metadata_id` field, verify user row + pending_signup row have valid FKs.
7. **Pytest:** `pytest app/tests/` green.
8. **Grep for dead references:** `grep -r "city_info" app/` returns zero non-comment matches.
9. **Frontend smoke** (after deploy): vianda-home "Apply to Partner" flow populates cities for an unserved country; vianda-app signup flow picks a city and completes.
10. **Multi-timezone kitchen day:** create two US restaurants — one with an NYC address (`city_metadata_id` for New York), one with an LA address (`city_metadata_id` for Los Angeles) — both under the same market. Set `market.kitchen_close_time = 13:30`. Invoke `get_effective_current_day` / `_get_kitchen_close_time` for each. Expect: NY restaurant cuts over at `13:30 America/New_York`, LA restaurant cuts over at `13:30 America/Los_Angeles` — a 3-hour wall-clock gap. Verify no residual `market.timezone` references remain in `plate_selection_service` or anywhere else in the restaurant code path.
11. **Multi-timezone billing:** create an `institution_entity` with an Austin address and two restaurants (one in New York, one in Los Angeles). Fabricate transactions near a month boundary from both restaurants. Run the monthly billing closeout. Expect: the period boundary is interpreted in `America/Chicago` (Austin tz, from `institution_entity.address.timezone`), and transactions fall into the correct billing period regardless of which restaurant they came from.
12. **Timezone service retirement check:** `grep -r "PROVINCE_TIMEZONE_MAPPING" app/` returns zero matches. `grep -r "market.*\.timezone\b" app/` returns zero matches (the column no longer exists). `grep -r "from app.services.timezone_service" app/` returns zero matches (or only the retired-shim warning).
13. **Superadmin promotion flow:** starting from a clean DB, create a new market for Colombia via the admin endpoint. Expect: `country_metadata` row exists with `status='pending'`, `is_supplier_audience=TRUE`. Call `promote_supplier_cities('CO', top_n=50)`. Expect: 50 `city_metadata` rows with `show_in_supplier_form=TRUE`, `status='pending'`. Call `GET /leads/cities?country_code=CO&audience=supplier`. Expect: 50 cities in the response. Register a real supplier lead converting to a restaurant in Bogotá. Expect: `country_metadata('CO').status` flips to `active` via the service hook, and `city_metadata(Bogotá).status` flips to `active`.
14. **Localization end-to-end:** `GET /leads/cities?country_code=BR&audience=supplier` with `Accept-Language: en`. Expect: `display_name` includes "Sao Paulo" (or "São Paulo" if Portuguese is the canonical) and `canonical_name` is the GeoNames canonical. Same request with `Accept-Language: pt`. Expect: `display_name` is "São Paulo". Same request with `Accept-Language: zz` (unsupported). Expect: fallback to canonical. Insert a `city_metadata.display_name_override='Sampa'` for São Paulo. Expect: next uncached request returns `display_name='Sampa'`. Cache expires within 1 hour.
15. **Kitchen-hours onboarding:** create a market with `kitchen_open_time=08:00`, `kitchen_close_time=13:30`. Create a restaurant — expect `restaurant_info.kitchen_open_time=08:00` and `kitchen_close_time=13:30` copied from the market. Update the market to `kitchen_open_time=09:00`. Confirm the existing restaurant's `kitchen_open_time` is still `08:00` (the restaurant owns its value). Create a second restaurant — it should inherit the new `09:00` template.

---

## Cross-Repo Impact

- **vianda-home** — reads `/leads/markets` and `/leads/cities`. `audience=supplier` story unblocks. **Breaking**: `/leads/cities` response shape changes from `string[]` to `{city_metadata_id, display_name}[]`. Must update the cities dropdown and the "Apply to Partner" form submission to send `city_metadata_id` (if they post city back) or `display_name` (if not).
- **vianda-app (B2C)** — signup flow sends `city_metadata_id` instead of `city_name` string. Profile reads get city display name from a nested object. Coordinated deploy required.
- **vianda-platform (B2B)** — admin screens that display city read from the nested object. Employer / institution onboarding flows updated similarly.
- **infra-kitchen-gcp** — no direct impact for v1. If/when the diff-refresh cron is promoted from backlog, it'll need a new Cloud Run job + scheduler.

Docs produced by this plan:
- `docs/api/internal/COUNTRY_CITY_DATA_STRUCTURE.md` — new, authoritative for all future city/country questions
- Updates to `docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md`
- `CLAUDE_ARCHITECTURE.md` section update

---

## Backlog (out of scope for v1)

- **GeoNames diff-based refresh** — script + review report for updating `external.geonames_*` with newer snapshots. Must: (a) auto-apply changes to `external.geonames_*` (source of truth, no review needed); (b) **diff every GeoNames-sourced column against the copies living on `core.market_info` for markets that exist**, emit a review report, never auto-apply — ops decides whether to promote a change (e.g. a corrected `phone_prefix`); (c) never touch metadata override columns or flags; (d) invalidate the place-name resolver cache; (e) never auto-create metadata rows (metadata is always superadmin-driven).
- ~~**Migrate `credit_currency_info` and `ops.cuisine` into the `external` schema.**~~ **Resolved after scope assessment:**
  - **Currency — folded into v1.** `credit_currency_info` gets the two-tier split: raw ISO 4217 data in `external.iso4217_currency`, Vianda policy (`credit_value_local_currency`, `currency_conversion_usd`) in a new `core.currency_metadata`. Nine FK sites get a mechanical column rename. See "Implementation Ordering" for the PR slice where this lands.
  - **Cuisine — removed from scope.** Assessment revealed `ops.cuisine` is not externally sourced: it's a Vianda-curated taxonomy with hand-written i18n labels, a `parent_cuisine_id` hierarchy, a `slug`, and an `origin_source` column already tracking `'seed'` vs `'supplier'`. There's no authoritative external cuisine dataset to mirror. The "move to external" premise was miscategorized — cuisine belongs where it is. No change planned.
- **Additional locales beyond `en/es/pt`** — re-run the alternate-names filter with more `iso_language` values when we expand markets (e.g. `fr` for a Québec push).
- **Geocoding of free-form address inputs** — resolve a free-form address string to a `geonames_city` row + lat/lng (requires a geocoding API or fuzzy match service).
- **Admin UI for toggling metadata flags** — ops-facing screen (via vianda-platform) to promote/demote cities and flip audience flags without a SQL console. v1 has the backend endpoints; the UI polish is follow-up.
- **Monthly re-import cron** — Cloud Run job that runs `import_geonames.py` and posts a diff report to ops Slack. No cron in v1; manual refresh only.

---

## Implementation Ordering

Since this is a single tear-down-rebuild cutover, "phases" here means **PR slices on a long-lived feature branch** that merges to main all at once on cutover day. Individual PRs on the branch don't need to preserve a working build — only the final branch state does. Every PR is reviewed and unit-tested against the feature branch's accumulated state; integration tests against a rebuilt dev DB run after each merge to the branch.

Work is grouped so that reviewers can reason about one concern at a time (DDL, ingest tooling, resolver backbone, operational rewire, route surface, docs). The main cutover is a single coordinated backend + frontend deploy.

### Branch model

- **`main`** — current stable, untouched until cutover day.
- **`feat/country-city-rebuild`** — long-lived feature branch. All PR slices below merge here. This branch accumulates breaking changes; individual intermediate states are not guaranteed to build or pass tests against the old schema.
- **Feature branch has its own CI target:** `build_kitchen_db.sh` against a throwaway Postgres, plus the new integration tests. Passing CI on the branch is the gate for each PR slice.

### PR slice sequence

**PR 0 — Ingest tooling + committed TSVs + docs scaffolding.**
Safe, mergeable to **main** directly (does not depend on any schema change).
- `app/scripts/import_geonames.py` — downloads GeoNames dumps, runs alternate-names filter, produces committed TSVs.
- `app/db/seed/external/geonames_countryInfo.tsv`, `geonames_admin1_codes.tsv`, `geonames_cities5000.tsv`, `geonames_alternate_names.tsv` (pre-filtered).
- `app/db/seed/external/iso4217_currencies.tsv` — raw ISO 4217 data.
- `app/db/seed/external/README.md` — source URLs, CC-BY 4.0, refresh instructions, GL exception, filter rules.
- `docs/licenses/THIRD_PARTY_ATTRIBUTIONS.md` — GeoNames CC-BY 4.0 attribution.
- Tests: import script produces expected row counts against a pinned GeoNames snapshot.

Rationale: data files and tooling are self-contained. Merging early lets everyone pull the TSVs without waiting on schema work.

**PR 1 — DDL rewrite (on feature branch).**
The big schema change. Breaks the app for anyone syncing the branch; that's fine.
- `app/db/schema.sql`:
  - `CREATE SCHEMA external`
  - `external.geonames_country`, `external.geonames_admin1`, `external.geonames_city`, `external.geonames_alternate_name`, `external.iso4217_currency` with all documented indexes
  - `core.country_metadata`, `core.city_metadata`, `core.currency_metadata` with history siblings in `audit.*`
  - `core.market_info`: drop `country_name`, drop `timezone`, add FK on `country_code → external.geonames_country`, add `kitchen_open_time TIME NOT NULL`
  - `ops.restaurant_info`: add `kitchen_open_time TIME NOT NULL`, `kitchen_close_time TIME NOT NULL`
  - `core.address_info`: drop `city VARCHAR(50)`, add `city_metadata_id UUID NOT NULL`, FK to `external.geonames_country(iso_alpha2)` on `country_code`, composite FK on `(city_metadata_id, country_code)`
  - `core.user_info`: drop `city_id`, add `city_metadata_id UUID NOT NULL`
  - `customer.pending_customer_signup`: same rename
  - Currency column rename: every `credit_currency_id UUID REFERENCES credit_currency_info(...)` becomes `currency_metadata_id UUID REFERENCES core.currency_metadata(...)`. 9 call sites.
  - `DROP TABLE core.city_info CASCADE`
  - `DROP TABLE core.credit_currency_info CASCADE` (after the rename is applied)
- `app/db/trigger.sql`: history triggers for `country_metadata`, `city_metadata`, `currency_metadata`. **No** triggers on `external.*`.
- `app/db/seed/reference_data.sql`:
  - External loader: `\copy` into staging + upsert for all five external tables, in dependency order.
  - Bootstrap `country_metadata` rows for the 6 existing markets with `status = 'active'`, `is_customer_audience = is_supplier_audience = TRUE`.
  - Bootstrap `currency_metadata` rows preserving existing pricing (`credit_value_local_currency`, `currency_conversion_usd`).
  - Bootstrap `city_metadata` rows for the 22 legacy signup cities, resolved via `(country_iso, LOWER(unaccent(ascii_name)))` → `geonames_id`, with `show_in_signup_picker = TRUE`, `show_in_customer_form = TRUE`, `show_in_supplier_form = TRUE`, `is_served = TRUE`, `status = 'active'`. Log any unresolved legacy row for manual fix-up.
  - GL synthetic row in `external.geonames_country`, synthetic "Global" city in `external.geonames_city`, and corresponding metadata rows.
- `app/db/migrations/NNNN_country_city_rebuild.sql` — idempotent equivalent for any environment running incrementally. Default deploy is full rebuild via `build_kitchen_db.sh`.

Gate: `bash app/db/build_kitchen_db.sh` succeeds cleanly against a throwaway Postgres. Row-count assertions pass. App code still won't compile until later PRs — expected.

**PR 2 — DTOs, Pydantic schemas, metadata services.**
The foundational service layer. Unblocks every downstream PR.
- `app/dto/models.py` — add `CountryMetadata`, `CityMetadata`, `CurrencyMetadata`, `GeonamesCountry`, `GeonamesCity`, `GeonamesAdmin1`; update `UserInfo`, `AddressInfo`, `PendingCustomerSignup`, `MarketInfo`, `RestaurantInfo` to match new columns.
- `app/schemas/consolidated_schemas.py` — Pydantic schemas for the new types and the updated `/leads/cities` / `/admin/external/*` response shapes.
- `app/services/place_name_resolver.py` — `resolve_place_name(geonames_id, locale, db) → {display_name, canonical_name}`, with 1-hour in-process TTL cache, metadata-override → alternate_name → canonical fallback chain.
- `app/services/country_metadata_service.py` — `promote_country(iso_alpha2, audience_flags)`, `promote_to_active(country_iso)`.
- `app/services/city_metadata_service.py` — `promote_city(geonames_id, flags)`, `promote_to_active(city_metadata_id)`, `promote_supplier_cities(country_iso, top_n=200)`.
- `app/services/currency_metadata_service.py` — CRUD + policy updates.
- Unit tests for each service + resolver. Tests run against a metadata-only DB fixture (no need for full schema in these tests).

**PR 3 — Timezone + kitchen-hours operational rewire.**
Touches billing and kitchen-day code paths. Highest-risk PR on the branch.
- **Delete** `app/services/timezone_service.py`. `PROVINCE_TIMEZONE_MAPPING` gone.
- **Delete** `MarketConfiguration.kitchen_day_config` from `app/config/market_config.py`.
- `app/services/address_service.py` — `create_address` / `update_address` look up timezone via `city_metadata_id → external.geonames_city.timezone`; no more province-based deduction.
- `app/services/market_service.py` — `create_market` reads defaults from `external.geonames_country` (language, phone_dial_code, currency mapping) + writes to new schema; `get_market_enriched()` joins `external.geonames_country` for display fields.
- `app/services/kitchen_day_service.py` — new signatures: `(restaurant_id, db)` / `(address_id, db)`. Reads `restaurant.kitchen_open_time`/`kitchen_close_time` directly, no fallback through market.
- `app/services/cron/kitchen_start_promotion.py` — verify address-tz usage, delete any residual market.timezone reads.
- `app/services/cron/billing_events.py` — verify `institution_entity.address.timezone` is the source of tz for billing period boundaries. Fix if not.
- `app/services/plate_selection_service.py` — audit the current `market.timezone` usage, route through either the restaurant's address tz or UTC depending on what it's computing.
- `app/routes/admin/markets.py` — drop timezone and country_name from the admin form.
- **Integration tests** (new):
  - Multi-tz kitchen day: two US restaurants in NY + LA under the same market, assert 3-hour wall-clock gap in close events.
  - Multi-tz billing: institution_entity in Austin with restaurants in NY + LA, assert period boundary uses `America/Chicago`.
  - Kitchen-hours onboarding: market template change does not affect existing restaurants; new restaurants inherit the new template.
- Grep-based retirement checks: `PROVINCE_TIMEZONE_MAPPING` / `market.*\.timezone` / `from app.services.timezone_service` return zero matches.

**PR 4 — Signup + address write path rewire.**
Everywhere the app writes a city.
- `app/services/user_service.py`, signup / pending-signup service — accept `city_metadata_id` from the frontend, drop the legacy `city_name`-string lookup path.
- `app/services/address_service.py` (continued from PR 3) — `city_metadata_id` required on create.
- Every test fixture that built a `user_info` / `address_info` / `pending_customer_signup` row with a legacy city_name string gets updated to use a `city_metadata_id` from the bootstrap seed.
- Composite-FK sanity tests: assert that inserting an address with country_code='US' and a Mexican `city_metadata_id` fails with a clean FK violation.

**PR 5 — Route surface + admin picker endpoints + marketing-audience supplier fix.**
The customer-facing API shape change. This is the PR vianda-home and vianda-app couple to.
- `app/routes/leads.py`:
  - `/leads/cities` gets `audience=supplier` branch, response shape becomes `{cities: [{city_metadata_id, display_name, canonical_name}]}`. Locale handled via `Accept-Language` + `place_name_resolver`.
  - `/leads/markets` reads from `country_metadata` (filtered by audience flag) and returns enriched country data.
- `app/routes/admin/external.py` — new file. `/admin/external/countries`, `/admin/external/provinces?country_iso=`, `/admin/external/cities?country_iso=&admin1_code=&q=` — powers the cascading picker in vianda-platform. Auth: super_admin only.
- `application.py` — custom slowapi `RateLimitExceeded` handler returning `{detail: "rate_limited", retry_after_seconds: N}` + `Retry-After` header. Global for all `/leads/*`.
- `app/utils/rate_limit.py` — verify.
- Postman collections: `docs/postman/collections/leads.json` updated for new shape; new `admin_external.json` for the picker endpoints.

**PR 6 — Docs.**
Can parallelize with PR 5. Authoritative doc on the new data structure plus updates to existing docs.
- `docs/api/internal/COUNTRY_CITY_DATA_STRUCTURE.md` — NEW. The load-bearing doc for how all future country/city/currency work references this layer. Covers: two-tier model, superadmin promotion flow, kitchen hours + timezone semantics, localization resolver, place-name contract.
- `docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md` — update §2 with new `/leads/cities` audience param and response shape; update rate-limit section with structured 429 shape.
- `docs/api/AGENT_INDEX.md` — index the new doc.
- `CLAUDE_ARCHITECTURE.md` — add a Country/City section noting `city_info` retired, the `external/*` + `core.*_metadata` split, timezone model, localization resolver.
- Archive `docs/plans/marketing_audience_supplier.md` (mark as absorbed).

**PR 7 — Bulk test + fixture cleanup.**
Catch-all for test churn.
- `app/tests/` — grep for `city_info`, `credit_currency_info`, `market.timezone`, `PROVINCE_TIMEZONE_MAPPING`; fix every match.
- `app/tests/conftest.py` — updated fixtures for new schema.
- Postman collections — rerun against a rebuilt dev DB, fix any self-contained data setup that referenced the dropped entities.
- `pytest app/tests/` fully green.

### Currency rewire — specifics (lives inside PR 1 + PR 2)

The currency two-tier split is mechanical but wide. Spelling it out so reviewers of PR 1/2 know what to expect:

- **New `external.iso4217_currency`**: columns `(code VARCHAR(3) PK, name VARCHAR(100), numeric_code INTEGER, minor_unit INTEGER)`. Seeded from `iso4217_currencies.tsv`. Read-only.
- **New `core.currency_metadata`**: columns `(currency_metadata_id UUID PK DEFAULT uuidv7(), currency_code VARCHAR(3) UNIQUE FK external.iso4217_currency, credit_value_local_currency NUMERIC NOT NULL, currency_conversion_usd NUMERIC NOT NULL, is_archived, status, audit fields)`. Owns Vianda pricing policy. History table in `audit.currency_metadata_history`.
- **Drop `core.credit_currency_info`** after bootstrapping metadata rows.
- **Rename FK column across 9 tables**: everywhere currently has `credit_currency_id UUID REFERENCES core.credit_currency_info(credit_currency_id)` becomes `currency_metadata_id UUID REFERENCES core.currency_metadata(currency_metadata_id)`. Tables: `market_info`, `institution_entity_info`, `client_bill_info` / `institution_bill_info` / subscription / payout / referral / reward / related billing tables (the exact list is whatever the schema.sql grep returned — 9 sites).
- **DTO rename**: `CreditCurrencyInfo → CurrencyMetadata`. Every service/route/schema that imports or references the old DTO gets updated in PR 2/3/4.
- **Bootstrap seed**: for each of the 5 existing currencies (USD, ARS, PEN, CLP, MXN, BRL — 6 actually), look up `external.iso4217_currency(code)` and insert `currency_metadata` with the preserved `credit_value_local_currency` + `currency_conversion_usd` values.

### Cutover sequence

1. **Pre-cutover freeze** — feature branch `feat/country-city-rebuild` is fully green on CI. Frontend PRs in `vianda-home`, `vianda-app`, `vianda-platform` are staged and ready to deploy.
2. **Cutover window** — announce freeze on `main`. No other merges during cutover.
3. **Merge** `feat/country-city-rebuild` → `main`.
4. **Environment rebuilds** (dev → staging → prod):
   - `bash app/db/migrate.sh` for the idempotent migration path, OR
   - `bash app/db/build_kitchen_db.sh` for full rebuild (recommended: all envs since data is reproducible from seed).
5. **Backend deploy**.
6. **Frontend deploys** — vianda-home, vianda-app, vianda-platform merged and deployed simultaneously with backend. Any deploy-order skew shows up as a broken `/leads/cities` shape.
7. **Smoke tests** — run the verification checklist (rows, curl, multi-tz kitchen day, multi-tz billing, localization, superadmin promotion).
8. **Monitor** — watch billing closeout and kitchen-day cron runs for the next 24 hours.
9. **Unfreeze** `main`.

### Rollback posture

Because we're tearing down and rebuilding with seed data, there is no "point-in-time rollback" — the old schema doesn't know about the new columns and the new schema doesn't preserve old column names. Rollback is:

1. Revert the merge commit on `main`.
2. Rebuild the DB from the reverted `schema.sql` + `reference_data.sql` (full tear-down-rebuild).
3. Revert frontend deploys.

**This is acceptable only because there is no user-generated data yet.** Document this clearly in the cutover runbook — if this plan were being executed post-launch against real data, rollback would be much harder and PR 1 would need to preserve old columns through a dual-read window. For v1, we don't.

### Cross-repo coordination checklist

- **vianda-home** — consume new `/leads/cities` shape (`{city_metadata_id, display_name, canonical_name}`), send `Accept-Language`. Remove any client-side free-text city fallback for the supplier form. Append `&audience=supplier` on the Apply-to-Partner cities call.
- **vianda-app** — signup flow sends `city_metadata_id` instead of `city_name` string; profile displays nested city object with localized `display_name`.
- **vianda-platform** — new admin form for market creation with cascading country → province → city picker against the new `/admin/external/*` endpoints; "promote cities" UI flipping `show_in_supplier_form` / `show_in_customer_form` / `show_in_signup_picker` flags on `city_metadata`.
- **infra-kitchen-gcp** — no action required for v1. Future refresh cron is backlog.

Each frontend team is notified via the summary on the backend cutover PR, with pointers to `docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md` and the new `docs/api/internal/COUNTRY_CITY_DATA_STRUCTURE.md`.
