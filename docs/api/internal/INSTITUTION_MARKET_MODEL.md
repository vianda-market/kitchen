# Institution-Market Model

**Audience:** Backend, B2B client (vianda-platform), B2C client (vianda-app)

This doc describes the multinational institution model: how institutions span multiple countries, how the entity layer serves as the country boundary for both supplier and employer institution types, and how configuration cascades from entity down to market defaults.

---

## Overview

An institution can operate across multiple countries under one login. Country-specific concerns (legal entities, currencies, tax IDs, billing, email domains) are scoped per `institution_entity_info` row. The `institution_market` junction controls which markets an institution is allowed to operate in (admin-assigned).

**Key invariant:** `institution_entity_info` is the country boundary for **both** supplier and employer institutions. Employer institutions no longer use a separate `employer_info` table — employer identity is `institution_info` (type=`employer`) + one entity per country.

---

## Data Model

```
institution_info                    multi-market umbrella
  ├── institution_market (junction) ← allowed markets (admin-controlled multi-select)
  ├── user_info                     ← users belong to 1 institution
  │     ├── employer_entity_id?     ← for Customer Comensals: which employer entity
  │     └── employer_address_id     ← which office for pickup (user-selected)
  │
  ├── institution_entity_info       ← legal entity per country — BOTH suppliers AND employers
  │     ├── address_id              ← address has country_code
  │     ├── tax_id, currency        ← billing identity
  │     ├── email_domain?           ← email domain (optional, all entity types)
  │     ├── restaurant?             ← supplier entities only
  │     ├── supplier_terms?         ← entity-level override (optional)
  │     └── employer_benefits_program? ← entity-level override (currency-tied fields)
  │
  ├── supplier_terms                ← institution-level defaults
  ├── employer_benefits_program     ← institution-level defaults (rates, enrollment mode)
  └── employer_bill                 ← keyed by entity (currency-aware)
```

---

## `institution_market` Junction

```sql
CREATE TABLE core.institution_market (
    institution_id UUID NOT NULL REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    market_id      UUID NOT NULL REFERENCES core.market_info(market_id) ON DELETE RESTRICT,
    is_primary     BOOLEAN NOT NULL DEFAULT FALSE,
    created_date   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (institution_id, market_id)
);
CREATE INDEX idx_institution_market_market ON core.institution_market(market_id);
```

- Admin-assigned. An institution can only create entities in assigned markets.
- `is_primary` drives default UX (which market to show first, which language to default to for B2B users).
- Removing a market from the junction when entities exist is blocked (`RESTRICT` semantics).
- Enriched institution responses expose `market_ids` as a JSON array (pattern: `json_agg` in `enriched_service.py`).

---

## Entity as Country Boundary

`institution_entity_info` already had everything needed for multi-country suppliers: `address_id` (with `country_code`), `currency_metadata_id`, `tax_id`, `payout_provider_account_id`. Employer institutions now adopt this same layer.

### `email_domain` column on entity

```sql
ALTER TABLE ops.institution_entity_info ADD COLUMN email_domain VARCHAR(255) NULL;
CREATE UNIQUE INDEX idx_entity_email_domain
    ON ops.institution_entity_info(email_domain)
    WHERE email_domain IS NOT NULL AND is_archived = FALSE;
```

- Replaces the former `core.employer_domain` table.
- One domain per entity (nullable). Multiple domains for one employer = multiple entities.
- Partial unique index ensures domain uniqueness across all active entities.
- **Available to all entity types.** Employer entities use it for enrollment gating. Supplier entities can register a domain for future SSO. The column is type-agnostic.

**SSO note:** `email_domain → entity → institution` is the mapping needed for SAML/OIDC routing. The column being in place means no schema change is required when SSO lands.

### Employer-specific fields on entity

- `institution_entity_id` (nullable) added to `billing.employer_bill` — bills generated per entity per country.
- `employer_entity_id` on `core.user_info` — replaces former `employer_id` (which pointed to the now-removed `employer_info` table).
- Stripe: one Stripe customer per entity (`stripe_customer_id` lives at entity-level on `employer_benefits_program`).

### Removed tables

| Removed | Replaced by |
|---------|-------------|
| `core.employer_info` | `institution_info` (type=`employer`) + `institution_entity_info` per country |
| `core.employer_domain` | `email_domain` column on `institution_entity_info` |
| `audit.employer_history` | `audit.institution_entity_history` |

---

## Three-Tier Cascade

Both `supplier_terms` and `employer_benefits_program` resolve effective values via the same cascade:

```
resolve_effective_value(field, institution_id, entity_id):
    1. Entity-level row  (institution_id + entity_id)      → if field is not NULL, return
    2. Institution-level row (institution_id + entity_id IS NULL) → if field is not NULL, return
    3. Market default (supplier_terms: market_payout_aggregator; employer: N/A)
    4. Hardcoded default
```

