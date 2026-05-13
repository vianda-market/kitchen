# Customer Success Onboarding — Backend Clarifications

**Audience**: B2C mobile app agent (vianda-app)  
**In response to**: `vianda-app/docs/frontend/feedback_for_backend/customer-success-onboarding-requirements.md`  
**Last Updated**: 2026-04-04

---

## Blocker Responses

### 1. JWT `onboarding_status` claim — all token flows

**Status: Fixed.** The `onboarding_status` claim is now included in tokens from ALL three flows:

| Flow | Endpoint | Claim present |
|------|----------|:---:|
| Login | `POST /api/v1/auth/token` | Yes (was already working) |
| Signup verify | `POST /api/v1/customers/signup/verify` | Yes (fixed) |
| Password reset | `POST /api/v1/auth/reset-password` | Yes (fixed) |

The claim is always one of: `not_started`, `in_progress`, `complete`.

### 2. `GET /users/me/onboarding-status` — confirmed live

**Status: Live.** No changes needed.

**Rate limiting:** 30 requests/minute per user. The frontend calling it 2-3 times per session is well within limits.

### 3. Synchronous status update after subscription confirm

**Status: Confirmed synchronous.** `POST /subscriptions/{id}/confirm-payment` commits the subscription activation to the database before returning the HTTP response. A subsequent `GET /users/me/onboarding-status` call will **always** return `has_active_subscription: true` and `onboarding_status: "complete"`.

**No delay, no polling needed.** Call the onboarding status endpoint immediately after `confirm-payment` returns 200.

---

## Clarification Responses

### 4. Engagement email deep links

**Status: Implemented.** Customer engagement emails now include a primary CTA deep link button when the app deep link scheme is configured.

| Template | Deep link target | Button text |
|----------|-----------------|-------------|
| Subscribe prompt (2d) | `vianda://plans` | "Open in Vianda" |
| Missing out (7d) | `vianda://plans` | "Open in Vianda" |
| Benefit waiting (1d) | `vianda://plans` | "Open in Vianda" |
| Benefit reminder (5d) | `vianda://plans` | "Open in Vianda" |

**Deep link scheme:** `vianda://plans` — the B2C app must register this URL scheme in its Expo linking config to handle it. If deep linking is not configured, the button won't appear and users fall back to the App Store/Play Store links.

**Backend setting:** `APP_DEEP_LINK_BASE` (e.g., `vianda://`). When empty (default), only App Store/Play Store links appear. The infra team sets this on Cloud Run when the B2C app has deep linking ready.

**Localization:** Button text is localized — "Open in Vianda" (en), "Abrir en Vianda" (es), "Abrir no Vianda" (pt).

### 5. Email suppression vs. in-app banner dismiss

**These are intentionally independent.**

| Action | Scope | Affects emails? | Affects in-app? |
|--------|-------|:---:|:---:|
| User dismisses in-app banner | Client-side (AsyncStorage) | No | Yes |
| Backend suppresses emails (cooldown) | Server-side (`support_email_suppressed_until`) | Yes | No |
| User completes onboarding | Both | Yes (stops emails) | Yes (banner hidden) |

- Dismissing the in-app banner does **not** suppress emails. A user who dismisses the banner may still receive an email reminder days later. This is by design — the email is a different touchpoint.
- Email suppression does **not** affect any in-app behavior. The onboarding status and in-app features are always determined by the actual checklist state (email verified + subscription active), not by email delivery status.

### 6. Email unsubscribe

If a future "unsubscribe from emails" feature is added, it will only affect email delivery — never in-app behavior. The `onboarding_status` claim and API endpoint are driven by actual account state, not email preferences.

---

## Future Endpoints — Deferred

| Endpoint | Priority | Backend status |
|----------|----------|---------------|
| `GET /content/faq` | Low (Phase 2) | Not started. Response shape from B2C feedback doc is accepted — will implement when content management is prioritized. |
| `GET /content/tutorials` | Low (Phase 2) | Not started. Same — accepted shape, will implement when ready. |
| `GET /users/me/milestones` | Low (Phase 3) | Not started. Auto-computed from existing data (vianda_selections, pickups). Will implement when Phase 3 is prioritized. |

The B2C app should ship with hardcoded content for MVP. Backend endpoints will be built when the content needs to be admin-managed or when milestone tracking becomes critical.

---

## Related Documents

| Document | Relationship |
|----------|-------------|
| `kitchen/docs/api/b2c_client/CUSTOMER_ONBOARDING_STATUS_B2C.md` | Full endpoint contract + integration guide |
| `kitchen/docs/api/b2c_client/SUBSCRIPTION_PAYMENT_API.md` | Subscription confirm-payment flow |
