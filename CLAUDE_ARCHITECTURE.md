# Kitchen API Architecture

**Purpose:** Fast reference for AI-assisted development. Reduces exploratory searches and provides structural context in one place.

**Keep in context with:** [CLAUDE.md](./CLAUDE.md)

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
│   ├── settings.py          # App settings, env vars
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
│   ├── address_provider.py       # Factory: get_search_gateway(), get_geocoding_gateway() — driven by ADDRESS_PROVIDER setting
│   ├── mapbox_search_gateway.py  # Mapbox Search Box API (suggest + retrieve) — default provider
│   ├── mapbox_geocoding_gateway.py # Mapbox Geocoding API v6 (forward + reverse) — default provider
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
│   └── messages.py          # Message catalog stub (get_message, future error/alert i18n)
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
│   └── *.py                 # Domain routes (plate_selection, restaurant, address, etc.)
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
│   ├── cron/                # billing_events, currency_refresh, holiday_refresh, wikidata_enrichment, supplier_stall_detection, etc.
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
├── workers/                 # ARQ background tasks (ads conversion uploads)
│   ├── arq_settings.py      # ARQ WorkerSettings (Redis config, job timeout, retry)
│   └── conversion_worker.py # upload_conversion task (platform-agnostic, routes via factory)
└── utils/                   # Helpers
    ├── db.py                # db_read, db_write, get_db_connection
    ├── db_pool.py           # Connection pool, get_db_connection_context
    ├── country.py           # Country code utilities: normalize, alpha-2/3 conversion, name resolution
    ├── map_projection.py    # Web Mercator projection: lat/lng → pixel position, grid cells, zoom computation
    ├── log.py
    ├── gcs.py               # Google Cloud Storage (products, QR codes, supplier invoices)
    ├── checksum.py
    └── rate_limit.py

