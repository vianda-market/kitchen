# Email Registered Check — Client Guide

**Audience**: B2C app and any client with a lead/pre-signup flow  
**Consumers**: B2C app (and any client that needs to show “already registered” before sending the user to signup)  
**Status**: Implemented

---

## Purpose

In the **lead flow** (e.g. marketing home), the user enters **email** and **city** and taps “See restaurants near you”. The app shows a short summary (restaurant count in that city) and a CTA to “Continue to register”. If the **email is already registered**, we want to:

- Show the same city summary, plus: **“This email is already registered. Please log in.”**
- Hide the “Continue to register” button and only show **Login**.

This endpoint lets the frontend **check on first input** (after city/zipcode) so users are sent through the right route (login vs signup) without filling the full signup form.

---

## Endpoint

**GET** `/api/v1/leads/email-registered`

**Authentication**: None (public). Same as other lead endpoints (city-metrics, cities).

**Rate limiting**: Maximum **5 requests per 60 seconds per IP** (shared with all lead endpoints: cities, city-metrics, zipcode-metrics, email-registered). The **6th request** returns **429** and the user must wait **60 seconds** before retrying. After cooldown, a **human check** (e.g. CAPTCHA) may be required in a future release—see roadmap.

### Query parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `email`   | Yes      | Email address to check. Backend normalizes to lowercase; only “registered” vs “not registered” is returned. |

### Success response (200 OK)

```json
{
  "registered": true
}
```

or

```json
{
  "registered": false
}
```

- **`registered: true`** — A user with this email already exists (already signed up / verified). Route to **login**; show “This email is already registered. Please log in.” and only the Login button.
- **`registered: false`** — No user with this email exists. Show “Continue to register” + Login.

### Error responses

| Status | When | Body |
|--------|------|------|
| **400** | Invalid or missing `email` (empty or no `@`) | `{ "detail": "Valid email is required" }` |
| **429** | Rate limit exceeded (6th request within 60s) | `{ "detail": "Too many requests. Please try again in 60 seconds." }` |

---

## Security and enumeration

Returning “registered” vs “not registered” does allow **email enumeration**. Mitigations in place:

- **Rate limiting**: 5 requests per 60 seconds per IP (all lead endpoints share this limit). On the 6th request the user is blocked for 60 seconds. **Roadmap**: after cooldown, require a human check (e.g. CAPTCHA) before allowing further requests—see [LEAD_RATE_LIMIT_AND_HUMAN_CHECK.md](../../roadmap/LEAD_RATE_LIMIT_AND_HUMAN_CHECK.md).

The B2C app typically calls this once per “See restaurants near you” submission. If the endpoint is unavailable (e.g. 404/501), the client can treat the result as “not registered” and still show “Continue to register”.

---

## Client behavior (B2C)

1. User enters **email** and **city** and taps “See restaurants near you”.
2. Call **GET /api/v1/leads/city-metrics** (or zipcode-metrics) with city/zipcode; show city summary.
3. Call **GET /api/v1/leads/email-registered?email=...** with the trimmed, lowercased email.
4. **If 200 and `registered: true`**: show city summary + “This email is already registered. Please log in.” and only the **Login** button (no “Continue to register”).
5. **If 200 and `registered: false`**: show city summary + **“Continue to register”** + Login.
6. **If 429**: show “Too many requests. Please try again in 60 seconds.” (user is blocked for 60s; future: human check after cooldown per roadmap).
7. **If 400**: show the `detail` message (e.g. “Valid email is required”).

---

## Summary

| Item        | Value |
|------------|--------|
| Method     | GET |
| Path       | `/api/v1/leads/email-registered` |
| Auth       | None |
| Query      | `email` (required) |
| Response   | `{ "registered": boolean }` |
| Rate limit | 5 req / 60 s per IP (all lead endpoints). 6th request → 429 for 60s. |
| Purpose    | Route user to login vs signup on first input; do not ask to register when email is already known. |
| Roadmap    | Human check (e.g. CAPTCHA) after cooldown—see [LEAD_RATE_LIMIT_AND_HUMAN_CHECK.md](../../roadmap/LEAD_RATE_LIMIT_AND_HUMAN_CHECK.md). |
