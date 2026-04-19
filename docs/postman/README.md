# Postman Collections & Documentation

This directory contains Postman collections for API testing and their associated documentation.

## 📁 Directory Structure

### `collections/` – Postman collection files (`.json`)
All importable Postman collections live here:
- **`Permissions Testing - Employee-Only Access.postman_collection.json`** - Comprehensive permissions testing for all role combinations
- **`DISCRETIONARY_CREDIT_SYSTEM.postman_collection.json`** - End-to-end testing for discretionary credit system
- **`E2E Plate Selection.postman_collection.json`** - Complete plate selection workflow testing
- **`INSTITUTION_BANK_ACCOUNT_POSTMAN_COLLECTION.json`** - Institution bank account API testing
- **`RESTAURANT_EXPLORER_B2C.postman_collection.json`** - B2C restaurant explorer: GET /restaurants/cities (dropdown) and GET /restaurants/by-city (list/map). Bearer auth required; run Login first.
- **`ROLE_AND_FIELD_ACCESS.postman_collection.json`** - Role and field access: address_type (Supplier allowed/disallowed), user role_type (Supplier cannot create Customer), Customer cannot create users. Run with Supplier and Customer credentials (see collection variables).
- **`ADDRESS_AUTOCOMPLETE_AND_VALIDATION.postman_collection.json`** - Address suggest/validate and E2E create
- **`TIMEZONE_DEDUCTION_TESTS.postman_collection.json`** - Timezone auto-deduction by country/province
- **`ENUM_SERVICE.postman_collection.json`** - Enum service API tests
- **`006 LEADS_MARKETING_SITE.postman_collection.json`** - All public `/leads/*` surface consumed by vianda-home: zipcode metrics, country selectors (with ETag/304/Cache-Control), `country_code` contract on plans/restaurants/featured-restaurant, and admin override guardrails on `PUT /admin/markets/{id}`. Replaces the previous per-endpoint splits (`006 ZIPCODE_LEAD_METRICS`, `017 LEADS_COUNTRY_FILTER`). See `guidelines/LEADS_COLLECTION_CONVENTIONS.md` for the per-frontend-consumer organizing rule.
- **`Geolocation Testing.postman_collection.json`** - Geolocation testing
- **`009 CUSTOMER_STRIPE_CONFIG.postman_collection.json`** - Customer Stripe payment method management (Phase 2 mock): list, setup-session, mock-add, delete, set default. Requires Customer auth; run after E2E Client Setup. **Requires `PAYMENT_PROVIDER=mock`** in `.env` for mock-add/PUT/DELETE flow; with Stripe, mock-add returns 400 (tests treat as skipped).
- **`010 Permissions Testing - Employee-Only Access.postman_collection.json`** - Permissions testing (runs last; archives customer at end).

### Documentation

#### `guidelines/` – Active documentation
Guides, setup, and reference for using the Postman collections:
- **`ROLE_COVERAGE_ANALYSIS.md`** - Test coverage analysis and roadmap for role-based permissions
- **`PERMISSIONS_TESTING_GUIDE.md`** - Guide for the Permissions Testing collection
- **`DISCRETIONARY_CREDIT_SYSTEM_POSTMAN_GUIDE.md`** - Guide for the Discretionary Credit System collection
- **`QUICK_SETUP_GUIDE.md`** - Quick setup instructions
- **`INSTITUTION_BANK_ACCOUNT_POSTMAN_SCRIPTS.md`** - Scripts and examples for institution bank account testing
- **`POSTMAN_INSTITUTION_BANK_ACCOUNT_SCRIPTS.md`** - Additional institution bank account scripts
- **`POSTMAN_INSTITUTION_ENTITY_SCRIPTS.md`** - Institution entity API scripts
- **`POSTMAN_INSTITUTION_PAYMENT_ATTEMPT_SCRIPTS.md`** - Payment attempt API scripts
- **`ADDRESS_COLLECTIONS_REFERENCE.md`** - Where address autocomplete is tested; other collections that create addresses
- **`GEOLOCATION_TESTING_SETUP.md`** - Geolocation collection setup
- **`POSTMAN_MARKET_UPDATE.md`** - Market-based subscription update (E2E collection)
- **`COLLECTION_UPDATE_VERIFICATION.md`** - Verifying versioned paths in collections
- **`BANK_ACCOUNT_COLLECTION_FIX.md`** - Bank account collection variable fix
- **`TESTING_STRATEGY.md`** - Testing strategy
- **`LEADS_COLLECTION_CONVENTIONS.md`** - One leads-adjacent collection per frontend consumer; canonical `recaptchaToken` variable name; shared super-admin auth pattern (idempotent in-collection login + Newman `--globals`)

