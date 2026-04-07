# Config-to-DB migration (operational settings without deploy)

**Audience:** Backend, platform, and ops.  
**Purpose:** Move **operational configuration** from Python modules to **database-backed** tables with **Internal admin** APIs (and eventually admin UI), so changes to kitchen hours, billing timing, timezones, enum labels, messages, and archival policy do **not** require a code deploy.

**Relationship to other roadmaps**

- **[LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md](./LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md)** — Phase 7 (message translations DB) and Phase 9 (this doc) align on **`message_translation`** / admin copy.
- **Archival** — Partially DB-backed already (`app/db/archival_config_table.sql`, admin routes); Python in `app/config/archival_config.py` still holds mappings and defaults. Phase 9.5 completes the move.

**Last updated:** March 2026

---

## Problem statement

Today, many knobs live in code (`market_config.py`, `location_config.py`, `enum_labels.py`, `messages.py`, `archival_config.py`, …). With restaurants in **AR**, **PE**, **US**, and different schedules, **ops** need to adjust behavior **without** shipping a new backend build. A **DB-backed config** plus **admin management** is the professional pattern.

---

## Code inventory — laundry list (migrate candidates)

Below is a **repo survey** of `app/config/*`, `app/i18n/*`, and related modules. Use it for backlog grooming: not everything should move to DB (see **Tier D**).

### Tier A — High ops value (schedule, geography, copy, retention)

| Source | What it holds | Consumers (examples) |
|--------|----------------|----------------------|
| **`app/config/market_config.py`** | `MarketConfiguration.MARKETS`: per **weekday** `kitchen_close`, `billing_run`, `reservations_open`, `enabled`; **business_hours** open/close; **`address_street_order`**; **`billing_delay_minutes`** / **`reservation_opens_delay_minutes`** | `kitchen_day_service`, `date_service`, `billing_events` cron, `kitchen_start_promotion` cron, `restaurant_explorer_service`, `address_formatting` |
| **`app/config/location_config.py`** | `LOCATIONS`: `location_id` → `market` (country code) + IANA **timezone** (US split into Eastern/Central/Mountain/Pacific) | `kitchen_start_promotion`, `billing_events` |
| **`app/i18n/enum_labels.py`** | Static **enum display labels** per locale | `GET /api/v1/enums`, `get_label` |
| **`app/i18n/messages.py`** | Stub **message catalog** (`get_message`) | Future error handlers / routes (Phase 7 i18n) |
| **`app/config/archival_config.py`** + **`settings.RETENTION_PERIODS`** | **Category SLA**, `TABLE_CATEGORY_MAPPING`, defaults; **settings** also has a separate `RETENTION_PERIODS` dict used as high-level buckets | Archival crons, `get_table_archival_config`, hybrid read of DB + Python |

### Tier B — Reference / geo (often “data” more than “config”)

| Source | What it holds | Notes |
|--------|----------------|--------|
| **`app/config/supported_cities.py`** | `SUPPORTED_CITIES` tuples; `GLOBAL_CITY_*` constants | Drives **seed** and validation; runtime list is **`city_info`** (see below). |
| **`app/config/supported_provinces.py`** | `SUPPORTED_PROVINCES` tuples | **No `province_info` table** — provinces only in config + derived APIs. **Higher effective priority than generic Tier B:** new US states or Argentine provinces require a **code deploy** today; they feed **address validation** and **`TimezoneService.PROVINCE_TIMEZONE_MAPPING`** (US timezone derivation). Treat **province reference data** as **Tier A-adjacent** when launch geographies expand; consider **`province_info`** (or DB-backed list with admin API) **before** or **alongside** `location_info` if ops must add regions without deploy. |
| **`app/config/supported_countries.py`** | `SUPPORTED_COUNTRY_CODES` for market create / `GET /countries` | Policy list (Americas); could stay code or become a small reference table if ops add countries without deploy. |
| **`app/config/supported_currencies.py`** | Currency codes used in validation / UX | Backed by **`credit_currency_info`** for real rows; file is auxiliary. |
| **`app/config/supported_cuisines.py`** | Cuisine names for seed / checks | **`cuisine_info`** (or equivalent) in DB for live data. |
| **`app/config/supported_cities_bounds.py`** | **`CITY_BOUNDS`**: lat/lng bounding boxes per `(country, province, city)` | Autocomplete **locationRestriction**; **not** on `city_info` today. |
| **`app/config/supported_cities_default_location.py`** | **`CITY_DEFAULT_LOCATION`**: default center **lat/lng** per city | Explore / map focus; **not** on `city_info` today. |

