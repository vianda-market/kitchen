# Multinational Institutions

**Status:** Exploration / Not Started  
**Author:** Vianda CTO  
**Date:** 2026-04-12

---

## Motivation

Latin American economies are small. A single catering company or employer can easily span Argentina, Peru, and Colombia. Today, an institution is locked to one country (via `institution_info.market_id → market_info.country_code`). A supplier operating in AR and PE must create two separate institutions, two separate user sets, two separate logins. This is friction that doesn't reflect how these businesses actually work.

The goal: **allow one institution (one set of admin users, one login) to operate across multiple countries**, while keeping all country-specific concerns (legal entities, currencies, tax IDs, supplier agreements, billing) correctly scoped per country.

This is also a **normalization opportunity**: suppliers and employers converge on the same `institution_info` + `institution_entity_info` model. The separate `employer_info` table and `employer_domain` table are eliminated.

---

## Current Model (As-Is)

```
institution_info          1 institution = 1 market (country)
  ├── market_id (FK)      ← single country lock
  ├── user_info            ← users belong to 1 institution
  │
  ├── [Supplier path — uses entity layer]
  │   ├── institution_entity   ← legal entity (tax_id, currency, payout)
  │   │     ├── address_id     ← address has country_code
  │   │     └── restaurant     ← restaurant belongs to 1 entity
  │   └── supplier_terms       ← 1:1 with institution (UNIQUE)
  │
  └── [Employer path — NO entity layer]
      ├── employer_info              ← separate table (name, address_id) — NOT an entity
      ├── employer_benefits_program  ← 1:1 with institution (UNIQUE)
      ├── employer_domain            ← separate table, email domains, globally UNIQUE
      └── employer_bill              ← keyed by institution_id, currency from market
```

### Key Problems

| Problem | Detail |
|---------|--------|
| **Single-market lock** | `institution_info.market_id` pins institution to one country |
| **Supplier/employer divergence** | Suppliers use entities; employers use a separate `employer_info` table with no entity |
| **No employer tax entity** | Employers can't be billed properly per-country — no tax_id, no per-country currency, no per-country Stripe |
| **employer_info is redundant** | `institution_info` (type=employer) + `institution_entity_info` covers everything `employer_info` does |
| **employer_domain is a separate table** | One domain per entity is sufficient; separate table adds unnecessary complexity |

### What Already Works for Multi-Country (Supplier Side)

The **institution_entity** layer is already country-aware:
- `institution_entity_info` has `address_id` (with `country_code`), `currency_metadata_id`, `tax_id`, `payout_provider_account_id`
- `institution_bill_info` is keyed by `institution_entity_id` — supplier bills are already per-entity
- `institution_settlement` is per `institution_entity_id + restaurant_id`
- `restaurant_info` belongs to an entity, not directly to the institution
- Payout happens at entity level

**The entity layer was designed to be the country boundary.** Employers need to adopt it.

---

## Proposed Model (To-Be)

```
institution_info                    multi-market umbrella
  ├── institution_market (junction) ← allowed markets (admin-controlled multi-select)
  ├── user_info                     ← users belong to 1 institution
  │     ├── employer_entity_id?     ← for Customer Comensals: which employer entity (replaces employer_id)
  │     └── employer_address_id     ← which office for pickup (kept)
  │
  ├── institution_entity            ← legal entity per country — BOTH suppliers AND employers
  │     ├── address_id              ← address has country_code
  │     ├── tax_id, currency        ← billing identity
  │     ├── email_domain?            ← NEW column: email domain (optional, all entity types)
  │     ├── restaurant?             ← supplier entities only
  │     ├── supplier_terms?         ← entity-level override (optional)
  │     └── employer_benefits_program? ← entity-level override (currency-tied fields)
  │
  ├── supplier_terms                ← institution-level defaults
  ├── employer_benefits_program     ← institution-level defaults (rates, enrollment mode)
  └── employer_bill                 ← keyed by entity (currency-aware)
```

**Core ideas:**
1. **`institution_market` junction** controls which markets an institution can operate in (admin-assigned, multi-select)
2. **`institution_entity_info`** is the country boundary for **both** supplier and employer institutions
3. **`employer_info` table is removed** — employer identity is `institution_info` (type=employer) + entity per country
4. **`employer_domain` table is removed** — domain becomes `email_domain` column on `institution_entity_info` (one domain per entity; multiple domains = multiple entities). Available to all entity types — employers use it for enrollment gating, suppliers can use it in the future for SSO.
5. **Three-tier cascade:** `entity override → institution default → market default → hardcoded` for both `supplier_terms` and `employer_benefits_program`

---

## Schema Changes

### 1. `institution_info.market_id` → `institution_market` junction

```sql
-- Drop the single-market column from institution_info
-- (market_id column removed from CREATE TABLE)

-- New junction: which markets this institution is allowed to operate in
CREATE TABLE core.institution_market (
    institution_id UUID NOT NULL REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    market_id      UUID NOT NULL REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    is_primary     BOOLEAN NOT NULL DEFAULT FALSE,
    created_date   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (institution_id, market_id)
);
CREATE INDEX idx_institution_market_market ON core.institution_market(market_id);
```

