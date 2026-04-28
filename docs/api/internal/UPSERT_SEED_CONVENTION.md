# Upsert Endpoint & Canonical Fixture Convention

Applies to: **plans** (issue #130), **plates** (issue #166), **users** (issue #168), **restaurants** (issue #167), **institutions** (issue #190), and **markets** (issue #190).

## Overview

Postman collections and dev seed scripts that create plans, plates, users, or restaurants
should use the idempotent upsert endpoints (`PUT /api/v1/plans/by-key`,
`PUT /api/v1/plates/by-key`, `PUT /api/v1/users/by-key`,
`PUT /api/v1/restaurants/by-key`) rather than the corresponding `POST` endpoints.
Using POST creates a new row on every run, causing duplicate rows to accumulate
in the dev DB.

---

## Plans — `PUT /api/v1/plans/by-key`

```http
PUT /api/v1/plans/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `MARKET_AR_PLAN_STANDARD_50000_ARS` |
| `market_id` | UUID | yes | Market this plan belongs to (must not be Global) |
| `name` | string (<=100 chars) | yes | Human-readable plan name |
| `credit` | int (> 0) | yes | Credits granted per renewal |
| `price` | float (>= 0) | yes | Price in market local currency |
| `highlighted` | bool | no | Whether this plan is featured in plan selection UI |
| `status` | string | no | `active` (default) or `inactive` |
| `marketing_description` | string | no | Marketing copy (max 1000 chars) |
| `features` | list[string] | no | Feature bullet points |
| `cta_label` | string | no | Call-to-action label |
| `*_i18n` | object | no | Locale maps for localised fields |

`rollover` and `rollover_cap` are always forced to `true` and `null` respectively
(same enforcement as `POST /plans`).

Response body is `PlanResponseSchema` (same shape as `GET /api/v1/plans/{plan_id}`).

### canonical_key convention for plans

```
MARKET_{ISO2_CODE}_PLAN_{DESCRIPTION}_{PRICE}_{CURRENCY}
```

Examples:
- `MARKET_AR_PLAN_STANDARD_50000_ARS` — Argentina standard plan at 50 000 ARS
- `MARKET_US_PLAN_STANDARD_15_USD` — US standard plan at 15 USD
- `MARKET_AR_PLAN_PERMISSIONS_TEST` — Permissions test fixture (no price suffix)

### Stripe Minimum Price Requirement

Stripe rejects charges below its USD-equivalent minimum (~$0.50). Canonical
fixture plans must use realistic prices:

| Market | Minimum safe price | Canonical fixture price |
|---|---|---|
| AR (Argentine Peso) | ~500 ARS | **50 000 ARS** (comfortable margin) |
| US (USD) | $1.00 | **$15.00** |

Never create a plan priced at 10 ARS or $0.10.

### Schema Notes (plans)

- `customer.plan_info.canonical_key VARCHAR(200) NULL` — added in
  migration `0002_plan_canonical_key.sql`.
- Partial index `uq_plan_info_canonical_key` (sparse: only indexed when non-null).
- `PlanResponseSchema` includes `canonical_key` (nullable string).

---

## Plates — `PUT /api/v1/plates/by-key`

```http
PUT /api/v1/plates/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `RESTAURANT_LA_COCINA_PORTENA_PLATE_BONDIOLA` |
| `product_id` | UUID | yes | FK to `ops.product_info` — the recipe this plate is based on |
| `restaurant_id` | UUID | yes | FK to `ops.restaurant_info` — the restaurant offering this plate |
| `price` | decimal (>= 0) | yes | Local-currency price charged to subscribers |
| `credit` | int (> 0) | yes | Credit cost deducted from the subscriber's balance |
| `delivery_time_minutes` | int (> 0) | no | Estimated minutes to readiness (default 15) |
| `status` | string | no | `active` (default) or `inactive` |

Response body is `PlateResponseSchema` (same shape as `GET /api/v1/plates/{plate_id}`).

### canonical_key convention for plates

```
RESTAURANT_{RESTAURANT_SLUG}_PLATE_{PLATE_SLUG}
```

Examples:
- `RESTAURANT_LA_COCINA_PORTENA_PLATE_BONDIOLA` — La Cocina Portena's bondiola plate
- `RESTAURANT_LA_COCINA_PORTENA_PLATE_ENSALADA_GRIEGA` — same restaurant, different plate
- `RESTAURANT_E2E_PLATE_STANDARD` — generic E2E test fixture plate

### Pricing guidance for plates

Use realistic prices that reflect actual ARS subscription values:

| Market | Recommended plate price |
|---|---|
| AR | 15 000 - 25 000 ARS |
| US | $8 - $15 USD |

The E2E collection fixture uses 20 000 ARS / 8 credits.

### Why SQL fixtures are not used for plates

Unlike plans (which reference only `market_id` from reference data), plates
require both `product_id` and `restaurant_id`, which are created at test run
time via Postman. Therefore canonical plate fixtures live in the Postman
collection as `PUT /plates/by-key` calls rather than as SQL `INSERT` statements.

If you need a fully SQL-driven plate fixture (e.g. for geo tests), create the
product and restaurant rows with fixed UUIDs first, then use:

```sql
INSERT INTO ops.plate_info (...)
ON CONFLICT (canonical_key) WHERE canonical_key IS NOT NULL
DO UPDATE SET ...
```

### Schema Notes (plates)

- `ops.plate_info.canonical_key VARCHAR(200) NULL` — added in
  migration `0003_plate_canonical_key.sql`.
- Partial index `uq_plate_info_canonical_key` (sparse: only indexed when non-null).
- `PlateResponseSchema` includes `canonical_key` (nullable string).

---

## Users — `PUT /api/v1/users/by-key`

```http
PUT /api/v1/users/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

**INTERNAL SEED/FIXTURE ENDPOINT ONLY.** Never use for self-registration,
customer-facing signup, or B2B invite flows. Auth: Internal only. Returns 403
for Customer/Supplier roles.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `E2E_USER_SUPPLIER_ADMIN` |
| `institution_id` | UUID | yes | Institution this user belongs to |
| `role_type` | string | yes | `Supplier`, `Internal`, `Employer`, `Customer` |
| `role_name` | string | yes | Role name within the role_type |
| `username` | string (3-100 chars) | yes | Login username (must be unique) |
| `email` | string | yes | User email address |
| `password` | string (min 8 chars) | **INSERT only** | Plain-text password — hashed server-side before storage |
| `first_name` | string | no | Given name |
| `last_name` | string | no | Family name |
| `mobile_number` | string | no | E.164 format, e.g. `+15005550006` |
| `market_id` | UUID | no | Primary market ID |
| `status` | string | no | `active` (default) or `inactive` |

Response body is `UserResponseSchema` (same shape as `GET /api/v1/users/{user_id}`).

### Password semantics

| Operation | `password` field | Behavior |
|---|---|---|
| INSERT (new canonical_key) | Required | Plain-text is hashed server-side; hash stored in `hashed_password` |
| UPDATE (existing canonical_key) | Optional | If provided: re-hashed and stored. If absent: existing hash is left untouched |

**Never** send a pre-hashed value — only plain-text is accepted. The endpoint
always hashes before storage; the raw password is never persisted.

### Immutable fields on UPDATE

The following fields are stripped from the update payload and cannot be changed
via this endpoint (they were set at insert time and are immutable by design):

- `institution_id` — use the existing user's institution
- `role_type` — role type cannot change after creation
- `username` — login identifier; use a dedicated username-change flow if needed

### canonical_key convention for users

```
E2E_USER_{ROLE_TYPE}_{ROLE_NAME}[_{DISCRIMINATOR}]
```

Examples:
- `E2E_USER_SUPPLIER_ADMIN` — shared E2E supplier admin used across collections
- `E2E_USER_INTERNAL_ADMIN` — shared E2E internal admin
- `E2E_USER_CUSTOMER_COMENSAL` — shared E2E customer

### System-user skip list

The `scripts/cleanup_duplicate_users.py` script hard-skips the following
usernames and will **never** archive them, regardless of duplication:

| Username | Reason |
|---|---|
| `superadmin` | Seeded super_admin in `dev_fixtures.sql` |
| `vianda_admin` | Shared internal admin used by downstream collections |

Add entries to `SYSTEM_USER_SKIP_LIST` in `cleanup_duplicate_users.py` when
new system/sentinel accounts are added.

### Postman pre-request token elevation

`PUT /users/by-key` is Internal-only but Postman collection-level bearer auth
may resolve to the current step's supplier/customer token. Use the same
synchronous admin-token elevation pattern as `PUT /plates/by-key`:

1. Read the admin token from collection scope (not overwritten by supplier login).
2. Promote it to environment scope so `{{authToken}}` resolves to the admin token.
3. After the upsert, the environment scope is left for the next `Login ...` step
   to overwrite as normal.

See "Upsert Canonical Supplier User (idempotent)" in
`docs/postman/collections/000 E2E Plate Selection.postman_collection.json`.

### Re-align institutionId after upsert

On re-runs the user is already bound to a prior run's institution
(`institution_id` is immutable). The Postman test script must re-align
`institutionId` collection variable to `body.institution_id` after every upsert
call so downstream requests use the correct institution.

### Schema Notes (users)

- `core.user_info.canonical_key VARCHAR(200) NULL` — added in
  migration `0004_user_canonical_key.sql`.
- Partial index `uq_user_info_canonical_key` (sparse: only indexed when non-null).
- `UserResponseSchema` includes `canonical_key` (nullable string).

---

## Restaurants — `PUT /api/v1/restaurants/by-key`

```http
PUT /api/v1/restaurants/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

**INTERNAL SEED/FIXTURE ENDPOINT ONLY.** Never use for supplier self-registration
or ad-hoc restaurant creation. Auth: Internal only. Returns 403 for Customer/Supplier
roles.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `E2E_RESTAURANT_CAMBALACHE` |
| `institution_id` | UUID | yes | FK to `core.institution_info` — the supplier institution |
| `institution_entity_id` | UUID | yes | FK to `ops.institution_entity_info` — the legal entity |
| `address_id` | UUID | yes | FK to `core.address_info` — physical pickup location |
| `name` | string (<=100 chars) | yes | Display name of the restaurant |
| `cuisine_id` | UUID | no | FK to `ops.cuisine` — primary cuisine category |
| `pickup_instructions` | string (<=500 chars) | no | Free-text pickup instructions |
| `tagline` | string (<=500 chars) | no | Marketing tagline (primary locale) |
| `tagline_i18n` | object | no | Locale map: `{en: '...', es: '...'}` |
| `is_featured` | bool | no | Boost in explore listings |
| `cover_image_url` | string | no | CDN URL for cover image |
| `spotlight_label` | string (<=200 chars) | no | Short promotional label |
| `spotlight_label_i18n` | object | no | Locale map for spotlight label |
| `member_perks` | list[string] | no | Perk bullet points |
| `member_perks_i18n` | object | no | Locale map for member perks |
| `status` | string | no | `pending` (default on INSERT) |

Response body is `RestaurantResponseSchema` (same shape as `GET /api/v1/restaurants/{restaurant_id}`).

### INSERT vs UPDATE behaviour

- **INSERT path**: a new restaurant row is created **and** the corresponding
  `restaurant_balance` record is created atomically (same transaction as
  `POST /restaurants`). Status is forced to `pending` regardless of what the
  caller sends.
- **UPDATE path**: only the restaurant row is updated. The balance record is
  left untouched — do not re-create it.

### Immutable fields on UPDATE

The following fields are stripped from the update payload and cannot be changed
via this endpoint (they were set at insert time and are immutable by design):

- `institution_id` — FK to the owning institution; cannot change after creation
- `institution_entity_id` — FK to the legal entity; cannot change after creation

### canonical_key convention for restaurants

```
E2E_RESTAURANT_{SLUG}
```

Examples:
- `E2E_RESTAURANT_CAMBALACHE` — E2E test fixture restaurant
- `E2E_RESTAURANT_LA_COCINA_PORTENA` — alternate fixture restaurant

### Why SQL fixtures are not used for restaurants

Like plates, restaurants require `institution_id`, `institution_entity_id`, and
`address_id`, which are created at test run time via Postman. Therefore canonical
restaurant fixtures live in the Postman collection as `PUT /restaurants/by-key`
calls rather than as SQL `INSERT` statements.

### Postman pre-request token elevation

`PUT /restaurants/by-key` is Internal-only but Postman collection-level bearer
auth may resolve to the current step's supplier token. Use the same synchronous
admin-token elevation pattern as `PUT /plates/by-key`:

1. Read the admin token from collection scope (not overwritten by supplier login).
2. Promote it to environment scope so `{{authToken}}` resolves to the admin token.
3. Restore the supplier token in the test script post-upsert.

See "Upsert Canonical Restaurant (idempotent)" in
`docs/postman/collections/000 E2E Plate Selection.postman_collection.json`.

### Schema Notes (restaurants)

- `ops.restaurant_info.canonical_key VARCHAR(200) NULL` — added in
  migration `0005_restaurant_canonical_key.sql`.
- Partial index `uq_restaurant_info_canonical_key` (sparse: only indexed when non-null).
- `RestaurantResponseSchema` includes `canonical_key` (nullable string).

---

## Institutions — `PUT /api/v1/institutions/by-key`

```http
PUT /api/v1/institutions/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

**INTERNAL SEED/FIXTURE ENDPOINT ONLY.** Never use for admin-driven institution
creation or self-registration flows. Auth: Internal only. Returns 403 for
Customer/Supplier roles.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `E2E_INSTITUTION_SUPPLIER` |
| `name` | string (<=100 chars) | yes | Display name of the institution |
| `institution_type` | string | yes | `Supplier`, `Employer`, `Customer`, or `Internal` |
| `market_ids` | list[UUID] | yes | Markets to assign (first is primary). At least one required. |
| `status` | string | no | `active` (default) |

Response body is `InstitutionResponseSchema` (same shape as `GET /api/v1/institutions/{institution_id}`).

### INSERT vs UPDATE behaviour

- **INSERT path**: a new institution row is created and market assignments are
  inserted atomically into `core.institution_market` (same transaction).
- **UPDATE path**: only `name` and `status` are updated. `institution_type` is
  immutable after insert. Market assignments are always reapplied (delete + re-insert)
  so the institution stays in the expected markets on every idempotent run.

### Immutable fields on UPDATE

The following fields are stripped from the update payload and cannot be changed
via this endpoint (they were set at insert time and are immutable by design):

- `institution_type` — discriminator (supplier/employer/customer/internal) cannot
  change after creation

### canonical_key convention for institutions

```
E2E_INSTITUTION_{ROLE_TYPE}[_{DISCRIMINATOR}]
```

Examples:
- `E2E_INSTITUTION_SUPPLIER` — shared E2E supplier institution used across collections
- `E2E_INSTITUTION_EMPLOYER` — shared E2E employer institution

### System institution skip list

The `scripts/cleanup_duplicate_institutions.py` script hard-skips the following
institution IDs and will **never** archive them, regardless of duplication:

| Institution ID | Reason |
|---|---|
| `11111111-1111-1111-1111-111111111111` | Vianda Enterprises (internal, seeded in reference_data.sql) |
| `22222222-2222-2222-2222-222222222222` | Vianda Customers (customer group, seeded in reference_data.sql) |
| `aaaaaaaa-aaaa-0001-0000-000000000001` | Dev fixture: Mercado Vianda BA (supplier, in dev_fixtures.sql) |

Add entries to `SYSTEM_INSTITUTION_SKIP_LIST` in `cleanup_duplicate_institutions.py` when
new system/sentinel institutions are added.

### Postman pre-request token elevation

`PUT /institutions/by-key` is Internal-only but Postman collection-level bearer
auth may resolve to the current step's supplier/customer token. Use the same
synchronous admin-token elevation pattern as `PUT /restaurants/by-key`:

1. Read the admin token from collection scope (not overwritten by supplier login).
2. Promote it to environment scope so `{{authToken}}` resolves to the admin token.
3. After the upsert, restore `{{authToken}}` to the supplier token.

See "Upsert Canonical Supplier Institution (idempotent)" in
`docs/postman/collections/000 E2E Plate Selection.postman_collection.json`.

### Schema Notes (institutions)

- `core.institution_info.canonical_key VARCHAR(200) NULL` — added in
  migration `0006_institution_canonical_key.sql`.
- Partial index `uq_institution_info_canonical_key` (sparse: only indexed when non-null).
- `InstitutionResponseSchema` includes `canonical_key` (nullable string).

---

## Markets — `PUT /api/v1/markets/by-key`

```http
PUT /api/v1/markets/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

**INTERNAL SEED/FIXTURE ENDPOINT ONLY.** Never use for ad-hoc market creation.
Auth: Internal only. Returns 403 for Customer/Supplier roles.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `E2E_MARKET_AR` |
| `country_code` | string (2-3 chars) | yes | ISO 3166-1 alpha-2 or alpha-3; API normalizes to alpha-2. **Immutable after INSERT.** |
| `currency_metadata_id` | UUID | yes | FK to `core.currency_metadata` |
| `language` | string (2-5 chars) | no | Default UI locale: `en`, `es`, `pt`. Derived from country_code if omitted. |
| `phone_dial_code` | string (<=6 chars) | no | E.164 dial code prefix (e.g. `+54`) |
| `phone_local_digits` | int | no | Max digits in national number after dial code (e.g. 10) |
| `status` | string | no | `active` (default) or `inactive` |

Response body is `MarketResponseSchema` (same shape as `GET /api/v1/markets/{market_id}`).

### INSERT vs UPDATE behaviour

- **INSERT path**: a new market row is created and the corresponding
  `billing.market_payout_aggregator` record is created atomically (same
  transaction as `POST /markets`). `canonical_key` is set on the new row.
- **UPDATE path**: only the market row is updated. `country_code` is stripped
  — it is immutable after creation and cannot change via this endpoint.

### Immutable fields on UPDATE

The following fields are stripped from the update payload and cannot be changed
via this endpoint (they were set at insert time and are immutable by design):

- `country_code` — each market is keyed by country; cannot change after creation

### canonical_key convention for markets

```
E2E_MARKET_{ISO2_CODE}
```

Examples:
- `E2E_MARKET_AR` — Argentina E2E fixture market
- `E2E_MARKET_US` — US E2E fixture market

### System market skip list

The `scripts/cleanup_duplicate_markets.py` script hard-skips the following
market IDs and will **never** archive them, regardless of duplication:

| Market ID | Country | Reason |
|---|---|---|
| `00000000-0000-0000-0000-000000000001` | Global (XG) | Sentinel global market, seeded in `reference_data.sql` |
| `00000000-0000-0000-0000-000000000002` | Argentina (AR) | Canonical AR market, seeded in `reference_data.sql` |
| `00000000-0000-0000-0000-000000000003` | Peru (PE) | Canonical PE market, seeded in `reference_data.sql` |
| `00000000-0000-0000-0000-000000000004` | US | Canonical US market, seeded in `reference_data.sql` |
| `00000000-0000-0000-0000-000000000005` | Chile (CL) | Canonical CL market, seeded in `reference_data.sql` |
| `00000000-0000-0000-0000-000000000006` | Mexico (MX) | Canonical MX market, seeded in `reference_data.sql` |
| `00000000-0000-0000-0000-000000000007` | Brazil (BR) | Canonical BR market, seeded in `reference_data.sql` |

Add entries to `SYSTEM_MARKET_SKIP_LIST` in `cleanup_duplicate_markets.py` when
new system/sentinel markets are added.

### Postman pre-request script

`PUT /markets/by-key` is Internal-only. The "Upsert Canonical Market Argentina
(idempotent)" step runs early in the E2E collection before any supplier login, so
the super-admin token from "Login Super Admin" is already current in
`pm.environment.get('authToken')`. No token swap is needed.

The pre-request script reads `planCreditCurrencyId` from collection scope and
injects it into the body payload before sending:

```javascript
// planCreditCurrencyId may be null if the 409 async fallback in 'Create Credit Currency'
// has not completed yet. Fall back to the seeded ARS currency ID from reference_data.sql.
const SEEDED_ARS_CURRENCY_ID = '66666666-6666-6666-6666-666666666601';
const planCreditCurrencyId = pm.collectionVariables.get('planCreditCurrencyId')
    || pm.environment.get('planCreditCurrencyId')
    || SEEDED_ARS_CURRENCY_ID;
let payload = JSON.parse(pm.request.body.raw);
payload.currency_metadata_id = planCreditCurrencyId;
pm.request.headers.upsert({ key: 'Content-Type', value: 'application/json' });
pm.request.body.update(JSON.stringify(payload));
```

See "Upsert Canonical Market Argentina (idempotent)" in
`docs/postman/collections/000 E2E Plate Selection.postman_collection.json`.

### Schema Notes (markets)

- `core.market_info.canonical_key VARCHAR(200) NULL` — added in
  migration `0007_market_canonical_key.sql`.
- Partial index `uq_market_info_canonical_key` (sparse: only indexed when non-null).
- `MarketResponseSchema` includes `canonical_key` (nullable string).

---

## Shared Semantics (all entities)

- If a row with the given `canonical_key` **does not exist**: a new row is
  inserted with that `canonical_key`.
- If a row with the given `canonical_key` **already exists**: the row is
  updated in-place; the primary key does not change.
- Running the same request twice with identical payload is a no-op after the
  first call (idempotent).
- HTTP **200** on both insert and update (unlike POST which returns 201).
- Auth: Internal only. Returns 403 for Customer/Supplier roles.
- Keys are UPPER_SNAKE_CASE. Once published to a Postman collection or seed
  file the key must **not** be renamed (renaming would create a new row,
  orphaning the old one).

---

## When to Use Upsert vs POST

| Situation | Use |
|---|---|
| Postman seed request (create test data before a test run) | `PUT /by-key` |
| `dev_fixtures.sql` canonical plan row | `INSERT ... ON CONFLICT (canonical_key) DO UPDATE` |
| Admin creating a real production plan | `POST /plans` |
| Supplier creating a real production plate | `POST /plates` |
| Updating a known existing row | `PUT /{entity}/{id}` |

---

## Duplicate Cleanup Scripts

If the dev DB already has duplicate rows accumulated before the upsert
endpoints existed, run the cleanup scripts.

### Plans

```bash
# Dry-run first:
python scripts/cleanup_duplicate_plans.py --dry-run

# Live run — archives duplicates, keeps the oldest row per market+name:
python scripts/cleanup_duplicate_plans.py
```

Plans with a `canonical_key` are never touched by the cleanup script.

### Plates

```bash
# Dry-run first:
python scripts/cleanup_duplicate_plates.py --dry-run

# Live run — archives duplicates, keeps the oldest row per restaurant+product:
python scripts/cleanup_duplicate_plates.py
```

Plates with a `canonical_key` are never touched by the cleanup script.

### Users

```bash
# Dry-run first:
python scripts/cleanup_duplicate_users.py --dry-run

# Live run — archives duplicates, keeps the oldest row per username:
python scripts/cleanup_duplicate_users.py
```

Users with a `canonical_key` are never touched by the cleanup script.
System users in `SYSTEM_USER_SKIP_LIST` (superadmin, vianda_admin) are always
preserved regardless of duplication.

### Restaurants

```bash
# Dry-run first:
python scripts/cleanup_duplicate_restaurants.py --dry-run

# Live run — archives duplicates, keeps the oldest row per institution+name:
python scripts/cleanup_duplicate_restaurants.py
```

Restaurants with a `canonical_key` are never touched by the cleanup script.

### Institutions

```bash
# Dry-run first:
python scripts/cleanup_duplicate_institutions.py --dry-run

# Live run — archives duplicates, keeps the oldest row per name:
python scripts/cleanup_duplicate_institutions.py
```

Institutions with a `canonical_key` are never touched by the cleanup script.
System institutions (`SYSTEM_INSTITUTION_SKIP_LIST`) are always preserved
regardless of duplication.

### Markets

```bash
# Dry-run first:
python scripts/cleanup_duplicate_markets.py --dry-run

# Live run — archives duplicates, keeps the oldest row per country_code:
python scripts/cleanup_duplicate_markets.py
```

Markets with a `canonical_key` are never touched by the cleanup script.
System markets in `SYSTEM_MARKET_SKIP_LIST` (all 7 seeded markets) are always
preserved regardless of duplication.

All scripts are idempotent: running again after a clean state does nothing.
