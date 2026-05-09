# Mapbox Migration Roadmap

**Last Updated**: 2026-05-09
**Purpose**: Mapbox is the sole provider for geocoding, address autocomplete, and maps. This roadmap covers the remaining work to move from ephemeral free-tier usage to permanent storage of address data.

---

## Executive Summary

Google Places + Geocoding APIs have been retired. Their keys are removed from the repo. Mapbox is now the only address provider; there is no Google fallback path.

Mapbox offers two geocoding tiers that align with our growth trajectory:

1. **Temporary (ephemeral)** — free tier of 100K requests/month, results cannot be stored in DB
2. **Permanent** — $5/1,000 requests, results can be stored and reused indefinitely

This roadmap has two phases:

| Phase | Priority | What | Why |
|-------|----------|------|-----|
| **Phase 1** | **Done** | Mapbox ephemeral APIs in production | Address functionality restored on the free tier during early launch |
| **Phase 2** | **Medium** | Switch to Mapbox permanent APIs for DB storage | Scale without re-querying — store coordinates and address components permanently |

---

## Current State vs Target

| Aspect | Phase 1 (Mapbox Ephemeral — shipped) | Phase 2 Target (Mapbox Permanent) |
|--------|--------------------------------------|-----------------------------------|
| Address autocomplete | Search Box API `/suggest` + `/retrieve` | Same as Phase 1 (autocomplete is always session-based) |
| Address resolution | Search Box `/retrieve` by `mapbox_id` | Geocoding v6 `permanent=true` |
| Geocoding | Geocoding v6 (temporary) | Geocoding v6 (`permanent=true`) |
| Reverse geocoding | Geocoding v6 reverse (temporary) | Geocoding v6 reverse (`permanent=true`) |
| Data storage | **No DB storage** — always query API | All fields stored in DB (ToS compliant) |
| Coordinates in DB | Query on demand, cache in session only | Stored permanently in `geolocation_info` |
| Cost | **Free** (100K geocode + ~500 search sessions/month) | $5/1,000 permanent geocode requests |

---

## Mapbox API Primer

### Search Box API (Address Autocomplete)

Two-step suggest/retrieve flow — equivalent to Google Places Autocomplete:

1. **Suggest** (`GET /search/searchbox/v1/suggest`): User types → returns suggestions with `mapbox_id` (no coordinates)
2. **Retrieve** (`GET /search/searchbox/v1/retrieve/{mapbox_id}`): User selects → returns full GeoJSON with coordinates and address components

**Session rules:**
- One session = one or more `/suggest` calls + one `/retrieve` call, sharing a `session_token` (UUIDv4)
- Session expires after 180 seconds of inactivity
- Max 50 `/suggest` calls per session
- Billed per session, not per request

**Storage:** All Search Box data is **temporary only**. To store results, use the Geocoding API with `permanent=true` instead.

### Geocoding API v6

| Mode | Endpoint | Storage Allowed | Free Tier | Cost After |
|------|----------|-----------------|-----------|------------|
| Temporary | `GET /search/geocode/v6/forward` | No | 100,000/month | $0.75/1,000 |
| Permanent | `GET /search/geocode/v6/forward?permanent=true` | **Yes** | Shared quota | $5.00/1,000 |
| Reverse | `GET /search/geocode/v6/reverse` | Same rules | Same quota | Same rates |
| Batch | `POST /search/geocode/v6/batch` | Permanent only | Same quota | Same rates |

**Key parameters:** `q`, `country` (ISO alpha-2), `language`, `types`, `proximity`, `limit` (1-10), `permanent` (boolean)

**Response:** GeoJSON FeatureCollection with structured `context` hierarchy (country → region → postcode → district → place → locality → neighborhood → street → address).

### Maps SDK (Mapbox GL JS)

- 50,000 free map loads/month (web)
- 25,000 free MAU/month (mobile)
- A "map load" = one `Map` object initialization; interactions don't count as additional loads

---

## Affected Files

### Gateway Layer (replace/add)