#### `../zArchive/postman/` - Archived Documentation
Contains historical/outdated documentation that has been superseded:
- **`POSTMAN_COLLECTION_FIXES.md`** - Historical fixes (already applied)
- **`POSTMAN_E2E_API_CALLS.md`** - Incomplete template (contains "TO BE FILLED" placeholders)
- **`POSTMAN_E2E_API_CALLS_TEMPLATE.md`** - Outdated template file
- **`setup_discretionary_testing.md`** - Redundant setup guide (covered by QUICK_SETUP_GUIDE.md and DISCRETIONARY_CREDIT_SYSTEM_POSTMAN_GUIDE.md)

## User create and market_id (v1)

**POST /api/v1/users** requires or defaults **market_id** (UUID of a market from GET /api/v1/markets/ or GET /api/v1/markets/enriched/ or seed). For unauthenticated country list (country_code only), use GET /api/v1/leads/markets.  
- **Admin / Super Admin / Supplier Admin**: can omit `market_id` (backend defaults to Global Marketplace `00000000-0000-0000-0000-000000000001`).  
- **Manager / Operator**: must send `market_id` (e.g. Argentina `11111111-1111-1111-1111-111111111111`); only Super Admin can assign Global.  
- **Customer**: can omit (backend defaults to US market `66666666-6666-6666-6666-666666666666`).  
**GET /users/me** and **GET /users** responses include **market_id**. See [../roadmap/USER_MARKET_ASSIGNMENT_DESIGN.md](../roadmap/USER_MARKET_ASSIGNMENT_DESIGN.md).

## User market_ids and Global Manager (v2)

- **Responses**: **GET /users/me**, **GET /users**, **GET /users/{id}**, and list/lookup return **market_ids** (array of UUIDs, primary first) in addition to **market_id** (primary).
- **Create**: **POST /api/v1/users** accepts optional **market_ids** (array). If provided, first element is primary; all must exist and not be archived. **role_name** can be **Global Manager** (Employee only); only Super Admin, Admin, or Global Manager can create/assign Global Manager.
- **Update**: **PUT /users/me** and **PUT /users/{user_id}** accept optional **market_ids**; same validation. Only Admin/Super Admin/Global Manager can assign Global Manager or edit a Global Manager user.
- **Seed**: Global Manager user `globalmanager@example.com` (password as per seed) with Global market; use for testing Global Manager–only create/edit.
- See [../roadmap/USER_MARKET_AND_GLOBAL_MANAGER_V2.md](../roadmap/USER_MARKET_AND_GLOBAL_MANAGER_V2.md).

## Country codes in requests

All collections use **ISO 3166-1 alpha-2** for `country_code` (e.g. `AR`, `US`, not ARG or USA). See [../api/shared_client/COUNTRY_CODE_API_CONTRACT.md](../api/shared_client/COUNTRY_CODE_API_CONTRACT.md) for the full contract and common mistakes.

## Minimal DB + E2E flow

**Tear down and rebuild DB** → seed is minimal: one super_admin (superadmin / SuperAdmin1!), two institutions (Vianda Enterprises, Vianda Customers), one market (Global). **Run the E2E Plate Selection collection** to test all APIs: super admin logs in, creates one credit currency and one local market via API, then one plan, one supplier institution, one restaurant, and the rest of the flow. Postman is for testing APIs, not for populating extra data.

## 🚀 Quick Start

1. **Import Collections**: Import the `.json` files from **`collections/`** into Postman
2. **Set Environment Variables**: See individual collection guides in `guidelines/`
3. **Run Tests**: Execute collections in the order specified in their guides

## 📚 Documentation by Collection

