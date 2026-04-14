# Backward Compatibility Cleanup Tracker

**Purpose:** Track backward-compatible shims, deprecated endpoints, and transitional behaviors that exist to avoid breaking current clients. Each entry should be removed once all consumers have migrated.

---

## How to use this file

When introducing a backward-compatible behavior that should eventually be removed, add an entry below with:
- **What**: The shim / deprecated behavior
- **Why it exists**: Which client(s) depend on it
- **Remove when**: The condition that makes it safe to remove
- **Added**: Date

Review this list periodically and clean up entries whose removal conditions are met.

---

## Active Items

### 1. Separate `PUT /supplier-terms/{institution_id}` for initial creation

- **What**: The frontend currently calls `POST /institutions` then `PUT /supplier-terms/{id}` as two sequential requests to create a supplier with terms. The composite `POST /institutions` with embedded `supplier_terms` now handles this atomically.
- **Why it exists**: `vianda-platform` ships the two-call flow today and will migrate to the composite create once it's deployed.
- **Remove when**: `vianda-platform` has migrated `Institutions.tsx` to use the composite create. The `PUT` endpoint itself stays (it's the thin-update path for editing terms post-creation) — what gets removed is the frontend's reliance on it during creation.
- **Added**: 2026-04-12

### 2. Separate `POST /products/{id}/ingredients` for initial creation

- **What**: The frontend calls `POST /products` then `POST /products/{id}/ingredients` sequentially. Phase 2 of the composite-create plan will embed `ingredient_ids` in the product create payload.
- **Why it exists**: The composite product create hasn't been implemented yet.
- **Remove when**: Phase 2 lands and `vianda-platform` migrates `Products.tsx` to send `ingredient_ids` inline. The standalone endpoint stays for ingredient-only updates.
- **Added**: 2026-04-12
