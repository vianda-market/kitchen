# Institution Scoping & RBAC Design

**Updated:** 2025-11-11  
**Audience:** Backend & Vianda Platform engineers  
**Related Roadmap:** Plate Pickup / QR Code → “Institution Scoping & RBAC Enforcement”  
**Inputs:** Endpoint audit (`docs/investigations/institution_scoping_audit.md`)

---

## 1. Problem Statement

Non-employee roles (e.g., `Supplier Admin`, `Restaurant Admin`) must only see and mutate data tied to their institution(s). Today, all list/detail endpoints return global datasets, and mutations accept arbitrary IDs without verifying ownership. We need a consistent enforcement strategy that works for:

- Users & personnel
- Institution entities, addresses, restaurants
- Catalog items (products, plates, QR codes)
- Downstream objects (institution bank accounts, bills, payment attempts, balance info)

Employees (`role_type = Employee` or `Super Admin`) should retain global visibility.

---

## 2. Design Goals

1. **Server-side enforcement:** Do not rely on Vianda Platform/front-end to filter. Backend must enforce scoping for every request.
2. **Consistency:** One shared mechanism for CRUD routes and bespoke services to avoid drift.
3. **Opt-in Exceptions:** Employees/super admins stay global; other roles auto-scope.
4. **Minimal churn:** Reuse existing services (CRUDService, handle_* helpers) through extension points.
5. **Auditability:** Easy to test/log when scoping is applied and when access is denied.

---

## 3. Architecture Overview

### 3.1 Key Concepts

- **Institution Scope**  
  Derived from JWT claim `institution_id` (string UUID). Represents “primary” institution for the authenticated user.

- **Institution-Aware Entities**  
  Tables with direct or indirect `institution_id` relationship:
  - `user_info` (via `institution_id`)
  - `institution_entity_info`
  - `address_info` (institution-owned addresses)
  - `restaurant_info` (via `institution_id` & `institution_entity_id`)
  - `product_info` (via `institution_id`)
  - `plate_info` (via `restaurant_id`)
  - `qr_code` (via `restaurant_id`)
  - `institution_bank_account`, `institution_bill_info`, `institution_payment_attempt`, `restaurant_balance_info`, etc.

- **Global Roles**  
  `role_type` in `["Employee", "Super Admin"]` → no scoping filter.

### 3.2 Scoping Helpers (Backend)

Introduce a new module `app/security/institution_scope.py`:

```python
from typing import Optional
from uuid import UUID

class InstitutionScope:
    def __init__(self, institution_id: Optional[UUID], role_type: str):
        self.institution_id = institution_id
        self.role_type = role_type

    @property
    def is_global(self) -> bool:
        return self.role_type in {"Employee", "Super Admin"}

    def enforce(self, resource_institution_id: UUID):
        if self.is_global:
            return
        if not self.institution_id or resource_institution_id != self.institution_id:
            raise HTTPException(status_code=403, detail="Forbidden: institution mismatch")
```

Helper functions:

- `get_institution_scope(current_user: dict) -> InstitutionScope`
- `append_institution_clause(query: str, scope: InstitutionScope, column: str) -> (query, params)`

### 3.3 CRUDService Extensions

Add optional scoping hooks:

- `CRUDService` constructor accepts `institution_column: Optional[str] = None`.
- `get_all`, `get_by_id`, `create`, `update`, `soft_delete` accept `scope: InstitutionScope | None`.
- If scope is not provided → legacy behaviour (global).
- If scope provided and not global:
  - `get_all`: add `WHERE {institution_column} = %s`.
  - `get_by_id`: fetch record; verify column matches.
  - `create`: before insert, set institution field (if not provided) or verify equality.
  - `update/delete`: fetch record first, call `scope.enforce`.

For entities linked indirectly (e.g., `plate_info` via `restaurant_id`):

- Provide overrides in specific services (e.g., `PlateService`) to join against `restaurant_info` for scoping.
- Alternatively, expose `institution_join` metadata to `CRUDService`.

### 3.4 Route/Service Integration