Multi-select, admin-controlled. An institution can only create entities in markets assigned via this junction. `is_primary` drives default UX (which market to show first, which language to default).

**Enriched display:** `market_ids` as JSON array on enriched institution responses, following the `user_market_assignment → market_ids` pattern (`entity_service.py:384-397`, `json_agg` in `enriched_service.py:434-437`).

### 2. `billing.supplier_terms` — Three-tier cascade

```sql
-- Add optional entity FK for entity-level overrides
ALTER TABLE billing.supplier_terms ADD COLUMN institution_entity_id UUID NULL
    REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT;

-- Drop UNIQUE on institution_id; new composite constraint
ALTER TABLE billing.supplier_terms ADD CONSTRAINT uq_supplier_terms_scope
    UNIQUE (institution_id, institution_entity_id);
```

- `institution_entity_id IS NULL` → institution-level defaults (one row per institution)
- `institution_entity_id IS NOT NULL` → entity-level override

**Resolution:** `entity row → institution row → market_payout_aggregator → hardcoded`

Most suppliers operate in one country — they configure institution-level defaults once. Only multinational suppliers add entity overrides where local norms differ.

### 3. `institution_entity_info` — Extend to employers + add `email_domain` column

```sql
-- Add email_domain column (nullable; available to ALL entity types)
ALTER TABLE ops.institution_entity_info ADD COLUMN email_domain VARCHAR(255) NULL;
CREATE UNIQUE INDEX idx_entity_email_domain
    ON ops.institution_entity_info(email_domain)
    WHERE email_domain IS NOT NULL AND is_archived = FALSE;
```

The table already has everything needed: `institution_id`, `address_id`, `currency_metadata_id`, `tax_id`, `payout_provider_account_id`. No other structural changes required — just operational: employer institutions now create entities.

**`email_domain` on entity** replaces the separate `core.employer_domain` table:
- One domain per entity (nullable)
- Partial unique index ensures domain uniqueness across all active entities
- Multiple domains for one employer = multiple entities (different terms/currencies per domain if needed)
- Most employers have one domain, one entity per country — `@bigcorp.com` on the AR entity
- **Available to all entity types, not just employers.** Supplier entities can optionally register a domain for future SSO integration (e.g., supplier staff authenticate via `@catering-co.com`). For now, only employer entities use it for enrollment gating — but the column is type-agnostic so we don't need a schema change when SSO lands.

**Note on SSO:** Single Sign-On (SAML/OIDC) typically uses an email domain to route authentication to the correct identity provider. Storing `email_domain` on the entity now means the SSO mapping is already in place: `email_domain → entity → institution`. When SSO is implemented, the entity's domain tells us which identity provider to redirect to. This applies to both employers (employees log in) and suppliers (restaurant staff log in).

### 4. Drop `core.employer_info` table

**Removed.** Employer identity is now fully captured by:
- `core.institution_info` (type=`employer`) — name, organizational identity
- `ops.institution_entity_info` — per-country legal entity (tax_id, currency, address, domain)

**Migration of dependents:**

| Current reference | Migration |
|-------------------|-----------|
| `core.employer_info.employer_id` (PK) | Replaced by `institution_entity_info.institution_entity_id` |
| `core.employer_info.name` | Already on `institution_info.name` |
| `core.employer_info.address_id` | Now on `institution_entity_info.address_id` |
| `core.user_info.employer_id` → `employer_info` | **Becomes** `user_info.employer_entity_id` → `institution_entity_info` |
| `core.user_info.employer_address_id` | **Kept** — employee's pickup office address (may differ from entity's legal address) |
| `core.address_info.employer_id` → `employer_info` | **Drop column** — address links to entity via `institution_entity_info.address_id`, no need for reverse FK |
| Coworker matching (`employer_id + employer_address_id`) | **Becomes** `employer_entity_id + employer_address_id` |
| Restaurant explorer (`employer_id` for coworker flags) | **Becomes** `employer_entity_id` |
| `entity_service.create_employer_with_address()` | **Removed** — use standard entity creation flow |
| `entity_service.get_enriched_employers()` | **Removed** — enriched entity endpoints serve both types |
| `app/routes/employer.py` (full CRUD) | **Removed** — entity routes handle employer entities |
| `PUT /users/me/employer` (assign employer) | **Becomes** `PUT /users/me/employer-entity` — assigns `employer_entity_id` |
| `EmployerDTO`, `EmployerCreateSchema`, etc. | **Removed** — entity DTOs/schemas cover both types |
| `app/services/crud_service.py` `employer_service` | **Removed** |
| `app/db/index.sql` employer indexes | **Removed**, replaced by entity indexes |
| `audit.employer_history` | **Removed** — entity changes audited via `audit.institution_entity_history` |

**Also removed:**
- `core.employer_domain` table (replaced by `email_domain` column on entity)
- `audit.employer_history` table
- `EmployerDomainDTO` (replaced by `email_domain` field on entity DTO)
- All employer domain CRUD routes (`POST/GET/DELETE /employer/domains`)

### 5. `core.employer_benefits_program` — Three-tier cascade

```sql
-- Add optional entity FK for entity-level overrides
ALTER TABLE core.employer_benefits_program ADD COLUMN institution_entity_id UUID NULL
    REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT;

-- Drop UNIQUE on institution_id; new composite constraint
ALTER TABLE core.employer_benefits_program ADD CONSTRAINT uq_employer_program_scope
    UNIQUE (institution_id, institution_entity_id);
```