| File | Current Role | Migration Action |
|------|-------------|-----------------|
| `app/gateways/mapbox_search_gateway.py` | Search Box suggest + retrieve | Phase 1: shipped. Phase 2: no change |
| `app/gateways/mapbox_geocoding_gateway.py` | Forward + reverse geocoding | Phase 1: shipped. Phase 2: pass `permanent=true` for storable calls |
| `app/gateways/mapbox_static_gateway.py` | Static map images | Phase 1: shipped |
| `app/gateways/base_gateway.py` | Abstract base with dev/prod switching | No change |
| `app/gateways/google_places_gateway.py` / `app/gateways/google_maps_gateway.py` | _Removed._ Google keys are out of the repo and these gateways are no longer wired | Delete any remaining references during Phase 2 schema cleanup |

### Service Layer (refactor)

| File | Current Role | Migration Action |
|------|-------------|-----------------|
| `app/services/address_autocomplete_service.py` | Orchestrates suggest via Google Places | Phase 1: Switch to Mapbox Search Box gateway |
| `app/services/address_autocomplete_mapping.py` | Maps Google Places response → address fields | Phase 1: Rewrite for Mapbox GeoJSON response format |
| `app/services/address_service.py` | Business logic, calls `_resolve_address_from_place_id()` | Phase 1: Replace place_id resolution with `mapbox_id` resolution |
| `app/services/geolocation_service.py` | Geocoding wrapper around Google Maps gateway | Phase 1: Switch to Mapbox Geocoding gateway |

### Database (Phase 2 changes)

| File | Migration Action |
|------|-----------------|
| `app/db/schema.sql` | Phase 2: Add `mapbox_id VARCHAR(255)` to `geolocation_info`; rename `formatted_address_google` → `formatted_address`; drop the legacy `place_id` column |
| `app/db/trigger.sql` | Phase 2: Mirror new columns in `audit.geolocation_history` |
| `app/dto/models.py` | Phase 2: Add `mapbox_id` to `GeolocationDTO` |
| `app/schemas/consolidated_schemas.py` | Phase 2: Add `mapbox_id` to response schemas |

### Configuration

| File | Migration Action |
|------|-----------------|
| `app/config/settings.py` | Phase 1: shipped — `MAPBOX_ACCESS_TOKEN_DEV/STAGING/PROD` + `get_mapbox_access_token()`. `ADDRESS_PROVIDER` is fixed to `mapbox`; the multi-provider toggle was removed when Google was retired |
| `.env.example` | Phase 1: Add `MAPBOX_ACCESS_TOKEN_DEV=` |

### Mocks

| File | Migration Action |
|------|-----------------|
| `app/mocks/address_autocomplete_mocks.json` | Phase 1: Add Mapbox suggest/retrieve mock responses |
| `app/mocks/google_maps_responses.json` | Delete during Phase 2 cleanup — Google is no longer a provider |

### Tests

| File | Migration Action |
|------|-----------------|
| `app/tests/gateways/test_google_maps_gateway.py` | Delete during Phase 2 cleanup — Google gateway is retired |
| `app/tests/services/test_address_autocomplete_service.py` | Phase 1: Update for Mapbox flow |
| `app/tests/services/test_address_autocomplete_mapping.py` | Phase 1: Rewrite for Mapbox GeoJSON mapping |

---

## Phase 1: Mapbox Ephemeral Integration (High Priority)

**Goal:** Restore address autocomplete and geocoding using Mapbox free tier. No DB storage of Mapbox results — always query the API. This mirrors how Google *should* have been used, but now with Mapbox's generous free tier.

**Functional parity constraint:** The migration must not change any behavior visible to clients. Address autocomplete suggestions, geolocation data powering the B2C explore map icons, and all address detail fields exposed to customers must continue to work identically. Client-facing response schemas (`AddressSuggestResponse`, `AddressResponse`, `GeolocationResponse`) must remain structurally unchanged — the provider swap is a backend-internal concern. Any new fields (e.g., `mapbox_id`) are additive; no existing fields are removed or renamed in API responses during Phase 1.

### 1.1 — Mapbox Search Box Gateway

Create `app/gateways/mapbox_search_gateway.py`:

