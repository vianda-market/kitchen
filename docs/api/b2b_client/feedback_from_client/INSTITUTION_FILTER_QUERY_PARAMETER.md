# Institution Filter – Centralized Query Parameter for List Endpoints

**Date**: February 2026  
**Context**: B2B client needs a consistent way to scope dropdowns and lists by institution. Employees must choose an institution first; Suppliers use their JWT institution. This document requests backend support for an optional `institution_id` query parameter on relevant list endpoints so the same pattern can be reused across forms (Institution Bank Account, Addresses, Restaurant, and future flows).  
**Status**: Request for backend implementation (no frontend code changes in this document).

---

## Situation

### Role-based institution context

- **Employees**: Can act on behalf of any institution. When creating records that belong to an institution (e.g. institution bank account, address, restaurant), the UI must let them **choose the institution first**. Downstream dropdowns (institution entities, addresses, users, etc.) should then be limited to that institution.
- **Suppliers (and Customers where applicable)**: Are scoped to a single institution (JWT `institution_id`). The UI does **not** show an institution picker; the backend (or client) uses the user’s institution. Downstream dropdowns are already effectively scoped by that same institution.

So we need:

1. **UI**: For Employees, show an “Institution” field first; for Suppliers/Customers, keep it hidden and set from the user’s context.
2. **Data**: Once we have an institution context (either chosen or from JWT), all dependent lists (entities, addresses, etc.) should be filterable by that institution in a **consistent, reusable** way.

### Current gap

Today, list endpoints (e.g. `GET /api/v1/institution-entities/enriched/`, `GET /api/v1/addresses/enriched/`) return data according to existing auth/scoping only. There is no standard way to pass “only return items for this institution” when the client already has an institution (e.g. selected by an Employee). The B2B client can filter client-side using `institution_id` on each item, but:

- Employees may see very large lists (all entities, all addresses) before filtering.
- Every form would implement the same “load all, filter in UI” logic.
- A single, backend-supported filter is easier to maintain and scales better.

We want a **centralized** contract: list endpoints that are institution-scoped accept an optional **`institution_id`** query parameter and return only items for that institution, so the B2B client (and other clients) can reuse the same pattern everywhere.

---

## Use cases (existing and future)

| Form / flow              | Institution source                    | Needs filtered lists by institution     |
|--------------------------|----------------------------------------|-----------------------------------------|
| **Institution Bank Account** | Employee: picker; Supplier: JWT        | Institution entities, addresses         |
| **Address**              | Employee: picker; Supplier: JWT        | Users (same institution)               |
| **Restaurant**           | Supplier: JWT (or Employee: picker)    | Institution entities, addresses         |
| **Institution Entity**   | Employee: picker; Supplier: JWT        | Addresses                               |
| Future forms             | Same pattern                           | Any institution-scoped list              |

All of these benefit from the same backend contract: **optional `institution_id` on list (and, where applicable, enriched) endpoints** for institution-scoped resources.

---

## Plan for UI (no code in this doc)

The B2B client will adopt a single pattern for “institution first, then institution-scoped dropdowns”:

1. **Institution field**
   - **Employees**: Show “Institution” as the first field; value is stored in form state (e.g. `formData.institution_id`).
   - **Suppliers (and Customers where applicable)**: Do **not** show the field; set institution from the user’s JWT (e.g. `initialData.institution_id = user.institutionId`) and pass `hiddenFields: ['institution_id']` so the field is not rendered. Same pattern as the existing **Addresses** create modal.

2. **Dependent dropdowns**
   - Any dropdown that is institution-scoped (institution entities, addresses, users, etc.) will be filtered by the current institution context:
     - Either use the optional **`institution_id`** query parameter when calling the list endpoint (preferred), or
     - If the backend does not support the parameter yet, filter client-side using `institution_id` on each item (current fallback).
   - Fields that depend on institution will be disabled or show “Select institution first” until an institution is set (for Employees) or until initialData is applied (for Suppliers).

3. **Submit payload**
   - The institution value is used only for UX and filtering. Create/update payloads do not need to change: the backend can continue to derive institution from the main entity (e.g. `institution_entity_id` for bank accounts). If the client sends `institution_id` in the body, the backend may ignore it or use it for validation only.

