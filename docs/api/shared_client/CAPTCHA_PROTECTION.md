# CAPTCHA Protection on Auth Endpoints

**Status:** Implemented  
**Applies to:** B2B (vianda-platform), B2C web (vianda-app), B2C mobile (exempt)

---

## Overview

reCAPTCHA v3 (invisible, score-based) is now enforced on login, signup, and password recovery endpoints. Protection is either **always-on** (every web request) or **conditional** (activates after repeated failed/abusive attempts from the same IP).

Mobile clients (`x-client-type: b2c-mobile`) are **exempt** from all CAPTCHA checks.

---

## Endpoints

### 1. `POST /api/v1/auth/token` (login) — Conditional

**Trigger:** After **5 failed login attempts** from the same IP within **15 minutes**.

**Response when CAPTCHA required (no token sent):**
```
HTTP 429
{
  "detail": {
    "code": "captcha_required",
    "message": "Too many attempts. Please verify you are human."
  }
}
```

**reCAPTCHA action:** `login`

**Reset:** Counter clears on successful login.

### 2. `POST /api/v1/customers/signup/request` — Always-on (web only)

**Trigger:** Every request from a web client must include a reCAPTCHA token.

**Response when token missing (web client):**
```
HTTP 403
{
  "detail": {
    "code": "captcha_required",
    "message": "Verification required."
  }
}
```

**reCAPTCHA action:** `signup`

### 3. `POST /api/v1/customers/signup/verify` — Conditional

**Trigger:** After **3 failed verification attempts** from the same IP within **15 minutes**.

**Response:** Same 429 format as login.

**reCAPTCHA action:** `signup_verify`

### 4. `POST /api/v1/auth/forgot-password` — Conditional

**Trigger:** After **3 requests** from the same IP within **15 minutes** (counts all requests, not just failures).

**Response:** Same 429 format as login.

**reCAPTCHA action:** `forgot_password`

### 5. `POST /api/v1/auth/forgot-username` — Conditional

**Trigger:** After **3 requests** from the same IP within **15 minutes**.

**Response:** Same 429 format as login.

**reCAPTCHA action:** `forgot_username`

### 6. `POST /api/v1/auth/reset-password` — Conditional

**Trigger:** After **3 failed reset attempts** from the same IP within **15 minutes**.

**Response:** Same 429 format as login.

**reCAPTCHA action:** `reset_password`

---

## Frontend Integration Guide

### Detection

Check error responses for `detail.code === "captcha_required"`:
- **429** → conditional CAPTCHA (threshold exceeded). Retry with token.
- **403** → always-on CAPTCHA (token was required but missing). Send with token.

### Token Submission

Send reCAPTCHA v3 token in the `X-Recaptcha-Token` HTTP header:
```
X-Recaptcha-Token: <token-from-grecaptcha.execute>
```

### reCAPTCHA Actions

Use the correct `action` value per endpoint:
```javascript
const token = await grecaptcha.execute(siteKey, { action: 'login' });
// action values: login, signup, signup_verify, forgot_password, forgot_username, reset_password
```

### Lazy Loading

Load the reCAPTCHA v3 script **only when needed** (on `captcha_required` response or before signup/request for web). Do not include it on every page.

### Mobile Clients

B2C mobile apps must send `x-client-type: b2c-mobile` header on all requests. This exempts them from CAPTCHA verification.

### User-Facing Message

Show a subtle, non-technical notice: **"Additional verification required"**. Never expose CAPTCHA internals to the user.

---

## Summary Table

| Endpoint | Action | When CAPTCHA is sent | Status Code |
|----------|--------|---------------------|-------------|
| `POST /auth/token` | `login` | After 5 failures | 429 |
| `POST /customers/signup/request` | `signup` | Always (web only) | 403 |
| `POST /customers/signup/verify` | `signup_verify` | After 3 failures | 429 |
| `POST /auth/forgot-password` | `forgot_password` | After 3 requests | 429 |
| `POST /auth/forgot-username` | `forgot_username` | After 3 requests | 429 |
| `POST /auth/reset-password` | `reset_password` | After 3 failures | 429 |

---

## Environment Variables

Frontend teams need:
- **B2B:** `VITE_RECAPTCHA_SITE_KEY` — reCAPTCHA v3 public site key
- **B2C:** `EXPO_PUBLIC_RECAPTCHA_SITE_KEY` — same key for web builds

Backend variables (already configured):
- `RECAPTCHA_SECRET_KEY` — server-side verification
- `RECAPTCHA_SCORE_THRESHOLD` — minimum score (default 0.3)
- Per-endpoint thresholds: `LOGIN_CAPTCHA_THRESHOLD`, `SIGNUP_VERIFY_CAPTCHA_THRESHOLD`, etc.
