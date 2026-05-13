# Supplier Terms — Roadmap

**Status**: Implemented
**Last Updated**: 2026-04-05
**Purpose**: Extract supplier-specific negotiation terms from `core.institution_info` into a dedicated `billing.supplier_terms` table, consolidating no-show discount, payment frequency, invoicing stringency, and future deal terms into a single supplier-scoped configuration surface.

---

## 1. Context and motivation

### 1.1 Problem (resolved)

`no_show_discount` lived on `core.institution_info` — a general-purpose table shared by all institution types. This created schema noise (CHECK constraint, route-level stripping for non-Suppliers), left no home for other supplier deal terms, and scattered invoice compliance settings across `market_payout_aggregator`, `institution_entity_info`, and `institution_info`.

### 1.2 Design principle

Follow the same pattern as `core.employer_benefits_program`: a dedicated table keyed by `institution_id` that holds all program-specific configuration for a single institution type. This keeps `institution_info` general-purpose and groups related terms together.

### 1.3 What goes in `supplier_terms`

Terms that are negotiated per-supplier institution as part of a commercial agreement:

| Term | Column | Description |
|------|--------|-------------|
| No-show discount | `no_show_discount` | Percentage (0-100) deducted from credit when customer does not collect. Existing behavior, relocated. |
| Payment frequency | `payment_frequency` | How often the supplier is paid. Default: `'daily'`. Override: `'weekly'`, `'biweekly'`, `'monthly'`. |
| Invoice hold days | `invoice_hold_days` | Max days of uninvoiced bills before payouts are held. Default: 30. Relocates from `institution_entity_info.invoice_hold_override_days`. |
| Invoice required | `require_invoice` | Whether this supplier must provide invoices. Default: inherits from market. Allows per-supplier override of market-level `require_invoice`. |

**Future candidates** (not in Phase 1, but the table is designed to accommodate them):
- Commission rate (platform fee percentage)
- Minimum payout threshold
- Payout hold period (days after bill before eligible for payout)
- Preferred payout method override
- Contract start/end dates

---

## 2. Data model

### 2.1 New table: `billing.supplier_terms`

One row per Supplier institution. Created when the institution is created or when terms are first configured.

```sql
CREATE TYPE payment_frequency_enum AS ENUM ('daily', 'weekly', 'biweekly', 'monthly');

CREATE TABLE IF NOT EXISTS billing.supplier_terms (
    supplier_terms_id       UUID        PRIMARY KEY DEFAULT uuidv7(),
    institution_id          UUID        NOT NULL UNIQUE,
    -- Pricing
    no_show_discount        INTEGER     NOT NULL DEFAULT 0 CHECK (no_show_discount >= 0 AND no_show_discount <= 100),
    -- Payment schedule
    payment_frequency       payment_frequency_enum NOT NULL DEFAULT 'daily'::payment_frequency_enum,
    -- Invoice compliance (per-supplier overrides of market defaults)
    require_invoice         BOOLEAN     NULL,       -- NULL = inherit from market_payout_aggregator; TRUE/FALSE = override
    invoice_hold_days       INTEGER     NULL CHECK (invoice_hold_days IS NULL OR invoice_hold_days > 0),
                                                    -- NULL = inherit from market_payout_aggregator.max_unmatched_bill_days
    -- Audit
    is_archived             BOOLEAN     NOT NULL DEFAULT FALSE,
    status                  status_enum NOT NULL DEFAULT 'Active'::status_enum,
    created_date            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by              UUID        NULL,
    modified_by             UUID        NOT NULL,
    modified_date           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (institution_id) REFERENCES core.institution_info(institution_id) ON DELETE RESTRICT,
    FOREIGN KEY (modified_by) REFERENCES core.user_info(user_id) ON DELETE RESTRICT
);
```

### 2.2 Audit table: `audit.supplier_terms_history`

Standard history table mirroring `billing.supplier_terms`.

```sql
CREATE TABLE IF NOT EXISTS audit.supplier_terms_history (
    event_id                UUID        PRIMARY KEY DEFAULT uuidv7(),
    supplier_terms_id       UUID        NOT NULL,
    institution_id          UUID        NOT NULL,
    no_show_discount        INTEGER     NOT NULL,
    payment_frequency       payment_frequency_enum NOT NULL,
    require_invoice         BOOLEAN     NULL,
    invoice_hold_days       INTEGER     NULL,
    is_archived             BOOLEAN     NOT NULL,
    status                  status_enum NOT NULL,
    created_date            TIMESTAMPTZ NOT NULL,
    created_by              UUID        NULL,
    modified_by             UUID        NOT NULL,
    modified_date           TIMESTAMPTZ NOT NULL,
    is_current              BOOLEAN     DEFAULT TRUE,
    valid_until             TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
    FOREIGN KEY (supplier_terms_id) REFERENCES billing.supplier_terms(supplier_terms_id) ON DELETE RESTRICT
);
```