### Tier C — Product tuning / environment (lower priority for DB)

| Source | What it holds | DB? |
|--------|----------------|-----|
| **`app/config/recommendation_config.py`** | Favorite weights, recommendation threshold | **Tier C for MVP** — usually stay in code or feature flags. **Promote to Tier A post-launch** when recommendation tuning becomes a **regular** ops/data-science activity. Consider a generic **`ops_settings`** table `(key, value, description, modified_by, modified_date)` as an escape hatch for **low-frequency numeric tuning** that does not justify a dedicated table (weights, thresholds, rate limits). Validate `value` type per key in application code. |
| **`app/config/address_autocomplete_config.py`** | `ADDRESS_AUTOCOMPLETE_MIN_CHARS` (env) | **Env / settings** is appropriate; optional `ops_settings` table if needed. |
| **`app/config/settings.py`** | Secrets, pool, Stripe, GCS, **`SUPPORTED_LOCALES`**, feature flags | **Secrets never** in DB as plain text; only non-secret tunables are candidates. |

### Tier D — Keep in code (engineering contracts)

| Source | Why not DB-first |
|--------|------------------|
| **`app/config/filter_registry.py`** | Maps API query params → SQL columns; **code review** territory. |
| **`app/config/restricted_institutions.py`** | Hard safety rules (Vianda Customers / Enterprises); tied to **seed UUIDs** in settings. |
| **`app/config/enums/*.py`** | Canonical **enum values** match PostgreSQL enums; changes are **schema** + deploy, not ops UI. |

---

## Extend existing tables vs new tables

| Need | Already in DB | Prefer **extend** | Prefer **new table** |
|------|----------------|------------------|------------------------|
| Market **timezone**, default **kitchen close**, **`language`** | **`market_info`**: `timezone`, `kitchen_close_time`, `language` (+ admin **`PUT /api/v1/markets/{id}`**) | Use **`market_info`** for **one** default time per market if product accepts a single cutoff | **`market_kitchen_config`** when **per-weekday** (and future per-day overrides) differ from a single column — avoids wide `market_info` or fragile JSON without history |
| **US multi-timezone** cron locations | `market_info` is one row per **country** (one US market) | Do **not** duplicate US rows per TZ | **`location_info`** (or `cron_location`) keyed by `US-Eastern`, … → `market_id` + `timezone` |
| City **bounds** / **default map center** | **`city_info`**: `city_id`, `name`, `country_code`, `province_code` only | Add nullable **`bounds_south`**, **`bounds_west`**, **`bounds_north`**, **`bounds_east`**, **`default_lat`**, **`default_lng`** (or one **JSONB** column) to **`city_info`** | Separate table only if many alternate centers per city (unlikely) |
| Enum **labels** | N/A | N/A | **`enum_label`** (natural key `(enum_type, code, locale)`) — too wide for `market_info` |
| **Messages** | N/A | N/A | **`message_translation`** (Phase 7) |
| **Per-table archival** policy | **`archival_config`** + **`archival_config_history`** | **Extend** admin CRUD already on `archival_config` | Category **defaults** could move from Python into **`archival_category_defaults`** only if product wants DB-editable SLAs separate from per-table rows |
| Province list | No `province_info`; ties to **`TimezoneService.PROVINCE_TIMEZONE_MAPPING`** | Add **`province_info`** (FK to `market_info` or `country_code`) when adding states/provinces must **not** require deploy — **prioritize** if expanding US/AR coverage is on the critical path | Or keep config-driven `GET /provinces` only for stable geographies |

**Duplication alert:** `market_info.kitchen_close_time` and `market_config.py` both express “kitchen close” today — **consolidate** during migration (single source: either column for default only + child table for per-day, or only child table with a view/default).

---

## Existing APIs vs net-new work

