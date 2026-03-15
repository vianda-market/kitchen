# Shared Client Documentation

**Last Updated**: 2026-02-21  
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
| USER_UPDATE_PATTERN.md | User updates: self (use /me) and by others (admin/backend portal); immutable fields (username, role_type, institution_id) |
| USER_SELF_UPDATE_PATTERN.md | `/me` for self-updates; migration and deprecation |
| USERNAME_IMMUTABLE_CLIENT.md | Username read-only; B2B and B2C must not send username on profile update; backend portal same rule |
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
| USER_AND_MARKET_API_CLIENT.md | User–market storage and API: `market_id` / `market_ids` from GET /users/me; B2C restore market selector; B2B assigned market |
| ENUM_SERVICE_API.md | Enum service |
| **PLATE_API_CLIENT.md** | **Combined plate guide:** enriched endpoint (ingredients, pickup_instructions, address_display), plate create/update (no savings), plate selection, plate pickup pending. Replaces PLATE_SELECTION_API, PLATE_PICKUP_PENDING_API, PLATE_API_NO_SAVINGS (archived in docs/zArchive/api/shared_client/). |
| USERNAME_RECOVERY.md | Username recovery (forgot username), both B2B and B2C |
| DEBUG_LOGGING_STRATEGY.md | Debug logging: single env var `DEBUG_PASSWORD_RECOVERY` (1/true/yes), same for backend and clients |
| STATUS_ON_CREATE.md | Status on create: omit or send null; backend assigns default (e.g. Active). Clients can stop sending status on creation. |
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
