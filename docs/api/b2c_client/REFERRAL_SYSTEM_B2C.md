# Referral System — B2C Integration Guide

**Audience**: vianda-app (B2C mobile)
**Status**: Ready for implementation
**Backend**: Fully implemented — all endpoints live

---

## Overview

Users can share a personal referral code. When a new user signs up with that code and completes their first subscription payment, the referrer earns bonus credits. The B2C app needs to integrate referral codes into signup, display the user's own code for sharing, and show referral activity.

---

## 1. Signup Flow — Accept Referral Code

### Step 1: `POST /api/v1/customers/signup/request`

Add an **optional** `referral_code` field to the signup form.

```json
{
  "username": "maria",
  "password": "securePass123",
  "email": "maria@example.com",
  "first_name": "Maria",
  "last_name": "Lopez",
  "country_code": "AR",
  "city_id": "...",
  "referral_code": "CARLOS-V7X2"
}
```

**Validation**: The backend validates the code immediately. If invalid:
- `400 Bad Request` with `"Invalid referral code"`

**Validation**: The backend validates the code immediately. If invalid:
- `400 Bad Request` with `"Invalid referral code"` — silently drop the code and proceed with normal signup

**Device-based fallback**: If no `referral_code` is in the body, the backend checks the `X-Device-Id` header for a pre-assigned code (see section 1b below). Send the header on every signup request.

### Step 2: `POST /api/v1/customers/signup/verify`

No changes — the referral code is stored in the pending signup and carried through automatically. The user's own referral code is generated on verification.

### Deep link format

```
https://vianda.app/r/{REFERRAL_CODE}
```

When the app opens from this link, call the assign-code endpoint (section 1b) to persist the code server-side.

---

## 1b. Pre-Auth Referral Code Assignment (Deep Link Lifecycle)

When a user taps a referral deep link **before signing up**, the app should persist the code server-side so it survives app restarts, reinstalls, etc.

### `POST /api/v1/referrals/assign-code` (public, no auth)

**Rate limit**: 10/minute per IP

```json
{
  "referral_code": "CARLOS-V7X2",
  "device_id": "<device fingerprint>"
}
```

**Response** `200`:
```json
{ "success": true, "referral_code": "CARLOS-V7X2" }
```

- `400` if referral code is invalid
- If the device already has an assignment, the new code **replaces** it (last link wins)
- Assignments auto-expire after 48 hours

### `GET /api/v1/referrals/assigned-code?device_id={device_id}` (public, no auth)

**Rate limit**: 20/minute per IP

**Response** `200`:
```json
{ "referral_code": "CARLOS-V7X2" }
```

- `404` if no active assignment

**UX flow**:
1. User taps `vianda.app/r/CARLOS-V7X2` → app calls `POST /referrals/assign-code`
2. On register screen: call `GET /referrals/assigned-code` to check if a code exists → show "Referred by a friend" badge
3. On signup submit: send `X-Device-Id` header — backend resolves the code automatically if not in body

---

## 2. View Own Referral Code

### `GET /api/v1/referrals/my-code`

**Auth**: Bearer token (Customer)

**Response** `200`:
```json
{
  "referral_code": "MARIA-V7X2"
}
```

**UX**: Show on the user's profile or a dedicated "Refer a Friend" screen. Include a share button that composes the message with the deep link.

---

## 3. View Referral Activity

### `GET /api/v1/referrals/my-referrals`

**Auth**: Bearer token (Customer)

**Response** `200`:
```json
[
  {
    "referral_id": "uuid",
    "referrer_user_id": "uuid",
    "referee_user_id": "uuid",
    "referral_code_used": "MARIA-V7X2",
    "market_id": "uuid",
    "referral_status": "rewarded",
    "bonus_credits_awarded": 3,
    "bonus_plan_price": 12000,
    "bonus_rate_applied": 15,
    "qualified_date": "2026-04-05T14:30:00Z",
    "rewarded_date": "2026-04-05T14:30:05Z",
    "is_archived": false,
    "status": "active",
    "created_date": "2026-04-01T10:00:00Z"
  }
]
```

**`referral_status` values**:
| Value | Display | Meaning |
|---|---|---|
| `pending` | Invited | Friend registered but hasn't subscribed yet |
| `qualified` | Processing | Friend subscribed, reward being processed |
| `rewarded` | Earned | Credits received |
| `expired` | Expired | Friend didn't subscribe in time, or referrer had no active subscription |
| `cancelled` | Cancelled | Voided (refund, fraud) |

---

## 4. Referral Stats Summary

### `GET /api/v1/referrals/stats`

**Auth**: Bearer token (Customer)

**Response** `200`:
```json
{
  "total_referrals": 5,
  "total_credits_earned": 12,
  "pending_count": 2
}
```

**UX**: Use for a stats card on the referral screen — "You've earned 12 credits from 5 referrals. 2 pending."

---

## 5. Reward Mechanics (display only)

The app does **not** trigger rewards — the backend handles this automatically when the referee's first payment succeeds. The app just displays results.

- **Bonus formula**: `floor(plan_price * bonus_rate% / credit_value)` — higher-value plans yield more credits
- **Referrer must have active subscription** to receive credits. If not active at qualification time, the reward is held for up to 48 hours
- **Monthly cap**: Configurable per market (default 5 rewards/month)
- **One referral per user**: Each user can only be referred once

---

## 6. UI Screens Summary

| Screen | Data source | Key elements |
|---|---|---|
| **Signup form** | N/A | Optional referral code field (pre-filled from deep link) |
| **Refer a Friend** | `GET /referrals/my-code` | Code display, share button (WhatsApp, copy link, etc.) |
| **Referral Activity** | `GET /referrals/my-referrals` | List of referrals with status badges |
| **Referral Stats** | `GET /referrals/stats` | Credits earned, total referrals, pending count |