### 2.3 Resolution order for invoice compliance settings

Two-tier resolution (most specific wins):

1. **`billing.supplier_terms`** (per-institution): `require_invoice`, `invoice_hold_days` — if non-NULL, use these
2. **`billing.market_payout_aggregator`** (per-market): `require_invoice`, `max_unmatched_bill_days` — market-wide defaults

---

## 3. What was implemented

Single-phase, clean cut. No backward compatibility — old columns removed in the same pass.

**Schema:**
- Added `payment_frequency_enum`, `billing.supplier_terms`, `audit.supplier_terms_history` + trigger
- Dropped `institution_info.no_show_discount`, `chk_institution_no_show_discount`, `institution_entity_info.invoice_hold_override_days`
- Removed those columns from corresponding audit/history tables and triggers

**Application:**
- `SupplierTermsDTO`, `SupplierTermsCreateSchema`, `SupplierTermsUpdateSchema`, `SupplierTermsResponseSchema` with `PaymentFrequency` enum validation
- `app/routes/supplier_terms.py` — GET/PUT with institution scoping (`_resolve_supplier_institution`)
- `app/security/field_policies.py` — `ensure_can_edit_supplier_terms` (Internal Manager/Admin/Super Admin)
- Removed all `no_show_discount` logic from institution create/update in `route_factory.py`

**Pipeline wiring:**
- `no_show_discount` → vianda enriched queries JOIN `supplier_terms`; promotion service reads from `supplier_terms`
- `payment_frequency` → `_is_supplier_payout_due()` in `institution_billing.py` gates bill creation (settlements accumulate daily; bills created only when due)
- `require_invoice` + `invoice_hold_days` → `_check_invoice_compliance()` in `institution_billing.py` gates payout execution (checks for unmatched bills older than threshold)
- Effective value resolution → `app/services/billing/supplier_terms_resolution.py` (shared by API route and billing pipeline)

---

## 4. API endpoints

All under `/api/v1/`. Scoped by institution — Supplier Admin sees own, Internal sees all.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/supplier-terms/{institution_id}` | Supplier Admin (own) / Internal | Get terms for institution |
| `PUT` | `/supplier-terms/{institution_id}` | Internal Admin / Super Admin | Create or update terms |
| `GET` | `/supplier-terms` | Internal only | List all supplier terms (admin view) |

**Note**: `no_show_discount` continues to appear in vianda/transaction response schemas — the field name stays the same, but the source changes from `institution_info` JOIN to `supplier_terms` JOIN.

---

## 5. B2B agent guidance (vianda-platform)

### What changes for the B2B UI

The vianda-platform B2B React application needs to surface supplier terms management for Internal users and read-only display for Supplier Admins.

### Where to add it

Supplier terms configuration fits in the existing **Institution Detail** or **Entity Management** area of the B2B platform. Specifically:

1. **Institution Detail page** (Internal view): Add a "Supplier Terms" tab/section that appears only for Supplier-type institutions. This section shows and allows editing of:
   - No-show discount (percentage slider or input, 0-100)
   - Payment frequency (dropdown: Daily, Weekly, Biweekly, Monthly)
   - Invoice required (tri-state: Inherit from market / Yes / No)
   - Invoice hold days (number input; placeholder shows market default when blank)

2. **Supplier Dashboard** (Supplier Admin view): Read-only display of their terms. The Supplier sees what was agreed but cannot change it.

3. **Institution Create flow**: When creating a Supplier institution, the B2B wizard should include a "Terms" step. `no_show_discount` is required (currently validated at institution create — moving to supplier terms create). Other fields have sensible defaults.

### API contract

```
GET  /api/v1/supplier-terms/{institution_id}
Response: {
  "supplier_terms_id": "uuid",
  "institution_id": "uuid",
  "no_show_discount": 15,
  "payment_frequency": "daily",
  "require_invoice": null,        // null = inherit from market
  "invoice_hold_days": null,      // null = inherit from market
  "effective_require_invoice": true,   // resolved value (computed)
  "effective_invoice_hold_days": 30,   // resolved value (computed)
  "is_archived": false,
  "status": "Active"
}

