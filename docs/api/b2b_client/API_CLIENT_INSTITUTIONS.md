# Institutions API — Multinational Model

## Breaking Changes
- `market_id` (single UUID) replaced by `market_ids` (array of UUIDs) on all institution endpoints
- `employer_info` table and `/employers/` routes removed — employers use `institution_info` (type=employer) + `institution_entity_info`
- `employer_domain` table removed — `email_domain` is now a column on `institution_entity_info`

## Primary Market

Each institution has one **primary market** and zero or more secondary markets, assigned via the `market_ids` array. The first element (`market_ids[0]`) is always the primary.

The backend stores this in `core.institution_market` with `is_primary = TRUE` for the primary market. All API responses return `market_ids` with the primary first.

### What primary market controls

| Area | Effect |
|---|---|
| **Supplier terms cascade** | Primary market's `market_payout_aggregator` provides default `require_invoice`, `kitchen_open_time`, `kitchen_close_time` when institution-level terms don't override them |
| **Employer billing currency** | Primary market's currency used as fallback when entity has no currency specified |
| **User signup default** | New supplier/employer staff auto-assigned to institution's primary market |
| **Onboarding display** | Primary market name shown in institution onboarding checklist |
| **Payout aggregator** | Primary market's payout config shown in entity Stripe onboarding |
| **API response ordering** | `market_ids` array always returns primary first |

### UI contract for institution create/edit

- **Primary Market**: Required single-select field. Sets `market_ids[0]`.
- **Secondary Markets**: Optional multi-select for additional markets. Appended after primary in `market_ids`.
- On update, if `market_ids` is sent, the backend replaces all market assignments. First element becomes the new primary.
- Changing primary market affects cascade defaults for all entities that don't have institution-level or entity-level overrides.

---

## POST /api/v1/institutions
Create institution with market assignment.

Request:
```json
{
  "name": "Company Name",
  "institution_type": "supplier",  // or "employer"
  "market_ids": ["<primary-market-uuid>", "<secondary-market-uuid>"],  // first is primary
  "supplier_terms": {               // optional, only for supplier type
    "no_show_discount": 0,
    "payment_frequency": "daily"
  }
}
```

Response (201):
```json
{
  "institution_id": "uuid",
  "name": "Company Name",
  "institution_type": "supplier",
  "market_ids": ["<primary-market-uuid>", "<secondary-market-uuid>"],
  "is_archived": false,
  "status": "active",
  "created_date": "...",
  "modified_date": "..."
}
```

## GET /api/v1/institutions
Returns array. Each institution has `market_ids` array (primary first).

## PUT /api/v1/institutions/{id}
Send `market_ids` to replace assigned markets (first becomes primary). Omit to leave unchanged.

---

## Institution Entity (per-country legal entity)

Both supplier and employer institutions create entities via `POST /api/v1/institution-entities`.

Each entity belongs to exactly one country/market, determined by its address. An entity can only be created if its address country matches one of the institution's assigned markets.

### POST /api/v1/institution-entities

```json
{
  "institution_id": "uuid",
  "address_id": "uuid",
  "tax_id": "30-12345678-9",
  "name": "Company AR S.A.",
  "email_domain": "company.com"  // optional, for employer enrollment gating or future SSO
}
```

Entity creation validates that the address's country is in the institution's assigned markets.

### GET /api/v1/institution-entities/enriched
List all entities with joined institution, address, and market data. Supports optional `institution_id` query param for filtering.

Response: `InstitutionEntityEnrichedResponseSchema[]`
```json
{
  "institution_entity_id": "uuid",
  "institution_id": "uuid",
  "institution_name": "Company Name",
  "institution_type": "supplier",        // from parent institution
  "currency_metadata_id": "uuid",
  "market_id": "uuid",                   // derived from address country → market
  "market_name": "Argentina",
  "country_code": "AR",
  "address_id": "uuid",
  "address_country_name": "Argentina",
  "address_country_code": "AR",
  "address_province": "Buenos Aires",
  "address_city": "CABA",
  "tax_id": "30-12345678-9",
  "name": "Company AR S.A.",
  "payout_provider_account_id": "acct_xxx",  // null if not onboarded
  "payout_aggregator": "stripe",              // null if not onboarded
  "payout_onboarding_status": "complete",     // null if not started
  "email_domain": "company.com",              // null if not set
  "is_archived": false,
  "status": "active",
  "created_date": "...",
  "modified_by": "uuid",
  "modified_date": "..."
}
```

`institution_type` lets the frontend filter or group entities by type (supplier vs employer) without a separate institutions lookup.

### GET /api/v1/institution-entities/enriched/{entity_id}
Same response shape, single entity by ID.

### Entity Archiving Rules

An entity **cannot be archived** if it has:
1. Active restaurants (`is_archived = FALSE`) — archive restaurants first
2. Active plate pickups (pending/active status) via its restaurants — complete or cancel pickups first

Archiving an entity that still has active dependencies returns **409 Conflict** with a descriptive message listing what must be resolved first.

A restaurant **cannot be archived** if it has pending or active plate pickups.

---

## Employer Flow (replaces /employers/ routes)
1. Create institution (type=employer) with market_ids (first is primary)
2. Create entity with email_domain, tax_id
3. Create benefits program via POST /employer/program
4. Enroll employees

## Key Changes for UI
- Replace any `market_id` field with primary market selector + optional secondary markets multi-select
- `market_ids[0]` is always the primary market — UI should make this explicit
- Remove employer CRUD pages — employers are institutions + entities
- Institution list/detail views show `market_ids` as badges (primary badge distinct)
- Entity creation form includes `email_domain` field
- Entity list views can use `institution_type` from enriched response to filter/group by supplier vs employer