```
MapboxSearchGateway(BaseGateway)
├── suggest(query, country, language, session_token, limit) → list[suggestion]
├── retrieve(mapbox_id, session_token) → GeoJSON Feature
```

**Suggest response mapping:**

| Mapbox Field | Internal Field |
|-------------|----------------|
| `suggestions[].name` | `display_text` (primary line) |
| `suggestions[].full_address` | `display_text` (fallback if name insufficient) |
| `suggestions[].mapbox_id` | `mapbox_id` (replaces `place_id` in suggest flow) |
| `suggestions[].address` | Structured address preview |
| `suggestions[].context` | Country, region, place hierarchy |

**Retrieve response mapping (GeoJSON Feature):**

| Mapbox Field | Internal Field | DB Column |
|-------------|----------------|-----------|
| `properties.context.country.country_code` | `country_code` | `address_info.country_code` |
| `properties.context.region.name` | `province` | `address_info.province` |
| `properties.context.place.name` | `city` | `address_info.city` |
| `properties.context.postcode.name` | `postal_code` | `address_info.postal_code` |
| `properties.context.street.name` | `street_name` | `address_info.street_name` |
| `properties.context.address.address_number` | `building_number` | `address_info.building_number` |
| `geometry.coordinates[1]` | `latitude` | _(not stored in Phase 1)_ |
| `geometry.coordinates[0]` | `longitude` | _(not stored in Phase 1)_ |
| `properties.mapbox_id` | `mapbox_id` | _(not stored in Phase 1)_ |

### 1.2 — Mapbox Geocoding Gateway

Create `app/gateways/mapbox_geocoding_gateway.py`:

```
MapboxGeocodingGateway(BaseGateway)
├── geocode(address_string, country, language) → {latitude, longitude, mapbox_id, formatted_address, context}
├── reverse_geocode(latitude, longitude, language) → {formatted_address, address_components, context}
├── geocode_structured(address_number, street, place, region, postcode, country) → same as geocode
```

All calls use `permanent=false` (default) in Phase 1.

### 1.3 — Rewrite Address Autocomplete Mapping

Rewrite `app/services/address_autocomplete_mapping.py` for Mapbox GeoJSON:

**Key differences from Google Places mapping:**

| Concern | Google Places | Mapbox Search Box |
|---------|--------------|-------------------|
| Address components | Flat array of `{longText, types[]}` | Nested `context` hierarchy |
| Street type extraction | Parse from `route` name ("Avenida San Martín" → Ave) | Same logic applies to `context.street.name` |
| Country code format | Alpha-2 in response | Alpha-2 in `context.country.country_code` |
| Coordinates | `location.latitude/longitude` | `geometry.coordinates` (GeoJSON: `[lng, lat]`) |
| Place identifier | `place_id` (Google-proprietary) | `mapbox_id` |

### 1.4 — Provider Abstraction

`ADDRESS_PROVIDER` is fixed to `mapbox` in `app/config/settings.py`. The setting exists so a future second provider (e.g., Smarty for an international market with poor Mapbox coverage — see Risk Assessment) can be wired in without refactoring `address_autocomplete_service.py` or `geolocation_service.py`. Until that contingency materialises, only the Mapbox gateway is registered.

### 1.5 — Session Token Management

Mapbox Search Box requires a `session_token` (UUIDv4) shared across suggest + retrieve calls.

**Implementation:** The client generates a session token when the user starts typing and passes it as a query parameter on both `/addresses/suggest` and the subsequent `POST /addresses`. The backend forwards it to Mapbox.

**API change:**

```
GET /api/v1/addresses/suggest?q=Av+San&country=AR&session_token=<uuid>
POST /api/v1/addresses { mapbox_id: "...", session_token: "..." }
```

The `session_token` is optional — if omitted, the backend generates one per request (suboptimal for billing but functional).

### 1.6 — Geolocation in Ephemeral Mode

In Phase 1, coordinates are **not stored in DB**. Instead:

- `geolocation_info` rows are still created but with `latitude=0, longitude=0` as placeholders (or the table is made optional for this phase)
- Any feature that needs coordinates (distance calculation, map display) calls the Mapbox Geocoding API on demand using the stored address string
- `mapbox_id` is stored in `geolocation_info.place_id` column temporarily (both are opaque string identifiers)

