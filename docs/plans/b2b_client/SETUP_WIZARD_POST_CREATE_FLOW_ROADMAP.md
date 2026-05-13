# Setup Wizard / Post-Create Flow Roadmap

**Document Version**: 1.0  
**Date**: March 2026  
**Purpose**: Define a reusable setup wizard pattern for entity creation workflows that naturally require follow-up steps. To be reviewed with backend for API and UX alignment.

---

## Overview

Many entity creation flows in the Vianda platform require **dependent follow-up steps** before the entity is fully operational. Today, users must navigate between pages and create records one-by-one. A **setup wizard** pattern would guide users through these steps in a single flow, reducing friction and errors.

This document defines the pattern and lists all workflows where it applies, so frontend and backend can plan a consistent approach rather than one-off post-create modals.

---

## Pattern Definition

### Multi-Step Setup Wizard

A **setup wizard** is a multi-step flow that:

1. Creates a **primary entity** (e.g. restaurant, vianda, institution).
2. Guides the user through **dependent configuration** steps (e.g. add viandas, assign kitchen days, create QR code).
3. Optionally **activates** or **finalizes** the entity when all requirements are met.

### Key Characteristics

- **Linear or branching steps**: Each step may depend on the previous (e.g. "Add viandas" requires restaurant_id from step 1).
- **"Skip for now" vs "Continue"**: Optional steps allow users to defer configuration and return later.
- **Progress indicator**: Breadcrumb or step indicator shows where the user is in the flow.
- **Shared primitives**: Reusable wizard component(s) that can be applied across entities.
- **Atomic vs non-atomic**: Some steps may be atomic (create + configure in one API call); others may be sequential API calls.

### UX Primitives to Consider

| Primitive | Description |
|-----------|-------------|
| Step indicator | "Step 1 of 4" or breadcrumb (e.g. Restaurant → Viandas → Kitchen Days → QR → Activate) |
| "Skip for now" | Allow user to exit wizard and complete setup later from the resource page |
| "Continue" | Proceed to next step; may auto-create if step is optional |
| Back/Edit | Return to a previous step to change values |
| Summary step | Before final activation, show summary of what will be created |

---

## Workflows Where Post-Create Flow Applies

### 1. Restaurant Setup

**Source**: [RESTAURANT_STATUS_AND_VIANDA_KITCHEN_DAYS.md](../backend/shared_client/RESTAURANT_STATUS_AND_VIANDA_KITCHEN_DAYS.md)

**Current flow**: Create restaurant → Navigate to Viandas → Create viandas → Navigate to Kitchen Days → Assign days → Navigate to QR Codes → Create QR → Edit restaurant → Set status Active.

**Proposed wizard steps**:
1. Create restaurant (institution entity, address, name, cuisine).
2. Add viandas (product, price, credit, delivery time) — can add multiple or skip.
3. Assign kitchen days for each vianda (bulk Mon–Fri) — can use bulk API.
4. Create QR code(s) — at least one required for activation.
5. Activate restaurant (PUT status Active) — backend validates viandas + kitchen days + QR.

**Backend coordination**: Activation requires viandas with active vianda_kitchen_days and at least one active QR code. No new API needed; wizard orchestrates existing endpoints.

---

### 2. Vianda Setup

**Source**: [VIANDA_API_CLIENT.md](../backend/shared_client/VIANDA_API_CLIENT.md)

**Current flow**: Create vianda → Navigate to Kitchen Days → Add one day at a time (or use bulk once UI supports it).

**Proposed wizard steps**:
1. Create vianda (product_id, restaurant_id, price, credit, delivery_time_minutes).
2. Assign kitchen days — multi-select (Mon–Fri); bulk `POST /api/v1/vianda-kitchen-days/` with `kitchen_days: [...]`.

**Backend coordination**: Bulk kitchen days API exists. Post-create modal or inline step on Viandas page could offer "Assign kitchen days?" with vianda pre-selected. See the Bulk Vianda Kitchen Days UI plan for current implementation.

---

### 3. Institution Setup

**Current flow**: Create institution → Navigate to Institution Entities → Create entities → Navigate to Addresses → Add addresses.

**Proposed wizard steps**:
1. Create institution (market_id, name, institution_type, no_show_discount).
2. Add institution entity(ies) — tax entity linked to institution.
3. Add address(es) for entity or institution — address type, country, city, etc.

**Backend coordination**: No compound API today; wizard would call endpoints sequentially. Consider if `POST /institutions/` could accept optional `entities` and `addresses` in body for atomic creation.

