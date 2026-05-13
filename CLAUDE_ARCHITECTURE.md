# Kitchen API Architecture

**Purpose:** Fast reference for AI-assisted development. Reduces exploratory searches and provides structural context in one place.

**Keep in context with:** [CLAUDE.MD](./CLAUDE.MD)

---

## Directory Structure

```
app/
├── auth/                    # JWT auth, dependencies, permission checks
│   ├── dependencies.py      # get_current_user, get_employee_user, get_super_admin_user, etc.
│   ├── recaptcha.py         # verify_recaptcha (always-on, leads) + verify_recaptcha_token (reusable core)
│   ├── captcha_guard.py     # Conditional CAPTCHA factories: require_captcha_after_threshold, always_require_captcha_for_web
│   ├── ip_attempt_tracker.py # In-memory sliding-window IP attempt counter (login, signup, recovery)
│   ├── routes.py            # Login (with conditional CAPTCHA), JWT token creation
│   └── middleware/
│       └── permission_cache.py
├── config/                  # Settings, enums, static config
│   ├── settings.py          # App settings, env vars. `.env` file loaded ONLY when ENVIRONMENT=local (or unset); Cloud Run envs (dev/staging/prod) read from process environment only (issue #189).
│   ├── enums/               # Python enums (kitchen_days, address_types, status, etc.)
│   ├── location_config.py   # Location/city configuration
│   ├── market_config.py     # Market-specific configuration
│   └── supported_*.py       # supported_cities, supported_countries, supported_currencies, etc.
├── core/                    # Versioning infrastructure + shared GCP utilities
│   ├── versioning.py        # create_versioned_router, APIVersion
│   └── gcp_secrets.py       # GCP Secret Manager client (TTL cache, ADC auth)
├── db/                      # Schema, triggers, seed
│   ├── schema.sql           # Table definitions, enums
│   ├── trigger.sql          # History triggers
│   ├── seed.sql
│   └── index.sql            # Index definitions
├── dependencies/            # FastAPI request-scoped dependencies
│   └── database.py          # get_db() - connection from pool
├── dto/                     # Data Transfer Objects (DB ↔ services)
│   ├── models.py            # Pure Pydantic models, no logic
│   └── dynamic_models.py    # Dynamic DTO generation
├── gateways/                # External service abstractions
│   ├── base_gateway.py
│   ├── address_provider.py       # Factory: get_search_gateway(), get_geocoding_gateway(permanent=False) — driven by ADDRESS_PROVIDER setting
│   ├── mapbox_geocode_cache.py   # Geocoding cache: MapboxGeocodeCache, CacheMode (replay_only/record/bypass), make_geocode_key / make_forward_search_key / make_reverse_geocode_key; key includes permanent flag + op segment (geocode vs forward_search)
│   ├── mapbox_search_gateway.py  # Mapbox Search Box API (suggest + retrieve) — Q2 fallback autocomplete provider
│   ├── mapbox_geocoding_gateway.py # Mapbox Geocoding API v6 (forward + reverse + forward_search); two modes: permanent=False (ephemeral) / permanent=True (persistent-storage)
│   ├── mapbox_static_gateway.py  # Mapbox Static Images API — generates static map PNGs with pin overlays
│   ├── google_maps_gateway.py    # Google Maps Geocoding (fallback provider)
│   ├── google_places_gateway.py  # Google Places API (fallback provider)
│   └── ads/                      # Ad platform gateways (Google Ads, Meta Ads, Gemini)
│       ├── base.py               # AdsConversionGateway + AdsCampaignGateway ABCs
│       ├── factory.py            # get_conversion_gateway(platform) — mock/live routing
│       ├── mock_gateway.py       # Logs payloads, returns success (DEV_MODE / provider=mock)
│       ├── google/               # Google Ads API (Enhanced Conversions, Performance Max)
│       │   ├── auth.py           # GoogleAdsClient singleton (OAuth2, Secret Manager)
│       │   ├── conversion_gateway.py  # ClickConversion upload (gclid/wbraid/gbraid, hashed PII)
│       │   └── campaign_gateway.py    # Stub (Phase 9)
│       ├── meta/                 # Meta Marketing API + Conversions API (CAPI)
│       │   ├── auth.py           # FacebookAdsApi singleton (system user token)
│       │   ├── conversion_gateway.py  # CAPI EventRequest (fbc/fbp, event_id dedup)
│       │   └── campaign_gateway.py    # Stub (Phase 10)
│       └── gemini/               # Gemini advisor (Phase 22)
├── i18n/                    # Internationalization (locale-aware labels, names, messages)
│   ├── enum_labels.py       # Enum display labels per locale (get_label, labels_for_values)
│   ├── locale_names.py      # Country/currency name localization via pycountry gettext
│   ├── error_codes.py       # ErrorCode StrEnum — stable dotted error keys; namespaces:
│   │                        #   auth.*, subscription.*, qr_code.*, product.*, plan.*,
│   │                        #   institution.*, ingredient.*, notification.*, user.*,
│   │                        #   upload.*, service.* (K15/K16 phases); append-only, never rename
│   ├── envelope.py          # envelope_exception() factory — wraps HTTPException with
│   │                        #   {"detail":{"code","message","params"}} contract shape
│   └── messages.py          # Localized message catalog — en/es/pt entries for every
│                            #   ErrorCode; used by envelope_exception(locale=...)
├── routes/                  # API endpoints
│   ├── crud_routes.py       # Admin CRUD (Product, Plan, Restaurant, etc.)
│   ├── crud_routes_user.py  # User CRUD (Subscription, PaymentMethod)
│   ├── admin/               # Admin-only (markets, discretionary, archival, archival_config, leads interest dashboard)
│   ├── super_admin/         # Super Admin only (discretionary approval)
│   ├── billing/             # Client bills, institution bills, supplier invoices, W-9
│   ├── customer/            # B2C payment methods
│   ├── payment_methods/     # Mercado Pago, etc.
│   ├── ingredients.py       # Ingredient search (OFF-backed), custom ingredient creation
│   ├── onboarding.py        # GET /institutions/{id}/onboarding-status, GET /institutions/onboarding-summary
│   ├── locales.py           # GET /locales — public, cacheable supported-locales discovery
│   ├── uploads.py           # POST/GET/DELETE /uploads — image-asset signed-URL upload pipeline
│   └── *.py                 # Domain routes (vianda_selection, restaurant, address, etc.)
├── schemas/                 # Pydantic API contracts (request/response)
│   ├── consolidated_schemas.py
│   ├── billing/             # client_bill, institution_bill, supplier_invoice
│   ├── institution_entity.py
│   ├── payment_method.py
│   ├── subscription.py
│   └── versioned_schemas.py
├── security/                # Scoping, access control
│   ├── scoping.py           # InstitutionScope, UserScope (central implementation)
│   ├── institution_scope.py # Re-exports from scoping.py (backward compat)
│   ├── entity_scoping.py    # EntityScopingService - per-entity scope rules
│   └── field_policies.py    # Field-level access policies
├── services/                # Business logic
│   ├── crud_service.py      # Generic CRUD
│   ├── route_factory.py     # create_crud_routes, create_*_routes()
│   ├── versioned_route_factory.py
│   ├── billing/             # client_bill, institution_billing, supplier_invoice_service, tax_doc_service
│   ├── cron/                # billing_events, currency_refresh, holiday_refresh, wikidata_enrichment, supplier_stall_detection, city_centroid_job (weekly — recomputes centroid_lat/lng on core.city_metadata), etc.
│   ├── leads_public_service.py # Public restaurant/plan projections, lead interest CRUD, cuisine/range enums
│   ├── ingredient_service.py # OFF-backed search, custom ingredient creation, product ingredient management
│   ├── onboarding_service.py # Supplier/employer onboarding checklist, status, admin summary
│   ├── open_food_facts_service.py # Open Food Facts suggest + taxonomy API gateway
│   ├── email/               # Email provider abstraction
│   │   ├── provider_factory.py   # get_email_provider() — returns SMTP or SendGrid based on EMAIL_PROVIDER
│   │   └── providers/            # base.py (ABC), smtp_provider.py, sendgrid_provider.py
│   ├── payment_provider/    # Stripe inbound (live, mock) + Connect outbound (connect_gateway, connect_mock)
│   └── ads/                 # Ads platform services (conversion tracking, zones, click attribution)
│       ├── models.py            # ConversionEvent, AdsPlatform, CampaignStrategy enums
│       ├── pii_hasher.py        # SHA256 hashing (shared by Google + Meta)
│       ├── conversion_service.py # enqueue_conversion_for_all_platforms() fan-out
│       ├── error_handler.py     # AdsErrorCategory enum, platform error mapping
│       ├── subscription_ads_hook.py # Best-effort hook: webhook/renewal -> conversion events
│       ├── zone_service.py      # Ad zone CRUD, flywheel state transitions, overlap validation
│       ├── zone_metrics_service.py  # Refresh zone metrics (restaurants, subscribers, leads)
│       ├── click_tracking_service.py # Store/query frontend click identifiers
│       └── notify_me_sync.py    # Aggregate notify-me leads per zone, audience export
├── workers/                 # ARQ background tasks + Cloud Run job entrypoints
│   ├── arq_settings.py      # ARQ WorkerSettings (Redis config, job timeout, retry)
│   ├── conversion_worker.py # upload_conversion task (platform-agnostic, routes via factory)
│   └── image_pipeline/      # Image-processing pipeline (STUB — real logic not yet implemented)
│       └── __init__.py      # run_image_event_listener(), run_image_backfill() stubs
└── utils/                   # Helpers
    ├── db.py                # db_read, db_write, get_db_connection
    ├── db_pool.py           # Connection pool, get_db_connection_context
    ├── country.py           # Country code utilities: normalize, alpha-2/3 conversion, name resolution
    ├── map_projection.py    # Web Mercator projection: lat/lng → pixel position, grid cells, zoom computation
    ├── log.py
    ├── gcs.py               # Google Cloud Storage (products, QR codes, supplier invoices, image-asset pipeline)
    ├── checksum.py
    └── rate_limit.py

application.py               # FastAPI app, route registration, lifespan
```

---

## Mapbox Geocoding — Two-Mode Contract

Mapbox Geocoding API v6 operates in two modes; **the mode must match the callsite's intent**.