### Permissions Testing Collection
- **Guide**: `guidelines/PERMISSIONS_TESTING_GUIDE.md`
- **Coverage Analysis**: `guidelines/ROLE_COVERAGE_ANALYSIS.md`
- **Purpose**: Tests role-based access control for all role combinations

### Discretionary Credit System Collection
- **Guide**: `guidelines/DISCRETIONARY_CREDIT_SYSTEM_POSTMAN_GUIDE.md`
- **Quick Setup**: `guidelines/QUICK_SETUP_GUIDE.md`
- **Purpose**: End-to-end testing of discretionary credit workflows

### E2E Plate Selection Collection
- **Purpose**: Minimal run to test each API (credit currencies, markets, plans, supplier setup, restaurant, client flow, billing). Seed is minimal; super admin creates localized markets/currencies via API in this collection.
- **Flow**: After DB rebuild, run the full collection; no manual data prep.
- **Variables**: `baseUrl` (default `http://localhost:8000`), `adminUsername=superadmin`, `adminPassword=SuperAdmin1!`. If you use an environment, set `baseUrl` there to override (e.g. `https://your-api.example.com`).
- **PAYMENT_PROVIDER**: The Client Setup folder includes "Confirm Payment (mock)", which only works when `PAYMENT_PROVIDER=mock` in `.env`. With `PAYMENT_PROVIDER=stripe`, that request returns 400 (expected); the test treats it as skipped. For full E2E including subscription activation, set `PAYMENT_PROVIDER=mock` locally; use Stripe webhook for production.

### Institution Bank Account Collection
- **Scripts**: `guidelines/INSTITUTION_BANK_ACCOUNT_POSTMAN_SCRIPTS.md`
- **Purpose**: Testing institution bank account management APIs

### Restaurant Explorer B2C Collection
- **API doc**: `../api/b2c_client/feedback_from_client/RESTAURANTS_BY_ZIPCODE.md`
- **Purpose**: B2C explore-by-city flow. Run **Login** first to set `authToken`; then **GET cities** (dropdown), **GET by-city** (list/map). Variables: `sampleCountryCode` (e.g. AR), `sampleCity` (e.g. Buenos Aires).

### Customer Stripe Config Collection (009)
- **API doc**: `../api/b2c_client/CUSTOMER_PAYMENT_METHODS_B2C.md`, `../api/shared_client/CUSTOMER_PAYMENT_METHODS_API.md`
- **Purpose**: E2E Customer Stripe payment method management (Phase 2 mock). Run **Login Customer User** (or use `clientUserAuthToken` from E2E Client Setup), then run Customer Payment Methods folder: GET list, POST setup-session, POST mock-add, GET (verify 1), PUT default, DELETE, GET (verify empty). **Requires `PAYMENT_PROVIDER=mock`** for mock-add flow; with Stripe, mock-add returns 400 and subsequent steps are skipped.

## 🔄 Recent Updates

### Phase 3 Scope Logic Implementation (Completed)
- Added Employee Operator blocking tests for:
  - `DELETE /users/{user_id}`
  - `GET /users/enriched/{user_id}`
  - `DELETE /addresses/{address_id}`
- Added address creation request for test setup
- All tests verify 403 Forbidden responses for unauthorized access

## User Endpoint Pattern (Deprecation)

**Self-updates must use `/me` endpoints:**
- `GET /users/me` — get current user's profile (not `GET /users/{user_id}` when reading self)
- `PUT /users/me` — update current user's profile (not `PUT /users/{user_id}` when updating self)
- `PUT /users/me/employer` — assign employer
- `PUT /users/me/terminate` — terminate account

**Use `/{user_id}` only for admin operations** (editing another user). See [USER_MODEL_FOR_CLIENTS.md](../api/shared_client/USER_MODEL_FOR_CLIENTS.md#6-self-service-usersme-and-410-on-self-use-of-user_id) and [API_DEPRECATION_PLAN.md](../zArchive/roadmap/API_DEPRECATION_PLAN.md).

## 📝 Notes

- All collections use **collection variables** (not environment variables) for tokens and IDs
- Token management follows the pattern: `{roleType}{roleName}Token`
- Collections are self-contained and can run independently after initial setup