---

### 4. User Onboarding

**Current flow**: Create user → User receives invite → Navigate to Addresses → Add address (if needed) → Navigate to Payment Methods → Add method → Navigate to Subscriptions → Add subscription.

**Proposed wizard steps**:
1. Create user (role_type, institution_id, username, email, etc.).
2. Add address(es) — for Customer/Comensal, may need home/billing.
3. Add payment method — method_type, is_default.
4. Add subscription — plan_id, balance, renewal_date (if applicable).

**Backend coordination**: User create triggers invite email. Address, payment method, and subscription are separate resources. Wizard could batch creates or offer "Complete profile later" after user create.

---

### 5. Institution Entity Setup

**Current flow**: Create institution entity → Navigate to Addresses → Add address → Navigate to Restaurants → Create restaurant(s).

**Proposed wizard steps**:
1. Create institution entity (institution_id, restaurant_id or address_id).
2. Add address — if entity needs address before restaurant.
3. Add restaurant(s) — link to entity and address.

**Backend coordination**: Entity links to address and/or restaurant. May need address before restaurant create. Sequential APIs; no compound endpoint.

---

### 6. Product → Vianda Setup

**Current flow**: Create product → Navigate to Viandas → Create vianda(s) linking product to restaurant(s).

**Proposed wizard steps**:
1. Create product (institution_id, name, ingredients, dietary).
2. Create vianda(s) — for each restaurant, set price, credit, delivery_time_minutes. Optionally assign kitchen days in same flow.

**Backend coordination**: Viandas require product_id and restaurant_id. Bulk vianda create (multiple restaurants at once) could reduce round-trips. Not implemented today.

---

### 7. Market Setup

**Current flow**: Create market → Navigate to National Holidays → Add holidays one-by-one.

**Proposed wizard steps**:
1. Create market (country, credit_currency_id, timezone).
2. Add national holidays — bulk `POST /api/v1/national-holidays/bulk` for yearly calendar.

**Backend coordination**: National holidays bulk API exists. UI does not yet offer bulk create. See [BULK_OPERATIONS_AUDIT.md](BULK_OPERATIONS_AUDIT.md).

---

### 8. Restaurant Holidays

**Current flow**: Create restaurant → Navigate to Restaurant Holidays → Add holidays one-by-one.

**Proposed wizard steps**:
1. Create restaurant (or select existing).
2. Add restaurant holidays — multiple holidays (e.g. annual closures) in one flow.

**Backend coordination**: No bulk restaurant-holidays API today. Could add `POST /restaurant-holidays/bulk` or array-in-body pattern.

---

## Backend Coordination Notes

### Compound / Wizard Requests

| Approach | Pros | Cons |
|---------|------|------|
| Sequential calls | Uses existing APIs; no backend changes | More round-trips; partial failure handling |
| Compound endpoint (e.g. `POST /restaurants/with-viandas-and-qr`) | Single transaction; atomic | New endpoints; schema complexity |
| Optional nested body (e.g. `restaurant` + `viandas[]` in one POST) | Flexible; one call | Validation complexity; partial success? |

**Recommendation**: Start with sequential calls and shared wizard UX. Propose compound endpoints only where atomicity is critical (e.g. institution + entity + address).

### Idempotency

For wizard steps that may be retried (e.g. network failure, user clicks "Back"), consider:

- Idempotency keys for create operations.
- Safe "update if exists" semantics for optional steps.

---

## Implementation Priority (Suggested)

| Priority | Workflow | Rationale |
|----------|----------|-----------|
| 1 | Vianda setup (post-create kitchen days) | Bulk API exists; small scope |
| 2 | Restaurant setup | Highest friction; many steps |
| 3 | National holidays bulk (Market setup) | Bulk API exists; UI gap |
| 4 | Institution setup | Common onboarding path |
| 5 | User onboarding | Depends on invite flow maturity |
| 6 | Product → Vianda | Medium complexity |
| 7 | Restaurant holidays | Lower frequency |
| 8 | Institution entity setup | Niche |

---

## Next Steps

1. **Frontend**: Implement shared `SetupWizard` component (or stepper pattern) that can be parameterized per workflow.
2. **Backend**: Review compound endpoint needs; confirm idempotency strategy for create operations.
3. **Design**: Define step indicator, "Skip for now", and error recovery UX.
4. **Iterate**: Start with Vianda post-create (kitchen days) as pilot; expand to Restaurant wizard.

---

*Last Updated: March 2026*
