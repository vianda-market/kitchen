# Service Consolidation – Phases 2 & 3 (Pending)

**Purpose:** Track remaining CRUD service consolidation for efficiency and discoverability.  
**Phase 1:** Complete (see `docs/zArchive/roadmap/PHASE_1_COMPLETE_2026-01-30.md`).  
**Status:** Not started. No refactor planned right now; this stays on the roadmap for when you want to continue.

---

## Why this is on the roadmap

- **Efficiency / maintainability:** Same pattern as Phase 1 – methods on service classes, clearer API, better IDE discoverability.
- **Not bug fixes:** App works with current structure; this is optional consolidation.

---

## Phase 2: Restaurant Transaction Service

**Scope:** 4 functions in `app/services/crud_service.py` → add as methods to a restaurant transaction service (same pattern as Phase 1).

| Function | Purpose |
|----------|---------|
| `get_by_plate_selection_id()` | Transaction by plate selection |
| `mark_collected()` | Mark transaction collected |
| `update_final_amount()` | Update transaction amount |
| `update_transaction_arrival_time()` | Update arrival time |

- **Priority:** Medium  
- **Estimated time:** 1–2 hours  
- **Reference:** `docs/zArchive/roadmap/SERVICE_CONSOLIDATION_ANALYSIS.md` (proposed method signatures and notes).

---

## Phase 3: Miscellaneous services (5 methods)

**Scope:** One method per area; add to existing or appropriate service instances in `crud_service.py`.

| Area | Function (approx.) | Service |
|------|--------------------|---------|
| QR Code | `get_by_restaurant_id()` | `qr_code_service` |
| Subscription | `get_by_user_id()` | `subscription_service` |
| Client Bill | `get_by_payment_id()` | `client_bill_service` |
| Credit Currency | `get_by_code()` | `credit_currency_service` |
| Geolocation | `get_by_address_id()` | `geolocation_service` |

- **Priority:** Low  
- **Estimated time:** 1–2 hours  
- **Reference:** `docs/zArchive/roadmap/SERVICE_CONSOLIDATION_ANALYSIS.md`.

---

## Phase 2 + 3 summary

- **Total:** 9 functions/methods to consolidate (Phase 1 already did 14).  
- **Approach:** Same as Phase 1: add methods to CRUDService (or relevant service), add deprecation wrappers, update callers.  
- **When:** At your discretion; no urgency.

---

## Related docs (archived)

- `docs/zArchive/roadmap/PHASE_1_COMPLETE_2026-01-30.md` – Phase 1 summary and pattern  
- `docs/zArchive/roadmap/SERVICE_CONSOLIDATION_ANALYSIS.md` – Full analysis and proposed APIs  
- `docs/zArchive/roadmap/SERVICE_CONSOLIDATION_ROADMAP.md` – Original implementation guide  
- `docs/CODING_GUIDELINES.md` – Service consolidation patterns (active)
