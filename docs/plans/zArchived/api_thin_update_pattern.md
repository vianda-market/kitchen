# Plan: Composite Create Pattern

**Status:** Phase 1 & 2 complete, Phase 3 pending (design constraint only)
**Date:** 2026-04-12
**Source:** `vianda-platform` feedback — `docs/frontend/feedback_for_backend/composite_create_thin_update_pattern.md`

---

## Context

The B2B frontend orchestrates 2-3 sequential writes from a single form to create one logical entity. This pushes atomicity onto the client and creates partial-failure windows with real consequences (e.g., supplier running on default billing terms the user didn't choose, products missing allergen data).

The backend already has the mechanism for multi-step atomic creates — `commit=False` chaining with a single `db.commit()` at the end (used in restaurant balance updates, payment method + address creation). The missing piece is applying this pattern at the route level for entity creation.

---

## Pattern Decision

**Adopt composite create as the convention** for entities that span multiple tables by lifecycle:

- **Composite create**: `POST /{resource}` accepts optional embedded sub-resource blocks. All inserts happen in one DB transaction. One request, one commit, one success/failure.
- **Updates stay granular**: `PUT`/`PATCH` endpoints remain per-resource. Sub-resources are still edited through their own endpoints with their own permissions and audit scope.

This only applies when a create operation spans multiple tables with separate lifecycles. Most entities are single-table and don't need this. The granular endpoints keep working untouched; the composite create is transactional sugar over them.

### Answers to Frontend Open Questions

1. **Transaction scope**: All-or-nothing. Validate everything, then insert everything inside one transaction. If `supplier_terms` validation fails, no institution row is created.
2. **Partial embed**: `"supplier_terms": {}` (empty object) = same as omitting the field. Backend creates terms row with defaults in both cases. Only an object with at least one explicit field triggers non-default creation.
3. **Read side**: No `?include=` param for now. Reads stay granular — existing enriched endpoints already serve the frontend's needs. We can revisit if a concrete use case emerges.
4. **Product image**: Option 1 — keep image as a separate endpoint. Image upload is multipart, potentially large, and its failure mode is narrow and obvious. The frontend should treat it as a deliberate second action, not part of the atomic create.

---

## Rollout Plan

Three independent phases, ordered by value. Each phase is a self-contained deliverable.

### Phase 1: Institution + Supplier Terms (highest priority)

**Why first**: Unblocks the `Institutions.tsx` UX fix. Cleanest case — one optional sub-resource block, clear permission boundary, existing upsert logic to reuse.

#### Schema Changes

None. Both `institution` and `supplier_terms` tables already exist with the right structure.

#### API Contract

```
POST /api/v1/institutions
{
  "name": "Cocina del Sur",
  "institution_type": "Supplier",
  "market_id": "uuid",
  "supplier_terms": {                    // optional; only valid when institution_type == "Supplier"
    "no_show_discount": 15,              // default: 0
    "payment_frequency": "weekly",       // default: "daily"
    "require_invoice": true,             // default: null (inherit from market)
    "invoice_hold_days": 45              // default: null
  }
}
```

- `supplier_terms` present when `institution_type != "Supplier"` → 422
- `supplier_terms` absent or `null` → backend creates terms row with all defaults (every supplier always gets a terms row)
- `supplier_terms: {}` → same as absent — terms row created with defaults

**Response**: Same `InstitutionResponseSchema` as today. The terms are a separate resource for reads — no embedding on the response side.

#### Implementation Steps

1. **Schema layer** (`consolidated_schemas.py`):
   - Add `SupplierTermsEmbedSchema` — same fields as `SupplierTermsCreateSchema` but all optional (every field has a default).
   - Add `supplier_terms: Optional[SupplierTermsEmbedSchema] = None` to `InstitutionCreateSchema`.

2. **Route layer** (`route_factory.py`, institution custom create ~line 1323):
   - Extract `supplier_terms` from payload before passing to `institution_service.create()`.
   - Validate: if `supplier_terms` is not None and `institution_type != "Supplier"`, raise 422.
   - Treat `supplier_terms == {}` (all defaults) as None.
   - Call `institution_service.create(institution_data, db, scope=scope, commit=False)`.
   - If `supplier_terms` provided: call `supplier_terms_service.create(terms_data, db, commit=False)` with the new `institution_id`.
   - If `supplier_terms` not provided but `institution_type == "Supplier"`: call `supplier_terms_service.create(defaults, db, commit=False)` — preserves current behavior where every supplier gets a terms row.
   - Single `db.commit()`.
   - On any failure: `db.rollback()`, raise `HTTPException`.
   - Return institution response (same as today).

3. **No changes to**:
   - `PUT /supplier-terms/{institution_id}` — stays as-is, granular, Internal-only.
   - `GET /institutions/{id}` — no embedding on reads.
   - Institution DTO — no new fields.

#### Existing Code to Reuse

- `commit=False` pattern: already used in `create_with_conservative_balance_update()` (`crud_service.py:2102-2132`) and payment method + address creation (`route_factory.py:1378-1408`).
- Supplier terms defaults: already handled by `SupplierTermsCreateSchema` field defaults.
- Supplier terms enrichment (effective values from market): already in `supplier_terms.py:35-40`.

---

### Phase 2: Product + Ingredients

**Why second**: Ingredients missing from a product has regulatory implications (allergen data). The fix is straightforward — `ingredient_ids` becomes an optional field on the product create/update payload.

#### API Contract

```
POST /api/v1/products
{
  "name": "Milanesa napolitana",
  "institution_id": "uuid",
  ...existing product fields,
  "ingredient_ids": ["uuid", "uuid", ...]   // optional; max 30
}
```

```
PUT /api/v1/products/{product_id}
{
  ...existing update fields,
  "ingredient_ids": ["uuid", "uuid", ...]   // optional; if present, full-replaces ingredient set
}
```

- `ingredient_ids` absent or `null` → no ingredients assigned (create) or no change to existing ingredients (update).
- `ingredient_ids: []` → explicitly removes all ingredients.
- Image upload stays as a separate `POST /products/{id}/image` call (Option 1).

#### Implementation Steps

1. **Schema layer** (`consolidated_schemas.py`):
   - Add `ingredient_ids: Optional[List[UUID]] = None` with `max_length=30` to both `ProductCreateSchema` and `ProductUpdateSchema`.

2. **Route layer** (`route_factory.py`, product custom create ~line 487):
   - Extract `ingredient_ids` from payload before passing to `product_service.create()`.
   - Call `product_service.create(product_data, db, scope=scope, commit=False)`.
   - If `ingredient_ids` provided and non-empty: call `ingredient_service.set_product_ingredients(product_id, ingredient_ids, db, commit=False)`.
   - Single `db.commit()`.
   - Return product response.

3. **Ingredient service** (`ingredient_service.py:250-302`):
   - Refactor `set_product_ingredients()` to accept `commit=False` parameter (currently auto-commits). This is a minor change — move the `db.commit()` behind the `commit` flag.

4. **Update route** (product custom update):
   - Same pattern: extract `ingredient_ids`, update product with `commit=False`, conditionally replace ingredients with `commit=False`, single commit.

5. **No changes to**:
   - `POST /products/{product_id}/ingredients` — stays as-is for callers who want ingredient-only updates.
   - `POST /products/{product_id}/image` — stays as-is.

---

### Phase 3: Employer Institution + Employer Settings (forward-looking)

**Why last**: The employer-settings table doesn't exist yet. This phase is a design constraint, not an implementation task.

#### Design Constraint

When the employer-specific settings split happens (moving employer fields from `institution` to their own table), the composite-create pattern must land at the same time or before. The frontend must never ship a chained-write version of employer creation.

#### Expected Shape

```
POST /api/v1/institutions
{
  "name": "TechCorp",
  "institution_type": "Employer",
  "market_id": "uuid",
  "employer_settings": {               // optional; only valid when institution_type == "Employer"
    ...employer-specific fields TBD
  }
}
```

Same validation rules: `employer_settings` rejected with 422 if `institution_type != "Employer"`. Absent → defaults.

**No implementation work until the employer-settings table is designed.**

---

## Implementation Pattern (Template for Future Cases)

When a new entity needs composite creation:

1. **Keep the lifecycle split** — separate tables, separate update endpoints, separate permissions.
2. **Add an optional embed block** to the create schema — named after the sub-resource (e.g., `supplier_terms`, `employer_settings`).
3. **Validate the embed block** against the parent entity type — reject with 422 if the block doesn't match the entity type.
4. **Use `commit=False` chaining** — create parent, create children, single `db.commit()`.
5. **Don't embed on reads** — keep `GET` responses flat. Enriched endpoints already handle joined data where needed.
6. **Don't touch update endpoints** — thin updates stay granular.

---

## Files to Modify

| Phase | File | Change |
|-------|------|--------|
| 1 | `app/schemas/consolidated_schemas.py` | Add `SupplierTermsEmbedSchema`, extend `InstitutionCreateSchema` |
| 1 | `app/services/route_factory.py` | Refactor institution create to extract + transact supplier_terms |
| 2 | `app/schemas/consolidated_schemas.py` | Add `ingredient_ids` to product create/update schemas |
| 2 | `app/services/route_factory.py` | Refactor product create/update to extract + transact ingredients |
| 2 | `app/services/ingredient_service.py` | Add `commit` param to `set_product_ingredients()` |

## Documentation To Produce After Implementation

- `docs/api/internal/COMPOSITE_CREATE_PATTERN.md` — pattern reference for future entities
- Update `CLAUDE_ARCHITECTURE.md` — note the pattern in the relevant sections
- Notify `vianda-platform` agent with the final schemas once Phase 1 lands