### Already manage DB records (reuse or extend)

| Area | Route prefix (typical) | What exists today |
|------|-------------------------|-------------------|
| **Markets** | **`/api/v1/markets`** (`app/routes/admin/markets.py`) | **GET/POST/PUT/DELETE** markets; body includes `timezone`, `kitchen_close_time`, `language`, currency, etc. **Internal** for writes; broad read access for lists. **Does not** expose per-weekday kitchen/billing rows from `market_config.py`. |
| **Archival policy** | **`/api/v1/admin/archival-config`** (`app/routes/admin/archival_config.py`) | **GET** list, **GET** by table, **POST/PUT/DELETE** config rows, **history**, **refresh-cache**, categories, priority order. |
| **Archival runs** | **`/api/v1/admin/archival`** | Stats, manual archive, retention policy **read**, health — operational, not the same as editing `archival_config` rows. |
| **Cities** | **`/api/v1/cities`** | **GET** list from **`city_info`** (no public admin CRUD in this router). Adding a city today is **seed / SQL**, not a documented Internal admin flow. |
| **Countries / provinces / currencies / cuisines** | **`/api/v1/countries`**, **`/provinces`**, **`/currencies`**, **`/cuisines`** | Mostly **read** reference APIs backed by DB or config; confirm per-router whether **Internal write** exists before assuming ops can edit. |

### Net-new (expected for Phase 9)

| Capability | Suggested surface |
|------------|-------------------|
| Per-market **per-day** kitchen / billing / reservations | **`GET/PUT /api/v1/admin/markets/{market_id}/kitchen-config`** (or nested resource under markets) |
| **Cron location** rows (`US-Eastern`, …) | **`GET/PUT /api/v1/admin/locations`** or **`/admin/cron-locations`** |
| **Enum labels** | **`GET/PUT /api/v1/admin/enum-labels`** |
| **Message translations** | **`GET/PUT /api/v1/admin/translations`** (Phase 7) |
| **City bounds / map defaults** | Prefer **extending Internal market/city admin** (if added) or **`PUT /api/v1/admin/cities/{city_id}`** with new columns — **new** if city admin CRUD does not exist yet |

---

## Staged migration strategy (per subsystem)

Use the same pattern for each area so there is **no big-bang breaking change**:

| Stage | Behavior |
|-------|----------|
| **Phase 1** | Keep config file; **add** DB table and optional seed. Writers go to DB only when admin exists; readers unchanged or feature-flagged. |
| **Phase 2** | **Read from DB first**; **fallback** to config file if row missing or cache miss. |
| **Phase 3** | **DB is authoritative**; remove or shrink config file to dev-only defaults / tests. |
| **Phase 4** | **Admin API + UI** for runtime edits; audit/history where required. |

The config file remains a **safety net** until data in DB is verified in production-like environments.

---

## Post-MVP priority order

1. **`market_kitchen_config`** — Ops need this most (restaurant-adjacent schedule and billing window changes per market).
2. **`location_info`** (or equivalent) — Needed when adding markets/timezones without code changes; infra (e.g. Pulumi) can read DB or call API.
3. **`message_translation`** — Aligns with i18n **Phase 7** in the language roadmap.
4. **`enum_label`** — Lower priority; labels change rarely vs hours and copy.
5. **Archival config** — Complete migration; retention is already partially DB-driven.

6. **Province reference** (when needed) — If ops must add provinces/states without deploy, **`province_info`** + admin API **before** heavy investment in city bounds alone; coordinate with **`TimezoneService`** / US timezone mapping.

---

## 9.1 Market kitchen config (`market_config.py` → DB)

**Goal:** Per-market, per–kitchen-day open/close, billing run time, reservations window — editable by Internal users.

**Overlap with today’s DB:** `market_info` already stores **`timezone`**, **`kitchen_close_time`** (single `TIME`), and **`language`**, and **`PUT /api/v1/markets/{market_id}`** updates them. Python **`market_config.py`** goes further: **per weekday** cutoffs, **business_hours**, **`address_street_order`**, and **delay minutes** used to derive times. Migration should **reconcile** one default vs many rows (see inventory **Duplication alert** above).

**Illustrative schema** (exact names subject to schema review; new rows use UUID7 per project standards):