**Trade-off:** Higher API call volume but fully ToS-compliant and within free tier for testing/early users.

### 1.7 — Mock Data

Add Mapbox mock responses to `app/mocks/address_autocomplete_mocks.json` following the GeoJSON format. Use realistic Argentine addresses to match existing test data.

### Phase 1 Deliverables

- [ ] `mapbox_search_gateway.py` — suggest + retrieve
- [ ] `mapbox_geocoding_gateway.py` — geocode + reverse geocode
- [ ] Rewritten `address_autocomplete_mapping.py` for Mapbox GeoJSON
- [ ] `ADDRESS_PROVIDER` config toggle
- [ ] `session_token` support on suggest + create endpoints
- [ ] Updated mock data
- [ ] Updated tests
- [ ] Updated `CLAUDE_ARCHITECTURE.md` gateway section

---

## Phase 2: Mapbox Permanent Storage (Medium Priority)

**Goal:** Switch from ephemeral to permanent geocoding so coordinates and address components are stored in DB — same data model as today, but Mapbox-sourced and ToS-compliant.

### 2.1 — Enable Permanent Geocoding

Change geocoding calls to include `permanent=true`:

```
GET /search/geocode/v6/forward?q=...&permanent=true
```

This is a one-parameter change in the gateway but has billing implications ($5/1,000 vs free).

### 2.2 — Schema Changes

**`geolocation_info` table updates:**

```sql
-- Add Mapbox-specific identifier
ALTER TABLE core.geolocation_info ADD COLUMN mapbox_id VARCHAR(255) NULL;

-- Rename Google-era column to provider-neutral name
ALTER TABLE core.geolocation_info RENAME COLUMN formatted_address_google TO formatted_address;

-- Drop legacy Google place_id column (Google provider is retired)
ALTER TABLE core.geolocation_info DROP COLUMN IF EXISTS place_id;
```

Follow the schema change protocol: `schema.sql` → `trigger.sql` → `seed.sql` → `models.py` → `consolidated_schemas.py`

### 2.3 — Restore Full Geolocation Storage

Re-enable the address creation flow that stores coordinates:

1. `POST /addresses` with `mapbox_id` → call Mapbox Geocoding `permanent=true` to get coordinates
2. Store `latitude`, `longitude`, `mapbox_id`, `formatted_address`, `viewport` in `geolocation_info`
3. Distance calculations, map display, and explore features read from DB instead of querying API

### 2.4 — Batch Backfill

For addresses created during Phase 1 (ephemeral mode) that have no stored coordinates:

- Use Mapbox Batch Geocoding API (`POST /search/geocode/v6/batch`) with `permanent=true`
- Process up to 1,000 addresses per request
- One-time backfill script or cron job

### 2.5 — Strategic Ephemeral vs Permanent by Address Context (Cost Optimization)

The switch from ephemeral to permanent does not need to be all-or-nothing. Different address types and user states have different storage economics:

**Addresses worth storing permanently (high reuse, shared across users):**
- **Restaurant addresses** — queried by every customer browsing the explore map; geocoded once, displayed thousands of times
- **Institution entity addresses** (employers, pickup points) — shared by all employees in a benefit program; used on invoicing
- **Customer home/work addresses for subscribed users** — needed for delivery, invoicing, and recurring display

**Addresses NOT worth storing permanently (low reuse, speculative):**
- **Unsubscribed customer addresses** — a user may register, enter their home/work address, and never return. Paying $5/1,000 to permanently store addresses for users who never convert is waste
- **Lead/prospect addresses** — address entered during exploration before any commitment

**Implementation approach:**

The decision to use `permanent=true` is made at geocoding time based on:

1. **Address type** (`address_type_enum`): Restaurant, Employer, Pickup Point → always permanent. Customer Home, Customer Work → conditional.
2. **User subscription status**: If the user has an active paid subscription → permanent. If free/trial/unsubscribed → ephemeral.

This can be implemented as a simple function in the geocoding service:

