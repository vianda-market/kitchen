# Supplier Onboarding Status — B2B Client Guide

**Audience**: B2B React frontend agent (vianda-platform)  
**Last Updated**: 2026-04-04  
**Status**: Active — ready for integration

---

## What This Enables

The backend computes a 7-item onboarding checklist for each Supplier institution. The frontend can use this to:

- **Gate sidebar navigation** — disable menu items whose dependencies aren't met
- **Show dashboard progress banner** — "You're 57% through setup — next: add a product"
- **Trigger guided walkthroughs** — when `next_step` changes, prompt the user to complete it
- **Fast page-load gating** via JWT `onboarding_status` claim — no extra API call needed

---

## JWT Claim: `onboarding_status`

Every Supplier/Employer JWT token includes an `onboarding_status` claim:

| Value | Meaning |
|-------|---------|
| `not_started` | No checklist items completed |
| `in_progress` | Some items completed, setup ongoing |
| `complete` | All 7 checklist items done |

**Use for:** Initial page-load gating (e.g., redirect to setup wizard if `not_started`). For detailed progress, call the API endpoint below.

**Refresh:** The claim is recomputed on every login and token refresh. No cache — always reflects current state.

---

## API: Get Onboarding Status

### `GET /api/v1/institutions/{institution_id}/onboarding-status`

**Auth:** Bearer token (any authenticated user). Supplier users can only see their own institution. Internal Admin/Super Admin can see any.

**Scoping:** The backend enforces institution scoping — a Supplier user's request is automatically filtered to their `institution_id` from the JWT. Passing a different institution's ID returns 403.

### Success Response (200)

```json
{
  "institution_id": "550e8400-e29b-41d4-a716-446655440000",
  "institution_type": "Supplier",
  "onboarding_status": "in_progress",
  "completion_percentage": 57,
  "next_step": "product",
  "days_since_creation": 5,
  "days_since_last_activity": 2,
  "last_activity_date": "2026-04-02T14:30:00Z",
  "checklist": {
    "has_active_address": true,
    "has_active_entity_with_payouts": true,
    "has_active_restaurant": true,
    "has_active_product": false,
    "has_active_plate": false,
    "has_active_kitchen_day": false,
    "has_active_qr_code": false
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `institution_id` | UUID | The institution |
| `institution_type` | string | `"Supplier"` or `"Employer"` |
| `onboarding_status` | string | `not_started`, `in_progress`, or `complete` |
| `completion_percentage` | int | 0–100, rounded |
| `next_step` | string or null | Label of the first incomplete step, null if complete |
| `days_since_creation` | int | Days since institution was created |
| `days_since_last_activity` | int or null | Days since any onboarding resource was modified |
| `last_activity_date` | datetime or null | Most recent modification across all onboarding resources |
| `checklist` | object | Boolean for each checklist item |

### Checklist Items (Supplier)

These are checked in dependency order — `next_step` returns the first `false`:

| Key | What it checks | Next step label | Depends on |
|-----|---------------|-----------------|------------|
| `has_active_address` | Active, non-archived address for the institution | `address` | — |
| `has_active_entity_with_payouts` | Active entity with `payout_onboarding_status = 'complete'` | `entity_payout_setup` | address |
| `has_active_restaurant` | Active, non-archived restaurant | `restaurant` | address, entity |
| `has_active_product` | Active, non-archived product | `product` | — |
| `has_active_plate` | Active plate linked to a restaurant | `plate` | restaurant, product |
| `has_active_kitchen_day` | Active kitchen day on a plate | `kitchen_day` | plate |
| `has_active_qr_code` | Active QR code on a restaurant | `qr_code` | restaurant |

### Error Responses

| Status | Detail | When |
|--------|--------|------|
| 401 | Unauthorized | Missing or invalid token |
| 403 | Forbidden: institution mismatch | Supplier user requesting another institution's status |
| 404 | Institution not found | Invalid institution_id |

---

## Frontend Integration Guide

### 1. Page-Load Gating (JWT claim)

```typescript
const token = parseJwt(accessToken);
if (token.onboarding_status === "not_started") {
  redirect("/setup-wizard");
} else if (token.onboarding_status === "in_progress") {
  showOnboardingBanner();
}
```

### 2. Dashboard Progress Banner

Call the API to get `completion_percentage` and `next_step`:

```typescript
const { data } = await api.get(`/institutions/${institutionId}/onboarding-status`);
// data.completion_percentage = 57
// data.next_step = "product"
// data.checklist.has_active_restaurant = true
```

### 3. Sidebar Navigation Gating

Use the `checklist` to enable/disable menu items:

```typescript
const nav = {
  "Addresses":    true,  // always enabled
  "Entities":     data.checklist.has_active_address,
  "Restaurants":  data.checklist.has_active_entity_with_payouts,
  "Products":     true,  // independent of restaurant
  "Plates":       data.checklist.has_active_restaurant && data.checklist.has_active_product,
  "Kitchen Days": data.checklist.has_active_plate,
  "QR Codes":     data.checklist.has_active_restaurant,
};
```

### 4. Regression Handling

If a supplier archives a resource that was part of the checklist, the status may regress from `complete` to `in_progress`. The JWT claim updates on next login. Poll the API if you need real-time status after destructive operations.

---

## Employer Onboarding (Same Endpoint)

The same endpoint works for Employer institutions with a different checklist:

| Key | What it checks | Next step label |
|-----|---------------|-----------------|
| `has_benefits_program` | Active employer_benefits_program | `benefits_program` |
| `has_email_domain` | Active employer_domain | `email_domain` |
| `has_enrolled_employee` | At least 1 active Customer user in the institution | `enroll_employee` |
| `has_active_subscription` | At least 1 active subscription from an enrolled employee | `employee_subscription` |

---

## Related Documents

| Document | Relationship |
|----------|-------------|
| `docs/plans/SUPPLIER_SUCCESS_MANAGEMENT_ROADMAP.md` | Full roadmap with rationale and phases |
| `docs/api/b2b_client/API_CLIENT_SUPPLIER_INVOICES.md` | Related B2B API pattern |
