# Breaking Changes Log

**Last Updated**: 2026-02-10  
**Purpose**: API changes that require frontend coordination. Add entries before merging backend changes.

---

## Format

Each entry should include:

- **Date**: When the change was/will be deployed
- **Change**: What changed
- **Affected endpoints**: List of endpoints
- **Frontend action required**: What kitchen-web / kitchen-mobile must do
- **Backward compatible?**: Yes/No

---

## Current / Upcoming

### Supplier Terms — no_show_discount relocated from institution

**Date**: 2026-04-05
**Change**: `no_show_discount` removed from institution create/update/response schemas. `invoice_hold_override_days` removed from institution entity schemas. Both relocated to new `billing.supplier_terms` table with dedicated endpoints.
**Affected endpoints**:
- `POST /api/v1/institutions/` — no longer accepts `no_show_discount`
- `PUT /api/v1/institutions/{id}` — no longer accepts `no_show_discount`
- `GET /api/v1/institutions/{id}` — no longer returns `no_show_discount`
- `GET /api/v1/institution-entities/enriched/` — no longer returns `invoice_hold_override_days`
- **New**: `GET /api/v1/supplier-terms/{institution_id}`, `PUT /api/v1/supplier-terms/{institution_id}`, `GET /api/v1/supplier-terms`
**Frontend action required**:
- B2B: Remove `no_show_discount` from institution create/edit forms. Add Supplier Terms tab/section on institution detail (Supplier type only). Call `PUT /supplier-terms/{id}` to configure terms after creating a Supplier institution. Re-run TypeScript codegen (`npx openapi-typescript`).
**Backward compatible?**: No
**Migration doc**: `docs/api/b2b_client/SUPPLIER_TERMS_B2B.md`

---

## Deprecations

See [client/README.md](./client/README.md) for deprecated endpoints and migration steps (including `ENDPOINT_DEPRECATION_GUIDE.md`).
