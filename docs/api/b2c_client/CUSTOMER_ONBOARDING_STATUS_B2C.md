# Customer Onboarding Status — B2C Client Guide

**Audience**: B2C mobile app agent (vianda-app)  
**Last Updated**: 2026-04-04  
**Status**: Active — ready for integration

---

## What This Enables

The backend tracks whether a Customer has completed onboarding (email verification + active subscription). The mobile app can use this to:

- **Show subscribe prompts** — when `onboarding_status != "complete"`, prompt the user to subscribe
- **Gate features** — disable plate browsing or ordering until subscribed
- **Fast page-load check** via JWT `onboarding_status` claim — no extra API call needed
- **Benefit employee awareness** — benefit employees see the same status; their subscription may be employer-paid

---

## JWT Claim: `onboarding_status`

Every Customer JWT token includes an `onboarding_status` claim:

| Value | Meaning |
|-------|---------|
| `not_started` | Email not verified AND no subscription |
| `in_progress` | Email verified but no active subscription (or vice versa) |
| `complete` | Email verified AND active subscription |

**Use for:** Decide whether to show subscribe/verify prompts on app launch. For detailed checklist, call the API.

**Refresh:** Recomputed on every login and token refresh. Always reflects current state.

---

## API: Get My Onboarding Status

### `GET /api/v1/users/me/onboarding-status`

**Auth:** Bearer token (Customer role only). Uses `user_id` from the JWT — no path parameter needed.

**Non-Customer users:** Returns 404. Supplier/Employer users should use `GET /institutions/{id}/onboarding-status` instead.

### Success Response (200)

```json
{
  "institution_id": null,
  "institution_type": "Customer",
  "onboarding_status": "in_progress",
  "completion_percentage": 50,
  "next_step": "subscribe",
  "days_since_creation": 3,
  "days_since_last_activity": 1,
  "last_activity_date": "2026-04-03T10:15:00Z",
  "checklist": {
    "has_verified_email": true,
    "has_active_subscription": false
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `institution_id` | null | Always null for customers (user-level, not institution-level) |
| `institution_type` | string | Always `"Customer"` |
| `onboarding_status` | string | `not_started`, `in_progress`, or `complete` |
| `completion_percentage` | int | 0, 50, or 100 (2 checklist items) |
| `next_step` | string or null | `"verify_email"`, `"subscribe"`, or null if complete |
| `days_since_creation` | int | Days since user account was created |
| `days_since_last_activity` | int or null | Days since last user or subscription modification |
| `last_activity_date` | datetime or null | Most recent modification |
| `checklist` | object | Boolean for each checklist item |

### Checklist Items (Customer)

| Key | What it checks | Next step label |
|-----|---------------|-----------------|
| `has_verified_email` | `email_verified = TRUE` on the user record | `verify_email` |
| `has_active_subscription` | At least 1 active subscription for this user | `subscribe` |

### Error Responses

| Status | Detail | When |
|--------|--------|------|
| 401 | Unauthorized | Missing or invalid token |
| 404 | Onboarding status is only available for Customer users | Non-Customer role |

---

## Frontend Integration Guide

### 1. App Launch Check (JWT claim)

```typescript
const token = parseJwt(accessToken);
if (token.onboarding_status === "not_started") {
  // Show email verification screen
  navigateTo("/verify-email");
} else if (token.onboarding_status === "in_progress") {
  // Show subscribe prompt
  navigateTo("/plans");
}
// "complete" → normal app experience
```

### 2. Detailed Status (API call)

```typescript
const { data } = await api.get("/users/me/onboarding-status");

if (!data.checklist.has_verified_email) {
  showVerifyEmailPrompt();
} else if (!data.checklist.has_active_subscription) {
  showSubscribePrompt();
}
```

### 3. Benefit Employees

Benefit employees (enrolled via employer program) follow the same checklist. Their subscription may be:
- **Fully subsidized** (100% employer-paid) — employer admin subscribes them, they're `complete` immediately
- **Partially subsidized** — employee must self-subscribe via `POST /subscriptions/with-payment`, status shows `in_progress` until they do

The `onboarding_status` doesn't distinguish benefit employees from regular customers. To detect if a user is a benefit employee, check if `institution_id` in the JWT is NOT the Vianda Customers institution.

---

## Automated Engagement Emails

The backend automatically sends engagement emails to unsubscribed customers:

| Timing | Regular Customer | Benefit Employee |
|--------|-----------------|-----------------|
| 1-2 days after signup | "Start your subscription" | "Your employer benefit is waiting" |
| 5-7 days after signup | "You're missing out" | "Don't miss your meal benefit" |

These are sent via the daily `customer_engagement` cron. Max 1 email per 3-day window. Emails are localized (en/es/pt) based on the user's `locale` field.

---

## Related Documents

| Document | Relationship |
|----------|-------------|
| `docs/api/b2c_client/SUBSCRIPTION_PAYMENT_API.md` | How to create a subscription |
| `docs/api/b2c_client/CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md` | Email verification flow |
| `docs/plans/SUPPLIER_SUCCESS_MANAGEMENT_ROADMAP.md` | Full roadmap context |
