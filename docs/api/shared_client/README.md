# Shared Client Documentation

**Last Updated**: 2026-03-22  
**Purpose**: Docs to copy to BOTH kitchen-web (B2B) and kitchen-mobile (B2C) repos. No duplication – this folder is the single source.

---

## Copy Instructions

Copy **shared_client** and the relevant client folder. Keep folder structure so links work.

### To kitchen-web (B2B)

```bash
cp -r docs/api/shared_client /path/to/kitchen-web/docs/api/
cp -r docs/api/b2b_client /path/to/kitchen-web/docs/api/
```

### To kitchen-mobile (B2C)

```bash
cp -r docs/api/shared_client /path/to/kitchen-mobile/docs/api/
cp -r docs/api/b2c_client /path/to/kitchen-mobile/docs/api/
```

**Result**: `docs/api/shared_client/` and `docs/api/b2b_client/` (or `b2c_client/`) in each repo. Links `../shared_client/FILE.md` work from b2b_client and b2c_client.

---

## Contents (shared)

| File | Use |
|------|-----|
| API_PERMISSIONS_BY_ROLE.md | Permission matrix by role |
| **USER_MODEL_FOR_CLIENTS.md** | **Single user guide:** roles/institutions, **`mobile_number` (E.164)** + read-only verification flags, username/email lowercase, **`email_verified` / email change** (`PUT` + **`POST /users/me/verify-email-change`**), lead **`GET /leads/email-registered`**, immutable username, **`PUT /users/me`** vs admin **`PUT /users/{user_id}`**, **`market_id` / `market_ids`**, forgot-username, password recovery. Replaces USER_UPDATE_PATTERN, USER_SELF_UPDATE_PATTERN, USERNAME_*, USER_AND_MARKET_API_CLIENT, PASSWORD_RECOVERY_CLIENT, EMAIL_REGISTERED_CHECK_CLIENT (archived under `docs/zArchive/api/shared_client/`). |
| ENRICHED_ENDPOINT_PATTERN.md | `/enriched/` for denormalized data |
| ARCHIVED_RECORDS_PATTERN.md | `include_archived` behavior |
| SCOPING_BEHAVIOR_FOR_UI.md | Institution/user scoping |
| BULK_API_PATTERN.md | Bulk operations |
| ENRICHED_ENDPOINT_UI_IMPLEMENTATION.md | TypeScript, React examples |
| COUNTRY_CODE_API_CONTRACT.md | Country code: alpha-2 or alpha-3 accepted, normalized to alpha-2 at entry, Postman |
| ADDRESSES_API_CLIENT.md | Suggest, create (place_id or structured), Address CRUD |
| **PROVINCES_API_CLIENT.md** | **Supported provinces/state:** `GET /api/v1/provinces/`, cascading Country → Province → City, address validation |
| PLANS_FILTER_CLIENT_INTEGRATION.md | Plans filtering |
| **MARKET_AND_SCOPE_GUIDELINE.md** | **Single guideline:** initial phase (single market per institution, Comensal at signup), Markets API, scope, subscriptions, country-flag UI, migration. Replaces and merges MARKET_SCOPE_FOR_CLIENTS, MARKET_BASED_SUBSCRIPTIONS, MARKET_MIGRATION_GUIDE, MARKET_COUNTRY_FLAG_UI_PATTERN (archived in docs/zArchive/api/shared_client/). |
| ENUM_SERVICE_API.md | Enum service |
| **VIANDA_API_CLIENT.md** | **Combined vianda guide:** enriched endpoint (ingredients, pickup_instructions, address_display), vianda create/update (no savings), vianda selection, vianda pickup pending. Replaces VIANDA_SELECTION_API, VIANDA_PICKUP_PENDING_API, VIANDA_API_NO_SAVINGS (archived in docs/zArchive/api/shared_client/). |
| **CREDIT_AND_CURRENCY_CLIENT.md** | **Credit and currency guide:** credit_value_local_currency, currency_conversion_usd, credit_cost_local_currency, expected_payout_local_currency, market_credit_value_local_currency. Credit currency create/edit, plan/restaurant/entity currency from market, vianda payouts, B2C savings. Replaces SUPPORTED_CURRENCIES_API, CREDIT_CURRENCY_EDIT_IMMUTABLE_CURRENCY, PLAN_API_MARKET_CURRENCY, RESTAURANT_AND_INSTITUTION_ENTITY_CREDIT_CURRENCY, EXPLORE_AND_SAVINGS (archived in docs/zArchive/api/). |
| DEBUG_LOGGING_STRATEGY.md | Debug logging: single env var `DEBUG_PASSWORD_RECOVERY` (1/true/yes), same for backend and clients |
| STATUS_ON_CREATE.md | Status on create: omit or send null; backend assigns default (e.g. Active). Clients can stop sending status on creation. |
| **LANGUAGE_AND_LOCALE_FOR_CLIENTS.md** | **i18n scaffolding:** supported locales, `Accept-Language`, `user.locale` / JWT `locale`, `market.language` on lead markets, labeled **`GET /api/v1/enums?language=`**, `X-Content-Language`, password-reset `access_token`, MVP limits (errors still English). |
| **LEADS_API_SCOPE.md** | **All unauthenticated endpoints** under `/api/v1/leads/`: markets, cities, city-metrics, zipcode-metrics, email-registered. No auth; rate-limited. |
| ZIPCODE_METRICS_LEAD_API.md | Lead encouragement: **GET** `/api/v1/leads/zipcode-metrics` (zip, country_code). No auth; rate-limited. Use this path, not zipcode-check or by-zipcode. |
| **PAYMENT_AND_BILLING_CLIENT_CHANGES.md** | **Payment atomic with billing + Fintech link deprecation:** Remove all fintech link pages/modals and any manual “create bill” / “process bill” flows. Use only subscription with-payment and confirm-payment for subscription payment. |
| **CUSTOMER_PAYMENT_METHODS_API.md** | **Payment method management:** List, add (setup session), delete, set default. Customer-only. Mock endpoints for UI; live Stripe in roadmap. B2C implements; B2B suppliers use separate payout flow. |

---

## Folder Structure in Kitchen Repo

| Path | Purpose |
|------|---------|
| **docs/api/** | Internal API docs (backend, not shared) |
| **docs/api/shared_client/** | Shared docs for both client repos |
| **docs/api/b2b_client/** | B2B-specific (kitchen-web) |
| **docs/api/b2c_client/** | B2C-specific (kitchen-mobile) |
