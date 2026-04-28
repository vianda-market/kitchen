# Upsert Endpoint & Canonical Fixture Convention

Applies to: **plans** (issue #130), **plates** (issue #166), **users** (issue #168), **restaurants** (issue #167), **institutions** (issue #190), **markets** (issue #190), **institution entities** (issue #190), and **products** (issue #190).

## Overview

Postman collections and dev seed scripts that create plans, plates, users, restaurants,
or products should use the idempotent upsert endpoints (`PUT /api/v1/plans/by-key`,
`PUT /api/v1/plates/by-key`, `PUT /api/v1/users/by-key`,
`PUT /api/v1/restaurants/by-key`, `PUT /api/v1/products/by-key`) rather than
the corresponding `POST` endpoints. Using POST creates a new row on every run,
causing duplicate rows to accumulate in the dev DB.

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
- `E2E_USER_SUPPLIER_ADMIN` — shared E2E supplier admin used across collections (collection 000)
- `E2E_USER_INTERNAL_ADMIN` — shared E2E internal admin (`vianda_admin`); used by downstream collections 001, 008, 010 (collection 000)
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

## Institution Entities — `PUT /api/v1/institution-entities/by-key`

```http
PUT /api/v1/institution-entities/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

**INTERNAL SEED/FIXTURE ENDPOINT ONLY.** Never use for supplier self-registration
or ad-hoc entity creation. Auth: Internal only. Returns 403 for Customer/Supplier
roles.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `E2E_INSTITUTION_ENTITY_SUPPLIER` |
| `institution_id` | UUID | yes | FK to `core.institution_info` — the owning institution |
| `address_id` | UUID | yes | FK to `core.address_info` — registered office address for this entity |
| `tax_id` | string (<=50 chars) | yes | Tax identification number for the entity's jurisdiction |
| `name` | string (<=100 chars) | yes | Legal entity name as registered with the tax authority |
| `email_domain` | string (<=255 chars) | no | Email domain for domain-gated employer enrollment or SSO. NULL for suppliers. |
| `is_archived` | bool | no | Archive state (default `false`) |
| `status` | string | no | `active` (default) or `inactive` |

Note: `currency_metadata_id` is **not** a request field — it is always derived
server-side from the address country code (same policy as `POST /institution-entities`).

Response body is `InstitutionEntityResponseSchema` (same shape as `GET /api/v1/institution-entities/{entity_id}`).

### INSERT vs UPDATE behaviour

- **INSERT path**: a new institution entity row is created and `currency_metadata_id`
  is derived from the address country code. The address country must map to a market
  assigned to the institution (`institution_market`) — a 400 is returned otherwise.
- **UPDATE path**: only the entity row is updated. `institution_id` is stripped from
  the update payload — it is immutable after creation. `currency_metadata_id` is
  re-derived if `address_id` is changed.

### Immutable fields on UPDATE

The following fields are stripped from the update payload and cannot be changed
via this endpoint (they were set at insert time and are immutable by design):

- `institution_id` — entities cannot move between institutions after creation

### canonical_key convention for institution entities

```
E2E_INSTITUTION_ENTITY_{ROLE_TYPE}[_{DISCRIMINATOR}]
```

Examples:
- `E2E_INSTITUTION_ENTITY_SUPPLIER` — shared E2E supplier entity used across collections

### System institution entity skip list

The `scripts/cleanup_duplicate_institution_entities.py` script hard-skips the following
entity IDs and will **never** archive them, regardless of duplication:

| Entity ID | Reason |
|---|---|
| `aaaaaaaa-aaaa-0001-0000-000000000002` | Dev fixture: Mercado Vianda BA Entidad (in dev_fixtures.sql) |

Add entries to `SYSTEM_INSTITUTION_ENTITY_SKIP_LIST` in
`cleanup_duplicate_institution_entities.py` when new system/sentinel entities are added.

### Postman pre-request token elevation

`PUT /institution-entities/by-key` is Internal-only but Postman collection-level bearer
auth may resolve to the current step's supplier/customer token. Use the same
synchronous admin-token elevation pattern as `PUT /restaurants/by-key`:

1. Read the admin token from collection scope (not overwritten by supplier login).
2. Promote it to environment scope so `{{authToken}}` resolves to the admin token.
3. Restore the supplier token in the test script post-upsert.

See "Upsert Canonical Supplier Entity (idempotent)" in
`docs/postman/collections/000 E2E Plate Selection.postman_collection.json`.

### Schema Notes (institution entities)

- `ops.institution_entity_info.canonical_key VARCHAR(200) NULL` — added in
  migration `0008_institution_entity_canonical_key.sql`.
- Partial index `uq_institution_entity_info_canonical_key` (sparse: only indexed when non-null).
- `InstitutionEntityResponseSchema` includes `canonical_key` (nullable string).

---

## Products — `PUT /api/v1/products/by-key`

```http
PUT /api/v1/products/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

**INTERNAL SEED/FIXTURE ENDPOINT ONLY.** Never use for supplier ad-hoc product
creation or management flows. Auth: Internal only. Returns 403 for
Customer/Supplier roles.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `E2E_PRODUCT_BIG_BURGUER` |
| `institution_id` | UUID | yes | FK to `core.institution_info` — the owning supplier institution. **Immutable after INSERT.** |
| `name` | string (<=100 chars) | yes | Display name of the product |
| `name_i18n` | object | no | Locale map: `{en: '...', es: '...'}` |
| `ingredients` | string (<=255 chars) | no | Free-text ingredient list (primary locale) |
| `ingredients_i18n` | object | no | Locale map for ingredient list |
| `description` | string (<=1000 chars) | no | Short product description |
| `description_i18n` | object | no | Locale map for description |
| `dietary` | list[string] | no | Dietary attribute slugs (e.g. `vegan`, `gluten_free`) |
| `status` | string | no | `active` (default) or `inactive` |

Response body is `ProductResponseSchema` (same shape as `GET /api/v1/products/{product_id}`).

### Immutable fields on UPDATE

The following fields are stripped from the update payload and cannot be changed
via this endpoint (they were set at insert time and are immutable by design):

- `institution_id` — FK to the owning institution; cannot change after creation

### canonical_key convention for products

```
E2E_PRODUCT_{SLUG}
```

Examples:
- `E2E_PRODUCT_BIG_BURGUER` — shared E2E product used across collections (the plate upsert references it via `productId`)

### Why SQL fixtures are not used for products

Like restaurants and plates, products require `institution_id` which is created
at test run time via Postman. Therefore canonical product fixtures live in the
Postman collection as `PUT /products/by-key` calls rather than as SQL
`INSERT` statements.

### Postman pre-request token elevation

`PUT /products/by-key` is Internal-only but at the point where it runs in the
E2E collection the environment-scope `authToken` holds the supplier token from
"Login Supplier Admin". Use the same synchronous admin-token elevation pattern
as `PUT /plates/by-key`:

1. Read the admin token from collection scope (not overwritten by supplier login).
2. Promote it to environment scope so `{{authToken}}` resolves to the admin token.
3. After the upsert, restore `{{authToken}}` to the supplier token.

See "Upsert Canonical Supplier Product (idempotent)" in
`docs/postman/collections/000 E2E Plate Selection.postman_collection.json`.

### productId downstream propagation

The test script sets `pm.collectionVariables.set('productId', body.product_id)` so
the downstream "Upsert Canonical Plate" step can inject it as `payload.product_id`.
Do not remove or rename this variable.

### Schema Notes (products)

- `ops.product_info.canonical_key VARCHAR(200) NULL` — added in
  migration `0009_product_canonical_key.sql`.
- Partial index `uq_product_info_canonical_key` (sparse: only indexed when non-null).
- `ProductResponseSchema` includes `canonical_key` (nullable string).

---
## Plate Kitchen Days — `PUT /api/v1/plate-kitchen-days/by-key`

```http
PUT /api/v1/plate-kitchen-days/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

**INTERNAL SEED/FIXTURE ENDPOINT ONLY.** Never use for ad-hoc kitchen day creation
(use `POST /plate-kitchen-days` instead). Auth: Internal only. Returns 403 for
Customer/Supplier roles.

Plate kitchen days are unique by `(plate_id, kitchen_day)`.  The canonical_key
identifies the logical fixture row — one key per plate + weekday combination.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `E2E_PKD_E2E_PLATE_STANDARD_MONDAY` |
| `plate_id` | UUID | yes | FK to `ops.plate_info`. **Immutable after INSERT.** |
| `kitchen_day` | string | yes | Weekday: `monday`–`friday`. **Immutable after INSERT.** |
| `status` | string | no | `active` (default) or `inactive` |

Response body is `PlateKitchenDayResponseSchema` (same shape as
`GET /api/v1/plate-kitchen-days/{plate_kitchen_day_id}`).

### INSERT vs UPDATE behaviour

- **INSERT path**: a new plate kitchen day row is created with the given
  `canonical_key`, `plate_id`, `kitchen_day`, and `status`. If a non-canonical
  row already occupies the `(plate_id, kitchen_day)` slot (e.g. from a prior
  `POST`), that existing row is adopted (stamped with the canonical_key) instead
  of creating a duplicate.
- **UPDATE path**: only `status` and `canonical_key` are updated.  `plate_id`
  and `kitchen_day` are immutable after creation — any values sent in the payload
  are silently ignored on the update path.

### Immutable fields on UPDATE

The following fields are locked after INSERT and cannot be changed via this
endpoint:

- `plate_id` — FK to the plate; cannot change after creation. To reassign a
  kitchen day to a different plate, archive the old row and create a new
  canonical row.
- `kitchen_day` — the weekday this row represents; cannot change after creation.
  To move the same plate to a different day, archive the old row and create a
  new canonical row for the new day.

### canonical_key convention for plate kitchen days

```
E2E_PKD_{PLATE_SLUG}_{DAY}
```

Where `PLATE_SLUG` is derived from the plate's canonical key (the segment after
`RESTAURANT_..._PLATE_`) uppercased, and `DAY` is the weekday in UPPER_SNAKE_CASE.

Examples:
- `E2E_PKD_E2E_PLATE_STANDARD_MONDAY` — Monday slot for the standard E2E plate
- `E2E_PKD_E2E_PLATE_STANDARD_TUESDAY` — Tuesday slot
- `E2E_PKD_CAMBALACHE_BONDIOLA_MONDAY` — Monday slot for a named plate

### Postman pre-request token elevation

`PUT /plate-kitchen-days/by-key` is Internal-only.  The canonical kitchen-day
upserts run inside the "Supplier Menu Setup" folder where the collection-level
auth resolves to the supplier token.  Use the same admin-token elevation pattern
as `PUT /plates/by-key`:

1. Read the admin token from collection scope (not overwritten by supplier login).
2. Promote it to environment scope so `{{authToken}}` resolves to the admin token.
3. Restore the supplier token in the test script post-upsert (so downstream
   supplier steps continue to work).

See "Upsert Canonical Plate Kitchen Day Monday (idempotent)" through
"Upsert Canonical Plate Kitchen Day Friday (idempotent)" in
`docs/postman/collections/000 E2E Plate Selection.postman_collection.json`.

### Schema Notes (plate kitchen days)

- `ops.plate_kitchen_days.canonical_key VARCHAR(200) NULL` — added in
  migration `0012_plate_kitchen_day_canonical_key.sql`.
- Partial index `uq_plate_kitchen_days_canonical_key` (sparse: only indexed when non-null).
- `PlateKitchenDayResponseSchema` includes `canonical_key` (nullable string).

---

## QR Codes — `PUT /api/v1/qr-codes/by-key`

```http
PUT /api/v1/qr-codes/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

**INTERNAL SEED/FIXTURE ENDPOINT ONLY.** Never use for supplier QR code
generation or ad-hoc kiosk setup. Auth: Internal only. Returns 403 for
Customer/Supplier roles.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `E2E_QR_CAMBALACHE` |
| `restaurant_id` | UUID | yes | FK to `ops.restaurant_info`. **Immutable after INSERT** — ignored on the update path. |

Response body is `QRCodeResponseSchema` (same shape as `GET /api/v1/qr-codes/{qr_code_id}`).

### INSERT vs UPDATE behaviour

- **INSERT path**: a new QR code row is created atomically (same image-generation
  pipeline as `POST /qr-codes`). `canonical_key` is stamped onto the new row
  immediately after atomic creation. Status is `active` and the QR image is
  generated in GCS.
- **UPDATE path**: only the `canonical_key` stamp and `modified_date` are
  refreshed. The QR image, payload, and `restaurant_id` are left untouched —
  do not re-generate the image.

### Immutable fields on UPDATE

The following fields are stripped from the update payload and cannot be changed
via this endpoint (they were set at insert time and are immutable by design):

- `restaurant_id` — FK to the owning restaurant; cannot change after creation

### canonical_key convention for QR codes

```
E2E_QR_{RESTAURANT_SLUG}
```

Examples:
- `E2E_QR_CAMBALACHE` — QR code for the E2E test restaurant "Cambalache"
- `E2E_QR_LA_COCINA_PORTENA` — QR code for the alternate E2E fixture restaurant

### Why SQL fixtures are not used for QR codes

QR codes require `restaurant_id` (created at test run time via Postman) and
trigger GCS image generation that cannot be replicated in SQL. Therefore
canonical QR code fixtures live in the Postman collection as
`PUT /qr-codes/by-key` calls rather than as SQL `INSERT` statements.

### Postman pre-request token elevation

`PUT /qr-codes/by-key` is Internal-only but at the point in the E2E collection
where QR codes are created, the supplier login has already set the environment
`authToken`. Use the same synchronous admin-token elevation pattern as
`PUT /restaurants/by-key`:

1. Read the admin token from collection scope (not overwritten by supplier login).
2. Promote it to environment scope so `{{authToken}}` resolves to the admin token.
3. Restore the supplier token in the test script post-upsert.

See "Upsert Canonical Restaurant QR Code (idempotent)" in
`docs/postman/collections/000 E2E Plate Selection.postman_collection.json`.

### Schema Notes (QR codes)

- `ops.qr_code.canonical_key VARCHAR(200) NULL` — added in
  migration `0010_qr_code_canonical_key.sql`.
- Partial index `uq_qr_code_canonical_key` (sparse: only indexed when non-null).
- `QRCodeResponseSchema` includes `canonical_key` (nullable string).

---

## Restaurant Holidays — `PUT /api/v1/restaurant-holidays/by-key`

```http
PUT /api/v1/restaurant-holidays/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

**INTERNAL SEED/FIXTURE ENDPOINT ONLY.** Never use for ad-hoc holiday creation.
Auth: Internal only. Returns 403 for Customer/Supplier roles.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `E2E_HOLIDAY_CAMBALACHE_MAINTENANCE` |
| `restaurant_id` | UUID | yes | FK to `ops.restaurant_info`. **Immutable after INSERT.** |
| `holiday_date` | date (YYYY-MM-DD) | yes | Calendar date of the closure. **Immutable after INSERT.** |
| `holiday_name` | string (<=100 chars) | yes | Display name (e.g. `Restaurant Maintenance Day`) |
| `is_recurring` | bool | no | When `true`, holiday repeats annually on `recurring_month`/`recurring_day` (default `false`) |
| `recurring_month` | int (1-12) | no | Month of annual recurrence. Required when `is_recurring=true`. |
| `recurring_day` | int (1-31) | no | Day-of-month of annual recurrence. Required when `is_recurring=true`. |
| `status` | string | no | `active` (default) or `inactive` |

Response body is `RestaurantHolidayResponseSchema` (same shape as `GET /api/v1/restaurant-holidays/{holiday_id}`).

### INSERT vs UPDATE behaviour

- **INSERT path**: a new holiday row is created with the given `canonical_key`. The
  `restaurant_id`, `holiday_date`, and `canonical_key` are all set at creation and are
  immutable after this point.
- **UPDATE path**: only `holiday_name`, `is_recurring`, `recurring_month`,
  `recurring_day`, and `status` are updated. `restaurant_id` and `holiday_date` are
  stripped from the update payload — they cannot change after creation.

### Immutable fields on UPDATE

The following fields are stripped from the update payload and cannot be changed
via this endpoint (they were set at insert time and are immutable by design):

- `restaurant_id` — the restaurant that owns this holiday; cannot change after creation
- `holiday_date` — the identity of a holiday is `(restaurant_id, holiday_date)`; changing the date would create a logically different holiday

### canonical_key convention for restaurant holidays

```
E2E_HOLIDAY_{RESTAURANT_SLUG}_{DESCRIPTION}
```

Examples:
- `E2E_HOLIDAY_CAMBALACHE_MAINTENANCE` — maintenance closure for E2E fixture restaurant Cambalache
- `E2E_HOLIDAY_CAMBALACHE_STAFF_TRAINING` — staff training closure for the same restaurant

### Postman pre-request script

`PUT /restaurant-holidays/by-key` is Internal-only but the Postman collection-level
bearer auth may resolve to the current step's supplier token. Use the same
synchronous admin-token elevation pattern as `PUT /restaurants/by-key`:

1. Read the admin token from collection scope (not overwritten by supplier login).
2. Promote it to environment scope so `{{authToken}}` resolves to the admin token.
3. The test script restores `{{authToken}}` to the supplier token.

See "Upsert Canonical Restaurant Holiday (idempotent)" in
`docs/postman/collections/000 E2E Plate Selection.postman_collection.json`.

### Schema Notes (restaurant holidays)

- `ops.restaurant_holidays.canonical_key VARCHAR(200) NULL` — added in
  migration `0010_restaurant_holiday_canonical_key.sql`.
- Partial index `uq_restaurant_holidays_canonical_key` (sparse: only indexed when non-null).
- `RestaurantHolidayResponseSchema` includes `canonical_key` (nullable string).

---

## Credit Currencies — `PUT /api/v1/credit-currencies/by-key`

```http
PUT /api/v1/credit-currencies/by-key
Authorization: Bearer {internal-token}
Content-Type: application/json
```

**INTERNAL SEED/FIXTURE ENDPOINT ONLY.** Never use for ad-hoc currency creation
(use `POST /credit-currencies` instead). Auth: Internal only. Returns 403 for
Customer/Supplier roles.

### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `canonical_key` | string (<=200 chars) | yes | Stable identifier, e.g. `E2E_CURRENCY_ARS` |
| `currency_name` | string (<=50 chars) | yes | ISO 4217 currency name — resolved to `currency_code` server-side (e.g. `Argentine Peso`) |
| `credit_value_local_currency` | decimal (> 0) | yes | How many local currency units equal one Vianda credit |

Response body is `CreditCurrencyResponseSchema` (same shape as `GET /api/v1/credit-currencies/{id}`),
with `canonical_key` field included.

### INSERT vs UPDATE behaviour

- **INSERT path (new canonical_key, no existing row for this currency_code):** a new `core.currency_metadata` row is created, the USD conversion rate is fetched from the currency-refresh source, and `canonical_key` is stamped.
- **Adopt path (new canonical_key, existing row with the same currency_code e.g. a seeded reference row):** the existing row is adopted — `canonical_key` is stamped and `credit_value_local_currency` is updated in-place. No new row is created. This is the common case for the 6 currencies seeded in `reference_data.sql` (USD, ARS, PEN, CLP, MXN, BRL).
- **UPDATE path (existing canonical_key):** only `credit_value_local_currency` is updated. `currency_code` is immutable.

### Immutable fields on UPDATE

The following fields are stripped from the update payload and cannot be changed
via this endpoint:

- `currency_code` — ISO 4217 natural unique key; immutable after insert

### canonical_key convention for credit currencies

```
E2E_CURRENCY_{ISO4217_CODE}
```

Examples:
- `E2E_CURRENCY_ARS` — Argentine Peso E2E fixture currency
- `E2E_CURRENCY_USD` — USD E2E fixture currency

### Retiring the old POST + retry pattern (issue #190)

The Postman collection previously used `POST /credit-currencies` + a pre-request
"if 409 skip" try/catch to handle re-runs.  This ad-hoc pattern has been retired
in favour of `PUT /credit-currencies/by-key`.  The "Create Credit Currency" step
in collection 000 has been replaced with "Upsert Canonical Credit Currency
(idempotent)".  There is no longer any 409/try-catch branching in the currency
setup step — the upsert handles insert, adopt, and update transparently, always
returning 200.

This was the final entity in umbrella issue #190 to be migrated to the canonical
upsert pattern.  All 9 seed entity types now use `PUT /by-key` endpoints.

### System currency skip list

The `scripts/cleanup_duplicate_credit_currencies.py` script hard-skips the
following currency IDs and will **never** archive them, regardless of duplication:

| Currency ID | Code | Reason |
|---|---|---|
| `55555555-5555-5555-5555-555555555555` | USD | Seeded in `reference_data.sql` |
| `66666666-6666-6666-6666-666666666601` | ARS | Seeded in `reference_data.sql` |
| `66666666-6666-6666-6666-666666666602` | PEN | Seeded in `reference_data.sql` |
| `66666666-6666-6666-6666-666666666603` | CLP | Seeded in `reference_data.sql` |
| `66666666-6666-6666-6666-666666666604` | MXN | Seeded in `reference_data.sql` |
| `66666666-6666-6666-6666-666666666605` | BRL | Seeded in `reference_data.sql` |

Add entries to `SYSTEM_CREDIT_CURRENCY_SKIP_LIST` in
`cleanup_duplicate_credit_currencies.py` when new system/sentinel currencies
are added.

### Postman pre-request script

`PUT /credit-currencies/by-key` is Internal-only. The "Upsert Canonical Credit
Currency (idempotent)" step runs early in collection 000 (before any supplier
login), so the super-admin token from "Login Super Admin" is already current in
`pm.environment.get('authToken')`. No token swap is needed.

The pre-request script only upserts the `Content-Type` header:

```javascript
pm.request.headers.upsert({ key: 'Content-Type', value: 'application/json' });
```

### Schema Notes (credit currencies)

- `core.currency_metadata.canonical_key VARCHAR(200) NULL` — added in
  migration `0013_credit_currency_canonical_key.sql`.
- Partial index `uq_credit_currency_canonical_key` (sparse: only indexed when non-null).
- `CreditCurrencyResponseSchema` includes `canonical_key` (nullable string).

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
| Supplier creating a real production product | `POST /products` |
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

### Institution Entities

```bash
# Dry-run first:
python scripts/cleanup_duplicate_institution_entities.py --dry-run

# Live run — archives duplicates, keeps the oldest row per institution+tax_id:
python scripts/cleanup_duplicate_institution_entities.py
```

Institution entities with a `canonical_key` are never touched by the cleanup script.
System entities (`SYSTEM_INSTITUTION_ENTITY_SKIP_LIST`) are always preserved
regardless of duplication.
### Products

```bash
# Dry-run first:
python scripts/cleanup_duplicate_products.py --dry-run

# Live run — archives duplicates, keeps the oldest row per institution+name:
python scripts/cleanup_duplicate_products.py
```

Products with a `canonical_key` are never touched by the cleanup script.
All scripts are idempotent: running again after a clean state does nothing.
