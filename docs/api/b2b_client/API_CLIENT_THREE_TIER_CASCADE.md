# Three-Tier Configuration Cascade

Both supplier terms and employer benefits programs support entity-level overrides.

## Resolution Order
```
Entity override → Institution default → Primary market default → Hardcoded fallback
```

- **Primary market**: The institution's first market in `market_ids` (stored as `is_primary = TRUE` in `institution_market`). See `API_CLIENT_INSTITUTIONS.md` for what primary market controls.
- **Hardcoded fallback**: Safety net only — `kitchen_open_time = 09:00`, `kitchen_close_time = 13:30`, `require_invoice = false`, `invoice_hold_days = 30`. Only triggers if `market_payout_aggregator` row is missing for the primary market.

## How It Works

### Supplier Terms (`billing.supplier_terms`)
- Institution-level row: `institution_entity_id IS NULL` — default for all entities
- Entity-level row: `institution_entity_id = <uuid>` — overrides specific fields for one entity
- Unique constraint: `(institution_id, institution_entity_id)`
- Fields: no_show_discount, payment_frequency, kitchen_open_time, kitchen_close_time, require_invoice, invoice_hold_days
- NULL on any field = inherit from next tier

### Employer Benefits Program (`core.employer_benefits_program`)
- Same pattern: institution-level defaults + entity-level overrides
- Unique constraint: `(institution_id, institution_entity_id)`
- Currency-tied fields (benefit_cap, minimum_monthly_fee, stripe_customer_id) only exist at entity level
- Percentage/boolean fields (benefit_rate, price_discount, enrollment_mode) default from institution level

---

## Entity-Level API Contract

Entity-level behavior is accessed via an optional `institution_entity_id` query parameter on existing endpoints. When omitted, behavior is unchanged (institution-level). When provided, targets entity-level overrides.

### Supplier Terms

#### GET /api/v1/supplier-terms/{institution_id}?institution_entity_id={entity_id}
Returns supplier terms for the specified scope. Omit `institution_entity_id` for institution-level defaults.

Response: `SupplierTermsResponseSchema`
```json
{
  "supplier_terms_id": "uuid",
  "institution_id": "uuid",
  "institution_entity_id": "uuid | null",
  "no_show_discount": 5,
  "payment_frequency": "weekly",
  "kitchen_open_time": "08:00",
  "kitchen_close_time": "14:00",
  "require_invoice": true,
  "invoice_hold_days": 15,
  "effective_kitchen_open_time": "08:00",
  "effective_kitchen_close_time": "14:00",
  "effective_require_invoice": true,
  "effective_invoice_hold_days": 15,
  "is_archived": false,
  "status": "active"
}
```

- `institution_entity_id`: null for institution-level, UUID for entity-level
- `kitchen_open_time`, `kitchen_close_time`, `require_invoice`, `invoice_hold_days`: null = inherited from next tier
- `effective_*` fields: resolved from full cascade (entity → institution → market → hardcoded)

Auth: Internal sees all; Supplier sees own institution only.

#### PUT /api/v1/supplier-terms/{institution_id}?institution_entity_id={entity_id}
Upsert supplier terms. Omit `institution_entity_id` for institution-level, provide for entity override.

Request body: `SupplierTermsCreateSchema`
```json
{
  "no_show_discount": 5,
  "payment_frequency": "weekly",
  "kitchen_open_time": "08:00",
  "kitchen_close_time": "14:00",
  "require_invoice": true,
  "invoice_hold_days": 15
}
```

Auth: Internal Manager/Admin/Super Admin only.

#### GET /api/v1/supplier-terms
List all supplier terms (institution-level + entity-level overrides across all institutions). Internal only. Each row includes `institution_entity_id` to distinguish scope.

#### DELETE /api/v1/supplier-terms/{institution_id}?institution_entity_id={entity_id}
Archive entity-level override. `institution_entity_id` is **required** (cannot delete institution-level defaults). Entity reverts to institution defaults.

Response: 204 No Content. Auth: Internal Manager/Admin/Super Admin only.

---

### Employer Program

#### POST /api/v1/employer/program
Create a benefits program. Send `institution_entity_id` in body for entity-level override, omit for institution-level default.

```json
{
  "institution_id": "uuid",
  "institution_entity_id": "uuid",
  "benefit_rate": 80,
  "benefit_cap": 5000.00,
  "benefit_cap_period": "monthly",
  "price_discount": 10,
  "minimum_monthly_fee": 200.00,
  "billing_cycle": "monthly",
  "billing_day": 1,
  "enrollment_mode": "domain_gated",
  "allow_early_renewal": false
}
```

Returns 409 if a program already exists for the (institution_id, entity_id) scope.

#### GET /api/v1/employer/program?institution_entity_id={entity_id}
Returns program for the specified scope. Omit `institution_entity_id` for institution-level default.

Query param `institution_id` required for Internal users; Employer users use their JWT institution.

Response: `ProgramResponseSchema` — includes `institution_entity_id` (null for institution-level).

#### GET /api/v1/employer/programs
List all programs for an institution (institution-level default + all entity overrides).

Response: `ProgramResponseSchema[]`

#### PUT /api/v1/employer/program?institution_entity_id={entity_id}
Update program for the specified scope.

Request body: `ProgramUpdateSchema` (all fields optional).

#### DELETE /api/v1/employer/program?institution_entity_id={entity_id}
Archive entity-level override. `institution_entity_id` is **required**. Entity reverts to institution defaults.

Response: 204 No Content. Auth: Internal only (`get_employee_user`).

---

## UI Implications
- Show "Inherited" badge on fields that come from the institution level
- Show "Overridden" badge on fields set at entity level
- Entity-level config form should pre-fill from institution defaults
- Currency-tied fields (benefit_cap, minimum_monthly_fee) should show the entity's currency (from entity → currency_metadata)
- For supplier terms, NULL field values mean "inherit" — UI should render these as placeholder text showing the inherited value with a visual indicator

## Implementation Status

| Component | Institution-Level | Entity-Level |
|---|---|---|
| Supplier Terms DB schema | Done | Done |
| Supplier Terms resolution service | Done | Done |
| Supplier Terms DTO | Done | Done |
| Supplier Terms routes | Done | Done (GET/PUT with query param, DELETE) |
| Employer Program DB schema | Done | Done |
| Employer Program service | Done | Done |
| Employer Program DTO | Done | Done |
| Employer Program routes | Done | Done (POST body, GET/PUT/DELETE with query param, GET list) |
