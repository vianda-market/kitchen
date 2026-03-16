# B2C Customer Registration (Email Verification Flow)

**Audience**: B2C app (React Native / mobile)  
**Last updated**: February 2026  
**Status**: Current flow for new customer signup

This document describes the **two-step customer registration flow** with email verification. Use it to implement signup in the B2C app. The backend creates a user in `user_info` only **after** the user verifies their email.

---

## 1. Flow overview

```text
┌─────────────┐     POST /signup/request      ┌─────────┐     Store pending     ┌──────────┐
│   B2C App   │ ─────────────────────────────► │   API   │ ────────────────────► │  Email   │
│ (signup     │  (username, password, email,  │         │  Send 6-digit         │  (SMTP)  │
│  form)      │   country_code, cellphone,    │         │  verification code    │          │
│             │   first_name, last_name)      │         │                       │          │
└─────────────┘                                └─────────┘                       └────┬─────┘
       │                                          │ 201 + generic message              │
       │ Show "Check your email"                  │                                    │
       │                                          │                                    │
       │  User receives 6-digit code in email (no link)                               │
       │  User enters code in app                                                  │
       │                                          │                                    │
       │     POST /signup/verify                   │                                    │
       │     { "code": "123456" }                  │                                    │
       └─────────────────────────────────────────►│ Create user, mark code used      │
                                                    │ 201 + user + access_token        │
                                                    │◄─────────────────────────────────┘
       ◄───────────────────────────────────────────┘
       Store access_token, show user as logged in
```

| Step | App action | API | Result |
|------|------------|-----|--------|
| 1 | User submits signup form | `POST /api/v1/customers/signup/request` | 201 + generic message; verification email with 6-digit code sent |
| 2 | User receives email and enters 6-digit code in app | — | App has `code` from user input |
| 3 | App calls verify with code | `POST /api/v1/customers/signup/verify` | 201 + user + `access_token`; user is created and logged in |

### Process in plain language

- **Step 1:** The user submits the signup form. The backend stores the request in a pending table and sends a verification email containing a **6-digit code** (no link). No user is created in `user_info` yet.
- **Step 2:** The user opens the email and enters the 6-digit code in the app.
- **Step 3:** The app calls the verify endpoint with that `code`. The backend creates the user, marks the code as used, and returns the user object plus an `access_token`.
- **Step 4:** The app stores the token and treats the user as logged in for all subsequent requests.

### Why two steps?

This flow ensures the email address is valid and owned by the person signing up. The one-time verification code reduces fake signups and keeps a clear audit trail. Only after the user proves access to the inbox does the backend create the account and issue a session token.

---

## 2. Base URL and auth

- **Base URL**: Same as the rest of the B2C API (e.g. `https://api.example.com` or your env base).
- **Prefix**: `/api/v1`.
- **Auth for signup**: **None**. Both `signup/request` and `signup/verify` are **unauthenticated**. Do **not** send `Authorization` for these two endpoints.
- **Auth after signup**: Use the `access_token` returned by `signup/verify` (or `POST /api/v1/auth/token` for login) in the `Authorization: Bearer <access_token>` header for all other endpoints.

---

## 3. Step 1 — Request signup (send verification email)

### Endpoint

```http
POST /api/v1/customers/signup/request
Content-Type: application/json
```

**No `Authorization` header.**

### Request body

| Field | Type | Required | Constraints | Notes |
|-------|------|----------|-------------|-------|
| `username` | string | Yes | 3–100 chars | Unique; must not already exist in the system |
| `password` | string | Yes | min 8 chars | Sent in plain text over HTTPS; backend hashes before storing |
| `email` | string | Yes | Valid email format | Unique; stored and compared in lowercase |
| `country_code` | string | **Yes** | ISO 3166-1 alpha-2 (e.g. US, AR) | Country the user selected. Must be from `GET /api/v1/leads/markets`. Backend resolves to market internally. |
| `city_id` | UUID | One of city_id or city_name | Valid city UUID | City UUID. Use when you have it (e.g. from `GET /api/v1/cities/`). Optional if `city_name` is provided. |
| `city_name` | string | One of city_id or city_name | City name from API | City name the user selected. Must be from `GET /api/v1/leads/cities?country_code={country_code}`. Backend resolves to city_id. **Preferred for B2C** (no auth needed for cities list). |
| `cellphone` | string | No | max 20 chars | Optional; users can add later in profile. |
| `first_name` | string | No | max 50 chars | |
| `last_name` | string | No | max 50 chars | |

