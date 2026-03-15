# Address Subpremise (Floor / Unit) – Store Data Without Splitting Address IDs

**Last Updated**: 2026-03-09  
**Purpose**: Roadmap for storing floor and apartment_unit data while preserving building-level grouping for coworker scoping. Today we omit these fields for employer addresses to avoid creating separate `address_id`s per floor/unit.

---

## Executive Summary

**Current behavior**: For **Customer Employer** addresses, the backend omits `floor` and `apartment_unit` at create/update so that users in the same building share one `address_id`. Coworker scoping (e.g. "Offer to pick up") matches on `employer_id` + `employer_address_id` — if we stored floor/unit on the address, two users on different floors would need different addresses and would not see each other as coworkers.

**Goal**: Keep building-level grouping (one `address_id` per building) but **store** floor and unit data for display and pickup instructions (e.g. "I'm on floor 5, unit 5A").

**Solution**: Introduce a separate **address subpremise** table that links `(address_id, user_id)` to `floor` and `apartment_unit`. The address remains shared; floor/unit is per-user at that address. This applies to any shared-address scenario (today: employer; future: multi-tenant home if needed).

---

## Current State

- **Schema**: `address_info` has `floor` and `apartment_unit` columns.
- **Employer addresses**: `address_service.py` and `address_business_service` explicitly set `floor = None` and `apartment_unit = None` when `employer_id` is set (create and update).
- **Coworker scoping**: `user_info.employer_id` + `user_info.employer_address_id`; coworkers must share the same `employer_address_id`.
- **Other address types** (Customer Home, Customer Billing, Restaurant): floor/unit are stored on `address_info` as today.

---

## Proposed Solution: `address_subpremise` Table

### Design

| Column       | Type   | Description |
|--------------|--------|-------------|
| `subpremise_id` | UUID | PK, uuidv7 |
| `address_id`   | UUID | FK → address_info (building-level address) |
| `user_id`      | UUID | FK → user_info (owner of this floor/unit at this address) |
| `floor`        | VARCHAR(50) | Floor (e.g. "5", "Main Floor") or null |
| `apartment_unit` | VARCHAR(20) | Unit (e.g. "5A") or null |
| `created_date`  | TIMESTAMPTZ | |
| `modified_date` | TIMESTAMPTZ | |

**Unique constraint**: `(address_id, user_id)` — at most one subpremise row per user per address.

### Semantics

- **Employer addresses**: Many users can share `address_id` (employer_address_id). Each user has their own `address_subpremise` row with their floor/unit. Coworker scoping stays on `employer_address_id`; floor/unit is display-only.
- **Home / Billing addresses** (1:1 user:address today): One `address_subpremise` row per address, with `user_id` = address creator. Optional migration: move existing `address_info.floor` / `apartment_unit` into `address_subpremise` for consistency.
- **Restaurant / Entity addresses**: Typically no per-user floor/unit; no subpremise row. Could add later if needed (e.g. office within restaurant building).

---

## Migration Strategy

### Phase 1: Add table, keep current behavior

1. Create `address_subpremise` table and migration.
2. Do **not** change employer address create/update logic; continue omitting floor/unit on `address_info`.
3. No API changes yet.

### Phase 2: Accept and store employer floor/unit

1. On employer address create/update, accept `floor` and `apartment_unit` from client.
2. Insert/update `address_subpremise` with `(address_id, user_id, floor, apartment_unit)`; do **not** write to `address_info.floor` / `apartment_unit`.
3. On read (GET address, employer enriched, etc.), JOIN `address_subpremise` and return `floor`/`apartment_unit` when present.
4. Update client docs to show floor/unit fields for employer addresses.

### Phase 3 (optional): Generalize to all address types

1. For Home/Billing: when address has floor/unit, write to `address_subpremise` instead of (or in addition to) `address_info`. Prefer single source of truth in `address_subpremise`; deprecate `address_info.floor` / `apartment_unit` over time.
2. Migration script: for existing addresses with non-null floor/unit, insert `address_subpremise` rows.

---

## API Changes

### Create / Update

- **Employer address**: Accept `floor` and `apartment_unit` in request body. Store in `address_subpremise`, not `address_info`.
- **Other types**: Unchanged initially; can later route floor/unit to subpremise.

### Response

- Enriched address, employer address responses: Include `floor` and `apartment_unit` from `address_subpremise` when a row exists for the current user/context. Fall back to `address_info` for backward compatibility during migration.

---

## Client Impact

| Context | Before | After |
|---------|--------|-------|
| Employer address form | No floor/unit fields | Show floor/unit; send to API |
| Employer address response | `floor: null`, `apartment_unit: null` | Populated when stored |
| Coworker list | Unchanged (same employer_address_id) | Unchanged |
| Home/Billing | floor/unit on address | Unchanged in Phase 2; optionally migrated in Phase 3 |

---

## Implementation Checklist

- [ ] DB migration: create `address_subpremise` table
- [ ] DTO / schema: `AddressSubpremiseDTO`, response schema updates
- [ ] Address service: on employer create, insert subpremise when floor/unit provided
- [ ] Address service: on employer update, upsert subpremise
- [ ] Read paths: JOIN subpremise for employer addresses, return floor/unit
- [ ] Remove omit logic: stop setting `floor`/`apartment_unit` to null for employer in `address_service` and `address_business_service`
- [ ] Client docs: update ADDRESSES_API_CLIENT.md to allow floor/unit for employer
- [ ] (Optional) Phase 3: migrate Home/Billing floor/unit to subpremise; deprecate columns on address_info

---

## Related Docs

- [ADDRESSES_API_CLIENT.md](../api/shared_client/ADDRESSES_API_CLIENT.md) — Current employer floor/unit omission
- [EMPLOYER_MANAGEMENT_B2C.md](../api/b2c_client/EMPLOYER_MANAGEMENT_B2C.md) — Employer address create flow
- [coworker_service.py](../../app/services/coworker_service.py) — Coworker scoping by employer_id + employer_address_id