1. **Route Factory**  
   - Update `create_crud_routes` to compute scope with `current_user`.
   - Pass scope to CRUD operations.
   - Provide config flags:
     ```python
     RouteConfig(
         prefix="/products",
         tags=["Products"],
         entity_name="product",
         entity_name_plural="products",
         institution_scoped=True,
         institution_field="institution_id"
     )
     ```
   - For custom routes (e.g., product image upload), enforce scope by fetching record then calling `scope.enforce(record.institution_id)`.

2. **Custom Routers**  
   - `restaurant.py`, `qr_code.py`, `plate_selection`, etc. need to:
     - Build scope.
     - Use scoped service methods (e.g., `restaurant_service.get_scoped(scope, db)`).

3. **Services using raw SQL**  
   - e.g., `entity_service.get_pending_bills_by_institution`: adjust to accept `scope`.
   - Ensure queries include `WHERE institution_entity_id = %s` when `scope` not global.

### 3.5 Open Questions

- **Multi-Institution Users:** Currently JWT only carries single `institution_id`. If we support multi-institution access (e.g., consultants), we will need claims array and `scope.allows(resource_id)`.
- **Historical Data Access:** History tables (`*_history`) might remain global for auditors; confirm requirements.
- **Seed/Admin Accounts:** Ensure seeds for restaurant admins align with scoping rules (their `institution_id` must match).

---

## 4. Implementation Plan

### Phase 1 — Infrastructure (Backend)
1. Add `InstitutionScope` helper module.
2. Extend CRUDService with optional scoping params.
3. Update route factory to pass scope automatically when `config.institution_scoped` is true.
4. Update DTOs/services for indirect relationships (plates, QR codes) with scoped variants.
5. Add Pydantic validator to ensure create schemas align with `scope.institution_id` (when non-global).

### Phase 2 — Endpoint Roll-out
1. Convert admin CRUD routes (`crud_routes.py`) to scoped behaviour for: products, plates, institution entities, addresses, restaurants, QR codes.
2. Update bespoke routes:
   - `/restaurants/...` (list/detail/create/update/delete)
   - `/qr-codes/...`
   - `/users/...` (non-employees should only see users from same institution; employees stay global).
3. Handle dependent modules (bank accounts, bills, payment attempts, balance info).

### Phase 3 — Tests & Tooling
1. Unit tests for `InstitutionScope`.
2. CRUD service tests verifying filters are applied.
3. API tests (pytest + Postman) covering:
   - Non-employee fetches own data.
   - Non-employee blocked from other institutions.
   - Employee sees everything.
4. Update Postman collections to include institution-scoped assertions.

### Phase 4 — Frontend Coordination (Vianda Platform)
1. Vianda Platform auth context continues to expose `institutionId`.
2. Ensure non-employee requests no longer attempt to fetch global lists (even though backend now protects).
3. Handle 403 gracefully with helpful messaging (“Switch institution” or “Access denied”).

---

## 5. Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Performance hit from added joins | Use indexes, push filters to SQL rather than Python post-filtering. |
| Legacy scripts/postman flows expect global data | Update collections & docs as part of roll-out. |
| Missing indirect relationships (e.g., plates → restaurant → institution) | Explicitly document dependencies; add tests for each. |
| Employee role definition changes | Keep role-type constants centralised. |

---

## 6. References

- Endpoint audit: `docs/investigations/institution_scoping_audit.md`
- Auth payload structure: `app/auth/routes.py` (JWT fields)
- CRUD services: `app/services/crud_service.py`
- Route factory: `app/services/route_factory.py`
- Roadmap entry: `docs/PLATE_PICKUP_QR_CODE_ROADMAP.md`

---

## 7. Next Actions

1. Implement infrastructure changes (Phase 1).  
2. Schedule endpoint-by-endpoint roll-out (Phase 2) starting with highest-risk resources (users, restaurants, products).  
3. Update roadmap checklist with design completion (done) and link to this doc.  
4. Coordinate with Vianda Platform repo before enabling strict enforcement to avoid UI regressions.  
5. After implementation, re-run audit to confirm no global leakage remains.