**Example**

```json
{
  "username": "jane_doe",
  "password": "securePass123",
  "email": "jane.doe@example.com",
  "country_code": "US",
  "city_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
  "cellphone": "+5491112345678",
  "first_name": "Jane",
  "last_name": "Doe"
}
```

Use the `country_code` value from the leads/markets response (e.g. `US`, `AR`). Do not submit signup without `country_code`. Use the `city_id` from `GET /api/v1/cities/?country_code={country_code}&exclude_global=true`. Do not submit signup without `city_id` (or `city_name`); the Global city cannot be assigned to B2C customers.

### Country selection

The app must call **`GET /api/v1/leads/markets`** (no auth) to get the list of countries. The response returns `country_code` and `country_name` only. The user selects one in the UI; send its `country_code` in the signup request body. `country_code` is **required**. See [MARKET_SELECTION_AT_SIGNUP.md](MARKET_SELECTION_AT_SIGNUP.md) and [Markets API](../../b2b_client/MARKETS_API_CLIENT.md).

**City selection:** Call `GET /api/v1/leads/cities?country_code={country_code}` (no auth) to get city names for the signup picker. Send the selected `city_name` in the signup body; the backend resolves it to `city_id`. One of `city_id` or `city_name` is **required** at signup.

When `cellphone` is optional (backend support), it can be omitted or sent as `null`.

### Success response (verification email sent)

- **Status**: `201 Created`
- **Body**:

```json
{
  "success": true,
  "message": "A verification code has been sent to your email.",
  "already_registered": false
}
```

**App behavior**: Show the message (or a localized “Check your email to verify your account”) and, if needed, a note that the link expires in 24 hours.

### Email already registered

- **Status**: `409 Conflict`
- **Body**: Standard error shape with `detail`:

```json
{
  "detail": "This email is already registered. Please log in."
}
```

**App behavior**: Stop the user at signup; show an alert (or inline message) with the `detail` text and a button/link to go to the **login** screen. Do not show “Check your email”.

### Error responses

| Status | When | App behavior |
|--------|------|--------------|
| `400 Bad Request` | Validation error (e.g. missing field, short password, invalid email) or **username already exists** | Show `detail` from the response body. For “Username already exists”, prompt a different username. |
| `409 Conflict` | **Email already registered** | Show `detail` (“This email is already registered. Please log in.”) and navigate user to login. |
| `500 Internal Server Error` | Server or DB error | Show a generic “Something went wrong” and suggest retry. |

**Note**: If the **email** is already registered, the API still returns **201** with the same success message and **does not** send an email. The app should not distinguish this case (no email enumeration).

---

## 4. Step 2 — Verify email and complete signup

The user receives an email with a **6-digit verification code** (no link). The app must:

1. Show a screen for the user to enter the 6-digit code.
2. Call the verify endpoint with that `code`.

### Endpoint

```http
POST /api/v1/customers/signup/verify
Content-Type: application/json
```

**No `Authorization` header.**

### Request body

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `code` | string | Yes* | The 6-digit verification code from the email. |
| `token` | string | No | Legacy: verification token (use `code` for new flows). |

*Either `code` or `token` is required.

**Example**

```json
{
  "code": "123456"
}
```

### Success response

- **Status**: `201 Created`
- **Body**:

