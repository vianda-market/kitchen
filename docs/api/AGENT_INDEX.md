# Kitchen API — Agent Documentation Index

Single reference for all API integration docs in this repository.
Add this file's path to your repo's `CLAUDE.md` to give your agent full context.

```
/Users/cdeachaval/learn/vianda/kitchen/docs/api/AGENT_INDEX.md
```

**Plans index** (planned features, cross-repo coordination): `/Users/cdeachaval/learn/vianda/kitchen/docs/plans/AGENT_INDEX.md`
**Live schema** (when backend is running): `http://localhost:8000/openapi.json`
**TypeScript types**: `npx openapi-typescript http://localhost:8000/openapi.json -o src/api/types.ts`
**Auth**: `POST /api/v1/auth/token` → `Authorization: Bearer {token}`

**Audience key**: `B2C` = kitchen-mobile (Customer role) · `B2B` = kitchen-web (Employee/Supplier roles) · `Both` = applies to both

---

## Start Here — Entry Points

| Audience | File | Description |
|----------|------|-------------|
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/FRONTEND_AGENT_README.md` | B2C agent entry point — auth, essential docs, codegen |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/FRONTEND_AGENT_README.md` | B2B agent entry point — auth, roles, essential docs |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/B2C_ENDPOINTS_OVERVIEW.md` | Complete index of Customer-accessible endpoints |

---

## Data Structures

| Audience | File | Description |
|----------|------|-------------|
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/DATA_STRUCTURES.md` | Enum convention, enum API endpoint format, all enum values |

---

## Authentication & Users
_Routes: `/auth/token`, `/users/`, `/users/me`, `/customers/signup/`_

| Audience | File | Description |
|----------|------|-------------|
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/USER_MODEL_FOR_CLIENTS.md` | User model, roles, `/users/me`, mobile number format, recovery |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/API_PERMISSIONS_BY_ROLE.md` | Which endpoints each role (Customer, Supplier, Employee) can access |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_ROLE_FIELD_ACCESS.md` | Route-level and field-level access matrix by role |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md` | Customer signup flow with email verification |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/B2B_USER_INVITE_FLOW.md` | Invited users set their own password via email link |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_PASSWORD_MANAGEMENT.md` | Password change and admin-triggered user reset |

---

## Discovery & Onboarding
_Routes: `/leads/`, `/markets/`, `/enums/`, `/institutions/{id}/onboarding-status`, `/users/me/onboarding-status`_