| Mode | Token | Mapbox param | Cache key suffix | When to use |
|------|-------|-------------|-----------------|-------------|
| Ephemeral (`permanent=False`) | `pk.*` (MAPBOX_ACCESS_TOKEN_DEV/STAGING/PROD) | _(none)_ | `\|permanent=false` | Autocomplete / suggest — result NOT written to DB |
| Persistent (`permanent=True`) | `sk.*` (MAPBOX_ACCESS_TOKEN_DEV/STAGING/PROD_PERSISTENT) | `permanent=true` | `\|permanent=true` | Geocoding for DB storage — result written to `geolocation_info` |

Storing Mapbox results obtained via the ephemeral endpoint violates Mapbox ToS.  Using the persistent token costs $5/1,000 geocode calls.

### How the flag flows

```
get_geocoding_gateway(permanent=True)           # address_provider.py factory
  → MapboxGeocodingGateway(permanent=True)      # mapbox_geocoding_gateway.py
      → get_mapbox_access_token(permanent=True) # settings.py — sk.* token, raises RuntimeError if not set
      → _make_request adds params["permanent"]="true" to Mapbox v6 URL
      → call() dispatches to make_geocode_key / make_forward_search_key / make_reverse_geocode_key → key ends with |permanent=true
```

### Module-level singletons

| Singleton | Exported from | Mode | Used by |
|-----------|---------------|------|---------|
| `geolocation_service` | `geolocation_service.py` | ephemeral | Backward-compat callers; does NOT write lat/lng to DB |
| `persistent_geolocation_service` | `geolocation_service.py` | persistent | `address_service._geocode_address()`, `_update_restaurant_geolocation()` |
| `get_mapbox_geocoding_gateway(permanent=False)` | `mapbox_geocoding_gateway.py` | ephemeral | Backfill script |
| `get_mapbox_geocoding_gateway(permanent=True)` | `mapbox_geocoding_gateway.py` | persistent | `persistent_geolocation_service`, `GeocodingAutocompleteProvider` |

### Short-circuit rule

`address_service._geocode_address()` checks `geolocation_info` for existing non-zero coordinates **before** calling Mapbox.  If coordinates already exist, the function returns immediately (no Mapbox call, no cost).  Zero-coordinate placeholder rows (from Phase 1 ephemeral mode) are NOT treated as "existing coordinates" — they proceed to geocode.

### Cache key format

```
geocode|{normalized_q}|{country}|{language}|permanent={true|false}
forward_search|{normalized_q}|{country}|{language}|permanent={true|false}
reverse_geocode|{lat}|{lng}|{language}|permanent={true|false}
```

`forward_search` keys (from `MapboxGeocodingGateway.forward_search()`) are distinct from `geocode` keys so that autocomplete partial-input entries never collide with geocode-resolution entries for the same query string. Both entry kinds can coexist in `seeds/mapbox_geocode_cache.json`.

The `permanent` segment was added in Step 2.  The committed seed file (`seeds/mapbox_geocode_cache.json`) contains both `permanent=false` and `permanent=true` entries for every demo-day address so replay_only mode works for both gateway modes without any live Mapbox calls.

### Autocomplete provider switch (ADDRESS_AUTOCOMPLETE_PROVIDER)

Two-provider abstraction for the `/suggest` endpoint, selectable at runtime without redeploy.

```
ADDRESS_AUTOCOMPLETE_PROVIDER=geocoding  (default)
  → GeocodingAutocompleteProvider
      → MapboxGeocodingGateway(permanent=True).forward_search(autocomplete=true)
      → places-permanent dataset, one paid call per address, TOS-clean

ADDRESS_AUTOCOMPLETE_PROVIDER=search_box  (Q2 fallback)
  → SearchBoxAutocompleteProvider
      → MapboxSearchGateway.suggest() (ephemeral session)
      → two paid calls per address (suggest + resolve)
```

Both providers return the same canonical shape — `{"place_id": str, "display_text": str, "country_code": str (optional)}` — so the `/suggest` response contract is byte-identical regardless of the active provider. Frontends are unaffected by a flag flip.

**Q2 rule (always enforced regardless of provider):** every persisted address field comes from `places-permanent` geocoding. `_resolve_address_from_place_id` in `address_service.py` always returns `None` for the geoloc tuple, forcing coordinates through `_geocode_address()` → `persistent_geolocation_service` → `places-permanent`.

**place_id format compatibility:** Mapbox Search Box `mapbox_id` and Geocoding API `mapbox_id` are the same underlying entity-ID namespace. The downstream `_resolve_address_from_place_id` call (which uses Search Box `retrieve`) accepts IDs from either provider without modification.

**Provider location:** `app/services/address_autocomplete_service.py` — `SearchBoxAutocompleteProvider`, `GeocodingAutocompleteProvider`, `get_autocomplete_provider()` factory.

**Abort criteria:** flip to `search_box` immediately if real users report autocomplete failure on common partial inputs, typo tolerance becomes a measurable issue, or forward-endpoint latency exceeds 400ms p50.

### DB tracking columns (migration 0019)

`core.geolocation_info` columns written by the persistent geocoding path:
- `mapbox_geocoded_at TIMESTAMPTZ` — timestamp of the geocoding call
- `mapbox_normalized_address TEXT` — cache key query string stored for backfill re-derivation

---

## Maps Subsystem

The kitchen exposes two map endpoints under `app/routes/maps.py` (router prefix `/maps`, registered as `/api/v1/maps/`):