```sql
CREATE TABLE market_kitchen_config (
    config_id UUID PRIMARY KEY DEFAULT uuidv7(),
    market_id UUID NOT NULL REFERENCES market_info(market_id),
    day_of_week kitchen_day_enum NOT NULL,
    kitchen_open TIME NOT NULL,
    kitchen_close TIME NOT NULL,
    billing_run TIME NOT NULL,
    reservations_open TIME NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    modified_by UUID NOT NULL REFERENCES user_info(user_id),
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    -- Add UNIQUE(market_id, day_of_week) where one row per day per market
);
```

### Address display order (`address_street_order`)

**Today:** `DEFAULT_ADDRESS_STREET_ORDER` and per-market **`address_street_order`** lists in `market_config.py` control how `format_street_display` orders components (e.g. US: number before name; AR/PE: type + name + number). This is **per market**, not per day — **do not** put it in `market_kitchen_config`.

**Preferred shape:** extend **`market_info`** with a single discriminant (simpler than a new table):

```sql
-- Illustrative: map UI semantics to one column per market
ALTER TABLE market_info ADD COLUMN IF NOT EXISTS
  address_street_order VARCHAR(20) NOT NULL DEFAULT 'number_first'
  CHECK (address_street_order IN ('number_first', 'street_first'));
```

- **`number_first`:** e.g. building number before street name (typical US-style ordering in concatenated display).
- **`street_first`:** e.g. street type + name + number (typical AR/PE-style).

**Implementation note:** Today’s Python config uses **ordered field name lists**; migrate by mapping those lists to these two modes (or add more CHECK values if product requires). Expose the field on **`MarketUpdateSchema`** / existing admin **`PUT /api/v1/markets/{market_id}`** so ops can switch display mode without deploy. **Invalidate** any cache used by address formatting after market update (see **Cache invalidation** below).

**Admin APIs (examples):**

- **Per-day kitchen / billing / reservations:** `GET` / `PUT /api/v1/admin/markets/{market_id}/kitchen-config` (Internal-only; net-new resource).
- **Market-level row** (existing): `PUT /api/v1/markets/{market_id}` — already covers `timezone`, `kitchen_close_time`, `language`; add **`address_street_order`** here (not under `kitchen-config`).

**Runtime:**

- **Cron jobs** and services that today read `market_config.py` read from **DB** (with cache).
- **Cache:** TTL and **on-write invalidation** per **Cache invalidation** section below.
- **History:** `market_kitchen_config_history` (or generic audit) for who changed what and when.

---

## 9.2 Location config (`location_config.py` → DB)

**Goal:** Map logical **location keys** (e.g. `AR`, `US-Eastern`) to **`market_id`** and **IANA timezone** without redeploying Python maps.

**Illustrative schema:**