4. **First concrete flow: Institution Bank Account**
   - **Step 1**: Institution (visible for Employees only; hidden for Suppliers with value from JWT).
   - **Step 2**: Institution entity → list filtered by selected institution (`institution_id`).
   - **Step 3**: Address → list filtered by selected institution (`institution_id`).
   - Then: account holder name, bank name, account type, routing number, account number. No change to the existing create payload contract; backend derives institution from `institution_entity_id` if needed.

This mirrors the existing **Addresses** modal (institution picker for Employees, hidden for non-Employees, user dropdown filtered by institution) and will be reused for Restaurant, Institution Entity, and future forms.

---

## Backend requirements (centralized institution filter)

To support this in a **centralized, reusable** way, we ask for the following.

### 1. Optional query parameter: `institution_id`

- **Name**: `institution_id`
- **Type**: UUID (optional)
- **Semantics**: When present, the list (or search) endpoint returns **only** items whose `institution_id` matches the given value. When absent, behavior is unchanged (existing auth and scoping apply).
- **Auth/scoping**: Existing rules still apply. For example:
  - Employees may pass any institution they are allowed to access.
  - Suppliers may only pass their own `institution_id` (or the backend may ignore the parameter and apply supplier scope as today). Same for Customers if they can call these endpoints.

### 2. Endpoints to extend (recommended)

Apply the optional `institution_id` filter to the list (and, where applicable, enriched) endpoints for resources that are tied to an institution:

| Endpoint(s) | Purpose |
|-------------|--------|
| `GET /api/v1/institution-entities/` and `GET /api/v1/institution-entities/enriched/` | Filter entities by institution so “Institution entity” dropdown only shows entities for the selected institution (e.g. Institution Bank Account, Restaurant, future forms). |
| `GET /api/v1/addresses/` and `GET /api/v1/addresses/enriched/` | Filter addresses by institution so “Address” dropdown only shows addresses for the selected institution. (Note: `GET /api/v1/addresses/search/` already supports `institution_id`; having the same on the list/enriched endpoints keeps the contract consistent.) |

Other institution-scoped list endpoints (e.g. users, restaurants) can follow the same pattern later if needed.

### 3. Response shape

- No change to response schema. Each item already includes `institution_id` where applicable (e.g. enriched institution entities and addresses). Filtering is done by restricting which items are returned.

### 4. Create/patch payloads

- **No change** to create or update payloads for institution bank accounts (or other entities). The client may send `institution_id` in form state for UI purposes only; the backend should **not** require it on the body and can derive institution from the main resource (e.g. `institution_entity_id`). Backend may optionally validate that a client-sent `institution_id` matches the derived institution.

---

## Summary

| Item | Request |
|------|--------|
| **Contract** | Optional query parameter `institution_id` (UUID) on institution-scoped list/enriched endpoints. |
| **Behavior** | When `institution_id` is present, return only items for that institution; when absent, keep current behavior. |
| **Endpoints** | At least: `institution-entities`, `institution-entities/enriched`, `addresses`, `addresses/enriched`. Same pattern can be applied to other institution-scoped lists later. |
| **Reuse** | One consistent mechanism for all B2B forms that need “institution first, then filtered dropdowns” (Institution Bank Account, Addresses, Restaurant, Institution Entity, future). |
| **Payload** | No new required fields on create/update; backend continues to derive institution where appropriate. |

---

## References

- **Addresses modal**: Institution field visible only for Employees; `hiddenFields` and `initialData` for Suppliers; user dropdown filtered by `institution_id`. See B2B client Addresses page and address form config.
- **Restaurant form**: Already uses `institution_id` in form state and filters address dropdown by it (client-side using `institution_id` on enriched addresses). Would benefit from server-side `institution_id` on addresses and institution-entities.
- **RESTAURANT_ADDRESS_PICKER_AND_ENRICHED.md**: Addresses enriched and search endpoints; notes that addresses search already supports `institution_id`. This document asks for the same filter on list/enriched for consistency and reuse.