```python
def should_use_permanent_geocoding(address_type: str, user_has_active_subscription: bool) -> bool:
    # Business addresses are always worth storing
    if address_type in ("Restaurant", "Employer", "Pickup Point"):
        return True
    # Customer addresses only worth storing if they're paying
    return user_has_active_subscription
```

**Migration path for ephemeral customer addresses:** When a customer subscribes to a paid plan, a one-time job re-geocodes their addresses with `permanent=true`. This is a single batch call per new subscriber — negligible cost.

> **Note:** This optimization is not required for Phase 2 launch. Phase 2 can ship with a simple all-permanent approach and this refinement can be layered on afterward once we have usage data to justify the complexity. The schema and gateway support both modes from Phase 1 — no additional schema changes needed.

### 2.6 — Cost Monitoring

Track permanent geocoding usage to ensure it stays within budget:
- Log each permanent geocoding call with request metadata
- Alert if monthly volume approaches pricing thresholds
- Consider caching: once an address is permanently geocoded, never re-geocode it

### Phase 2 Deliverables

- [ ] `permanent=true` on all geocoding calls that feed DB storage
- [ ] Schema migration: `mapbox_id` column, `formatted_address` rename
- [ ] Full geolocation storage restored
- [ ] Batch backfill for Phase 1 addresses
- [ ] Cost monitoring / logging
- [ ] _(Optional)_ Strategic ephemeral/permanent routing by address type and subscription status
- [ ] Updated `CLAUDE_ARCHITECTURE.md`

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Mapbox address quality varies by country | Vianda operates in **major urban commercial districts** around offices — exactly where Mapbox has the strongest coverage. We do not develop markets in suburban or rural areas where quality gaps are more likely. Test per market before launch. |
| Billing/invoicing addresses may be in lower-quality areas | Customer home addresses may be in suburbs far from their workplace. However, payment aggregators (Stripe) collect billing addresses directly — we only need our own address data for invoicing features, which are institution-level (urban). For edge cases, see Smarty fallback below. |
| Phase 1 ephemeral mode means no stored coordinates | Acceptable for testing; features needing coords call API on demand |
| Mapbox Search Box data cannot be stored (even with permanent geocoding) | Use Search Box for suggest only; re-geocode via Geocoding API `permanent=true` for storage |
| Session token billing complexity | Client-generated tokens are simple; document pattern for frontend teams |
| Street type extraction logic may differ | Mapbox street names follow similar patterns; reuse existing extraction with Mapbox-specific adjustments |
| Batch backfill cost in Phase 2 | $5/1,000 addresses — budget before running; one-time cost |
| Mapbox quality insufficient in a future international market | **Contingency: Smarty** (formerly SmartyStreets). If Mapbox shows poor address/geolocation quality in a specific international market, evaluate Smarty as a targeted provider for that market's address validation and geocoding. Smarty has strong international address verification. This is not planned work — it is a contingency documented so the provider abstraction layer (Phase 1.4) can accommodate a second provider without refactoring. |

---

## Pricing

| Scenario (monthly) | Mapbox Ephemeral | Mapbox Permanent |
|--------------------|------------------|------------------|
| 1,000 autocomplete sessions | Free (within 500 free sessions) | N/A (autocomplete is session-based) |
| 10,000 geocode requests | Free (within 100K free tier) | $50.00 |
| 100,000 geocode requests | Free (at limit) | $500.00 |
| 50,000 map loads (web) | Free (within 50K free tier) | Free (maps are separate) |

**Phase 1 cost during early launch:** Effectively **$0/month** — well within Mapbox free tiers.
**Phase 2 cost at scale:** $5/1,000 permanent geocode requests — the cost we accept in exchange for legal data storage.

---

## Timeline Dependencies

```
Phase 1 (shipped) ──────────────► Phase 2
(Mapbox ephemeral)                (Mapbox permanent)

├── Google API keys removed       ├── Requires billing setup
├── Free tier                     ├── $5/1K permanent geocode calls
└── Early launch + testing        └── Scale + stored coordinates / address data
```

---

---

## Geocoding Cache (Shipped — 2026-05-09)

### Why a cache instead of locking down the dev DB