```sql
CREATE TABLE location_info (
    location_id VARCHAR(20) PRIMARY KEY,  -- e.g. 'AR', 'US-Eastern'
    market_id UUID NOT NULL REFERENCES market_info(market_id),
    timezone VARCHAR(50) NOT NULL,        -- IANA, e.g. America/Argentina/Buenos_Aires
    modified_by UUID NOT NULL REFERENCES user_info(user_id),
    modified_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**Consumers:**

- **Pulumi / scheduler:** Read at deploy time, or call Internal API to resolve location → timezone.
- **Backend:** Any code that today imports `location_config` should eventually resolve via a cached DB lookup.

Adding a new US timezone region becomes a **DB insert** (plus admin UI), not a PR.

---

## 9.3 Enum labels (`app/i18n/enum_labels.py` → DB)

**Goal:** Ops or content can adjust display labels per locale without deploy; API still returns **canonical codes** in `values`.

**Illustrative schema:**

```sql
CREATE TABLE enum_label (
    enum_type VARCHAR(50) NOT NULL,
    code VARCHAR(50) NOT NULL,
    locale VARCHAR(5) NOT NULL,
    label VARCHAR(200) NOT NULL,
    PRIMARY KEY (enum_type, code, locale)
    -- Optional: modified_by, modified_date, is_active
);
```

**Admin API (example):**

- `GET /api/v1/admin/enum-labels?locale=es`
- `PUT /api/v1/admin/enum-labels` (batch or per-row; Internal-only)

**Runtime:**

- `GET /api/v1/enums` (and `get_label`) resolve labels from **DB** with fallback chain: **DB → static `enum_labels.py` → `en` → code** during migration; later DB + `en` + code only.
- **Cache aggressively** — labels change rarely; invalidate on admin update.

---

## 9.4 Message translations (`messages.py` → DB)

**Already described** in [LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md](./LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md) **Phase 7**:

- Table such as **`message_translation`** (`message_key`, `locale`, `text`, `is_active`, …).
- Admin `GET/PUT /api/v1/admin/translations` (Internal-only).
- Cache + fallback: **DB → static `messages.py` → `en` → key**.

Phase 9 treats **message_translation** as the same class of operational config as kitchen and location; implement **after** or **in parallel** with Phase 7 i18n work, not duplicated specs here.

---

## 9.5 Archival config (complete DB + admin)

**Today:** Hybrid — **`archival_config`** / **`archival_config_history`** tables (`app/db/archival_config_table.sql`), full **CRUD-style** API at **`/api/v1/admin/archival-config`**, plus **`app/config/archival_config.py`** for **`TABLE_CATEGORY_MAPPING`**, **`CATEGORY_SLA_CONFIG`** fallbacks, and merge logic when DB rows are missing. **`settings.RETENTION_PERIODS`** is a **second** bucket-style dict (category names like `orders`, `user_data`) — understand whether it is still authoritative for any path or redundant with `archival_config`; **converge** during this phase.

**Goal:**

- **Remove remaining hardcoded** values from `archival_config.py` (and trim **`settings.RETENTION_PERIODS`** if superseded) that should be operator-tunable.
- **Extend** existing **`/api/v1/admin/archival-config`** where possible instead of inventing parallel routes.
- **Admin UI** for retention policies without deploy.
- Keep **history** (`archival_config_history`) for compliance.

See also: `docs/archival/ARCHIVAL_CRON_STRATEGY.md`, `docs/guidelines/database/DATABASE_REBUILD_PERSISTENCE.md`.

---

## 9.6 City bounds, default map center, and Google `locationRestriction`

**Goal:** Move **`supported_cities_bounds.py`** and **`supported_cities_default_location.py`** onto **`city_info`** (nullable **`bounds_*`**, **`default_lat`**, **`default_lng`** — or a single **JSONB** column per concern).

### Fallback chain for `locationRestriction` (autocomplete)

When building **Google Maps `locationRestriction`** (or equivalent), use this **explicit** order so behavior stays predictable during staged migration:

| Phase | Source | Behavior |
|-------|--------|----------|
| **Phase 1** | **`city_info`** nullable bounds columns | If all **`bounds_south/west/north/east`** (or JSONB equivalent) are **non-NULL** for the resolved city → use them for **locationRestriction**. |
| **Phase 2** | **`supported_cities_bounds.py`** | If DB bounds are **NULL** → fall back to the static dict keyed by `(country_code, province_code, city_name)` (same key shape as today). |
| **Phase 3** | **Country-level bounds** | If file fallback also misses (unknown city) → optional **country-level** bounding box from a small config table or static map by `country_code` (product-defined). |
| **Phase 4** | **No restriction** | When the static file is **removed** and DB/file/country all absent → **omit locationRestriction** (wider suggestions; monitor cost and quality). Document this as intentional for that city until ops add bounds in admin UI. |

**Phase 2** of *migration* (dual read) matches “DB first, file fallback”; **Phase 4** above is the *runtime* stage when config files are gone — do not confuse with the global “Staged migration strategy” section numbering.

**Default center for Explore / map focus:** Apply the same pattern: **`city_info.default_lat/lng`** → fallback **`CITY_DEFAULT_LOCATION`** → country or app default.

---

## Security, access, and cache invalidation

### Access

- All **admin** endpoints: **`role_type` Internal** (and tighter roles if needed, e.g. Super Admin only for destructive changes).
- **Audit columns** and **history tables** for kitchen config, enum labels, and messages where product requires traceability.

### Cache invalidation (consistent pattern)

Any **admin write** that mutates DB-backed config consumed through a cache must **invalidate** (or bump a version key) **after** a successful commit. Use **`POST /api/v1/admin/archival-config/refresh-cache`** as the **model**: either **automatic invalidation on every successful PUT/POST** for that subsystem, or a dedicated **`POST .../refresh-cache`** for batch warm-up — **pick one pattern per subsystem** and document it in the route docstring.

**Documented TTL targets** (tune in implementation; invalidate on write regardless):

| Subsystem | Suggested TTL | Rationale |
|-----------|----------------|-----------|
| **`market_kitchen_config`** (incl. cron readers) | **5 minutes** | Changes should affect **next cron tick** without hammering DB. |
| **`location_info`** | **60 minutes** | Changes rarely; Pulumi/infra may read at deploy time. |
| **`enum_label`** | **60 minutes** | Changes rarely. |
| **`message_translation`** | **15 minutes** | Copy changes should propagate **reasonably quickly** to users. |
| **`market_info`** fields (incl. **`address_street_order`**, `kitchen_close_time`) | **Invalidate on write** via existing market update path; if cached separately, **5 minutes** or on-write. |

---

## Summary checklist for implementers

- [ ] **9.1** `market_kitchen_config` + admin CRUD + cron reads DB + TTL cache + history  
- [ ] **9.1b** **`market_info.address_street_order`** (or equivalent) + admin market PUT + address-formatting cache invalidation  
- [ ] **9.2** `location_info` + admin + consumers updated (Pulumi/backend)  
- [ ] **9.3** `enum_label` + admin + `get_label` / enums route reads DB + cache  
- [ ] **9.4** Align with Phase 7 `message_translation` + `get_message`  
- [ ] **9.5** Finish archival: DB/UI authoritative; trim `archival_config.py` to tests/dev only  
- [ ] **9.6** City bounds + default lat/lng on `city_info` + **locationRestriction fallback chain** (§9.6) implemented in address/autocomplete gateway  
- [ ] Apply **staged migration** (dual read → DB primary → remove file fallback) per subsystem  
- [ ] **Cache:** Admin writes call shared invalidation (or per-resource refresh); TTLs documented per subsystem  
- [ ] **Review cadence:** Re-run **laundry list** after each major feature addition (new `app/config/*.py` or large `settings.py` dicts)  
- [ ] **Review cadence:** Audit **hardcoded dicts in `settings.py`** quarterly for ops-tunable candidates  

---

## References (current code / docs)

| Area | Current artifacts |
|------|-------------------|
| Market / kitchen timing | `app/config/market_config.py`; DB: `market_info` (`schema.sql`); API: `app/routes/admin/markets.py` |
| Location / cron TZ regions | `app/config/location_config.py`; crons: `app/services/cron/kitchen_start_promotion.py`, `app/services/cron/billing_events.py` |
| Kitchen / billing logic | `app/services/kitchen_day_service.py`, `app/services/date_service.py`, `docs/billing/*` |
| Enum labels (MVP) | `app/i18n/enum_labels.py`; route: `app/routes/enums.py` |
| Messages (MVP) | `app/i18n/messages.py` |
| Archival | `app/config/archival_config.py`, `app/db/archival_config_table.sql`, `app/routes/admin/archival_config.py`, `app/config/settings.py` → `RETENTION_PERIODS`, `AUTO_ARCHIVAL_ENABLED`, `ARCHIVAL_GRACE_PERIOD` |
| City / map tuning | `app/config/supported_cities*.py`, `supported_cities_bounds.py`, `supported_cities_default_location.py`; DB: `city_info` |
| Address display order | `DEFAULT_ADDRESS_STREET_ORDER` + per-market overrides inside `market_config.py` |
| Reference lists | `supported_provinces.py`, `supported_countries.py`, `supported_currencies.py`, `supported_cuisines.py` |
| Engineering-only | `filter_registry.py`, `restricted_institutions.py`, `app/config/enums/*` |
| Timezone / province mapping | `TimezoneService` / `PROVINCE_TIMEZONE_MAPPING` (see services); ties to **province** reference data |

**Ongoing:** See **Summary checklist** — review cadence items for laundry list and `settings.py` audits.