- `GET /api/v1/maps/city-pins` **(active)** — returns restaurant markers + recommended NE/SW viewport + centroid anchor for client-side interactive Mapbox rendering. Accepts optional `center_lat`/`center_lng` (user address anchor) and `limit` (1–50). Three-branch algorithm: user-anchor inside cluster (`centroid.source="user_nearest"`), user-anchor outlier >10 km (`centroid.source="city_fallback"`), no anchor (`centroid.source="city"`). Also returns `more_available` and `omitted_count` for overflow chip. See `app/routes/maps.py` and `city_map_service.get_pins()`. No image generated; no Mapbox call made server-side.
- `GET /api/v1/maps/city-snapshot` **(dormant since #214 cutover)** — returns a Mapbox Static Images PNG cached in GCS with per-marker pixel positions for tap-target overlay. Preserved as a future cost optimization if interactive-map MAU economics deteriorate. Do not delete without operator review.

### Key files

| File | Purpose |
|---|---|
| `app/routes/maps.py` | Both endpoints: `/city-pins` (active, with centroid + user-anchor params) + `/city-snapshot` (dormant) |
| `app/services/city_map_service.py` | `CityMapService.get_pins()` (three-branch centroid logic), `get_snapshot()` (dormant path), `_query_restaurants()` (unordered, snapshot path), `_query_restaurants_ordered()` (haversine ORDER BY, city-pins path), `_get_city_centroid()` (reads `core.city_metadata.centroid_lat/lng`) |
| `app/utils/map_projection.py` | `compute_bounding_box()`, `lat_lng_to_pixel()`, `grid_cell()`, `is_within_frame()`, `distance_from_center()`, `slugify_city()` |
| `app/tests/utils/test_map_projection.py` | 28 pytest unit tests covering all `compute_bounding_box` branches plus legacy projection helpers |
| `app/schemas/consolidated_schemas.py` | `MapPinSchema`, `ViewportCornerSchema`, `ViewportSchema`, `CentroidSchema` (source enum: user_nearest/city/city_fallback), `CityPinsResponseSchema` (extended with centroid, more_available, omitted_count); `CitySnapshotResponseSchema`, `CitySnapshotMarkerSchema` (dormant) |
| `app/gateways/mapbox_static_gateway.py` | Mapbox Static Images API — used only by the dormant `/city-snapshot` path |

### `compute_bounding_box` contract

- Empty list → `None` (caller returns `recommended_viewport: null`).
- Single marker → `±0.01°` expansion on both axes (`_SINGLE_MARKER_EXPANSION_DEG` constant).
- ≥ 2 markers → tight bounding box; no server-side padding (client adds via Mapbox `fitBounds` options).
- Antimeridian crossing: explicitly out of scope; not served by any current market.

### Auth

Both endpoints require `get_current_user` (Bearer JWT). No role restriction — any authenticated user (Customer, Supplier, Employee) can call them.

### Postman coverage

`docs/postman/collections/022 MAPS_CITY_PINS.postman_collection.json` — 6 requests, 16 assertions covering happy path, empty city, missing param, invalid `country_code`, unauthorized.

### Client integration doc

`docs/api/b2c_client/MAPS_API.md`

---

## Route Registration Flow

1. **`application.py`** creates the app and registers all routers.
2. **Versioned wrappers:** Every business route uses `create_versioned_router("api", ["Tag"], APIVersion.V1)` → prefix `/api/v1`.
3. **Two CRUD routers:**
   - **`crud_routes.py`** → Admin/System CRUD (no user context): Product, Plan, Restaurant, CreditCurrency, Institution, Vianda, Geolocation, InstitutionEntity.
   - **`crud_routes_user.py`** → User CRUD (user_id from `current_user`): Subscription, PaymentMethod; includes subscription_payment (with-payment, confirm-payment) before generic CRUD.
4. **Route factory** (`app/services/route_factory.py`) generates standard CRUD routes via `create_plan_routes()`, `create_product_routes()`, etc.
5. **Custom/manual routes** (not in CRUD routers): vianda_selection, vianda_pickup, vianda_review, favorite, address, qr_code, restaurant, restaurant_balance, restaurant_transaction, restaurant_staff, vianda_kitchen_days, national_holidays, restaurant_holidays, client_bill, institution_bill, supplier_invoice, ingredients, markets, countries, currencies, cities, provinces, cuisines, leads, locales, webhooks, customer payment_methods, enums, admin discretionary, super_admin discretionary, archival, archival_config, admin leads, admin city_centroid (POST /admin/city-centroid/recompute — manual trigger for weekly centroid cron job). (**employer routes removed** — employer identity is `institution_info` + `institution_entity_info`.)
6. **Registration order:** Institution entities router registered before CRUD so `/enriched` matches before `/{entity_id}`. Manual/custom routes must be registered before auto-generated if they share paths (FastAPI matches first).
7. **Composite-create pattern:** When an entity spans multiple tables by lifecycle, `POST` accepts optional embedded sub-resource blocks in a single transaction (`commit=False` chaining). Updates stay granular per sub-resource. Applied to: institutions (+ supplier_terms + institution_market), products (+ ingredient_ids), markets (+ billing_config). See `docs/api/internal/COMPOSITE_CREATE_PATTERN.md`.

---

## Data Flow

```
Request
  → Middleware (CORS, PermissionCache)
  → Route (FastAPI)
  → Depends(get_current_user, get_db)
  → Service (business logic)
  → db_read / db_write (app/utils/db.py)
  → psycopg2 via connection from pool (app/utils/db_pool.py)
  → PostgreSQL
```

**Lifespan:** `application.py` lifespan initializes `app.state.db_pool` at startup and closes it at shutdown. Routes use `get_db()` which yields connections from `get_db_connection_context()`.

---

## Key Entry Points

| Concern | Location |
|--------|----------|
| Auth / permissions | `app/auth/dependencies.py` |
| Institution scoping | `app/security/scoping.py` (InstitutionScope, UserScope), `app/security/entity_scoping.py` (EntityScopingService) |
| Database connection | `app/dependencies/database.py` (get_db), `app/utils/db_pool.py` (get_db_connection_context, get_db_pool) |
| CRUD generation | `app/services/route_factory.py`, `versioned_route_factory.py` |
| DTOs | `app/dto/models.py`, `app/dto/dynamic_models.py` |
| API schemas | `app/schemas/consolidated_schemas.py`, `app/schemas/billing/`, domain-specific schemas |
| i18n / locale | `app/i18n/` (enum labels, locale names, messages), `app/utils/locale.py` (resolution), `app/auth/dependencies.py` (`get_resolved_locale`) |
| DB schema | `app/db/schema.sql` |

---

## Route Categories

| Category | Example | Auth |
|----------|---------|------|
| Infrastructure | `/health`, `/pool-stats` | `/health` none; `/pool-stats` JWT |
| Versioned v1 | `/api/v1/plans/`, `/api/v1/restaurants/` | JWT |
| Admin (versioned) | `/api/v1/admin/archival/*`, `/api/v1/admin/archival-config/*`, `/api/v1/admin/city-centroid/*`, `/api/v1/admin/discretionary/*`, `/api/v1/admin/markets/*`, `/api/v1/admin/leads/*` | Internal |
| Super-Admin (versioned) | `/api/v1/super-admin/discretionary/*` | Super Admin only |
| Webhooks | `/api/v1/webhooks/*` | Stripe signature |
| Leads | `/api/v1/leads/*` | None, rate-limited, reCAPTCHA v3 required (exempt for b2c-mobile, **also exempt for `/leads/countries` and `/leads/supplier-countries`** — navbar-load fetches) |
| Locales | `/api/v1/locales` | None, cacheable |

---

## Versioning

- **Strategy:** URL path (`/api/v1/...`).
- **Implementation:** `app/core/versioning.py` — `create_versioned_router(prefix, tags, version)`.
- Route files define prefix without version (e.g. `/plans`); the wrapper adds `/api/v1`.

---

## Scoping

- **Internal:** Global (all institutions).
- **Supplier:** Scoped to `institution_id` from JWT.
- **Employer:** Institution-scoped (like Supplier).
- **Market filter:** Enriched endpoints accept optional `?market_id=` to narrow results within the institution. Validated against `core.institution_market` — can't filter to an unassigned market. Internal users bypass this validation.
- **Institution market boundary:** `core.institution_market` junction controls which markets an institution can operate in. Entity creation validates the entity's address country is in an assigned market. User market assignments validate against `institution_market` (Supplier/Employer only; Internal bypasses).
- **EntityScopingService** (`app/security/entity_scoping.py`) maps entity types to scope logic for both base and enriched endpoints. Use `EntityScopingService.get_scope_for_entity(entity_type, current_user)` in routes.
- **InstitutionScope** and **UserScope** live in `app/security/scoping.py`; `institution_scope.py` re-exports for backward compatibility.

---

## Auth Settings Safe Defaults

`app/config/settings.py` declares `SECRET_KEY`, `ALGORITHM`, and `ACCESS_TOKEN_EXPIRE_MINUTES` with the sentinel default `__UNSET_NOT_FOR_AUTH__`, so maintenance scripts (e.g., `scripts/backfill_mapbox_geocoding.py`) can import `app.config.settings` in CI runners that don't have those env vars set without crashing on Pydantic validation. The use sites (`create_access_token`, `verify_token`, `get_current_user`, `get_optional_user`) call `_require_auth_settings()` before any JWT operation; if the sentinel is still present at use time the guard raises clearly. Deployed environments (Cloud Run) inject real values via Secret Manager, so the defaults never fire there.

---

## Subscription Renewal Control

User-configurable early renewal threshold on `customer.subscription_info`.

- **Column:** `early_renewal_threshold INTEGER DEFAULT 10` — NULL = period-end only (renew only at 30-day mark); integer = renew early when balance drops below this value at order time.
- **Two renewal triggers:** Time-based cron (`app/services/cron/subscription_renewal.py`) always renews at 30-day mark regardless of threshold. Low-balance early renewal (`app/services/vianda_selection_service.py`) checks `subscription.early_renewal_threshold` — skips if NULL.
- **User endpoint:** `PATCH /api/v1/subscriptions/me/renewal-preferences` — Customer updates their threshold. Defined in `app/services/route_factory.py` inside `create_subscription_routes()`.
- **Schema:** `RenewalPreferencesSchema` in `app/schemas/subscription.py`.
- **Roadmap:** `docs/plans/vianda_employer_benefits_program.md` (Section 7 — prerequisite for employer benefits monthly cap).

---

## Employer Benefits Program

Enterprise meal subscription benefits — employers subsidize employee meal plans with configurable rate + cap. Employers use the same `institution_info` + `institution_entity_info` model as suppliers (normalized in the multinational institutions initiative).

- **Data model:** `core.employer_benefits_program` with three-tier cascade: `institution_entity_id IS NULL` = institution-level defaults; `institution_entity_id IS NOT NULL` = entity-level override. Unique constraint: `(institution_id, institution_entity_id)`. Currency-tied fields (`benefit_cap`, `minimum_monthly_fee`, `stripe_*`) exist only at entity level. `billing.employer_bill` (per-entity invoices, `institution_entity_id NOT NULL`). `billing.employer_bill_line` (per-renewal line items).
- **Three-tier resolution:** `resolve_effective_program(institution_id, entity_id, db)` in `app/services/employer/program_service.py` — entity program → institution program → None. Used by billing, enrollment, and benefit-plans endpoint.
- **No separate employer_info table.** Employer identity is `institution_info` (type=`employer`) + `institution_entity_info` per country. The `employer_info` and `employer_domain` tables were removed.
- **email_domain:** Stored as `email_domain` column on `ops.institution_entity_info` (nullable). Used for domain-gated enrollment. Available to all entity types (suppliers for future SSO).
- **Services:** `app/services/employer/program_service.py` (program CRUD with entity scoping), `app/services/employer/enrollment_service.py` (single + bulk employee enrollment, subscription), `app/services/employer/billing_service.py` (per-entity bill generation, benefit calculator)
- **Routes:** `app/routes/employer_program.py` — POST/GET/PUT `/employer/program`, PUT `/employer/program/by-key` (idempotent upsert for seed/demo fixtures), POST/GET/DELETE `/employer/employees`, POST `/employer/employees/bulk`, POST `/employer/employees/{user_id}/subscribe`, PUT `/employer/employee-link/by-key` (idempotent employee-program link upsert for seed/demo fixtures), GET `/employer/billing`, POST `/employer/billing/generate`, POST `/employer/billing/run-cron`. Domain routes removed (domain managed via entity CRUD).
- **Schemas:** `app/schemas/employer_program.py` — `ProgramCreateSchema` accepts optional `institution_entity_id`; `EmployerProgramUpsertSchema` (for `PUT /employer/program/by-key`); `EmployerEmployeeLinkUpsertSchema` and `EmployerEmployeeLinkResponseSchema` (for `PUT /employer/employee-link/by-key`).
- **Upsert services:** `program_service.upsert_program_by_canonical_key()` (idempotent program insert/update by `canonical_key`); `enrollment_service.upsert_employee_link_by_canonical_key()` (idempotent employer-sponsored subscription insert; returns existing if `canonical_key` already present on `subscription_info`).
- **DB columns added for upserts:** `core.employer_benefits_program.canonical_key VARCHAR(200) NULL` (migration `0017`); `customer.subscription_info.canonical_key VARCHAR(200) NULL` (migration `0018`). Both have partial unique indexes (sparse: only indexed when non-null).
- **Key design:** Benefit employees are Customer Comensals assigned to the Employer's institution. `user_info.employer_entity_id` links employees to their employer's entity (replaces former `employer_id`). `employer_address_id` kept for pickup office.
- **Domain-gated enrollment:** `email_domain` on `institution_entity_info` replaces former `employer_domain` table. B2C signup (`_apply_customer_signup_rules` in `user_signup_service.py`) checks entity `email_domain` and sets both `institution_id` and `employer_entity_id`.
- **Billing cron:** `app/services/cron/employer_billing.py` — iterates programs per entity, generates per-entity bills. Currency from `institution_entity_info.currency_metadata_id`. Month-end minimum fee reconciliation per entity.
- **Benefit plans endpoint:** `GET /subscriptions/benefit-plans` in `route_factory.py` uses `resolve_effective_program()` with employee's `employer_entity_id`.
- **B2B login restriction:** Customer Comensals blocked from B2B platform login when `x-client-type: b2b` header is sent.
- **Enums:** `benefit_cap_period_enum`, `enrollment_mode_enum`, `billing_cycle_enum`, `employer_bill_payment_status_enum`
- **Address types:** B2C customer addresses are user-selected: `customer_home` (Home), `customer_employer` (Work), `customer_other` (Other). No longer auto-derived from employer linkage.
- **Full design:** `docs/plans/MULTINATIONAL_INSTITUTIONS.md`

---

## Ingredients Subsystem

Structured ingredient management replacing legacy free-text field on `product_info`.

- **Data model:** `ops.ingredient_catalog` (multilingual: `name_es`, `name_en`, `name_pt`), `ops.product_ingredient` (junction), `ops.ingredient_alias` (dialect variants), `ops.ingredient_nutrition` (USDA data, future)
- **External source:** Open Food Facts (OFF) taxonomy — real-time autocomplete with local-first caching. Wikidata for image enrichment (CC licensed).
- **Search flow:** Local DB first (threshold: 5 verified results) → OFF fallback → upsert → return merged results
- **Services:** `app/services/ingredient_service.py` (search, custom create, product ingredient CRUD), `app/services/open_food_facts_service.py` (OFF API gateway)
- **Cron:** `app/services/cron/wikidata_enrichment.py` — enriches catalog entries with Wikidata images
- **Routes:** `app/routes/ingredients.py` — `/ingredients/search`, `/ingredients/custom`, `/products/{id}/ingredients`
- **Dietary flags:** `product_info.dietary` converted from VARCHAR to structured multi-select array (`DietaryFlag` enum in `app/config/enums/dietary_flags.py`)
- **Roadmap:** `docs/plans/STRUCTURED_INGREDIENTS_ROADMAP.md`

---

## Supplier Invoice Compliance Subsystem

Tracks supplier tax invoices (AFIP Factura Electronica for Argentina) and W-9 collection (US) linked to institution bills.

- **Data model:** `billing.supplier_invoice` (core, market-agnostic) + per-country extension tables: `billing.supplier_invoice_ar` (CAE, CUIT), `billing.supplier_invoice_pe` (serie, correlativo, CDR, RUC), `billing.supplier_invoice_us` (tax_year). Junction: `billing.bill_invoice_match`. Audit: `audit.supplier_invoice_history` (core only). US W-9: `billing.supplier_w9` (one per entity)
- **Payout gate config:** `billing.market_payout_aggregator` (`require_invoice`, `max_unmatched_bill_days`, `kitchen_open_time`, `kitchen_close_time`) — market-level defaults for supplier terms. Auto-created during `POST /markets` (composite create). Managed via `GET/PUT /markets/{id}/billing-config`. Propagation preview: `GET /markets/{id}/billing-config/propagation-preview`.
- **Supplier terms:** `billing.supplier_terms` with three-tier cascade: `institution_entity_id IS NULL` = institution-level defaults; `institution_entity_id IS NOT NULL` = entity-level override. Unique constraint: `(institution_id, institution_entity_id)`. Fields: `no_show_discount`, `payment_frequency`, `kitchen_open_time`, `kitchen_close_time`, `require_invoice`, `invoice_hold_days`. NULL = inherit from next tier. Audit: `audit.supplier_terms_history`. Routes: `app/routes/supplier_terms.py` (GET/PUT). Resolution: `app/services/billing/supplier_terms_resolution.py`.
  - `no_show_discount` → vianda enriched queries + promotion service transaction creation
  - `payment_frequency` → gates bill creation in `institution_billing.py:run_phase2_bills_and_payout()` via `_is_supplier_payout_due()`
  - `kitchen_open_time` → gates pickup availability / QR code scanning via `kitchen_day_service.is_pickup_available()`
  - `kitchen_close_time` → kitchen day cutoff (reservation lockdown, transaction finalization) via `kitchen_day_service._get_kitchen_close_time()`
  - `require_invoice` + `invoice_hold_days` → invoice compliance gate in payout loop via `_check_invoice_compliance()`
  - **Three-tier resolution chain:** `entity override → institution default → market_payout_aggregator → hardcoded defaults`. All public functions in `supplier_terms_resolution.py` accept optional `institution_entity_id` kwarg.
- **Services:** `app/services/billing/supplier_invoice_service.py` (create, match, review, list), `app/services/billing/supplier_w9_service.py` (W-9 create/upsert, get by entity)
- **Routes:** `app/routes/billing/supplier_invoice.py` — POST create (multipart), GET list, GET enriched, GET by ID, PATCH review, POST match. `app/routes/billing/supplier_w9.py` — POST submit W-9, GET by entity.
- **GCS storage:** `invoices/{country_code}/{entity_id}/{invoice_id}/document` and `w9/{entity_id}/{w9_id}/document` in `GCS_SUPPLIER_BUCKET`. Country prefix enables per-country lifecycle policies (AR=10yr, PE=5yr, US=7yr).
- **Validation:** AR requires CAE (14 digits), CUIT, punto de venta. PE requires serie (F+3 digits), correlativo, RUC (11 digits). US requires `tax_year`. W-9 validates `ein_last_four` (4 digits only; full EIN/SSN stays on the PDF in GCS).
- **API pattern:** POST accepts `country_details_json` (single JSON field) with country-specific fields. Response nests details as `ar_details`, `pe_details`, or `us_details`.
- **Auth:** All Supplier roles (Admin, Manager, Operator) can register/list/match invoices and submit W-9 (scoped). Internal can register (auto-approved) and review.
- **Roadmap:** `docs/plans/SUPPLIER_BILLING_COMPLIANCE_ROADMAP.md`

---

## Supplier Onboarding Status

Backend-computed onboarding checklist for Supplier/Employer institutions. Tracks 7-item setup progress (address → entity → restaurant → product → vianda → kitchen_day → qr_code).

- **Service:** `app/services/onboarding_service.py` — `get_onboarding_status()` (single institution), `get_onboarding_status_claim()` (JWT-safe), `get_onboarding_summary()` (admin funnel)
- **Routes:** `app/routes/onboarding.py` — `GET /institutions/{id}/onboarding-status` (scoped), `GET /institutions/onboarding-summary` (Super Admin)
- **Schemas:** `app/schemas/onboarding.py` — `OnboardingStatusResponseSchema`, `OnboardingSummaryResponseSchema`
- **JWT claim:** `onboarding_status` added for Supplier/Employer tokens via `merge_onboarding_token_claims()` in `app/auth/utils.py`. Values: `not_started`, `in_progress`, `complete` (never `stalled`).
- **Employer checklist:** Same endpoint, different items: `has_benefits_program`, `has_email_domain` (checks `email_domain` on entity), `has_enrolled_employee`, `has_active_subscription`. Dispatched by `institution_type`. Currently per-institution; future: per-market checklist.
- **Customer checklist (user-level):** `GET /users/me/onboarding-status` — `has_verified_email`, `has_active_subscription`. JWT claim included for Customer role.
- **Stalled status:** Internal-only. Derived when `days_since_last_activity >= 3` and checklist is partially complete.
- **Stall detection cron:** `app/services/cron/supplier_stall_detection.py` — daily job sends escalating emails (2d getting started → 3d need help → 7d incomplete → 14d manual escalation). 3-day cooldown between emails per institution. Manual suppression via `support_email_suppressed_until` column.
- **Regression detection:** `check_onboarding_regression()` in `onboarding_service.py` — called automatically after `CRUDService.soft_delete()` and restaurant status updates. Logs when a Supplier regresses from `complete`.
- **Customer engagement cron:** `app/services/cron/customer_engagement.py` — daily job sends subscription prompts to unsubscribed customers. Benefit employees get employer-specific emails. 3-day cooldown per user.
- **Cron endpoints:** `POST /api/v1/institutions/onboarding-stall-detection` (suppliers), `POST /api/v1/institutions/onboarding-customer-engagement` (customers). Internal only.
- **Roadmap:** `docs/plans/SUPPLIER_SUCCESS_MANAGEMENT_ROADMAP.md`

---

## Credit-Currency Spread (Margin Machine)

Per-market structural margin between the cheapest customer per-credit price and the stable
supplier credit value. Finance's primary lever for gross margin per redemption.

- **Schema:**
  - `core.currency_metadata.credit_value_supplier_local` — stable per-credit payout to suppliers. Renamed from `credit_value_local_currency`.
  - `core.market_info.min_credit_spread_pct NUMERIC(5,4)` — minimum required spread floor. Default 0.20 (20%). Super Admin only.
  - `audit.spread_acknowledgement` — event log of every write accepted despite a floor violation. Columns: `actor_user_id`, `market_id NOT NULL`, `write_kind` (enum: `plan`, `currency_value`, `spread_floor`), `entity_id NULL`, `observed_spread_pct`, `floor_pct`, `offending_plan_ids JSONB`, `justification`, `acknowledged_at`.
- **Services:**
  - `app/services/credit_spread.py` — `check_spread_floor`, `check_spread_floor_with_plan`, `check_spread_floor_with_new_supplier_value`, `check_spread_floor_with_new_floor_pct`, `record_acknowledgement`. All check functions acquire `SELECT FOR UPDATE` on market + currency rows.
  - `app/services/margin_report.py` — `get_margin_report()`: per-market per-period aggregation of `Σ (plan.credit_cost_local_currency − credit_value_supplier_local) × credits_redeemed` grouped by plan tier.
- **Routes:**
  - Plan writes (create/update/upsert-by-key in `route_factory.py`): spread check + warn-and-ack contract. Error code: `spread.floor_violation`.
  - Currency writes (create/update/upsert-by-key in `route_factory.py`): spread check against every market using the currency; decrease requires Super Admin (`spread.currency_decrease_super_admin_only`).
  - `PATCH /api/v1/markets/{market_id}/spread-floor` (`app/routes/admin/markets.py`): Super Admin only. Updates `min_credit_spread_pct` with warn-and-ack.
  - `GET /api/v1/markets/{market_id}/spread-readout` (`app/routes/admin/markets.py`): Employee (Internal). Returns `{cheapest_plan_per_credit, supplier_value, headroom_pct, floor_pct, offending_plan_ids}`.
  - `GET /internal/margin-report` (`app/routes/admin/margin_report.py`): Super Admin. Query params: `market_id`, `period_start`, `period_end`.
- **Warn-and-ack contract:** Violations return `422 spread.floor_violation` unless `acknowledge_spread_compression=true` is set, in which case the write proceeds and an audit row is written.
- **Durable doc:** `docs/api/internal/credit-currency-spread.md`

---

## Vianda Pickup Flow (B2C)

QR-code-based pickup confirmation flow for the B2C mobile app.

- **Signed QR codes:** `https://vianda.app/qr?id={qr_code_id}&sig={hmac_hex16}`. HMAC-SHA256 over `qr_code_id` using `QR_HMAC_SECRET`, truncated to 16 hex chars.
- **QR generation:** `app/services/qr_code_service.py` — `create_qr_code_atomic()` inserts QR record, computes signed URL, generates PNG image. QR image encodes the signed URL.
- **HMAC utility:** `app/utils/qr_hmac.py` — `sign_qr_code_id()`, `verify_qr_signature()`, `build_signed_qr_url()`
- **Scan endpoint:** `POST /api/v1/vianda-pickup/scan-qr` — accepts `{ qr_code_id, sig }`, verifies HMAC, returns pickup confirmation with `vianda_pickup_ids`, `restaurant_name`, `viandas[]`, `countdown_seconds`, `max_extensions`, `confirmation_code`.
- **Completion tracking:** `POST /api/v1/vianda-pickup/{id}/complete` — accepts optional `{ completion_type }` (`user_confirmed` | `timer_expired`). Stored on `vianda_pickup_live.completion_type` for analytics.
- **Timer config:** Global via `PICKUP_COUNTDOWN_SECONDS` (default 300) and `PICKUP_MAX_EXTENSIONS` (default 3) in `app/config/settings.py`.
- **Vianda reviews:** `POST /api/v1/vianda-reviews` — extended with `would_order_again` (bool) and `comment` (varchar 500). Comments surface to restaurants in B2B only, not in B2C app.
- **Error codes:** `invalid_signature` (400), `wrong_restaurant` (400), `outside_pickup_hours` (400), `no_active_reservation` (404).
- **Service:** `app/services/vianda_pickup_service.py` — `scan_qr_code_by_id()` (new, signed), `scan_qr_code_simplified()` (deprecated, payload-based).
- **Supplier review endpoint:** `GET /api/v1/vianda-reviews/by-institution/enriched` — institution-scoped, returns vianda name + restaurant name + ratings + comment. No customer PII. Optional `?vianda_id` and `?restaurant_id` filters. Service: `get_enriched_reviews_by_institution()` in `app/services/vianda_review_service.py`.
- **Portion complaints:** `POST /api/v1/vianda-reviews/{id}/portion-complaint` — customer files complaint after rating portion size as 1. Accepts photo (multipart) + text. Table: `customer.portion_complaint`. Photos in GCS customer bucket.

### Kiosk Mode (B2B)

Tablet/phone-optimized views for restaurant operators handling pickups during service hours.

- **Handed Out status:** New `status_enum` value. Lifecycle: `pending → arrived → handed_out → completed`. Separates "customer is here" from "vianda was given" from "customer confirms."
- **Numeric confirmation codes:** 6-digit numeric (not alphanumeric) for fast kiosk entry. Generated in `_generate_confirmation_code()` in `vianda_pickup_service.py`.
- **Enhanced daily-orders:** `GET /api/v1/restaurant-staff/daily-orders` now includes per-order: `vianda_pickup_id`, `expected_completion_time`, `completion_time`, `countdown_seconds`, `extensions_used`, `was_collected`, `confirmation_code`, `pickup_type`. Per-restaurant: `pickup_window_start/end`, `require_kiosk_code_verification`. Response: `server_time` for timer sync. Privacy: initials only (M.G.).
- **Verify-and-handoff:** `POST /api/v1/restaurant-staff/verify-and-handoff` — Layer 2 code verification. Clerk enters numeric code, system verifies and transitions to Handed Out. Consumes the code.
- **Hand-out:** `POST /api/v1/vianda-pickup/{id}/hand-out` — Layer 1 one-tap handoff. Transitions Arrived → Handed Out without code entry.
- **Per-restaurant toggle:** `require_kiosk_code_verification` boolean on `restaurant_info`. Supplier Admin only.
- **Supplier Operator restrictions:** Operators are blocked from all CRUD management routes (via `ensure_supplier_admin_or_manager()` in route factory). Operators can access: daily orders, verify code, hand out, mark complete, view feedback, self-profile.
- **Trust model:** See `docs/plans/PICKUP_HANDOFF_TRUST_MODEL.md` for the layered trust strategy.
- **Push notifications (FCM):** `core.user_fcm_token` stores device tokens. `POST/DELETE /users/me/fcm-token` for registration/logout. `app/services/push_notification_service.py` sends FCM push on Handed Out transition (checks `notify_vianda_readiness_alert` preference). `app/services/fcm_token_service.py` manages token lifecycle. Config: `FIREBASE_CREDENTIALS_PATH` (empty = push disabled, logs instead).

---

## In-App Notification Banners

Cross-platform in-app notification banner system. Frontends poll for active banners; backend owns creation, expiry, deduplication, and client-type filtering.

- **Data model:** `customer.notification_banner` — JSONB payload, dedup via `UNIQUE(user_id, dedup_key)`, `action_status` lifecycle (`active` → `dismissed`/`opened`/`completed`/`expired`), `client_types` array for backend-owned filtering.
- **Enums:** `notification_banner_type_enum` (`survey_available`, `peer_pickup_volunteer`, `reservation_reminder`), `notification_banner_priority_enum` (`normal`, `high`), `notification_banner_action_status_enum` (`active`, `dismissed`, `opened`, `completed`, `expired`).
- **Service:** `app/services/notification_banner_service.py` — `create_notification()` (raw SQL with ON CONFLICT dedup), `get_active_notifications()` (max 5, high priority first, 2h grace for surveys), `acknowledge_notification()` (idempotent), `expire_stale_notifications()` (bulk cleanup).
- **Routes:** `app/routes/notification_banner.py` — `GET /notifications/active` (Customer, polled every 60s), `POST /notifications/{id}/acknowledge` (Customer), `POST /notifications/expire` (Internal, cron trigger), `POST /notifications/generate-reminders` (Internal, cron trigger).
- **Survey trigger:** Wired into `ViandaPickupService.complete_order()` in `vianda_pickup_service.py` — creates `survey_available` banner after successful pickup completion (best-effort, fail-silent).
- **Reservation reminder cron:** `app/services/cron/notification_banner_cron.py` — `run_notification_banner_cron()` generates `reservation_reminder` notifications for pickups starting within 1h (market-local time) and expires stale notifications. Intended to run every 15 minutes.
- **Relationship to push:** Complementary — push (FCM) delivers when app is backgrounded, banners deliver when foregrounded. Same event may trigger both; frontend deduplicates by `notification_id`.
- **Plan doc:** `docs/plans/NOTIFICATION_BANNERS_PLAN.md`

---

## Email Provider Abstraction

Pluggable email transport: SMTP (Gmail, dev default) or SendGrid (production).

- **Provider base:** `app/services/email/providers/base.py` — `EmailProvider` ABC with `send()` and `is_configured()`
- **Providers:** `smtp_provider.py` (Gmail SMTP), `sendgrid_provider.py` (SendGrid REST API)
- **Factory:** `app/services/email/provider_factory.py` — `get_email_provider()` returns singleton based on `EMAIL_PROVIDER` setting
- **Templates:** `app/services/email/templates/` — Jinja2 files with `base.html` inheritance. Renderer: `app/services/email/template_renderer.py`.
- **Integration:** `app/services/email_service.py` delegates `send_email()` to the configured provider. 18 email methods use `render_email()` for templates.
- **Categories:** `transactional`, `onboarding`, `customer-engagement`, `promotional` — passed to SendGrid for analytics.
- **Config:** `EMAIL_PROVIDER` (smtp/sendgrid), `SENDGRID_API_KEY`, `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`, `EMAIL_REPLY_TO` in `app/config/settings.py`
- **Domain:** `hello@vianda.market` (from, Google Workspace alias via `admin@vianda.market`), `support@vianda.market` (reply-to). SendGrid activation is a config-flip when volume justifies it.

---

## Ads Platform (Google Ads + Meta Ads)

Multi-platform ad management: server-side conversion uploads, geographic flywheel, click attribution, and campaign management (future). Full design: `docs/plans/GOOGLE_META_ADS_INTEGRATION_V2.md`.

### Architecture

- **Gateway pattern:** `AdsConversionGateway` ABC with Google, Meta, and mock implementations. Factory (`app/gateways/ads/factory.py`) routes by platform + settings (mock/live). Same pattern as `address_provider.py` and `payment_provider/`.
- **ARQ worker:** Background job queue via Redis for deferred conversion uploads. Google: 24h delay. Meta: 5min delay. Worker: `app/workers/conversion_worker.py`.
- **Payment-provider-agnostic:** Ads hook is at the subscription confirmation layer, not the Stripe webhook. `subscription_ads_hook.py` is called best-effort after db.commit. Adding MercadoPago only requires a new webhook handler calling the same hook.
- **PII security:** `pii_hasher.py` SHA256-hashes email/phone before enqueuing to Redis. Raw PII never enters the job queue or logs.

### Geographic Flywheel

- **Data model:** `core.ad_zone` table with lat/lon center + radius, flywheel state, metrics, budget allocation.
- **Flywheel states:** `monitoring` -> `supply_acquisition` -> `demand_activation` -> `growth` -> `mature` -> `paused`. Operator can force any transition (cold start support).
- **Zone creation:** Two paths: operator-created (cold start, no data needed) or advisor-proposed (DBSCAN clustering on notify-me leads, future Phase 22).
- **Zone metrics:** `zone_metrics_service.py` refreshes restaurant/subscriber counts within zone radius using SQL haversine. Notify-me leads matched by city name (no lat/lon on leads yet).
- **Audience export:** Hashed notify-me email lists per zone for Custom Audience upload.
- **Campaign structure:** One campaign per strategy (B2C/B2B employer/B2B restaurant), one ad set per zone, CBO with per-zone min budgets.

### Conversion Pipeline

```
Payment webhook -> subscription confirmed -> subscription_ads_hook.py [best-effort]
    -> conversion_service.enqueue_conversion_for_all_platforms()
        -> ARQ job per platform (deferred)
            -> factory.get_conversion_gateway(platform)
                -> MockConversionGateway (DEV_MODE)
                OR GoogleAdsConversionGateway (Enhanced Conversions)
                OR MetaConversionGateway (CAPI)
```

### Three Campaign Strategies

| Strategy | Code | Events | Target |
|----------|------|--------|--------|
| B2C Individual | `b2c_subscriber` | Subscribe, Purchase, StartTrial | Consumers |
| B2B Employer | `b2b_employer` | Lead, CompleteRegistration, Subscribe | HR directors |
| B2B Restaurant | `b2b_restaurant` | Lead, CompleteRegistration, ApprovedPartner | Restaurant owners |

### Key Entry Points

| Concern | Location |
|---------|----------|
| Gateway factory | `app/gateways/ads/factory.py` |
| Canonical models | `app/services/ads/models.py` |
| Conversion dispatch | `app/services/ads/conversion_service.py` |
| Subscription hook | `app/services/ads/subscription_ads_hook.py` |
| Zone management | `app/services/ads/zone_service.py` |
| Zone metrics refresh | `app/services/ads/zone_metrics_service.py` |
| Click tracking | `app/services/ads/click_tracking_service.py` |
| ARQ worker config | `app/workers/arq_settings.py` |
| Settings | `app/config/settings.py` (ADS_*, GOOGLE_ADS_*, META_ADS_*, ZONE_*, GEMINI_*) |
| DB tables | `core.ad_click_tracking`, `core.ad_zone`, `flywheel_state_enum` |

### Routes

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/v1/ad-tracking` | JWT (any) | Frontend submits click IDs |
| POST | `/api/v1/admin/ad-zones` | Internal | Create zone |
| GET | `/api/v1/admin/ad-zones` | Internal | List zones |
| GET | `/api/v1/admin/ad-zones/{id}` | Internal | Get zone |
| PATCH | `/api/v1/admin/ad-zones/{id}` | Internal | Update zone |
| POST | `/api/v1/admin/ad-zones/{id}/transition` | Internal | Force state transition |
| GET | `/api/v1/admin/ad-zones/{id}/overlaps` | Internal | Check overlaps |
| DELETE | `/api/v1/admin/ad-zones/{id}` | Internal | Delete zone |
| POST | `/api/v1/admin/ad-zones/sync-metrics` | Internal | Refresh all zone metrics (cron) |
| POST | `/api/v1/admin/ad-zones/{id}/sync-metrics` | Internal | Refresh single zone |
| GET | `/api/v1/admin/ad-zones/{id}/audience` | Internal | Export hashed audience |

### Tests

| What | How |
|------|-----|
| `app/gateways/ads/`, `app/services/ads/pii_hasher.py`, `app/services/ads/models.py`, `app/services/ads/error_handler.py` | pytest (73 tests in `app/tests/gateways/ads/`) |
| `app/services/ads/`, `app/routes/admin/ad_zones.py`, `app/routes/ad_tracking.py` | Postman collections (future) |

---

## Marketing Site (vianda-home) API Surface

Unauthenticated, rate-limited endpoints under `/api/v1/leads/*` that the marketing site reads on every page render. Two sub-groups with different bot-protection treatment:

- **Navbar-load country selectors — no reCAPTCHA, private/no-store cache, geo suggestion.** `/leads/countries` (customer-facing, `market_info.status = 'active'`) and `/leads/supplier-countries` (supplier form, `status IN ('active', 'inactive')`). Both return `LeadsCountriesResponseSchema`: `{countries: [{code, name, currency, phone_prefix, default_locale}], suggested_country_code: str|null}`. `suggested_country_code` is resolved from the `cf-ipcountry` request header (Cloudflare); returns `null` when CF is not in the deploy chain (current state: Cloud Run direct). `Cache-Control: private, no-store` because the envelope is per-visitor. `If-None-Match`/ETag/304 retired (no-store). Mounted on a sibling router (`app/routes/leads_country.py::public_router`) that skips the router-level `Depends(verify_recaptcha)`. **Breaking change from former `list[LeadsCountrySchema]` root response — now object envelope (kitchen #217).**
- **Country-scoped content reads — reCAPTCHA v3 required, `country_code` required.** `/leads/plans`, `/leads/restaurants`, `/leads/featured-restaurant`, `/leads/cities`, `/leads/city-metrics`, `/leads/zipcode-metrics`. Missing `country_code` → 400. Unsupported country → `[]` (plans, restaurants) or `null` (featured-restaurant), always 200 and cacheable. Replaces the prior "return everything across countries" behavior that caused the mixed-currency flood on the dev marketing site.

**Captcha-on-rate-limit (issue #218):** When the per-IP rate limit is tripped on any country-scoped leads read endpoint, the 429 response body includes two additive fields: `captcha_required: true` and `action: "leads_read"`. This is the signal for the frontend to refresh a reCAPTCHA v3 token and retry with `X-Recaptcha-Token` header. The existing `verify_recaptcha` dependency accepts the token on retry. The navbar-load country endpoints are excluded. Implementation: `application.py::_structured_rate_limit_handler` detects the path and adds the fields; no changes to `app/routes/leads.py` or `app/auth/recaptcha.py`. Full policy: `docs/plans/CAPTCHA_AND_RATE_LIMIT_ROADMAP.md`.

**Empty-state contracts are documented behavior.** `countries: []` from `/leads/countries` means the frontend hides the navbar selector and every country-scoped section. `countries: []` from `/leads/supplier-countries` means the supplier form drops the country dropdown and promotes `partners@vianda.market` as the primary CTA.

Full contract + examples: `docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md`. Cross-repo feedback note: `vianda-home/docs/frontend/feedback_for_backend/country-filter-backend.md`. Postman coverage: `docs/postman/collections/006 LEADS_MARKETING_SITE.postman_collection.json` — one collection per frontend consumer; conventions in `docs/postman/guidelines/LEADS_COLLECTION_CONVENTIONS.md`.

---

## Country / City / Currency Data Layer

Two-tier geographic and currency data model replacing the retired `core.city_info` and `core.credit_currency_info` tables.

- **External layer** (`external.*`): Read-only GeoNames + ISO 4217 data, bulk-seeded via `app/scripts/import_geonames.py`. Tables: `geonames_country`, `geonames_admin1`, `geonames_city`, `geonames_alternate_name`, `iso4217_currency`. CC-BY 4.0 licensed.
- **Metadata layer** (`core.*_metadata`): Vianda-owned operational config. Tables: `country_metadata` (audience flags, pricing policy), `city_metadata` (display overrides, geonames_id FK), `currency_metadata` (currency_code FK). Audited via `audit.*_history` triggers.
- **Timezone**: Lives on `address_info.timezone` (per-restaurant address), NOT on `market_info`. Derived from `external.geonames_city.timezone` at address write time. Market-level fallback for cron jobs: `TimezoneService._MARKET_PRIMARY_TIMEZONE`.
- **XG pseudo-country**: ISO 3166-1 user-assigned code for Vianda's Global market. Synthetic rows in `external.geonames_country` (name="Global") and `geonames_city` (geonames_id=-1). `core.city_metadata` Global row at UUID `aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa`.
- **Audience flags**: `country_metadata.is_customer_audience`, `is_supplier_audience`, `is_employer_audience` control `/leads/markets` and `/leads/cities` filtering.
- **Market operational status**: `market_info.status` is the source of truth for whether a country surfaces to customers. `active` → serving customers; surfaces in `/leads/countries` + scopes plans/restaurants/featured-restaurant. `inactive` → configured in `market_info` but not serving; surfaces only in `/leads/supplier-countries` (supplier application form). Admin overrides are guardrailed (`app/routes/admin/markets.py:update_market` — refuses `→ active` without coverage, warns on `→ inactive` when coverage exists). Automated status maintenance via a daily forward-window cron is tracked in `docs/plans/market-status-cron.md` (not yet implemented — admin-maintained in the interim).
- **Country/currency names**: Always derived via JOIN to external tables, never stored redundantly.
- **Institution-market link**: `core.institution_market` junction table assigns markets to institutions (replaces former `institution_info.market_id`). An institution can operate in multiple markets. Enriched institution responses include `market_ids` array.
- **Key files**: `app/db/schema.sql`, `app/db/seed/reference_data.sql`, `app/scripts/import_geonames.py`, `app/services/timezone_service.py`, `app/routes/admin/external_data.py`, `app/routes/leads.py`
- **Full reference**: `docs/api/internal/COUNTRY_CITY_DATA_STRUCTURE.md`

---

## Multinational Institutions

Institutions can operate across multiple countries. One institution = one set of admin users, one login. Country-specific concerns (legal entities, currencies, tax IDs, billing) live on `institution_entity_info`.

- **Institution-market junction:** `core.institution_market` replaces the former `institution_info.market_id` column. Admin-controlled multi-select. Entities can only be created in assigned markets.
- **Entity as country boundary:** `ops.institution_entity_info` is the legal/fiscal boundary for **both** supplier and employer institutions. Each entity has: `tax_id`, `currency_metadata_id`, `address_id` (with `country_code`), `payout_provider_account_id`, `email_domain` (for enrollment/SSO).
- **Three-tier cascade:** Both `supplier_terms` and `employer_benefits_program` support entity-level overrides via nullable `institution_entity_id`. Resolution: entity → institution → market/hardcoded defaults. Single-market institutions use institution-level defaults with no entity overrides.
- **Employer normalization:** `employer_info` and `employer_domain` tables removed. Employer identity = `institution_info` (type=employer) + `institution_entity_info`. `user_info.employer_entity_id` replaces `employer_id`. `email_domain` column on entity replaces `employer_domain` table.
- **Address types:** B2C customer addresses are user-selected (Home/Work/Other). `customer_employer` ("Work") is no longer auto-derived.
- **JWT `market_id`:** B2C-only (vianda/restaurant scoping). Orthogonal to institution structure. B2B users use primary market for language default.
- **Validation:** Entity creation validates address country against `institution_market`. User market assignments validate against `institution_market` (Internal bypasses).
- **Full design:** `docs/plans/MULTINATIONAL_INSTITUTIONS.md`

## Filter Subsystem

Declarative query-param filtering for list and enriched endpoints. Three components:

- **Registry** (`app/config/filter_registry.py`) — `FILTER_REGISTRY` dict mapping entity keys (`plans`, `restaurants`, `viandas`, `pickups`) to per-field dicts with `op`, `col`/`cols`, `alias`, `cast`, and optional `enum`.
- **Builder** (`app/utils/filter_builder.py`) — `build_filter_conditions(entity_key, filters)` dispatches on `op` (`eq`, `in`, `gte`, `lte`, `ilike`, `bool`) and emits `list[(condition_str, params)]` for `EnrichedService.get_enriched()`.
- **Schema** (`docs/api/filters.json`) — machine-generated frontend contract. Regenerated by `scripts/generate_filter_schema.py`. Synced by `scripts/check_filter_schema.sh` in CI. Consumed by `vianda-hooks`, `vianda-platform`, and `vianda-app`.

**Full contract doc:** `docs/api/filters.md`

---

## Image Processing Pipeline

Async image pipeline for product photos — libvips resizing (three derived sizes), Cloud Vision SafeSearch moderation, GCS upload. Full design doc (orchestrator level): `~/learn/vianda/docs/plans/image-processing-pipeline.md`

### Upload flow (Phase 2 — implemented)

Two-step signed-URL upload: client requests a signed PUT URL from kitchen, then uploads the file directly to GCS. Kitchen never touches the raw bytes.

```
POST /api/v1/uploads           → insert image_asset row (pipeline_status='pending'), return signed PUT URL
Client PUT file → GCS          → directly (signed URL, no kitchen involvement)
GET  /api/v1/uploads/{id}      → poll pipeline_status; signed read URLs returned only when 'ready'
DELETE /api/v1/uploads/{id}    → purge GCS blobs, remove row
```

**Replace semantics:** if an `image_asset` row already exists for the product on `POST /uploads`, the old GCS blobs are purged and the row deleted before a new row and signed URL are created.

**Auth:** Supplier admin or Internal employee. Suppliers are scoped to their own institution's products via `EntityScopingService.get_scope_for_entity(ENTITY_PRODUCT, current_user)`.

### Key files

| File | Purpose |
|---|---|
| `app/routes/uploads.py` | POST / GET / DELETE upload lifecycle endpoints |
| `app/utils/gcs.py` | `generate_image_asset_write_signed_url()`, `get_image_asset_signed_urls()`, `delete_image_asset_blobs()` |
| `app/db/migrations/0014_image_asset.sql` | Creates `ops.image_asset` + `audit.image_asset_history` |
| `app/db/migrations/0015_drop_inline_product_image.sql` | Drops inline image columns from `ops.product_info` + `audit.product_history` |
| `app/tests/utils/test_gcs.py` | 10 unit tests for the three GCS helpers |

### DB tables

- **`ops.image_asset`** — one row per product (UNIQUE on `product_id`). Columns: `image_asset_id` (UUIDv7 PK), `product_id` (FK → CASCADE), `institution_id` (denormalized for scoping), `original_storage_path` (nullable TEXT), `original_checksum` (nullable TEXT), `pipeline_status` (`pending|processing|ready|rejected|failed`), `moderation_status` (`pending|passed|rejected`), `moderation_signals` (JSONB), `processing_version`, `failure_count`, `modified_by`.
- **`audit.image_asset_history`** — trigger-managed history mirror; never written by application code.

### Removed (migration 0015)

Five inline image columns dropped from `ops.product_info` and `audit.product_history`: `image_storage_path`, `image_checksum`, `image_url`, `image_thumbnail_storage_path`, `image_thumbnail_url`. The `has_image` filter now joins `ops.image_asset` instead (via `image_asset_id` column in `app/config/filter_registry.py`).

### Error codes (new)

`upload.product_not_found` (404), `upload.access_denied` (403), `upload.not_found` (404), `upload.signed_url_failed` (500). Defined in `app/i18n/error_codes.py`; messages in `app/i18n/messages.py` (en/es/pt).

### Schemas (new, in `app/schemas/consolidated_schemas.py`)

- `UploadCreateRequest` — `{ product_id: UUID }`
- `UploadCreateResponse` — `{ image_asset_id: UUID, signed_write_url: str, expires_at: datetime }`
- `UploadStatusResponse` — `{ image_asset_id: UUID, product_id: UUID, pipeline_status: str, moderation_status: str, signed_urls: dict | null }` — `product_id` closes the round-trip gap: callers can navigate from an upload back to the product without a separate products lookup.

### Image state on ProductEnriched (slice 2e)

`GET /api/v1/products/enriched` and `GET /api/v1/products/enriched/{id}` surface image state directly on each product via a `LEFT JOIN ops.image_asset ia ON ia.product_id = p.product_id`. Fields added to `ProductEnrichedResponseSchema`:

| Field | Type | Notes |
|---|---|---|
| `image_asset_id` | UUID \| null | PK of the `image_asset` row. Null when no upload exists. Pass to `DELETE /uploads/{id}` for removal. |
| `image_pipeline_status` | str \| null | `pending\|processing\|ready\|rejected\|failed`. Null when no row. |
| `image_moderation_status` | str \| null | `pending\|passed\|rejected`. Null when no row. |
| `image_signed_urls` | dict \| null | `{hero, card, thumbnail}` signed read URLs. Non-null only when `pipeline_status == 'ready'`. Computed at response-build time via `get_image_asset_signed_urls()` in `app/utils/gcs.py`. |

Implementation: `_populate_product_image_signed_urls()` in `app/services/entity_service.py` runs after the DB SELECT, with a per-request cache keyed on `(institution_id, product_id)` to avoid duplicate GCS HMAC calls when the same product appears multiple times.

B2B list view should use `image_signed_urls['card']` (600×400) for the thumbnail. The `image_asset_id` field is the handle for the supplier "remove image" button.

### GCS blob layout

```
products/{institution_id}/{product_id}/original      ← supplier upload (kept forever as source of truth for backfill)
products/{institution_id}/{product_id}/hero           ← pipeline output (WebP, 1600×1066)
products/{institution_id}/{product_id}/hero.jpg       ← pipeline output (JPEG fallback, 1600×1066)
products/{institution_id}/{product_id}/card           ← pipeline output (WebP, 600×400)
products/{institution_id}/{product_id}/card.jpg       ← pipeline output (JPEG fallback, 600×400)
products/{institution_id}/{product_id}/thumbnail      ← pipeline output (WebP, 200×200)
products/{institution_id}/{product_id}/thumbnail.jpg  ← pipeline output (JPEG fallback, 200×200)
```

Bucket: `GCS_SUPPLIER_BUCKET`. Signed-URL expiry: `GCS_SIGNED_URL_EXPIRATION_SECONDS`.

Clients should prefer `.webp` blobs and fall back to `.jpg` based on browser/platform support. The `get_image_asset_signed_urls()` helper currently returns `{hero, card, thumbnail}` (WebP keys). JPEG fallback keys are present in GCS alongside the WebP blobs; the signed-URL helper can be extended to surface them when frontends need them.

### Container entrypoint — `RUN_MODE`

The Dockerfile `CMD` invokes `scripts/entrypoint.sh`, which dispatches on the `RUN_MODE` environment variable:

| `RUN_MODE` value | Behavior |
|---|---|
| unset or `api` | Start FastAPI via uvicorn (default — same as before) |
| `image_event` | Run `run_image_event_listener()` — Pub/Sub push HTTP listener (port `PORT`, default 8080) |
| `image_backfill` | Run `run_image_backfill()` — batch re-processing worker (exits 0 on completion) |
| any other value | Log warning to stderr, fall through to API mode |

### Worker modules (slice 2d — implemented)

| Module | Purpose |
|---|---|
| `app/workers/image_pipeline/__init__.py` | Public exports: `run_image_event_listener`, `run_image_backfill` |
| `app/workers/image_pipeline/processing.py` | Core: `process_image()`, `PROCESSING_VERSION`, moderation logic |
| `app/workers/image_pipeline/event_entrypoint.py` | FastAPI sub-app for Pub/Sub push delivery |
| `app/workers/image_pipeline/backfill_entrypoint.py` | Batch iterator for stale rows |

### Processing version model

`PROCESSING_VERSION = 1` is the current standard. Bumping it in `processing.py` causes `run_image_backfill()` to re-process all rows where `processing_version < PROCESSING_VERSION`. Backfill always uses `force=True`, so already-ready rows are reprocessed against the new standard.

### Pub/Sub ack-vs-nack contract

| Worker return | HTTP status | Pub/Sub effect |
|---|---|---|
| Success | 204 | Message acknowledged — not redelivered |
| Permanent failure (malformed path, product not found) | 4xx | Message acknowledged — not redelivered (drop) |
| Transient failure (processing error, GCS timeout) | 5xx | Message redelivered by Pub/Sub (retry) |

On transient failure, `process_image()` increments `failure_count`. After 3 failures, `pipeline_status` is flipped to `failed` and subsequent Pub/Sub redeliveries are silently acked (4xx path — see event_entrypoint.py comment).

### Moderation threshold

`MODERATION_REJECT_LIKELIHOOD` env var (default `LIKELY`). One of `UNKNOWN`, `VERY_UNLIKELY`, `UNLIKELY`, `POSSIBLE`, `LIKELY`, `VERY_LIKELY`. Any of `adult / violence / racy` at or above this level causes rejection. The original blob is purged on rejection. Signals are captured in `moderation_signals JSONB` for audit regardless of outcome.

### pyvips invocation pattern

```python
img = pyvips.Image.new_from_buffer(image_bytes, "", access="sequential")
resized = img.thumbnail_image(width, height=height,
    crop=pyvips.enums.Interesting.ATTENTION,
    size=pyvips.enums.Size.FORCE)
webp_bytes = resized.webpsave_buffer(strip=True, Q=85)
jpeg_bytes = resized.jpegsave_buffer(strip=True, Q=85)
```

`ATTENTION` crop selects the most visually interesting region. `FORCE` size ensures exact output dimensions even when the input aspect ratio differs. `strip=True` removes EXIF / ICC metadata for privacy and size reduction.

### Manual smoke test (dev environment)

Prerequisites: `RUN_MODE=image_event` Cloud Run job deployed to `vianda-dev`, GCS notifications wired to `vianda-dev-image-processing` Pub/Sub topic, push subscription pointed at the job's execution endpoint.

1. Log in to vianda-platform as a Supplier Admin.
2. Upload a product image via `POST /api/v1/uploads` — note the `image_asset_id`.
3. Use the signed PUT URL to upload a real JPEG to GCS (e.g. `curl -X PUT -T photo.jpg "$SIGNED_URL"`).
4. Wait ~10-30s for the Pub/Sub notification round-trip.
5. Poll `GET /api/v1/uploads/{image_asset_id}` until `pipeline_status` is `ready` (or `rejected` / `failed`).
6. When `ready`, verify `signed_urls` contains `hero`, `card`, `thumbnail` keys and that URLs resolve to valid WebP images.
7. For a moderation test: upload an image that triggers SafeSearch rejection. Verify `pipeline_status=rejected`, `moderation_status=rejected`, and `moderation_signals` contains the signal that tripped the threshold.

### System dependency

`libvips` is installed in the Dockerfile via `apt-get install -y libvips`. Required by `pyvips` (Python bindings). Only affects the Docker image layer; no local-dev change needed unless running image-processing code locally.

### Env vars (image pipeline)

| Var | Default | Description |
|---|---|---|
| `RUN_MODE` | `api` | Container dispatch mode: `api`, `image_event`, `image_backfill` |
| `MODERATION_REJECT_LIKELIHOOD` | `LIKELY` | SafeSearch rejection threshold (adult/violence/racy) |
| `PORT` | `8080` | HTTP port for `image_event` listener (Cloud Run assigns this) |

### Tests

`app/tests/workers/test_image_pipeline_processing.py` — 21 pytest unit tests covering all `process_image` paths (happy path, idempotent re-run, force re-run, moderation rejection, threshold override, failure retry at counts 1/2/3). All GCS/Vision/pyvips/DB calls fully mocked.

---

## Demo Seed Subsystem

Three-layer dataset (PE + AR + US) that populates a narrative demo for stakeholder presentations against the dev environment. Never loaded in staging or production. Requires `PAYMENT_PROVIDER=mock` so subscriptions and orders flow through the API rather than SQL. Every demo address is created via the production Mapbox `suggest → create` flow; the geocode cache (`seeds/mapbox_geocode_cache.json`) replays these calls in `replay_only` mode so no live Mapbox calls are made on subsequent loads.

- **Layer A — `app/db/seed/demo_baseline.sql`:** SQL-only entities that must pre-exist before the API starts: the primary demo supplier institution (PE/AR/US markets, shared), three secondary supplier institutions (one per market), and the demo super-admin user (`demo-admin@vianda.market`). All rows use the `dddddddd-dec0-` UUID prefix and are idempotent (`ON CONFLICT ... DO UPDATE`). Does NOT create addresses, institution entities, or restaurants — those live in Layer B so they pass through Mapbox geocoding.
- **Layer B — `docs/postman/collections/900_DEMO_DAY_SEED.postman_collection.json`:** Newman collection (~900+ requests, PE + AR + US) running the full mock-Stripe happy path across all three markets. Per-market flow: Mapbox suggest→create for supplier office address → Mapbox suggest→create for each restaurant address → upsert institution entities by `canonical_key` → upsert restaurants → products/viandas/PKDs → plan → 7 customer signups (email-verified, neighborhood addresses via Mapbox) → 5–7 subscriptions → order loops → reviews. Additionally seeds employer institutions (3 markets), employer entities/offices (Mapbox addresses), employee signups, enrolments, and secondary supplier institutions (canonical_key entity upsert). Settlement pipeline runs in folder 45 for primary suppliers.
- **Layer C — `app/db/seed/demo_billing_backfill.sql`:** SQL run after Newman. Inserts 2 billing rows per secondary supplier (1 pending + 1 paid) to populate vianda-platform Billing/Invoices/Payouts pages. Secondary supplier entity UUIDs are DB-assigned at Newman runtime; Layer C resolves them by `canonical_key` (`DEMO_INSTITUTION_ENTITY_PE2/AR2/US2`). Will raise an error if Layer B has not run.
- **Dev wrapper — `app/db/build_dev_db.sh`:** One-command dev-rebuild driver above the demo loader. Calls `build_kitchen_db.sh` (schema + reference + dev fixtures) then `load_demo_data.sh` (demo_baseline.sql + 900 Newman seed). Pass `--target=local|gcp-dev` (forwarded to the loader). Used by the `db-reset-dev.yml` GH Actions workflow (`--target=gcp-dev`) and by devs locally (default `--target=local`). `build_kitchen_db.sh` itself stays the primitive — staging/prod composition (when those envs exist) will compose from it without the demo layer.
- **Loader — `scripts/load_demo_data.sh`:** Runs Layer A [1/5], generates and hashes a random demo-admin password [2/5], probes the API health endpoint [3/5], runs Newman [4/5], and runs Layer C billing backfill [5/5]. Prints credentials to stdout and `.demo_credentials.local` (gitignored). Two targets: `--target=local` (default; requires `PAYMENT_PROVIDER=mock`, runs against laptop API on `:8000`) and `--target=gcp-dev` (drives the deployed dev API, confirms PaymentIntents directly against Stripe sandbox using `STRIPE_SECRET_KEY` test key). Always refuses on non-`dev` ENV or staging/prod-smelling hosts.
- **GCP wrapper — `scripts/load_demo_data_gcp.sh`:** Convenience wrapper for the `gcp-dev` target. Discovers project/region/Cloud Run URL/Cloud SQL instance from gcloud; starts `cloud-sql-proxy` in the background (trap-cleaned on exit); pulls `STRIPE_SECRET_KEY` and the dev DB password from Secret Manager; execs the underlying loader. Accepts `--purge` and `--purge-only` for one-command resets. Refuses any stack other than `dev`.
- **Purge — `scripts/purge_demo_data.sh`:** Deletes all demo rows in child-first dependency order, wrapped in a single transaction. Matches: UUID prefix `dddddddd-dec0-` (institutions, admin user, dec0-prefixed entities), canonical key `DEMO_*` (restaurants, viandas, plans, employer entities, Newman-created supplier entities), username patterns (`demo.cliente.%@vianda.demo` etc.), and `dddddddd-dec0-0050%` bill IDs (Layer C billing rows whose entity FKs are dynamic). Transactional descendants (subscriptions, orders, reviews, pipeline billing rows) carry system-generated UUIDs and are matched via FK chains.
- **Geocode cache — `seeds/mapbox_geocode_cache.json`:** Committed replay cache for all 48 demo addresses (21 customer + 18 restaurant + 3 supplier offices + 3 secondary supplier offices + 3 employer offices). Cache is in `replay_only` mode by default; set `MAPBOX_CACHE_MODE=record` to re-record live Mapbox responses. Cache key format: `{op}|{normalized_q}|{country}|{language}|permanent={true|false}`.
- **Environment — `docs/postman/environments/dev.postman_environment.json`:** Dev-local Postman environment; adds `demoAdminUsername`, `demoAdminPassword`, `mediaBaseUrl`, `customerSharedPassword` on top of the standard CI vars.
- **Re-run posture:** Customer signups and transactional events are NOT idempotent. Reset pattern: `bash scripts/purge_demo_data.sh && bash scripts/load_demo_data.sh`.
- **Mechanics guide:** `docs/guidelines/database/DATABASE_REBUILD_PERSISTENCE.md` — "Demo Data (Third Layer)" section.
- **Dataset narrative (what's in it, persona table, feedback log):** `docs/guidelines/database/DEMO_DAY_DATASET.md`. Update this doc when the dataset changes or when stakeholder demos surface gaps.

---

## CI/CD

### Workflows

| File | Trigger | Purpose | Label gate |
|---|---|---|---|
| `.github/workflows/ci.yml` | PR to `main`, push to `main` | Lint/type/complexity/security/SQL/license/pytest/Newman acceptance. `ci-pass` aggregator job is the single required check for branch protection. | — |
| `.github/workflows/mutation.yml` | PR or push touching Tier-1 services, `workflow_dispatch` | Mutation testing via `mutmut` against money/credit business logic. Cache restored from `main`. | — |
| `.github/workflows/deploy.yml` | PR merged with label, `workflow_dispatch` (reason required) | Builds Docker image → Artifact Registry → `gcloud run services update` on Cloud Run dev service. No auto-deploy on every merge. | `deploy:dev` |

### Label semantics

- **`deploy:dev`** — opt-in gate on `deploy.yml`. Apply before merging a PR that should ship to the dev Cloud Run service (`vianda-dev-api` in `kitchen-dev-490222`). Merging without the label is a no-op for deploy.

### Deploy command

```
gcloud run services update ${CLOUD_RUN_SERVICE} \
  --image us-central1-docker.pkg.dev/${GCP_PROJECT}/kitchen/kitchen-backend:<sha7>-<ts> \
  --region us-central1 --project ${GCP_PROJECT}
```

Image tag format: `${GITHUB_SHA::7}-YYYYMMDDHHMMSS`. Auth is Workload Identity Federation — no service-account key secret in the repo.

### Rollback

Actions → *Deploy Kitchen Backend* → *Run workflow* → pick an older SHA as the ref, supply a `reason` like `"rollback to <sha>"`. The `run-name` surfaces the reason in the run title.

### Dependabot

`.github/dependabot.yml` — one weekly (Mondays 09:00 America/New_York) grouped `pip-minor-patch` PR + one grouped `github-actions` PR. Majors for system-critical libraries (fastapi, pydantic, psycopg2-binary, stripe, google-*, redis, httpx, etc.) are deferred and must be proposed as tracked manual migrations.

### Prerequisites (operational setup)

GitHub Environment `dev` on this repo needs variables `WIF_PROVIDER`, `DEPLOY_SA`, `GCP_PROJECT`, `CLOUD_RUN_SERVICE`. Full one-time setup (environments, WIF, Pulumi outputs): `infra-kitchen-gcp/docs/plans/ci-cd-activation-manual.md`.

<!-- vianda-siblings-backlinks -->
## Siblings

Part of the `~/learn/vianda/` tree. Cross-repo index at `/Users/cdeachaval/learn/vianda/CLAUDE_ARCHITECTURE.MD`.

- **infra-kitchen-gcp** — Pulumi + GCP infra; source of truth for GCP resources, WIF, CI deploy flow. `/Users/cdeachaval/learn/vianda/infra-kitchen-gcp/CLAUDE_ARCHITECTURE.MD`
- **vianda-platform** — B2B admin React web frontend. `/Users/cdeachaval/learn/vianda/vianda-platform/CLAUDE_ARCHITECTURE.MD`
- **vianda-app** — B2C consumer React Native app. `/Users/cdeachaval/learn/vianda/vianda-app/CLAUDE_ARCHITECTURE.MD`
- **vianda-home** — B2B2C React web marketing site. `/Users/cdeachaval/learn/vianda/vianda-home/CLAUDE_ARCHITECTURE.MD`
- **vianda-hooks** — Shared frontend hooks package. `/Users/cdeachaval/learn/vianda/vianda-hooks/CLAUDE_ARCHITECTURE.MD`