| Audience | File | Description |
|----------|------|-------------|
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_ONBOARDING_STATUS.md` | Supplier/employer onboarding status — 7-item checklist, JWT claim, gated navigation, dashboard progress |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/ONBOARDING_STATUS_DELIVERY_RESPONSE.md` | Delivery response: all 6 items complete, summary endpoint shape, stall detection, activity tracking, open questions answered |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/CUSTOMER_ONBOARDING_STATUS_B2C.md` | Customer onboarding — email verification + subscription checklist, JWT claim, subscribe prompts |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/ONBOARDING_CLARIFICATIONS_B2C.md` | Clarifications: JWT on all flows, sync status, deep links, email suppression, deferred endpoints |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/MARKET_CITY_COUNTRY.md` | Market, city & country selection — `/leads/markets`, `/leads/cities` (audience-aware), `/cities` (auth), `/admin/external/*` picker, `city_metadata_id` requirement for addresses |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/LEADS_ENDPOINTS_MIGRATION.md` | Market dropdown migrated from `/markets` to `/leads` — migration guide |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/ENUM_SERVICE_API.md` | Enum Service API — endpoints, value/title contract, caching, role filtering, TypeScript types |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/zArchive/ENUM_SERVICE_SPECIFICATION.md` | _(Archived)_ Original frontend request — superseded by ENUM_SERVICE_API.md |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/LANGUAGE_AND_LOCALE_FOR_CLIENTS.md` | i18n scaffolding — locales endpoint, locale-aware market names, BCP 47 locale field, enum labels, JWT locale claim |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/ERROR_ENVELOPE_FOR_CLIENTS.md` | Error response envelope (one-page frontend integration guide) — wire shape, `resolveErrorMessage` helper usage, code switch-on examples, per-frontend wiring notes |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_MARKETS.md` | Markets API — multi-currency, multi-timezone, institution scoping. Enriched endpoints expose `is_ready_for_signup` (computed, no DB column — see Market Readiness below) |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_INSTITUTIONS.md` | Multinational institution model — `market_ids` array, entity-based employers, `email_domain` |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/ZIPCODE_METRICS_LEAD_API.md` | Pre-signup coverage check with restaurant count by zipcode |
| Marketing | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/marketing_site/LEADS_COVERAGE_CHECKER.md` | Coverage checker, interest forms, reCAPTCHA, restaurant/plan endpoints for marketing site. **Country selector** via `/leads/countries` + `/leads/supplier-countries` (ETag + 24h cache). `country_code` required on `/leads/plans`, `/leads/restaurants`, `/leads/featured-restaurant`. |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/LEADS_SIMPLIFICATION.md` | Remove coverage check from app, simplify signup, add "not served" → marketing site link |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_INTEREST_DASHBOARD.md` | Internal read-only dashboard for lead interest data (`GET /admin/leads/interest`) |
| Infra | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/infrastructure/LEADS_MIGRATION_INFRA.md` | reCAPTCHA and CORS env vars for Cloud Run |

### Activation Readiness — `is_ready_for_signup` + `missing` fields (kitchen#123, Option B)

Computed at read time on admin enriched endpoints. No DB column. No DB constraint. Rules may evolve without a migration.

**Restaurant level** (`GET /api/v1/restaurants/enriched`, `GET /api/v1/restaurants/enriched/{id}`):
- `is_ready_for_signup: bool | null` — `true` when `restaurant.status='active'`, not archived, ≥1 active `plate_kitchen_days`, active QR code.
- `missing: list[str] | null` — subset of `["status_active", "not_archived", "plate_kitchen_days", "qr"]`.
- Plain CRUD endpoints (`GET /api/v1/restaurants`, `GET /api/v1/restaurants/{id}`) return `null` for both fields.

**Market level** (`GET /api/v1/admin/markets/enriched`, `GET /api/v1/admin/markets/enriched/{market_id}`):
- `is_ready_for_signup: bool | null` — `true` when `market.status='active'` AND ≥1 ready restaurant exists in the market.
- `missing: list[str] | null` — `["ready_restaurant"]` when no ready restaurant; `[]` when ready.
- Plain market endpoints return `null` for both fields.

**Lazy restaurant activation (one-way, silent):** When `plate_kitchen_days` is created OR a QR code is provisioned for a `pending` restaurant, and all prereqs are met, the backend auto-promotes `restaurant.status: pending → active`. No event, no email, no audit row. No auto-demotion.

**`market.active = true` does NOT imply readiness.** Use `is_ready_for_signup` for admin UI readiness indicators.

**Leading public endpoints are unaffected:** `/api/v1/leads/markets` and `/api/v1/leads/cities` continue to filter out non-ready records silently. They do not expose the new fields.

**Full contract doc:** `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md`

**Postman coverage:** `docs/postman/collections/019 MARKET_READINESS.postman_collection.json`

---

## Subscriptions & Billing (Customer)
_Routes: `/subscriptions/`, `/customer/payment-methods/`, `/customer/payment-providers/`_

| Audience | File | Description |
|----------|------|-------------|
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/SUBSCRIPTION_PAYMENT_API.md` | Create subscription and complete payment atomically |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/SUBSCRIPTION_ACTIONS_API.md` | Cancel, pause, and reactivate subscription endpoints |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/CREDIT_ROLLOVER_DISPLAY_B2C.md` | How unused credits carry over to next renewal period |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/CREDIT_AND_CURRENCY_CLIENT.md` | Credits, currency display, and pricing reference |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/CUSTOMER_PAYMENT_METHODS_B2C.md` | Saved cards UI flow — list, add via Setup Session, delete, set default |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/CUSTOMER_PAYMENT_METHODS_API.md` | Full API contract for `/customer/payment-methods/` endpoints |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/PAYMENT_PROVIDERS_B2C.md` | Payment provider accounts — Stripe connection, disconnect UI flow (Phase 2) |

---

## Institution Billing (B2B)
_Routes: `/institution-bills/`, `/supplier-invoices/`, `/admin/discretionary/`, `/super-admin/discretionary/`_

| Audience | File | Description |
|----------|------|-------------|
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_SUPPLIER_INVOICES.md` | Supplier invoice registration — bill matching, AR/US validation, W-9 collection, review flow |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/DISCRETIONARY_REQUEST_FORM_GUIDE.md` | Discretionary credit request form — category/reason schema |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_SUPPLIER_TERMS.md` | Supplier terms — no-show discount, payment frequency, invoice compliance overrides |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/PAYMENT_AND_BILLING_CLIENT_CHANGES.md` | Removed features: fintech links, manual bill creation, bank accounts |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_PAYOUT_HISTORY.md` | Enriched payout history list — entity-level view with institution, billing period |

---

## Payment Administration (B2B Internal)
_Routes: `/user-payment-summary`_

| Audience | File | Description |
|----------|------|-------------|
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_USER_PAYMENT_SUMMARY.md` | Employee portal — read-only view of which customers have Stripe payment methods registered |

---

## Restaurants & Menu
_Routes: `/restaurants/`, `/plates/`, `/plate-kitchen-days/`, `/cuisines/`, `/qr-codes/`, `/restaurant-holidays/`_

| Audience | File | Description |
|----------|------|-------------|
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md` | Restaurant activation — status logic and kitchen day requirements |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/PLATE_API_CLIENT.md` | Plate CRUD, enriched endpoints, bulk kitchen day assignment |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/CUISINES_API_CLIENT.md` | List supported cuisines for restaurant dropdown validation |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_PRODUCTS.md` | Product CRUD and enriched endpoints (image upload is a separate pipeline) |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_UPLOADS.md` | Image upload pipeline — `POST/GET/DELETE /api/v1/uploads`, async SafeSearch + pyvips pipeline, state machine, polling guidance |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_NATIONAL_HOLIDAYS.md` | Manage country-scoped holiday calendar |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md` | Restaurant activation logic with status and kitchen day requirements |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/SUPPLIER_DASHBOARD_METRICS_B2B.md` | Metrics and APIs for supplier/restaurant dashboard |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/PORTION_SIZE_DISPLAY_B2B.md` | Show portion feedback from reviews to restaurant staff |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/PORTION_SIZE_DISPLAY_B2C.md` | Show portion feedback from customer reviews on plate cards |

---

## Plate Selection & Pickup (Customer)
_Routes: `/plate-selections/`, `/plate-pickup/`, `/favorites/`_

| Audience | File | Description |
|----------|------|-------------|
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/EXPLORE_KITCHEN_DAY_B2C.md` | Enforce kitchen day requirement in the restaurant explore flow |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/PLATE_ALREADY_RESERVED_EXPLORE_UI.md` | Show alternative action buttons when a plate is already reserved |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/PLATE_SELECTION_DUPLICATE_REPLACE.md` | Handle 409 conflict when the same plate is reserved twice in a day |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/PLATE_RECOMMENDATION_AND_FAVORITES_B2C.md` | Recommendation badges and favorite hearts on plate cards |
| Shared | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/EXPLORE_SORTING_AND_PAGINATION.md` | Explore plate sorting logic, cursor-based infinite scroll pagination, FAQ |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/POST_RESERVATION_PICKUP_B2C.md` | Post-reservation pickup intent and coworker matching flow |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/PICKUP_AVAILABILITY_AT_KITCHEN_START.md` | Show when a reserved plate is ready for pickup |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/POST_PICKUP_FLOW_API.md` | Signed QR codes, enhanced scan-qr, completion tracking, extended reviews |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/PUSH_NOTIFICATIONS_API.md` | FCM token registration, push on Handed Out, timer sync fields, portion complaint field names |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/PLATE_REVIEW_FEEDBACK_B2B.md` | Customer review comments and feedback for restaurant dashboard |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/KIOSK_MODE_API.md` | Kiosk mode — daily orders, verify-and-handoff, hand-out, timer sync, Operator access matrix |

---

## Institutions, Entities & Employers
_Routes: `/institutions/`, `/institution-entities/`, `/employer/program`, `/employer/employees`, `/employer/billing`_

| Audience | File | Description |
|----------|------|-------------|
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_INSTITUTIONS.md` | **Multinational model** — `market_ids` array, employer flow via entities, `email_domain` |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_THREE_TIER_CASCADE.md` | **Three-tier cascade** — entity → institution → market config resolution for supplier terms and employer programs |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_EMPLOYER_ADDRESSES_CITIES.md` | Employer address restrictions and cities API behavior |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/EMPLOYER_MANAGEMENT_B2C.md` | Assign employer entity to customer — `employer_entity_id`, user-selected address types |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/plans/MULTINATIONAL_INSTITUTIONS.md` | Full design doc — institution_market junction, employer_info removal, three-tier cascade, migration plan |

---

## Workplace Groups (Coworker Pickup)
_Routes: `/workplace-groups/`, `/admin/workplace-groups/`, `/users/me/workplace`_

| Audience | File | Description |
|----------|------|-------------|
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/WORKPLACE_GROUPS_B2C.md` | Search, create, join workplace groups; select office address; coworker matching |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_WORKPLACE_GROUPS.md` | Admin list/enriched, rename, archive, bulk create, group address management |

---

## Geography
_Routes: `/addresses/`, `/maps/`, `/cities/`, `/provinces/`, `/countries/`_

| Audience | File | Description |
|----------|------|-------------|
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/ADDRESSES_API_CLIENT.md` | Address autocomplete and creation with geolocation (Mapbox provider, session_token) |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/MAPS_API.md` | **Maps API** — `GET /maps/city-pins` (active, interactive Mapbox) + `GET /maps/city-snapshot` (dormant, static PNG). Start here for all map work. |
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/archived/STATIC_MAP_SNAPSHOT_B2C.md` | **Archived** — implementation detail on the static-image map path (dormant since #214). See `MAPS_API.md` for the active endpoint. |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/PROVINCES_API_CLIENT.md` | Provinces for cascading country → province → city dropdowns |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/COUNTRY_CODE_API_CONTRACT.md` | Accept alpha-2 or alpha-3; always store and return alpha-2 |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/TIMEZONE_AUTO_DEDUCTION_UI_GUIDE.md` | Backend derives timezone from country/province — no client input needed |

---

## Referral Program
_Routes: `/referrals/`, `/admin/referral-config/`_

| Audience | File | Description |
|----------|------|-------------|
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/REFERRAL_SYSTEM_B2C.md` | Referral code in signup, share code, view referral activity and stats |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_REFERRAL_ADMIN.md` | Admin referral config per market — bonus rates, caps, enable/disable, cron trigger |

---

## Filter Subsystem
_Registry, builder, and machine-readable schema for query-param filtering on list endpoints_

| Audience | File | Description |
|----------|------|-------------|
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/filters.md` | **Filter contract** — registry shape, all ops/casts, URL encoding conventions, `filters.json` schema, pagination interaction, gotchas |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/filters.json` | **Generated schema** — machine-readable filter spec consumed by vianda-hooks, vianda-platform, vianda-app. Never hand-edit; regenerate via `python3 scripts/generate_filter_schema.py` |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/filters_inventory.md` | **Filter inventory** — per-entity breakdown of enriched-response fields vs registered filterable keys. Auto-generated by `scripts/lint_filter_inventory.py`; never hand-edit |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/filters_inventory.json` | **Filter inventory (machine-readable)** — structured rows `{entity, endpoint, model, field, status}` for automated tooling. Auto-generated alongside `filters_inventory.md` |

---

## Plans
_Routes: `/plans/`_

| Audience | File | Description |
|----------|------|-------------|
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/PLANS_FILTER_CLIENT_INTEGRATION.md` | Filter plans by market, status, and currency |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/PLAN_ROLLOVER_UI_HIDDEN.md` | Rollover is a fixed field — do not expose in plan configuration UI |
| Internal | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/PLAN_UPSERT_SEED_CONVENTION.md` | **`PUT /plans/by-key` upsert endpoint** — idempotent seed/fixture upsert, canonical_key naming convention, Stripe minimum prices, duplicate cleanup script |

---

## Ads Platform (Conversion Tracking, Geographic Flywheel, Zone Management)
_Routes: `/ad-tracking`, `/admin/ad-zones/`_

| Audience | File | Description |
|----------|------|-------------|
| B2C | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2c_client/ADS_TRACKING_INTEGRATION.md` | Click ID capture API, Meta Pixel JS (web), Meta SDK (native), event_id dedup, platform detection |
| Marketing | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/marketing_site/ADS_LANDING_PAGES.md` | Pixel JS installation, `/for-restaurants` + `/for-employers` landing pages, click ID capture in forms |
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/API_CLIENT_AD_ZONES.md` | Zone CRUD, flywheel state transitions, metrics refresh, overlap detection, audience export, Pixel on B2B portal |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/plans/GOOGLE_META_ADS_INTEGRATION_V2.md` | Full ads platform design (34 sections) -- conversion pipeline, geographic flywheel, campaign management, Gemini advisor |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/plans/RESTAURANT_VETTING_SYSTEM.md` | Restaurant supplier application form, vetting pipeline, approval workflow |

---

## i18n & Locale

| Audience | File | Description |
|----------|------|-------------|
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/i18n.md` | Catalog modules, locale resolution precedence, resolver selection guide, code lifecycle, parity tests index. **Start here for any i18n/locale work.** |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/error-envelope.md` | Error envelope wire shape, code namespaces, how to raise, pre-route handler behavior, validation handling (K3/K5), frontend contract via `resolveErrorMessage`, legacy transition. |

---

## API Patterns & Conventions
_Applies across all routes_

| Audience | File | Description |
|----------|------|-------------|
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/ENRICHED_ENDPOINT_PATTERN.md` | When and how to use `/enriched` endpoints to avoid N+1 queries |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/ENRICHED_ENDPOINT_UI_IMPLEMENTATION.md` | UI implementation guide for enriched endpoint data |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/ARCHIVED_RECORDS_PATTERN.md` | All GET endpoints return only non-archived records by default |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/SCOPING_BEHAVIOR_FOR_UI.md` | Backend enforces institution scoping — no client-side filtering needed |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/STATUS_ON_CREATE.md` | Do not send `status` on create requests — backend sets the default |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/BULK_API_PATTERN.md` | Atomic bulk create/update/delete for batch operations |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/MARKET_AND_SCOPE_GUIDELINE.md` | Market behavior, institution scoping, and subscription rules |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/RATE_LIMIT_HANDLING_CLIENT.md` | Per-user rate limiting — tiers, 429 handling, `X-RateLimit-*` headers, subscribe prompt for Free tier |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/GENERIC_PAGINATION_CLIENT.md` | Server-side pagination — `page`/`page_size` query params, `X-Total-Count` header, opt-in endpoint list |
| Both | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/shared_client/CAPTCHA_PROTECTION.md` | reCAPTCHA v3 on auth endpoints — conditional (login, verify, recovery) and always-on (signup/request for web) |

---

## Development Setup

| Audience | File | Description |
|----------|------|-------------|
| B2B | `/Users/cdeachaval/learn/vianda/kitchen/docs/api/b2b_client/LOCAL_NETWORK_DEV.md` | Run backend locally for kitchen-web testing on LAN |

---

## Infrastructure
_Deployment, hosting, and backend environment requirements_

| File | Description |
|------|-------------|
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/infrastructure/README.md` | Infrastructure is moving to a separate Pulumi repo (from legacy CloudFormation) |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/infrastructure/feedback_for_infra.md` | Backend requirements for the infra team — FastAPI, PostgreSQL, env vars, and dependency specs |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/infrastructure/STRIPE_PAYMENT_INFRASTRUCTURE.md` | Stripe payment infrastructure — GCP Secret Manager secrets, Cloud Run env vars, Stripe Dashboard webhook registration, per-environment activation checklist |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/infrastructure/SUPPLIER_INVOICE_STORAGE_INFRASTRUCTURE.md` | Supplier invoice GCS storage schema — bucket paths, per-country lifecycle policies for document retention |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/infrastructure/GCS_BUCKET_SCHEMA_STABILIZATION.md` | **GCS bucket schema stabilization** — canonical blob path inventory across all 4 private buckets, lifecycle policy gaps (QR code deletion risk), architectural questions, and deliverables for infra agent |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/infrastructure/MAPBOX_CONFIGURATION_INFRASTRUCTURE.md` | **Mapbox address/geocoding** — Secret Manager tokens, Cloud Run env vars, `ADDRESS_PROVIDER` toggle, per-environment activation checklist |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/infrastructure/SENDGRID_EMAIL_INFRASTRUCTURE.md` | **SendGrid email** — GCP Marketplace setup, Secret Manager API key, Cloud Run env vars, DNS domain auth (SPF/DKIM/DMARC on vianda.market), per-environment activation checklist |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/infrastructure/RATE_LIMIT_INFRASTRUCTURE.md` | **Rate limiting** — `RATE_LIMIT_ENABLED` env var, activation checklist, no Redis dependency |

---

## Testing & Quality
_Testing conventions, layer decisions, and CI gate reference for contributors._

| File | Description |
|------|-------------|
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/TESTING_LAYERS.md` | **Testing layers orientation** — layer table, decision flow, patterns (mypy baseline, vulture, diff-cover), hard gates vs signal-only, anti-patterns |

---

## Internal — Backend Reference
_Architecture decisions, design patterns, and implementation guides for agents working on the backend or coordinating cross-repo changes. Read these when you need to understand why something is designed a certain way, or before proposing a change that touches auth, scoping, billing, or routing._

### Overview & Cross-Repo Contracts

| File | Description |
|------|-------------|
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/overview.md` | High-level API overview — base URLs, versioning, OpenAPI access |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/handoffs.md` | API contract expectations between Kitchen backend and frontend repos |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/API_VERSIONING_GUIDE.md` | URL path versioning strategy (`/api/v1/`) |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/BREAKING_CHANGES.md` | Log of API changes requiring frontend coordination and deployment sequencing |

### Auth, Roles & Scoping

| File | Description |
|------|-------------|
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/API_PERMISSIONS_BY_ROLE.md` | Full endpoint permission matrix organized by role type |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/ROLE_BASED_ACCESS_CONTROL.md` | Comprehensive RBAC guide — two-tier role system and scope restrictions |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/ROLE_AND_FIELD_ACCESS.md` | Route-level and field-level access control patterns |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/ROLE_ASSIGNMENT_GUIDE.md` | How `role_type` and `role_name` are assigned and used for access decisions |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/SCOPING_SYSTEM.md` | Centralized institution scoping — how data access is restricted by institution |

### Payments & Billing

| File | Description |
|------|-------------|
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/STRIPE_INTEGRATION_HANDOFF.md` | Handoff guide for switching from mock to live Stripe payment provider |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/RESTAURANT_PAYMENT_FLOW_AND_APIS.md` | Credit/currency to payout flow connecting restaurant balance to Stripe settlement |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/SUPPLIER_INSTITUTION_PAYMENT.md` | Atomic settlement, bill, and payout flow — no zero-value transactions |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/UNIFIED_PAYMENT_METHODS_AND_ATTEMPT_DEPRECATION.md` | Unified payment methods backed by aggregators; payment attempts table removed |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/FINTECH_LINK_DEPRECATION.md` | Fintech link endpoints deprecated — use atomic subscription-with-payment instead |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/FINANCIAL_DATA_HIERARCHY.md` | **Start here for financial data** — Transaction → Balance → Settlement → Bill → Payout → Invoice hierarchy, table-to-level map, design decisions |

### Restaurant & Operations

| File | Description |
|------|-------------|
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/KITCHEN_DAY_SERVICE.md` | Centralized kitchen day service eliminating duplicate day calculations |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/KITCHEN_DAY_SLA.md` | Kitchen day cutoff at 1:30 PM and billing/reservation timing specifications |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/RESTAURANT_STATUS_VALIDATION.md` | Validation preventing plate bookings from inactive or holiday-closed restaurants |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/RESTAURANT_VALIDATION.md` | Restaurant validation in plate selection — non-operational restaurant rules |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/HOLIDAY_TABLES_ANALYSIS.md` | Two separate holiday tables: national holidays and restaurant-specific closures |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/PLATE_PICKUP_PENDING_API.md` | Pending order endpoint returns a single group or null — not an array |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/MARKETS_API.md` | Markets API for country-based subscription regions with currency and timezone |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/GEOLOCATION.md` | Google Maps API integration for address geocoding and reverse geocoding |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/PASSWORD_RECOVERY.md` | Password recovery — reset via email token flow |

### API Design Patterns

| File | Description |
|------|-------------|
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/STATUS_MANAGEMENT_PATTERN.md` | Status lifecycle: Pending on create, Active/Complete after processing |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/PYDANTIC_SCHEMA_DEFAULTS.md` | Schema defaults and placeholder management for database column defaults |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/USER_DEPENDENT_ROUTES_PATTERN.md` | Pattern for routes requiring user context extracted from the JWT |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/CENTRALIZED_DELETE_API.md` | Centralized soft-archival DELETE through `BaseModelCRUD` |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/SINGLE_ENDPOINT_ARRAY_DESIGN.md` | POST endpoint accepting an array of kitchen days — design rationale |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/BATCH_KITCHEN_DAYS_DESIGN_ANALYSIS.md` | Client queuing vs. batch endpoint for kitchen day assignment — trade-off analysis |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/BATCH_TRANSACTION_HANDLING_ANALYSIS.md` | Atomic batch operation design — required atomicity behavior |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/COMPOSITE_CREATE_PATTERN.md` | Composite create — atomic multi-table creation with `commit=False` chaining (institutions+supplier_terms, products+ingredients) |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/ENRICHED_ENDPOINTS_TESTING_STRATEGY.md` | Testing strategy for enriched endpoints using centralized `EnrichedService` |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/CRUD_VS_ENRICHED_SERVICE_ANALYSIS.md` | Whether `EnrichedService` should merge into `CRUDService` — consolidation analysis |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/DB_INSERT_REFACTORING_ANALYSIS.md` | `db_insert` refactoring options for DRY and improved code structure |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/LOGGING_STRATEGY.md` | Current logging gaps — missing error, debug, and critical log levels |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/SYSTEM_CONFIGURATION_TABLES_ANALYSIS.md` | Which system configuration tables are accessible and how they are managed |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/CITY_REQUIRED_AT_SIGNUP_IMPLEMENTATION_PLAN.md` | Plan to require `city_id` at signup with global city sentinel for B2B users |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/CUSTOMER_EMPLOYER_ADDRESS_VIANDA_CUSTOMERS_ONLY.md` | Scoping customer employer addresses to the Vianda Customers institution |
| `/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/COUNTRY_CITY_DATA_STRUCTURE.md` | Two-tier country/city/currency data model — external GeoNames/ISO 4217 layer + Vianda metadata layer, audience flags, timezone strategy, XG pseudo-country |