application.py               # FastAPI app, route registration, lifespan
```

---

## Route Registration Flow

1. **`application.py`** creates the app and registers all routers.
2. **Versioned wrappers:** Every business route uses `create_versioned_router("api", ["Tag"], APIVersion.V1)` → prefix `/api/v1`.
3. **Two CRUD routers:**
   - **`crud_routes.py`** → Admin/System CRUD (no user context): Product, Plan, Restaurant, CreditCurrency, Institution, Plate, Geolocation, InstitutionEntity.
   - **`crud_routes_user.py`** → User CRUD (user_id from `current_user`): Subscription, PaymentMethod; includes subscription_payment (with-payment, confirm-payment) before generic CRUD.
4. **Route factory** (`app/services/route_factory.py`) generates standard CRUD routes via `create_plan_routes()`, `create_product_routes()`, etc.
5. **Custom/manual routes** (not in CRUD routers): plate_selection, plate_pickup, plate_review, favorite, address, qr_code, restaurant, restaurant_balance, restaurant_transaction, restaurant_staff, plate_kitchen_days, national_holidays, restaurant_holidays, client_bill, institution_bill, supplier_invoice, ingredients, markets, countries, currencies, cities, provinces, cuisines, leads, locales, webhooks, customer payment_methods, enums, admin discretionary, super_admin discretionary, archival, archival_config, admin leads. (**employer routes removed** — employer identity is `institution_info` + `institution_entity_info`.)
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
| Admin (versioned) | `/api/v1/admin/archival/*`, `/api/v1/admin/archival-config/*`, `/api/v1/admin/discretionary/*`, `/api/v1/admin/markets/*`, `/api/v1/admin/leads/*` | Internal |
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

## Subscription Renewal Control

User-configurable early renewal threshold on `customer.subscription_info`.

- **Column:** `early_renewal_threshold INTEGER DEFAULT 10` — NULL = period-end only (renew only at 30-day mark); integer = renew early when balance drops below this value at order time.
- **Two renewal triggers:** Time-based cron (`app/services/cron/subscription_renewal.py`) always renews at 30-day mark regardless of threshold. Low-balance early renewal (`app/services/plate_selection_service.py`) checks `subscription.early_renewal_threshold` — skips if NULL.
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
- **Routes:** `app/routes/employer_program.py` — POST/GET/PUT `/employer/program`, POST/GET/DELETE `/employer/employees`, POST `/employer/employees/bulk`, POST `/employer/employees/{user_id}/subscribe`, GET `/employer/billing`, POST `/employer/billing/generate`, POST `/employer/billing/run-cron`. Domain routes removed (domain managed via entity CRUD).
- **Schemas:** `app/schemas/employer_program.py` — `ProgramCreateSchema` accepts optional `institution_entity_id`.
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
  - `no_show_discount` → plate enriched queries + promotion service transaction creation
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

Backend-computed onboarding checklist for Supplier/Employer institutions. Tracks 7-item setup progress (address → entity → restaurant → product → plate → kitchen_day → qr_code).

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

## Plate Pickup Flow (B2C)

QR-code-based pickup confirmation flow for the B2C mobile app.

- **Signed QR codes:** `https://vianda.app/qr?id={qr_code_id}&sig={hmac_hex16}`. HMAC-SHA256 over `qr_code_id` using `QR_HMAC_SECRET`, truncated to 16 hex chars.
- **QR generation:** `app/services/qr_code_service.py` — `create_qr_code_atomic()` inserts QR record, computes signed URL, generates PNG image. QR image encodes the signed URL.
- **HMAC utility:** `app/utils/qr_hmac.py` — `sign_qr_code_id()`, `verify_qr_signature()`, `build_signed_qr_url()`
- **Scan endpoint:** `POST /api/v1/plate-pickup/scan-qr` — accepts `{ qr_code_id, sig }`, verifies HMAC, returns pickup confirmation with `plate_pickup_ids`, `restaurant_name`, `plates[]`, `countdown_seconds`, `max_extensions`, `confirmation_code`.
- **Completion tracking:** `POST /api/v1/plate-pickup/{id}/complete` — accepts optional `{ completion_type }` (`user_confirmed` | `timer_expired`). Stored on `plate_pickup_live.completion_type` for analytics.
- **Timer config:** Global via `PICKUP_COUNTDOWN_SECONDS` (default 300) and `PICKUP_MAX_EXTENSIONS` (default 3) in `app/config/settings.py`.
- **Plate reviews:** `POST /api/v1/plate-reviews` — extended with `would_order_again` (bool) and `comment` (varchar 500). Comments surface to restaurants in B2B only, not in B2C app.
- **Error codes:** `invalid_signature` (400), `wrong_restaurant` (400), `outside_pickup_hours` (400), `no_active_reservation` (404).
- **Service:** `app/services/plate_pickup_service.py` — `scan_qr_code_by_id()` (new, signed), `scan_qr_code_simplified()` (deprecated, payload-based).
- **Supplier review endpoint:** `GET /api/v1/plate-reviews/by-institution/enriched` — institution-scoped, returns plate name + restaurant name + ratings + comment. No customer PII. Optional `?plate_id` and `?restaurant_id` filters. Service: `get_enriched_reviews_by_institution()` in `app/services/plate_review_service.py`.
- **Portion complaints:** `POST /api/v1/plate-reviews/{id}/portion-complaint` — customer files complaint after rating portion size as 1. Accepts photo (multipart) + text. Table: `customer.portion_complaint`. Photos in GCS customer bucket.

### Kiosk Mode (B2B)

Tablet/phone-optimized views for restaurant operators handling pickups during service hours.

- **Handed Out status:** New `status_enum` value. Lifecycle: `pending → arrived → handed_out → completed`. Separates "customer is here" from "plate was given" from "customer confirms."
- **Numeric confirmation codes:** 6-digit numeric (not alphanumeric) for fast kiosk entry. Generated in `_generate_confirmation_code()` in `plate_pickup_service.py`.
- **Enhanced daily-orders:** `GET /api/v1/restaurant-staff/daily-orders` now includes per-order: `plate_pickup_id`, `expected_completion_time`, `completion_time`, `countdown_seconds`, `extensions_used`, `was_collected`, `confirmation_code`, `pickup_type`. Per-restaurant: `pickup_window_start/end`, `require_kiosk_code_verification`. Response: `server_time` for timer sync. Privacy: initials only (M.G.).
- **Verify-and-handoff:** `POST /api/v1/restaurant-staff/verify-and-handoff` — Layer 2 code verification. Clerk enters numeric code, system verifies and transitions to Handed Out. Consumes the code.
- **Hand-out:** `POST /api/v1/plate-pickup/{id}/hand-out` — Layer 1 one-tap handoff. Transitions Arrived → Handed Out without code entry.
- **Per-restaurant toggle:** `require_kiosk_code_verification` boolean on `restaurant_info`. Supplier Admin only.
- **Supplier Operator restrictions:** Operators are blocked from all CRUD management routes (via `ensure_supplier_admin_or_manager()` in route factory). Operators can access: daily orders, verify code, hand out, mark complete, view feedback, self-profile.
- **Trust model:** See `docs/plans/PICKUP_HANDOFF_TRUST_MODEL.md` for the layered trust strategy.
- **Push notifications (FCM):** `core.user_fcm_token` stores device tokens. `POST/DELETE /users/me/fcm-token` for registration/logout. `app/services/push_notification_service.py` sends FCM push on Handed Out transition (checks `notify_plate_readiness_alert` preference). `app/services/fcm_token_service.py` manages token lifecycle. Config: `FIREBASE_CREDENTIALS_PATH` (empty = push disabled, logs instead).

---

## In-App Notification Banners

Cross-platform in-app notification banner system. Frontends poll for active banners; backend owns creation, expiry, deduplication, and client-type filtering.

- **Data model:** `customer.notification_banner` — JSONB payload, dedup via `UNIQUE(user_id, dedup_key)`, `action_status` lifecycle (`active` → `dismissed`/`opened`/`completed`/`expired`), `client_types` array for backend-owned filtering.
- **Enums:** `notification_banner_type_enum` (`survey_available`, `peer_pickup_volunteer`, `reservation_reminder`), `notification_banner_priority_enum` (`normal`, `high`), `notification_banner_action_status_enum` (`active`, `dismissed`, `opened`, `completed`, `expired`).
- **Service:** `app/services/notification_banner_service.py` — `create_notification()` (raw SQL with ON CONFLICT dedup), `get_active_notifications()` (max 5, high priority first, 2h grace for surveys), `acknowledge_notification()` (idempotent), `expire_stale_notifications()` (bulk cleanup).
- **Routes:** `app/routes/notification_banner.py` — `GET /notifications/active` (Customer, polled every 60s), `POST /notifications/{id}/acknowledge` (Customer), `POST /notifications/expire` (Internal, cron trigger), `POST /notifications/generate-reminders` (Internal, cron trigger).
- **Survey trigger:** Wired into `PlatePickupService.complete_order()` in `plate_pickup_service.py` — creates `survey_available` banner after successful pickup completion (best-effort, fail-silent).
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

- **Navbar-load country selectors — no reCAPTCHA, ETag + long cache.** `/leads/countries` (customer-facing, `market_info.status = 'active'`) and `/leads/supplier-countries` (supplier form, `status IN ('active', 'inactive')`). Both return `[{code, name, currency, phone_prefix, default_locale}]`, honor `If-None-Match` → 304, and set `Cache-Control: public, max-age=86400, stale-while-revalidate=3600`. Mounted on a sibling router (`app/routes/leads.py::public_router`) that skips the router-level `Depends(verify_recaptcha)`.
- **Country-scoped content reads — reCAPTCHA v3 required, `country_code` required.** `/leads/plans`, `/leads/restaurants`, `/leads/featured-restaurant`. Missing `country_code` → 400. Unsupported country → `[]` (plans, restaurants) or `null` (featured-restaurant), always 200 and cacheable. Replaces the prior "return everything across countries" behavior that caused the mixed-currency flood on the dev marketing site.

**Empty-state contracts are documented behavior.** `[]` from `/leads/countries` means the frontend hides the navbar selector and every country-scoped section. `[]` from `/leads/supplier-countries` means the supplier form drops the country dropdown and promotes `partners@vianda.market` as the primary CTA. The 429 → reCAPTCHA-unlock handshake for country-scoped reads is planned for a v2 ticket.

**ETag strategy (option c):** hash over response-field values + per-row `market_info.modified_date` and `currency_metadata.modified_date` + the `language` query param. No triggers, no materialized invalidation columns — natural invalidation via `modified_date` bumps when admins flip status or edit currencies.

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
- **JWT `market_id`:** B2C-only (plate/restaurant scoping). Orthogonal to institution structure. B2B users use primary market for language default.
- **Validation:** Entity creation validates address country against `institution_market`. User market assignments validate against `institution_market` (Internal bypasses).
- **Full design:** `docs/plans/MULTINATIONAL_INSTITUTIONS.md`

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