Mapbox TOS restricts long-term storage of ephemeral geocoding results, but caching **raw API responses** for replay during dev is fine (it's equivalent to caching any HTTP response). Locking the dev DB to prevent teardown would force real down-migrations on every risky schema change — a much bigger workflow tax than a 100-line cache. The cache lets us tear down freely **and** only pay Mapbox once per unique address across all devs and all rebuilds.

### Design

| File | Role |
|------|------|
| `app/gateways/mapbox_geocode_cache.py` | Cache module: `MapboxGeocodeCache`, `CacheMode`, `make_cache_key`, `MapboxCacheMiss` |
| `seeds/mapbox_geocode_cache.json` | Committed JSON cache — treat as production data, never `.gitignore` |
| `scripts/backfill_mapbox_geocoding.py` | Walk missing coordinates after rebuild, replay from cache |

### Cache key format

```
"geocode|{normalized_q}|{country}|{language}"
```

Where `normalized_q` = lowercase, trimmed, whitespace-collapsed address string.
For the default geocoding path (called without country param): `"geocode|{addr}||es"`.

### `MAPBOX_CACHE_MODE` values

| Value | Default for | Behavior on cache miss |
|-------|-------------|----------------------|
| `replay_only` | Tests + dev seed + DB rebuild | Raises `MapboxCacheMiss` — never calls Mapbox |
| `record` | Dev when adding new addresses | Calls live Mapbox API and writes response to cache |
| `bypass` | Prod | Skips cache entirely, always calls Mapbox live |

Set via env var. Setting is also exposed in `app/config/settings.py` as `MAPBOX_CACHE_MODE`.

### Adding a new address to the cache

```sh
# 1. Set a live Mapbox token (use the dev token — these are ephemeral calls):
export MAPBOX_ACCESS_TOKEN_DEV=pk.eyJ1...

# 2. Run backfill in record mode — new addresses hit the API, response is written to cache:
MAPBOX_CACHE_MODE=record PYTHONPATH=. python3 scripts/backfill_mapbox_geocoding.py

# 3. Commit the updated seeds/mapbox_geocode_cache.json.
```

### Tear-down / rebuild flow (zero Mapbox calls)

`build_kitchen_db.sh` automatically runs the backfill in `replay_only` mode after seeding:

```sh
bash app/db/build_kitchen_db.sh
# → ... seeding ...
# → Backfilling Mapbox geocoding from cache (replay_only, zero API calls)…
# [backfill-mapbox] restaurant aaaaa...: "500 Defensa, Buenos Aires, Buenos Aires, AR" → (-34.6226, -58.3701)
# [backfill-mapbox] done
```

Skip with `SKIP_GEOCODE_BACKFILL=1`.

### Schema additions (migration 0019)

Two nullable tracking columns added to `core.geolocation_info` (and mirrored in `audit.geolocation_history`):

| Column | Type | Purpose |
|--------|------|---------|
| `mapbox_geocoded_at` | `TIMESTAMPTZ NULL` | When coordinates were resolved (live or cache replay) |
| `mapbox_normalized_address` | `TEXT NULL` | Normalized query string = cache key, stored for backfill re-derivation |

---

## Infra Cutover Handoff (NOT YET EXECUTED)

**Status: documented only. Do NOT execute without explicit user confirmation.**

The current Mapbox token in use is the dev/free-tier token. Switching to the paid (permanent-storage-allowed) key requires an infra-executor task in `infra-kitchen-gcp`. Steps:

### 1. Provision paid Mapbox key in Secret Manager (infra-kitchen-gcp task)

```
# infra-executor brief (do NOT run from kitchen or this session):
# In src/components/backend.py (Pulumi):
#   - Add Secret Manager secret: mapbox_access_token_prod
#   - Mount as Cloud Run env var: MAPBOX_ACCESS_TOKEN_PROD
#   - Same for STAGING: mapbox_access_token_staging → MAPBOX_ACCESS_TOKEN_STAGING
# Confirm _DEPLOY_SA_ROLES includes secretmanager.secretAccessor for the new secrets.
```

### 2. Enable `permanent=true` in the geocoding gateway (kitchen task)

In `app/gateways/mapbox_geocoding_gateway.py`, `_make_request()`, add to `params` when `permanent=true` is appropriate:

```python
if kwargs.get("permanent"):
    params["permanent"] = "true"
```

And update `geocode_full()` call in `geolocation_service.geocode_address()` to pass `permanent=True` for restaurant and institution addresses (see Phase 2.5 for the cost-optimization logic).

### 3. Set `MAPBOX_CACHE_MODE=bypass` in prod Cloud Run config (infra task)

Add to the Cloud Run env var block in `infra-kitchen-gcp/src/components/backend.py`:
```python
{"name": "MAPBOX_CACHE_MODE", "value": "bypass"},
```

### 4. Run batch backfill for Phase 1 addresses (one-time ops task)

After deploying with the paid key:
```sh
MAPBOX_CACHE_MODE=record MAPBOX_ACCESS_TOKEN_PROD=pk.ey... PYTHONPATH=. \
  python3 scripts/backfill_mapbox_geocoding.py
```

This re-geocodes any restaurant/address rows that have placeholder `(0,0)` coordinates from Phase 1 ephemeral mode.

---

## Related Roadmap Documents

| Document | Relationship |
|----------|-------------|
| `docs/plans/database/ADDRESS_AUTOCOMPLETE_SESSION_TOKENS.md` | Mapbox Search Box session-token billing pattern |
| `docs/plans/database/ADDRESS_RATE_LIMITING_AND_CACHING.md` | Rate limiting and caching for Mapbox-backed address endpoints |
| `docs/plans/defer/GOOGLE_MAPS_OTHER_APIS_ROADMAP.md` | _(Deferred)_ Distance Matrix, Nearby Search — future evaluation for Mapbox equivalents |
| `docs/plans/database/ADDRESS_CITY_BOUNDS_SCOPING.md` | Superseded — Mapbox `country` + `proximity` params handle scoping natively |

---

## Cross-Repo Impact

### vianda-platform (B2B)

**Phase 1 — no breaking changes:**
- All existing address response schemas remain unchanged
- `POST /addresses` body: accept `mapbox_id` alongside `place_id` (additive)
- New optional `session_token` query param on `/addresses/suggest` (additive)

**Phase 2:**
- Response schemas gain `mapbox_id` field (additive)
- `formatted_address_google` renamed to `formatted_address` in responses (breaking — coordinate with B2B agent)

**Action:** Produce updated API doc in `docs/api/` once Phase 1 implementation begins.

### vianda-app (B2C)

**Phase 1 — no breaking changes to API contracts:**
- Address suggest, address detail, and geolocation responses remain structurally identical
- The explore map icon positioning, address display on restaurant/pickup screens, and all customer-facing address fields continue unchanged
- `mapbox_id` added as an optional field alongside existing `place_id`

**Phase 1 — Maps SDK migration (B2C agent must investigate):**
- The B2C app currently uses Google Maps SDK for the explore map. With the backend migrating to Mapbox, the **vianda-app agent must evaluate switching from Google Maps SDK to Mapbox Maps SDK (Mapbox GL JS / Mapbox Maps SDK for mobile)**
- The B2C agent should explore: migration effort, feature parity for map display + marker placement, offline map support, free tier (25,000 MAU/month mobile), and UX differences
- This is a B2C-side decision — the backend serves coordinates and the map SDK is a client concern, but aligning on one provider reduces API key management and cost complexity
- **The B2C agent should produce its own pros/cons analysis and roadmap for the Maps SDK switch**

**Phase 2:**
- Response schemas gain `mapbox_id` field (additive)
- `formatted_address_google` renamed to `formatted_address` in responses (breaking — coordinate with B2C agent)

**Action:** Share this roadmap with the vianda-app agent. The agent must read the Maps SDK section and produce a companion frontend roadmap.

### infra-kitchen-gcp

- Phase 1: Add `MAPBOX_ACCESS_TOKEN_DEV/STAGING/PROD` to Secret Manager and Cloud Run env
- Phase 1: Add `ADDRESS_PROVIDER=mapbox` to environment config
- Phase 2: No infra changes (same env vars)