**Supplier terms chain:** `entity_supplier_terms → institution_supplier_terms → market_payout_aggregator → hardcoded`

**Employer program chain:** `entity_employer_program → institution_employer_program → hardcoded`

Single-market institutions configure institution-level defaults once and never need entity overrides. The cascade is transparent to them.

### Schema changes enabling three-tier

```sql
-- supplier_terms
ALTER TABLE billing.supplier_terms ADD COLUMN institution_entity_id UUID NULL
    REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT;
ALTER TABLE billing.supplier_terms ADD CONSTRAINT uq_supplier_terms_scope
    UNIQUE (institution_id, institution_entity_id);

-- employer_benefits_program
ALTER TABLE core.employer_benefits_program ADD COLUMN institution_entity_id UUID NULL
    REFERENCES ops.institution_entity_info(institution_entity_id) ON DELETE RESTRICT;
ALTER TABLE core.employer_benefits_program ADD CONSTRAINT uq_employer_program_scope
    UNIQUE (institution_id, institution_entity_id);
```

`institution_entity_id IS NULL` = institution-level default row. `IS NOT NULL` = entity-level override.

### Currency-tied fields on employer program

Currency-tied fields (`benefit_cap`, `minimum_monthly_fee`, `stripe_customer_id`, `stripe_payment_method_id`) exist **only** at entity level — they are meaningless without a currency, and currency is derived from `institution_entity_info.currency_metadata_id`.

---

## Address Type Changes

The former `customer_employer` address type was auto-derived by checking `employer_info` and `address_info.employer_id`. With `employer_info` removed:

- Address type is now **user-selected** for B2C customers: `customer_home` ("Home"), `customer_employer` ("Work"), `customer_other` ("Other").
- `address_info.employer_id` column is dropped.
- `customer_other` i18n labels to add: en: "Other", es: "Otro", pt: "Outro".

---

## JWT and Auth

- **B2C customers:** JWT `market_id` reflects where they order food. Orthogonal to institution structure — unchanged.
- **B2B users:** JWT `market_id` set to the `is_primary` market from `institution_market`. Determines default language for the session.
- `InstitutionScope` (filters by `institution_id`) is unchanged.
- Optional `?market_id=` query filter on enriched endpoints — validated against `institution_market`.

---

## Route Changes

**Removed routes** (replaced by entity routes):
- `GET/POST/PUT/DELETE /employers/*` — entity CRUD handles both institution types
- `POST/GET/DELETE /employer/domains` — domain is `email_domain` field on entity, managed via entity CRUD

**Updated routes:**
- `PUT /users/me/employer` → `PUT /users/me/employer-entity` — assigns `employer_entity_id` + `employer_address_id`
- `POST/GET/PUT /employer/program` — gains optional `institution_entity_id` for entity-level overrides
- `GET /employer/billing` — bills grouped by entity (shows entity name, market, currency)
- `POST /institutions/{id}/markets` + `DELETE /institutions/{id}/markets/{market_id}` — assign/remove markets

---

## Scoping and Validation Invariants

- An entity can only be created in a market that is assigned to its institution via `institution_market`.
- `user_market_assignment` must validate against `institution_market` — prevents data leakage across countries.
- `institution_market` removal is blocked (`RESTRICT`) when entities exist in that market.
- Enriched institution responses include `market_ids` JSON array.
- Entity enriched responses include `email_domain` field (null unless set).
- User enriched responses: `employer_entity_id` + `employer_entity_name` replace former `employer_id` + `employer_name`.

---

## Single-Market Backward Compatibility

Most institutions operate in one country with one entity. The model is fully backward compatible:

- One `institution_market` row (was one `institution_info.market_id` column value)
- One `institution_entity_info` row
- One institution-level `supplier_terms` or `employer_benefits_program` row — no entity overrides needed
- Three-tier cascade returns institution-level row; behavior is identical to the former two-tier model

Complexity is structural, not per-user.

---

## Related Docs

- `docs/api/b2b_client/API_CLIENT_INSTITUTIONS.md` — B2B client guide: `market_ids` array, enriched response shape, institution market management routes
- `docs/api/b2b_client/API_CLIENT_THREE_TIER_CASCADE.md` — How supplier_terms and employer_program resolve; UI "inherited vs overridden" display
- `docs/api/b2b_client/API_CLIENT_EMPLOYER_ADDRESSES_CITIES.md` — Address type changes (employer_id removal, user-selected Work/Home/Other)
- `docs/api/b2c_client/EMPLOYER_MANAGEMENT_B2C.md` — Assign employer entity from B2C app (`employer_entity_id`, user-selected address types)
- `docs/api/shared_client/MARKET_AND_SCOPE_GUIDELINE.md` — Market behavior, institution scoping, subscription rules
