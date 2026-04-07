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
├── core/                    # Versioning infrastructure
│   └── versioning.py        # create_versioned_router, APIVersion
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
│   └── google_places_gateway.py  # Google Places API (fallback provider)
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
│   └── payment_provider/    # Stripe inbound (live, mock) + Connect outbound (connect_gateway, connect_mock)
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
5. **Custom/manual routes** (not in CRUD routers): plate_selection, plate_pickup, plate_review, favorite, employer, address, qr_code, restaurant, restaurant_balance, restaurant_transaction, restaurant_staff, plate_kitchen_days, national_holidays, restaurant_holidays, client_bill, institution_bill, supplier_invoice, ingredients, markets, countries, currencies, cities, provinces, cuisines, leads, locales, webhooks, customer payment_methods, enums, admin discretionary, super_admin discretionary, archival, archival_config, admin leads.
6. **Registration order:** Institution entities router registered before CRUD so `/enriched` matches before `/{entity_id}`. Manual/custom routes must be registered before auto-generated if they share paths (FastAPI matches first).

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
| Leads | `/api/v1/leads/*` | None, rate-limited, reCAPTCHA v3 required (exempt for b2c-mobile) |
| Locales | `/api/v1/locales` | None, cacheable |

---

## Versioning

- **Strategy:** URL path (`/api/v1/...`).
- **Implementation:** `app/core/versioning.py` — `create_versioned_router(prefix, tags, version)`.
- Route files define prefix without version (e.g. `/plans`); the wrapper adds `/api/v1`.

---

## Scoping

- **Employee (Internal):** Global (all institutions).
- **Supplier:** Scoped to `institution_id` from JWT.
- **Employer:** Institution-scoped (like Supplier).
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

Enterprise meal subscription benefits — employers subsidize employee meal plans with configurable rate + cap.

- **Data model:** `core.employer_benefits_program` (one row per Employer institution: benefit_rate, benefit_cap, benefit_cap_period, price_discount, minimum_monthly_fee, billing_cycle, enrollment_mode, allow_early_renewal). `billing.employer_bill` (aggregated employer invoices). `billing.employer_bill_line` (per-renewal line items with snapshotted rates).
- **Services:** `app/services/employer/program_service.py` (program CRUD), `app/services/employer/enrollment_service.py` (single + bulk employee enrollment, deactivation, subscription), `app/services/employer/billing_service.py` (bill generation, benefit calculator)
- **Routes:** `app/routes/employer_program.py` — POST/GET/PUT `/employer/program`, POST/GET/DELETE `/employer/employees`, POST `/employer/employees/bulk`, POST `/employer/employees/{user_id}/subscribe`, POST/GET/DELETE `/employer/domains`, GET `/employer/billing`, POST `/employer/billing/generate`, POST `/employer/billing/run-cron`
- **Schemas:** `app/schemas/employer_program.py`
- **Key design:** Benefit employees are Customer Comensals assigned to the Employer's institution (not Vianda Customers). Created directly via `user_service.create()` bypassing `process_admin_user_creation()` which would force Vianda Customers assignment. Fully subsidized subscriptions activate immediately with no Stripe payment. Partial subsidy: employee self-subscribes via `POST /subscriptions/with-payment` — backend detects employer benefit and charges employee their share only.
- **Domain-gated enrollment:** `core.employer_domain` table maps email domains to employer institutions. B2C signup (`_apply_customer_signup_rules` in `user_signup_service.py`) checks email domain before assigning institution. Retroactive migration on domain creation moves existing users to employer institution.
- **Billing cron:** `app/services/cron/employer_billing.py` — checks all active programs, generates bills where due (daily/weekly/monthly). Month-end minimum fee reconciliation for sub-monthly cycles.
- **B2B login restriction:** Customer Comensals blocked from B2B platform login when `x-client-type: b2b` header is sent. Returns structured 403 with app store URLs.
- **Benefit employee invite:** Dedicated email template via `email_service.send_benefit_employee_invite_email()` with app download links.
- **Benefit plans endpoint:** `GET /subscriptions/benefit-plans` in `route_factory.py` returns plans with employer/employee split breakdown for B2C app.
- **Enums:** `benefit_cap_period_enum` (per_renewal, monthly), `enrollment_mode_enum` (managed, domain_gated), `billing_cycle_enum` (daily, weekly, monthly), `employer_bill_payment_status_enum` (Pending, Paid, Failed, Overdue)
- **Roadmap:** `docs/plans/vianda_employer_benefits_program.md`

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
- **Payout gate config:** `billing.market_payout_aggregator` (`require_invoice`, `max_unmatched_bill_days`) + per-supplier override on `billing.supplier_terms` (`require_invoice`, `invoice_hold_days`)
- **Supplier terms:** `billing.supplier_terms` (1:1 with Supplier institution) — `no_show_discount`, `payment_frequency`, `require_invoice`, `invoice_hold_days`. Audit: `audit.supplier_terms_history`. Routes: `app/routes/supplier_terms.py` (GET/PUT). Resolution: `app/services/billing/supplier_terms_resolution.py`.
  - `no_show_discount` → plate enriched queries + promotion service transaction creation
  - `payment_frequency` → gates bill creation in `institution_billing.py:run_phase2_bills_and_payout()` via `_is_supplier_payout_due()` (settlements accumulate daily; bills created only when due)
  - `require_invoice` + `invoice_hold_days` → invoice compliance gate in payout loop via `_check_invoice_compliance()` (blocks payout if entity has unmatched bills older than threshold)
  - Effective value resolution (supplier override > market default) in `supplier_terms_resolution.py`, shared by API and billing pipeline
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
- **Employer checklist:** Same endpoint, different items: `has_benefits_program`, `has_email_domain`, `has_enrolled_employee`, `has_active_subscription`. Dispatched by `institution_type`.
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

- **Handed Out status:** New `status_enum` value. Lifecycle: `Pending → Arrived → Handed Out → Completed`. Separates "customer is here" from "plate was given" from "customer confirms."
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
- **Routes:** `app/routes/notification_banner.py` — `GET /notifications/active` (Customer, polled every 60s), `POST /notifications/{id}/acknowledge` (Customer), `POST /notifications/expire` (Internal, cron trigger).
- **Survey trigger:** Wired into `PlatePickupService.complete_order()` in `plate_pickup_service.py` — creates `survey_available` banner after successful pickup completion (best-effort, fail-silent).
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