PUT  /api/v1/supplier-terms/{institution_id}
Body: {
  "no_show_discount": 15,
  "payment_frequency": "weekly",
  "require_invoice": true,
  "invoice_hold_days": 45
}
```

The `effective_*` fields in the GET response are computed by the backend (supplier override > market default). The UI should display these as the "active" values and show the raw fields as "configured" values when they differ from the effective ones.

### Notes for B2B agent

- **Remove**: `no_show_discount` field from Institution Create and Institution Edit forms — this field no longer exists on the institution payload
- **Add**: Supplier Terms section/tab on Institution Detail (Supplier type only)
- **Keep**: `no_show_discount` in vianda and transaction response display (field name unchanged, source changes server-side)
- **Breaking change**: Institution create for Suppliers no longer accepts `no_show_discount`. The B2B UI must call `PUT /supplier-terms/{institution_id}` after creating the institution, or the create flow should be a two-step wizard (create institution, then configure terms)

### Relevant B2B docs

- Institution management UI: check `docs/api/AGENT_INDEX.md` for institution endpoints
- Invoice compliance UI: see `SUPPLIER_BILLING_COMPLIANCE_ROADMAP.md` Section 3 (Invoice Registration Flow)

---

## 6. Relationship to existing roadmaps

| Roadmap | Relationship |
|---------|-------------|
| `SUPPLIER_BILLING_COMPLIANCE_ROADMAP.md` | Invoice compliance settings (`require_invoice`, `invoice_hold_days`) move from market/entity level to supplier_terms. Payout gate logic references supplier_terms first. |
| `PAYOUT_DRILL_DOWN_VIEW_ROADMAP.md` | Drill-down views should show supplier terms (payment frequency, no-show discount) in context. |
| `SUPPLIER_SUCCESS_MANAGEMENT_ROADMAP.md` | Onboarding status can check if supplier_terms exist as part of completeness scoring. |

---

## 7. Files modified

| Layer | File | What changed |
|-------|------|-------------|
| Schema | `app/db/schema.sql` | Added `payment_frequency_enum`, `billing.supplier_terms`, `audit.supplier_terms_history`. Dropped `no_show_discount` from `institution_info`/history. Dropped `invoice_hold_override_days` from `institution_entity_info`/history. |
| Triggers | `app/db/trigger.sql` | Added `supplier_terms_history_trigger_func`. Removed `no_show_discount` from institution trigger, `invoice_hold_override_days` from entity trigger. |
| Seed | `app/db/seed.sql` | Removed `no_show_discount` from institution INSERTs |
| Enum | `app/config/enums/payment_frequency.py` (new) | `PaymentFrequency(str, Enum)` — daily, weekly, biweekly, monthly |
| DTO | `app/dto/models.py` | Added `SupplierTermsDTO`. Removed `no_show_discount` from `InstitutionDTO`, `invoice_hold_override_days` from `InstitutionEntityDTO`. |
| Schemas | `app/schemas/consolidated_schemas.py` | Added supplier terms schemas with `PaymentFrequency` enum validation. Removed old fields from institution/entity schemas. |
| Routes | `app/routes/supplier_terms.py` (new) | GET/PUT endpoints with institution scoping and effective value resolution |
| Registration | `application.py` | Registered supplier_terms router |
| Resolution | `app/services/billing/supplier_terms_resolution.py` (new) | `resolve_effective_invoice_config()`, `get_supplier_payment_frequency()` — shared by route and billing pipeline |
| Billing | `app/services/billing/institution_billing.py` | Added `_is_supplier_payout_due()` (frequency gate), `_check_invoice_compliance()` (invoice gate) |
| Service | `app/services/vianda_selection_promotion_service.py` | Reads `no_show_discount` from `supplier_terms` |
| Service | `app/services/entity_service.py` | Vianda queries JOIN `supplier_terms`; removed `invoice_hold_override_days` from entity queries |
| Service | `app/services/route_factory.py` | Removed all `no_show_discount` stripping/clearing logic |
| Security | `app/security/field_policies.py` | Replaced `ensure_can_edit_institution_no_show_discount` with `ensure_can_edit_supplier_terms` |
| Tests | `app/tests/routes/test_institution_no_show_discount.py` | Deleted |
| Tests | `app/tests/security/test_field_policies.py` | Updated for `ensure_can_edit_supplier_terms` |
| Tests | `app/tests/database/test_integration.py` | Removed `no_show_discount` from institution INSERTs |
| Tests | `app/tests/services/test_kitchen_start_promotion.py` | Mock reads from `supplier_terms` instead of institution |