**Which fields live where:**

| Field | Institution-level (default) | Entity-level (override) |
|-------|---------------------------|------------------------|
| `benefit_rate` | Default rate (e.g., 70%) | Override if country-specific |
| `benefit_cap` | N/A (currency-tied) | **Required** — cap in entity's currency |
| `benefit_cap_period` | Default period | Override if needed |
| `price_discount` | Default discount % | Override if local pricing differs |
| `minimum_monthly_fee` | N/A (currency-tied) | **Required** — fee in entity's currency |
| `billing_cycle` | Default cycle | Override if local norms differ |
| `billing_day` / `billing_day_of_week` | Default | Override |
| `enrollment_mode` | Default mode | Override |
| `allow_early_renewal` | Default | Override |
| `stripe_customer_id` | N/A | **Entity-level only** — one Stripe per entity |
| `stripe_payment_method_id` | N/A | **Entity-level only** |

Currency-tied fields (`benefit_cap`, `minimum_monthly_fee`, `stripe_*`) exist only at entity level. Currency is derived from `institution_entity_info.currency_metadata_id`.

### 6. `billing.employer_bill` — Key by entity

```sql
ALTER TABLE billing.employer_bill ADD COLUMN institution_entity_id UUID NOT NULL
    REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT;
```

Bills generated per entity (per country/currency). The `currency_code` field already exists — now derived from entity's `currency_metadata_id`.

### 7. `core.user_info` — Replace `employer_id` with `employer_entity_id`

```sql
-- Drop employer_id (was FK to employer_info)
-- Add employer_entity_id (FK to institution_entity_info)
-- Keep employer_address_id (employee's pickup office — may differ from entity's legal address)
```

