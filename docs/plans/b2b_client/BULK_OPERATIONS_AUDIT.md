# Bulk Operations Audit

**Document Version**: 1.0  
**Date**: March 2026  
**Purpose**: Identify all entities and workflows where bulk operations would reduce friction, improve performance, or align with backend capabilities. To be reviewed with backend for API planning.

---

## Overview

This audit catalogs existing bulk APIs, current UI integration status, and candidates for new bulk operations across the Vianda platform. Use it to prioritize backend work and frontend integration.

---

## Already Implemented (Backend)

### 1. Plate Kitchen Days

| Attribute | Value |
|-----------|-------|
| **Endpoint** | `POST /api/v1/plate-kitchen-days/` |
| **Pattern** | Array in POST body (`kitchen_days: string[]`) |
| **Access** | Suppliers (institution-scoped), Employees (global) |
| **UI integration** | In progress — Kitchen Days create form will use multi-select (checkbox_group) instead of single-day select. See Bulk Plate Kitchen Days UI plan. |

**Request**:
```json
{
  "plate_id": "uuid",
  "kitchen_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
  "status": "Active"
}
```

---

### 2. National Holidays

| Attribute | Value |
|-----------|-------|
| **Endpoint** | `POST /api/v1/national-holidays/bulk` |
| **Pattern** | Separate bulk endpoint (array of holiday objects) |
| **Access** | Employees only |
| **UI integration** | **Not integrated** — National Holidays page uses single-item `POST /api/v1/national-holidays/` for each holiday. Bulk endpoint exists but UI does not offer bulk create. |

**Request**:
```json
[
  {
    "country_code": "US",
    "holiday_name": "New Year's Day",
    "holiday_date": "2025-01-01",
    "is_recurring": true,
    "recurring_month": 1,
    "recurring_day": 1
  }
]
```

**Recommendation**: Add "Bulk create" or "Import holidays" action to National Holidays page. Allow CSV upload or multi-row form for yearly calendar import.

---

## Candidates for Bulk Operations

### High Priority (Clear Use Case)

| Entity | Use Case | Suggested Pattern | Notes |
|--------|----------|-------------------|-------|
| **Restaurant holidays** | Add multiple holidays per restaurant (e.g. year's closures) | `POST /restaurant-holidays/bulk` or array in body | Multiple holidays per restaurant; currently one-by-one |
| **National holidays** | Import yearly calendar for a country | Backend exists; UI integration needed | See above |

---

### Medium Priority (Common Workflows)

| Entity | Use Case | Suggested Pattern | Notes |
|--------|----------|-------------------|-------|
| **Plates** | Create multiple plates for same product across restaurants (or same restaurant with variants) | `POST /plates/bulk` or `{ plates: [...] }` | Product → Plate setup; reduce N round-trips |
| **Addresses** | Add multiple address types for institution entity (Restaurant, Entity Billing, etc.) | Array in body or compound endpoint | Address form has `address_type` checkbox_group; backend may accept multiple |
| **QR codes** | Generate multiple QR codes for a restaurant (e.g. one per table/zone) | `POST /qr-codes/bulk` with `restaurant_id` + count | Currently one at a time |
| **Credit currencies** | Create multiple credit currencies for a market | `POST /credit-currencies/bulk` | Lower frequency; market setup |

---

### Lower Priority / Edge Cases

| Entity | Use Case | Suggested Pattern | Notes |
|--------|----------|-------------------|-------|
| **Institution entities** | Bulk create entities for an institution (e.g. migration) | `POST /institution-entities/bulk` | Niche; admin/migration scenario |
| **Users** | Bulk invite for an institution | `POST /users/bulk-invite` or similar | Depends on invite flow; security considerations |
| **Discretionary requests** | Bulk approve/reject (e.g. same category, same resolution) | Batch endpoint or `PATCH` with list of IDs | Audit trail per request; may need individual records |
| **Restaurant holidays (recurring)** | Copy holidays from one restaurant to another | `POST /restaurant-holidays/copy` with source + target | Alternative to bulk create |

---

## Evaluation Criteria

Use these when prioritizing bulk operations:

| Criterion | Description |
|-----------|-------------|
| **Atomicity needs** | Must all succeed or all fail? (e.g. restaurant activation requires plates + kitchen days + QR) |
| **Typical batch size** | 2–5 (kitchen days), 5–20 (holidays), 50+ (import)? |
| **Role/permission alignment** | Employee vs Supplier vs Customer; institution scoping |
| **UX impact** | How much friction does one-by-one create today? |
| **Backend complexity** | New endpoint vs extending existing; validation and rollback |
| **Idempotency** | Retry safety; duplicate handling |

---

## API Pattern Summary

From [BULK_API_PATTERN.md](../backend/shared_client/BULK_API_PATTERN.md):

### Pattern 1: Array in POST Body

- Single endpoint accepts array field in body.
- Example: `plate-kitchen-days` with `kitchen_days: ["Monday", ...]`.
- Response: Always array of created records.

### Pattern 2: Separate Bulk Endpoint

- Dedicated `/bulk` or `/batch` endpoint.
- Example: `POST /national-holidays/bulk` with array of holiday objects.
- Response: Array of created records.

### Choosing a Pattern

| Use case | Prefer |
|---------|--------|
| Same entity, multiple values (e.g. days for one plate) | Pattern 1 (array in body) |
| Multiple unrelated records (e.g. holidays for country) | Pattern 2 (separate endpoint) |
| Compound create (e.g. restaurant + plates + QR) | New compound endpoint or wizard with sequential calls |

---

## Error Handling for Partial Success

Current bulk APIs are **fully atomic** — all or nothing. For future bulk operations, consider:

| Scenario | Options |
|----------|---------|
| **All-or-nothing** | Rollback on first failure (current behavior) |
| **Best-effort** | Return created + failed; client retries failures |
| **Idempotency keys** | Client sends keys; backend skips duplicates, returns created/skipped |

**Recommendation**: Keep atomicity for most bulk creates. Document partial success only where batch size is large and retry is expensive (e.g. bulk user invite).

---

## Backend Coordination Checklist

When proposing a new bulk operation:

- [ ] Define request/response schema (array in body vs separate endpoint)
- [ ] Confirm atomicity (rollback on any failure)
- [ ] Error response format (`detail` with clear message; 409 for conflicts)
- [ ] Access control (role, institution scoping)
- [ ] Idempotency or duplicate handling (if applicable)
- [ ] Pagination or limit (max batch size) for large imports

---

## Implementation Status Matrix

| Entity | Backend | UI | Priority |
|--------|---------|-----|----------|
| Plate kitchen days | ✅ | In progress | P0 |
| National holidays | ✅ | ❌ | P1 |
| Restaurant holidays | ❌ | — | P2 |
| Plates | ❌ | — | P2 |
| Addresses | ? | — | P3 |
| QR codes | ❌ | — | P3 |
| Credit currencies | ❌ | — | P4 |
| Institution entities | ❌ | — | P4 |
| Users (bulk invite) | ❌ | — | P4 |
| Discretionary (bulk) | ❌ | — | P5 |

---

*Last Updated: March 2026*