```json
{
  "user": {
    "user_id": "uuid",
    "institution_id": "uuid",
    "role_type": "Customer",
    "role_name": "Comensal",
    "username": "jane_doe",
    "email": "jane.doe@example.com",
    "first_name": "Jane",
    "last_name": "Doe",
    "cellphone": "+5491112345678",
    "employer_id": null,
    "is_archived": false,
    "status": "Active",
    "created_date": "2026-02-17T12:00:00Z",
    "modified_date": "2026-02-17T12:00:00Z"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**App behavior**:

1. Persist `access_token` (e.g. secure storage) and use it as the Bearer token for all subsequent API calls.
2. Optionally store or display fields from `user` (e.g. `user_id`, `email`, `first_name`) for profile or UI.
3. Navigate to the post-signup/home screen and treat the user as **logged in**.

### Error responses

| Status | When | App behavior |
|--------|------|--------------|
| `400 Bad Request` | Token missing, invalid, expired, or already used | Show a clear message (e.g. “Link expired or already used. Please request a new verification link from the signup screen.”) and offer a way to return to signup or “Resend verification”. |
| `422 Unprocessable Entity` | Body validation failed (e.g. empty `token`) | Show validation message or generic “Invalid request”. |
| `500 Internal Server Error` | Server error | Show generic error and suggest retry. |

**Common `detail` values for 400**:

- `"Invalid or expired verification token"`
- `"Verification link has already been used"`
- `"Verification link has expired"`

---

## 5. Deep linking and universal links

The verification email will contain a URL that should open the B2C app when possible.

- **Deep link**: e.g. `myapp://verify-signup?token=<token>`
- **Universal link / App link**: e.g. `https://app.your-domain.com/verify-signup?token=<token>` (configured to open the app)

The app must:

1. Register for the scheme/path (e.g. `verify-signup`).
2. On open, parse the URL and read the `token` query parameter.
3. Call `POST /api/v1/customers/signup/verify` with `{"token": "<token>"}`.
4. On success, store `access_token` and navigate to the main app; on error, show the error and an option to go back to signup or request a new link.

**Token format**: The token is a long URL-safe string (e.g. 64+ characters). Do not truncate or modify it.

---

## 6. Token expiry and resend

- **Expiry**: Verification links expire after **24 hours** (backend default).
- **One-time use**: Each token can only be used once. After a successful verify, the token is marked used.
- **Resend**: There is no separate “resend verification” endpoint. The user can submit the **signup form again** with the same email (and same or different username if applicable). The backend will replace any previous pending signup for that email and send a **new** verification email. So “Resend verification” in the app can be implemented as “Submit signup again with the same email” (and pre-filled form if desired).

---

## 7. Dev / E2E only (optional)

When the backend runs with **DEV_MODE** enabled (e.g. staging or local), a **dev-only** endpoint is available for E2E tests or tools that cannot read the email:

```http
GET /api/v1/customers/signup/dev-pending-token?email=<email>
```

- **Query**: `email` — the same email used in `signup/request` (must be lowercase to match; avoid `+` in the query or encode it as `%2B`).
- **Response**: `200 OK` with `{"token": "..."}`.
- **Use**: Only for automation; do **not** use in production builds. In production, `DEV_MODE` is expected to be false and this endpoint returns **403**.

---

## 9. Summary for implementation

| Item | Value |
|------|--------|
| Step 1 | `POST /api/v1/customers/signup/request` with `username`, `password`, `email`, `country_code`, `city_id` or `city_name`, `cellphone`, `first_name`, `last_name` |
| Step 1 success | 201; show “Check your email”; same message even if email already registered |
| Step 2 | User opens link → app gets `token` from URL → `POST /api/v1/customers/signup/verify` with `{"token": "..."}` |
| Step 2 success | 201; body has `user` and `access_token`; store token and treat user as logged in |
| Auth | No auth for signup/request and signup/verify; use `access_token` from verify (or login) for all other APIs |
| Link expiry | 24 hours; one-time use |

---

## 9. Related docs

- [B2C_ENDPOINTS_OVERVIEW.md](./B2C_ENDPOINTS_OVERVIEW.md) — Table of B2C APIs and short signup summary.
- [FRONTEND_AGENT_README.md](./FRONTEND_AGENT_README.md) — General B2C client guidance.
- Login: `POST /api/v1/auth/token` (form-urlencoded `username` and `password`) for existing users.