`employer_entity_id` identifies which employer entity (country) a Customer Comensal belongs to. Used for:
- Coworker matching (same entity + same office address)
- Benefit program resolution (entity's program config)
- Billing line items (which entity pays for this employee)

---

## Drop `core.address_info.employer_id` + Address Type Changes

Current: `address_info.employer_id` is a nullable FK to `employer_info`, used to auto-derive `address_type = CUSTOMER_EMPLOYER`. With `employer_info` gone:
- Entity's address links via `institution_entity_info.address_id` (already exists)
- Employee's pickup address links via `user_info.employer_address_id` (kept)
- **Drop `employer_id` column** from `address_info` and `address_history`

### Address type becomes user-selected (B2C)

Currently `customer_employer` is auto-derived by checking `employer_info` and `address_info.employer_id`. With those gone, **address type becomes user-selected** for B2C customers:

- **`customer_home`** — "Home" (existing)
- **`customer_employer`** — "Work". User enters an address and designates it as their workplace. Label change to "Work" in UI, enum value stays `customer_employer`.
- **`customer_other`** — "Other". Already in the enum (`address_type_enum`) and Python enum (`AddressType.CUSTOMER_OTHER`) but **missing i18n labels** — needs labels added.

The B2C app allows users to select which address to center their vianda/restaurant search around. Three options: Home, Work, Other.

**Changes to `address_service.py`:** The `customer_employer` type derivation logic (lines 61-76, queries `employer_info` and `address_info.employer_id`) is **removed**. Address type is now part of the address creation/update payload — the user selects "Home", "Work", or "Other" in the B2C app. The `address_type` array field on `address_info` already supports this; it just stops being auto-derived for work addresses.

**i18n labels to add** for `customer_other` in `app/i18n/enum_labels.py`:
- en: "Other"
- es: "Otro"
- pt: "Outro"

---

## JWT / Auth

Current JWT includes `institution_id` and `market_id`.

**B2C customers** use `market_id` in JWT to:
- Filter which restaurants/plans to show
- Resolve currency for price display
- Scope referral programs

This is **B2C-only** and orthogonal to the multinational institution change. Customers belong to the Vianda Customers institution (market_id = Global). Their JWT `market_id` reflects where they order food.

**Suppliers/Employers:** JWT `market_id` is not consumed by the B2B platform (verified with vianda-platform agent). We can leave it as-is for B2C. For B2B tokens, set it to `is_primary` market from `institution_market` — this also determines default language for the user's session.

**Language for B2B users:** `is_primary` market on `institution_market` determines the default language. B2B users in multinational institutions can switch their primary market (which updates their `user_market_assignment.is_primary`), changing their dashboard language. This is a future UX feature — for now, primary market = language.

**No breaking change.** B2C continues working. B2B gains language awareness via primary market.

---

## Service / App Layer Impact

### Three-Tier Resolution Pattern (New)

A shared pattern for `supplier_terms` and `employer_benefits_program`:

```
resolve_effective_value(field, institution_id, entity_id):
    1. Entity-level row (institution_id + entity_id) → if field is not NULL, return
    2. Institution-level row (institution_id + entity_id IS NULL) → if field is not NULL, return
    3. Market default (supplier_terms: market_payout_aggregator; employer: N/A)
    4. Hardcoded default
```

`supplier_terms_resolution.py` already implements a two-tier version. Extend to three-tier. Extract the pattern for reuse by employer program resolution.

### Scoping (Medium Impact)

`InstitutionScope` stays unchanged — filters by `institution_id`.

**New:** Optional `?market_id=` query filter on enriched endpoints. Validated against `institution_market` — can't filter to an unassigned market.

### Supplier Terms Resolution (Medium Impact)

Current: `supplier_terms → market_payout_aggregator → hardcoded`  
New: `entity_supplier_terms → institution_supplier_terms → market_payout_aggregator → hardcoded`

Callers that pass `institution_id` only get institution-level defaults (correct for single-market). Callers with `institution_entity_id` get the full cascade.

### Restaurant Creation (Low Impact)

Kitchen hours copied from supplier_terms at create time. Resolution now checks entity-level terms first.

### Employer Program Service (High Impact)

- **CRUD:** `create_program()` accepts optional `institution_entity_id`. NULL = institution defaults. Set = entity override.
- **Benefit calculator:** Resolves effective program for employee by `employer_entity_id` → three-tier cascade.
- **Routes:** `POST /employer/program` optionally accepts `institution_entity_id`.

### Employer Enrollment Service (High Impact)

- **Domain-gated signup:** `_check_employer_domain()` changes from querying `employer_domain` table to querying `institution_entity_info WHERE email_domain = %s`. Returns `institution_id` + `institution_entity_id`.
- **Employee assignment:** Sets `user_info.employer_entity_id` (not `employer_id`).
- **Benefit plans endpoint:** Resolves program via employee's `employer_entity_id`.
- **Bulk enrollment:** Entity-aware — each employee's benefit rate from their entity's program.

### Employer Billing Service (High Impact)

- **Cron:** Iterates entities with active employer programs (not institutions).
- **Currency:** From `institution_entity_info.currency_metadata_id`.
- **Minimum fee:** Per entity. AR entity in ARS, PE entity in PEN.
- **Stripe:** One per entity (on entity-level program row). Each entity = separate Stripe customer. Employers fund and pay per entity; internal transfers between entities are their concern.
- **Bill:** `employer_bill.institution_entity_id` links to the paying entity.

### Coworker Service (Medium Impact)

Currently filters by `employer_id + employer_address_id`. Becomes `employer_entity_id + employer_address_id`. Same logic, different FK.

### Restaurant Explorer Service (Low Impact)

Coworker offer/request flags: `employer_id` → `employer_entity_id`. Same queries, different column.

### Address Service (Medium Impact)

- Remove `employer_id` handling from address type derivation.
- Employer entity addresses are regular entity addresses. Employee pickup addresses link via `user_info.employer_address_id`.

### Onboarding (Medium Impact)

**Supplier:** Per-market checklist: entity + restaurant in each assigned market.  
**Employer:** Per-market checklist: entity (with `email_domain`) + program + enrolled employee per assigned market.

### Employer Routes Consolidation

**Removed routes** (replaced by entity routes):
- `GET/POST/PUT/DELETE /employers/*` — entity CRUD handles both types
- `POST/GET/DELETE /employer/domains` — domain is `email_domain` field on entity, managed via entity CRUD

**Updated routes:**
- `PUT /users/me/employer` → `PUT /users/me/employer-entity` — assigns `employer_entity_id` + `employer_address_id`
- `POST/GET/PUT /employer/program` — gains optional `institution_entity_id` for entity-level overrides
- `GET /employer/billing` — bills grouped by entity (shows entity name, market, currency)

### Enriched Endpoints (Low Impact)

- `institution_market` surfaces as `market_ids` JSON array on enriched institution responses
- Entity enriched responses include `email_domain` field (null unless set)
- User enriched responses: `employer_entity_id` + `employer_entity_name` replace `employer_id` + `employer_name`

---

## Migration Strategy

**Approach:** Full DB tear-down and rebuild via `build_kitchen_db.sh`. No incremental migrations. No client impact — API contracts evolve (new fields, deprecated fields removed), B2B and B2C clients updated in coordination.

### Phase 1: Schema Foundation
1. Drop `market_id` from `core.institution_info`
2. Add `core.institution_market` junction table
3. Add `email_domain VARCHAR(255) NULL` to `ops.institution_entity_info` with partial unique index
4. Add `institution_entity_id` (nullable) to `billing.supplier_terms`, new composite UNIQUE
5. Add `institution_entity_id` (nullable) to `core.employer_benefits_program`, new composite UNIQUE
6. Add `institution_entity_id` to `billing.employer_bill`
7. Replace `employer_id` with `employer_entity_id` on `core.user_info`
8. Drop `employer_id` from `core.address_info` (and `audit.address_history`)
9. Drop `core.employer_info` table + `audit.employer_history`
10. Drop `core.employer_domain` table
11. Add i18n labels for `customer_other` address type (en/es/pt)
12. Update all `audit.*_history` tables and `trigger.sql`
13. Update `seed/reference_data.sql`

### Phase 2: DTOs, Schemas, Services
1. Remove `EmployerDTO`, `EmployerDomainDTO` from `app/dto/models.py`
2. Add `email_domain` to entity DTO, `employer_entity_id` to user DTO
3. Remove `EmployerCreateSchema`, `EmployerUpdateSchema`, `EmployerResponseSchema`, `EmployerEnrichedResponseSchema`, `EmployerSearchSchema`, `AssignEmployerRequest` from schemas
4. Add `employer_entity_id` field to user schemas, `email_domain` to entity schemas
5. Remove `employer_service` from `crud_service.py`
6. Remove `app/routes/employer.py` (full CRUD)
7. Remove employer domain routes from `app/routes/employer_program.py`
8. Update `entity_service.py` — remove `create_employer_with_address()`, `get_enriched_employers()`, `get_enriched_employer_by_id()`
9. Update `address_service.py` — remove `employer_id` handling, remove `customer_employer` auto-derivation (lines 61-76), address type is now user-selected
10. Update `coworker_service.py` — `employer_id` → `employer_entity_id`
11. Update `restaurant_explorer_service.py` — `employer_id` → `employer_entity_id`
12. Update `user_signup_service.py` — `_check_employer_domain()` queries entity table `email_domain` instead of domain table
13. Update `app/routes/user.py` — `PUT /users/me/employer` → `PUT /users/me/employer-entity`

### Phase 3: Three-Tier Resolution + Billing
1. Extract shared resolution pattern
2. Update `supplier_terms_resolution.py` — entity → institution → market cascade
3. Create employer program resolution (same pattern)
4. Update `program_service.py` — CRUD with optional entity scoping
5. Update `billing_service.py` (employer) — per-entity bills, currency from entity
6. Update `enrollment_service.py` — entity-aware domain signup, benefit resolution
7. Update `benefit-plans` endpoint — resolve per `employer_entity_id`
8. Update employer billing cron — iterate entities with active programs

### Phase 4: Institution Market Management + Onboarding
1. Update institution composite create to insert `institution_market` rows
2. Add routes: manage assigned markets per institution
3. Validate entity creation against `institution_market`
4. Validate `user_market_assignment` against `institution_market`
5. Update enriched institution responses — `market_ids` JSON array
6. Update onboarding — per-market checklist for both supplier and employer
7. Employer entity creation flow (onboarding step, manual for now)
8. B2B UI: market selector, entity/program views (requirements from B2B agents)

---

## Setbacks / Risks

### employer_info Removal Scope

This is a significant refactor touching many files:

| Area | Files affected |
|------|---------------|
| Schema | `schema.sql`, `trigger.sql`, `index.sql`, `reference_data.sql` |
| DTOs | `models.py` — remove EmployerDTO, EmployerDomainDTO; update UserDTO |
| Schemas | `consolidated_schemas.py` — remove 6+ employer schemas; update user schemas |
| Routes | Remove `employer.py`; update `employer_program.py`, `user.py` |
| Services | `entity_service.py`, `address_service.py`, `coworker_service.py`, `restaurant_explorer_service.py`, `user_signup_service.py`, `onboarding_service.py`, `route_factory.py`, `crud_service.py` |
| Tests | `conftest.py`, employer-related test fixtures |

**Risk:** This is a lot of surface area in one pass. Mitigation: DB rebuild means no migration risk; all changes land together in a clean state. Existing employer data must be converted to entities during seed/fixture setup.

### Three-Tier Cascade Complexity
- Every service resolving supplier_terms or employer_program must understand the cascade.
- "Which row is effective?" harder to debug. Mitigation: resolution service logs which tier it resolved from.
- UI must show "inherited" vs "overridden" — B2B platform agents must design this.

### Employer Entity Adoption
- Employers didn't have entities before. Onboarding flow gets one more step (create entity before configuring program).
- Manual entity setup initially. Composite create / one-off onboarding form can come later.

### Scoping Validation
- `institution_market` is the permission boundary. Bugs = entities in wrong markets.
- `user_market_assignment` must validate against `institution_market`. Bugs = data leakage.
- Removing a market from `institution_market` when entities exist → must block (RESTRICT semantics).

### Billing Complexity
- **Employer bills per entity:** N bills per cycle (one per entity/currency).
- **Minimum fee per entity:** Independent per entity.
- **Stripe per entity:** Employer sets up payment per country.
- **Consolidated reporting:** Cross-currency totals require conversion (defer to reporting layer).

### Query Path Changes
- Queries using `institution_info.market_id` now need `institution_market` JOIN.
- Single-market institutions: one extra JOIN, same result.
- `is_primary` on junction provides quick default market.

### Testing Surface
- Every service touching terms/program needs multinational test cases.
- Three-tier resolution needs unit tests for all combinations.
- Employer entity flow is entirely new — Postman collections needed.
- Coworker matching with new FK needs regression testing.

### Not All Institutions Need This
- Most will operate in one country with one entity.
- Three-tier cascade is invisible to them — one institution-level row, no entity overrides, one `institution_market` row.
- Complexity is structural, not per-user.

---

## What This Approach Gets Right

1. **Normalized model** — suppliers and employers share the same `institution_info` + `institution_entity_info` pattern. No more divergent paths.
2. **Entity as the country boundary** — tax IDs, currencies, payout, billing, domains all live on entity for both institution types.
3. **Three-tier cascade** — sensible defaults at institution level, override only when needed. Single-market institutions configure once.
4. **Controlled expansion** — `institution_market` junction prevents uncontrolled entity creation. Admin assigns markets explicitly.
5. **Domain simplification** — `email_domain` column on entity replaces a whole table + CRUD routes + DTO + schema. Available to all entity types for future SSO.
6. **B2C unaffected** — JWT `market_id` is for customer vianda scoping, orthogonal to institution structure.
7. **Language via primary market** — B2B users get language from their primary market assignment. Future: market picker switches language.
8. **Backward compatible** — single-market institutions behave exactly like today (one junction row, one entity, no overrides).

---

## Resolved Decisions

| Question | Decision |
|----------|----------|
| `employer_info` fate | **Remove entirely.** Employer identity is `institution_info` (type=employer) + entity per country. |
| `employer_domain` table | **Remove.** Replaced by `email_domain` column on `institution_entity_info`. Available to all entity types (employers for enrollment, suppliers for future SSO). |
| Entity type indicator | **Derived from institution.** No `entity_type` column on entity — inherit from `institution_info.institution_type`. Avoids out-of-sync risk. |
| `employer_address_id` on user_info | **Kept.** Employee's pickup/work address. Users can pick any address as their work address (including client sites). The address itself stays; only `address_info.employer_id` column is dropped. |
| Address type derivation | **User-selected.** `customer_employer` ("Work") is no longer auto-derived. Users choose Home / Work / Other when creating an address. `customer_other` i18n labels to be added. |
| Employer entity enriched display | **One endpoint, nullable fields.** Enriched entity endpoint serves both types. `email_domain` is nullable — NULL for supplier entities (until SSO). Client filters display by institution type if needed. |
| Employer entity auto-creation | **Manual** for now. Composite create / onboarding form later. |
| Stripe per entity | **Yes.** One Stripe customer per entity. Employers fund and pay per entity; internal transfers between entities are their concern. |
| Benefit cap currency | **From entity.** `institution_entity_info.currency_metadata_id`. No explicit currency on program. |
| Cross-market employee transfers | **Manual process.** Re-enroll under new entity's program. |
| Customer institution | **Out of scope.** Vianda Customers stays special (no entities, B2C market per user). |
| Dashboard UX | **Defer to B2B agents** for requirements. |
| B2B language | **Primary market determines language.** `institution_market.is_primary` → `market_info.language`. |

---

## Open Questions

_(None remaining — all resolved. See Resolved Decisions below.)_

---

## Estimated Scope

| Area | Effort | Notes |
|------|--------|-------|
| Schema changes | Large | Drop 3 tables, add junction + columns, update triggers/indexes/seeds |
| DTO + schema cleanup | Medium | Remove employer DTOs/schemas, update user + entity DTOs/schemas |
| employer_info removal (services) | Large | Touch 10+ services, remove routes, update coworker/explorer |
| employer_domain → `email_domain` column | Small | Query changes in signup + enrollment, remove domain routes |
| Address type changes | Small | Remove auto-derivation, add `customer_other` i18n labels |
| Three-tier resolution | Medium | Shared pattern, supplier_terms + employer_program |
| Employer billing per entity | Medium | Cron, currency, Stripe per entity |
| Institution market management | Medium | Junction routes, validation, enriched responses |
| Onboarding updates | Medium | Per-market checklist for both types |
| Scoping / auth | Small | Market filter on enriched, JWT primary market |
| B2B UI (vianda-platform) | Large | Market selector, entity views, cascade UI — requirements from B2B agents |
| Postman test updates | Large | Multi-market scenarios, employer entity flow, coworker regression |

**Total:** Multi-sprint initiative. Phase 1 (schema) is a clean DB rebuild. Phase 2 (DTOs/services) is the heaviest code change due to `employer_info` removal. Phase 3 (resolution + billing) is the critical business logic. Phase 4 (market management + onboarding) is feature enablement. Supplier and employer work are now tightly coupled (shared entity model) — they proceed together, not in parallel.

---

## Documentation Updates

After implementation, the following documentation must be updated before sharing with frontend agents for integration planning.

### `CLAUDE_ARCHITECTURE.md` — Sections to Update

| Section | Changes |
|---------|---------|
| **Directory Structure** | Remove `employer.py` from routes listing. Add `institution_market` to schema description. Note `email_domain` on entity. |
| **Route Registration Flow** | Remove employer CRUD from route list. Update composite-create pattern to include employer entity creation. Note `institution_market` management routes. |
| **Data Flow** | No change (same request → service → DB flow). |
| **Key Entry Points** | Remove `employer.py` entry. Update `employer_program.py` description (domain routes removed). |
| **Route Categories** | Remove `/employers/*` routes. Add `/institutions/{id}/markets` management routes. |
| **Scoping** | Document market-filter behavior (`?market_id=` on enriched endpoints). Note `institution_market` as entity creation permission boundary. |
| **Employer Benefits Program** | Major rewrite. Document: three-tier cascade (entity → institution → market), `email_domain` on entity replaces `employer_domain` table, `employer_entity_id` on user_info replaces `employer_id`, `employer_bill` keyed by entity, Stripe per entity. Remove references to `employer_info` table. |
| **Supplier Invoice Compliance** | Update supplier_terms resolution chain to three-tier: `entity_supplier_terms → institution_supplier_terms → market_payout_aggregator → hardcoded`. |
| **Supplier Onboarding Status** | Note per-market checklist for both supplier and employer. |
| **Country / City / Currency Data Layer** | Note `institution_info.market_id` replaced by `institution_market` junction. Market resolution path changes for queries that used `institution_info.market_id`. |
| **New section: Multinational Institutions** | Add a section summarizing: `institution_market` junction, three-tier cascade pattern, entity as country boundary for both types, `email_domain` on entity. Reference this plan doc for full details. |

### B2B Client Docs — Impacted Files

**Must rewrite (core employer/institution changes):**

| File | Changes |
|------|---------|
| `b2b_client/API_CLIENT_EMPLOYER_ASSIGNMENT.md` | **Full rewrite.** `employer_info` gone. Employer assignment is now `PUT /users/me/employer-entity` with `employer_entity_id`. Employer search/create routes removed — entities serve both types. Document entity-based employer lookup. |
| `b2b_client/API_CLIENT_INSTITUTIONS.md` | **Major update.** `market_id` on institution replaced by `institution_market` junction. Document `market_ids` JSON array on enriched response. Document `POST/DELETE /institutions/{id}/markets` for market assignment. Entity creation gated by assigned markets. |
| `b2b_client/API_CLIENT_ONBOARDING_STATUS.md` | **Update.** Per-market checklist for both supplier and employer. Employer checklist: entity (with `email_domain`) + program + enrolled employee per market. |
| `b2b_client/ONBOARDING_STATUS_DELIVERY_RESPONSE.md` | **Update.** Onboarding response structure changes for per-market checklist. |
| `b2b_client/API_CLIENT_EMPLOYER_ADDRESSES_CITIES.md` | **Major update.** Employer address protection logic changes — `employer_id` gone from `address_info`. Address type is user-selected (Home/Work/Other). Employee pickup address via `user_info.employer_address_id` unchanged. |

**Must update (entity/market/terms changes):**

| File | Changes |
|------|---------|
| `b2b_client/API_CLIENT_SUPPLIER_TERMS.md` | Document three-tier cascade. Entity-level override rows. Resolution: entity → institution → market. |
| `b2b_client/API_CLIENT_SUPPLIER_PAYOUT.md` | Entity enriched response gains `email_domain` field. Entity creation now available for employer institutions too. |
| `b2b_client/API_CLIENT_PAYOUT_HISTORY.md` | Institution enriched response gains `market_ids` array. Payout still entity-scoped (no change to payout logic). |
| `b2b_client/API_CLIENT_MARKETS.md` | Markets are now assigned to institutions via junction. Document `institution_market` relationship. Market is no longer a column on institution. |
| `b2b_client/API_CLIENT_ROLE_FIELD_ACCESS.md` | Update address type access rules — `customer_employer` is user-selected, not auto-derived. |

**Review for indirect impact:**

| File | Why |
|------|-----|
| `b2b_client/API_CLIENT_SUPPLIER_INVOICES.md` | Invoice workflow references entity — confirm no breakage. |
| `b2b_client/API_CLIENT_NATIONAL_HOLIDAYS.md` | Country-scoped — confirm market resolution path still works. |
| `b2b_client/TIMEZONE_AUTO_DEDUCTION_UI_GUIDE.md` | Address model changes — confirm timezone derivation unaffected. |
| `b2b_client/DISCRETIONARY_REQUEST_FORM_GUIDE.md` | Institution/entity scoping — confirm no breakage. |

### B2C Client Docs — Impacted Files

| File | Changes |
|------|---------|
| `b2c_client/EMPLOYER_MANAGEMENT_B2C.md` | **Full rewrite.** Employer search/create removed. `PUT /users/me/employer-entity` replaces `PUT /users/me/employer`. Document entity-based employer lookup for B2C app. |
| `b2c_client/API_CLIENT_EMPLOYER_ADDRESSES_CITIES.md` | N/A (file is in b2b_client, not b2c — listed above). |
| `b2c_client/EMPLOYER_ADDRESS_SCOPING_FEEDBACK.md` | **Update.** Coworker scoping uses `employer_entity_id` instead of `employer_id`. Same behavior, different FK. |
| `b2c_client/MARKET_CITY_COUNTRY.md` | **Review.** B2C market selection unchanged (JWT `market_id` for customers stays). Confirm no references to `institution_info.market_id`. |

### Shared Client Docs — Impacted Files

| File | Changes |
|------|---------|
| `shared_client/MARKET_AND_SCOPE_GUIDELINE.md` | **Major update.** Core market behavior doc. Document `institution_market` junction, multi-market institutions, market filter on enriched endpoints. Institution no longer has single `market_id`. |
| `shared_client/ADDRESSES_API_CLIENT.md` | **Update.** Address type is user-selected for B2C (Home/Work/Other). `employer_id` dropped from `address_info`. Document `customer_other` as new user-facing option. |
| `shared_client/USER_MODEL_FOR_CLIENTS.md` | **Update.** `employer_id` → `employer_entity_id` on user model. `employer_name` derived from entity. Market assignment via `institution_market` for B2B users. |
| `shared_client/CREDIT_AND_CURRENCY_CLIENT.md` | **Review.** Currency now derived from entity, not institution market. Confirm client impact. |
| `shared_client/PLANS_FILTER_CLIENT_INTEGRATION.md` | **Review.** Plan filtering by market — confirm market resolution path. |
| `shared_client/COUNTRY_CODE_API_CONTRACT.md` | **Review.** Country codes unchanged, but market lookup path changes. |

### New Docs to Create

| File | Purpose | Audience |
|------|---------|----------|
| `b2b_client/API_CLIENT_INSTITUTION_MARKETS.md` | `institution_market` junction CRUD: assign/remove markets, enriched `market_ids`, validation rules | B2B agent |
| `b2b_client/API_CLIENT_EMPLOYER_ENTITY_ONBOARDING.md` | Employer entity creation flow, `email_domain` registration, benefits program setup per entity | B2B agent |
| `b2b_client/API_CLIENT_THREE_TIER_CASCADE.md` | How supplier_terms and employer_program resolve (entity → institution → market). UI must show inherited vs overridden. | B2B agent |

---

## Postman Collection Updates

### Impacted Collections

| Collection | Impact | Changes |
|------------|--------|---------|
| `000 E2E Vianda Selection` | **High** | Institution setup creates `institution_market` row. Employer path creates entity instead of `employer_info`. `employer_id` → `employer_entity_id` on user fixtures. |
| `002 ADDRESS_AUTOCOMPLETE_AND_VALIDATION` | **Medium** | Address creation with user-selected type (Home/Work/Other). Remove any `employer_id` references on address payloads. |
| `005 TIMEZONE_DEDUCTION_TESTS` | **Low** | Timezone derivation unchanged (from city_metadata). Verify no institution.market_id dependency. |
| `008 ROLE AND FIELD ACCESS` | **Medium** | Address type access rules — `customer_employer` is user-selected. Entity enriched includes `email_domain`. |
| `010 Permissions Testing` | **Medium** | Employer role tests — entity-based setup instead of `employer_info`. `employer_id` → `employer_entity_id`. |
| `011 EMPLOYER_PROGRAM` | **High** | **Major rewrite.** Remove employer domain CRUD requests. Add entity creation for employer. Program CRUD with optional `institution_entity_id`. Three-tier resolution tests. `email_domain` on entity. Bill generation per entity. |
| `012 BILLING_PAYOUT_AND_STRIPE_CONNECT` | **Medium** | Employer bills keyed by entity. Institution enriched gains `market_ids`. Supplier terms three-tier resolution. |
| `013 SUBSCRIPTION_ACTIONS` | **Low** | Benefit plan resolution by `employer_entity_id`. Verify domain-gated signup uses entity `email_domain`. |

### New Collections Needed

| Collection | Purpose |
|------------|---------|
| `017 INSTITUTION_MARKET_MANAGEMENT` | Create institution with multi-market assignment. Add/remove markets. Validate entity creation against assigned markets. Validate `user_market_assignment` against `institution_market`. |
| `018 MULTINATIONAL_INSTITUTION_E2E` | End-to-end: create institution → assign AR + PE markets → create entity per market → configure supplier_terms (institution default + PE entity override) → create restaurant in each → verify three-tier resolution. |
| `019 EMPLOYER_ENTITY_ONBOARDING` | Employer entity flow: create employer institution → assign market → create entity with `email_domain` → configure program (institution default + entity override) → domain-gated signup → verify billing per entity. |

### Integration Tests (`app/tests/`)

| Test File | Impact | Changes |
|-----------|--------|---------|
| `tests/services/test_employer_address_service.py` | **Remove or rewrite.** Tests employer_info-based address assignment. Replace with entity-based tests. |
| `tests/services/test_address_service.py` | **Update.** Remove `employer_id` derivation tests. Add user-selected address type tests. |
| `tests/routes/test_address_routes.py` | **Update.** Address creation with user-selected type. Remove employer_id from payloads. |
| `tests/routes/test_user_routes.py` | **Update.** `employer_id` → `employer_entity_id` in test fixtures and assertions. |
| `tests/services/test_user_profile_service.py` | **Update.** `employer_id` → `employer_entity_id` in employer address test fixtures. |
| `tests/database/test_qr_code_restaurant_activation.py` | **Review.** May reference institution.market_id in setup. |
| `tests/routes/test_admin_cuisines.py` | **Review.** May use institution setup that needs `institution_market`. |
| `tests/routes/test_cities.py` | **Review.** City/market resolution — verify no `institution_info.market_id` dependency. |
| `tests/routes/test_leads.py` | **Low.** Leads are public, no institution dependency. |
| `tests/conftest.py` | **Update.** Shared fixtures: institution creation must include `institution_market` row. Employer fixtures create entity instead of `employer_info`. |

### New Test Files Needed

| Test File | Purpose |
|-----------|---------|
| `tests/services/test_three_tier_resolution.py` | Unit tests for entity → institution → market cascade. All field combinations: entity set/null, institution set/null, market default, hardcoded. Both supplier_terms and employer_program. |
| `tests/services/test_institution_market.py` | Junction CRUD. Validation: entity creation blocked for unassigned market. User market assignment validated against institution markets. |
| `tests/services/test_email_domain_enrollment.py` | Domain-gated signup via `email_domain` on entity. Correct entity resolution. Cross-entity domain uniqueness. |
