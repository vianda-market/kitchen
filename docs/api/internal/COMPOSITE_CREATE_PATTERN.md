# Composite Create Pattern

**Audience:** Backend agents, frontend agents building create forms
**Status:** Implemented (Institutions, Products)

---

## Pattern

When an entity spans multiple tables with different lifecycles (permissions, update cadence, audit scope), the tables stay separate — but the **creation** endpoint accepts optional embedded sub-resource blocks so the client can create everything in one atomic request.

**This is not a blanket API convention.** Most entities are single-table and their creates are already simple. This pattern only applies when a create form needs to write to multiple tables that have separate lifecycles.

- **Composite create**: `POST /{resource}` accepts optional embedded sub-resource blocks. All inserts happen in one DB transaction (`commit=False` chaining, single `db.commit()`). One request, one commit, one success/failure.
- **Updates stay granular**: `PUT`/`PATCH` endpoints remain per-resource. Sub-resources are edited through their own endpoints with their own permissions and audit scope.

Reads are not affected — `GET` responses stay flat. Enriched endpoints already handle joined data where needed.

---

## Implemented Endpoints

### POST /api/v1/institutions (with embedded supplier_terms)

Creates an institution and, for suppliers, atomically creates the associated `supplier_terms` row.

```json
POST /api/v1/institutions
{
  "name": "Cocina del Sur",
  "institution_type": "Supplier",
  "market_id": "uuid",
  "supplier_terms": {
    "no_show_discount": 15,
    "payment_frequency": "weekly",
    "require_invoice": true,
    "invoice_hold_days": 45
  }
}
```

**Behavior:**
- `supplier_terms` is optional. Only valid when `institution_type` is `Supplier` (422 otherwise).
- Every supplier always gets a `supplier_terms` row — with explicit values if the block is provided, or with DB defaults if omitted.
- `supplier_terms: {}` or `supplier_terms: null` → treated as omitted (defaults applied).
- Response: Same `InstitutionResponseSchema` — terms are not embedded on reads.

**Defaults** (from DB column defaults in `billing.supplier_terms`):
| Field | Default |
|---|---|
| `no_show_discount` | `0` |
| `payment_frequency` | `daily` |
| `require_invoice` | `NULL` (inherit from market) |
| `invoice_hold_days` | `NULL` (inherit from market) |

**Thin update stays as-is:** `PUT /api/v1/supplier-terms/{institution_id}` — Internal-only, granular, audit-scoped to billing changes.

### POST /api/v1/products (with embedded ingredient_ids)

Creates a product and atomically assigns its ingredient list.

```json
POST /api/v1/products
{
  "name": "Milanesa napolitana",
  "institution_id": "uuid",
  "...other product fields",
  "ingredient_ids": ["uuid", "uuid", "..."]
}
```

**Behavior:**
- `ingredient_ids` is optional, max 30 items.
- Absent or `null` → no ingredients assigned.
- All ingredient UUIDs validated against `ops.ingredient_catalog` (404 on first missing).
- Image upload stays as a separate `POST /products/{id}/image` call — multipart, not embeddable in JSON.

### PUT /api/v1/products/{product_id} (with embedded ingredient_ids)

Updates a product and optionally full-replaces its ingredient set atomically.

```json
PUT /api/v1/products/{product_id}
{
  "name": "Updated name",
  "ingredient_ids": ["uuid", "uuid"]
}
```

**Behavior:**
- `ingredient_ids` absent → no change to existing ingredients.
- `ingredient_ids: []` → removes all ingredients.
- `ingredient_ids: [...]` → full-replaces the ingredient set.

**Thin update stays as-is:** `POST /api/v1/products/{product_id}/ingredients` — standalone ingredient-only replacement for callers who don't need to touch the product itself.

---

## Implementation Pattern (for future entities)

When a new entity needs composite creation:

1. **Keep the lifecycle split** — separate tables, separate update endpoints, separate permissions.
2. **Add an optional embed block** to the create schema — named after the sub-resource (e.g., `supplier_terms`, `employer_settings`).
3. **Validate the embed block** against the parent entity type — reject with 422 if invalid for the entity type.
4. **Use `commit=False` chaining** — create parent with `service.create(data, db, scope=scope, commit=False)`, create children with `commit=False`, single `db.commit()` at the end. Rollback on any failure.
5. **Don't embed on reads** — keep `GET` responses flat.
6. **Don't touch update endpoints** — thin updates stay granular.

**Key files:**
- Schema definitions: `app/schemas/consolidated_schemas.py`
- Route implementations: `app/services/route_factory.py` (`create_institution_routes`, `create_product_routes`)
- Transaction support: `CRUDService.create()` and `.update()` both accept `commit=False`
- Ingredient service: `app/services/ingredient_service.py` — `set_product_ingredients()` accepts `commit=False`

---

## Forward-Looking: Employer Settings

When employer-specific fields are split from `institution` into their own table, the composite-create pattern must land at the same time. Shape:

```json
POST /api/v1/institutions
{
  "name": "TechCorp",
  "institution_type": "Employer",
  "market_id": "uuid",
  "employer_settings": { "...TBD" }
}
```

Same validation rules: `employer_settings` rejected with 422 if `institution_type != "Employer"`.
