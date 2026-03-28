# User model for B2B/B2C clients

**Audience:** Mobile apps, web clients, and integrations.  
**Purpose:** Single reference for roles, profile fields, **`mobile_number` (E.164)**, username/email rules, **email verification and changing email** (including lead `email-registered` check), **`/users/me`** vs admin updates, user–market data, and auth recovery (forgot username / password).  
**Last updated:** March 2026

---

## Table of contents

1. [Roles, institutions, and breaking changes](#1-roles-institutions-and-breaking-changes)  
2. [Mobile number (`mobile_number`)](#2-mobile-number-mobile_number)  
3. [Username and email (lowercase)](#3-username-and-email-lowercase)  
   - [3.4 Email registered check (lead / pre-signup)](#34-email-registered-check-lead--pre-signup)  
   - [3.5 Email verification on the account](#35-email-verification-on-the-account)  
   - [3.6 Changing email (edit and verify flow)](#36-changing-email-edit-and-verify-flow)  
4. [Username is immutable](#4-username-is-immutable)  
5. [Who can update profiles (self vs admin)](#5-who-can-update-profiles-self-vs-admin)  
6. [Self-service: `/users/me` and 410 on self-use of `/{user_id}`](#6-self-service-usersme-and-410-on-self-use-of-user_id)  
7. [User and market (`market_id` / `market_ids`)](#7-user-and-market-market_id--market_ids)  
8. [Forgot username](#8-forgot-username)  
9. [Password recovery](#9-password-recovery)  
10. [Related documentation](#10-related-documentation)

---

## 1. Roles, institutions, and breaking changes

### 1.1 `role_type` values

| Value | Description |
|-------|-------------|
| `Internal` | Vianda Enterprises staff (backoffice). Global access to all institutions. |
| `Supplier` | Restaurant/institution users. Institution-scoped. |
| `Customer` | End users (mobile apps). Self-scoped. |
| `Employer` | Benefit-program managers. Institution-scoped. |

### 1.2 `role_name` values by `role_type`

| role_type | role_name values |
|-----------|------------------|
| **Internal** | Admin, Super Admin, Global Manager, Manager, Operator |
| **Supplier** | Admin, Manager, Operator |
| **Customer** | Comensal only |
| **Employer** | Admin, Manager, Comensal |

### 1.3 `institution_type` values

| Value | Description |
|-------|-------------|
| `Internal` | Vianda Enterprises institution |
| `Customer` | Vianda Customers (B2C end users) |
| `Supplier` | Restaurant/supplier institution |
| `Employer` | Benefit-program institution |

Use **Employer** consistently for benefit-program institutions. Do not use “benefits-program” as the canonical term.

### 1.4 `employer_id` (assign employer)

**Only Customer (Comensal) users can have `employer_id`.**

- Internal, Supplier, and Employer users **cannot** have `employer_id`.
- `PUT /users/me/employer` is blocked for Internal, Supplier, and Employer `role_type`.
- Only Customer users can assign themselves to an employer.

### 1.5 Breaking changes (Employee → Internal)

**`role_type`**

- **Before:** `role_type === "Employee"`
- **After:** `role_type === "Internal"`

```javascript
// OLD
if (user.role_type === "Employee") { ... }

// NEW
if (user.role_type === "Internal") { ... }
```

**`role_name` “Employer” removed from Customer**

- **Before:** Customer users could have `role_name === "Employer"`.
- **After:** Employer users are `role_type === "Employer"` with `role_name` Admin, Manager, or Comensal.

```javascript
// OLD
if (user.role_type === "Customer" && user.role_name === "Employer") { ... }

// NEW
if (user.role_type === "Employer") { ... }
```

### 1.6 Example valid combinations

| role_type | role_name | institution_type |
|-----------|-----------|------------------|
| Internal | Admin | Internal |
| Internal | Super Admin | Internal |
| Supplier | Admin | Supplier |
| Customer | Comensal | Customer or Employer |
| Employer | Admin | Employer |
| Employer | Manager | Employer |
| Employer | Comensal | Employer |

---

## 2. Mobile number (`mobile_number`)

The API field is **`mobile_number`**. It is **optional**.

### 2.1 Format and normalization

- Stored and returned in **E.164** (e.g. `+5491112345678`, `+14155552671`). Maximum length after normalization is **15 digits plus leading `+`** (16 characters).
- The backend **normalizes at write time** using the `phonenumbers` library (offline). Invalid numbers produce **422** with a clear validation message.
- **Customer signup** (`POST /api/v1/customers/signup/request`): optional `mobile_number`. The backend uses signup **`country_code`** as the default region when the user enters a national-format number (not already in E.164).
- **Admin user create** (`POST /api/v1/users/`): optional `mobile_number`; **no** country hint—users should send E.164 or a number parseable without a default region.
- **User update** (`PUT /users/me`, `PUT /users/{user_id}`): same optional field; treat empty string as “clear” where applicable.

**Client tip:** Do not rely on a short `max_length` on the **input** control to match the API: unformatted national numbers can be longer than 16 characters before normalization. The backend normalizes first; the database enforces `VARCHAR(16)` on stored values.

### 2.2 Verification flags (read-only; SMS is post-MVP)

Responses such as **`UserResponseSchema`** and **`UserEnrichedResponseSchema`** include:

| Field | Meaning |
|-------|---------|
| `mobile_number_verified` | `boolean` — reserved for future SMS OTP verification. **Currently always `false`** until Twilio Verify (or equivalent) exists. |
| `mobile_number_verified_at` | `datetime` or null — when the number was last verified. |

- **Do not send** `mobile_number_verified` or `mobile_number_verified_at` on create or update; the API does not accept client-controlled verification state.
- **Data integrity:** If the client sends an update that **changes** `mobile_number` (including **clearing it to `null`**), the API sets **`mobile_number_verified = false`** and **`mobile_number_verified_at = null`**. A removed number must not stay “verified.”
- **Post-MVP UX:** When `mobile_number` changes and `mobile_number_verified` becomes `false`, clients should treat that as a signal to **prompt re-verification** (SMS OTP) once that flow exists.

See **[MOBILE_VERIFICATION_ROADMAP.md](../../roadmap/MOBILE_VERIFICATION_ROADMAP.md)** for MVP vs post-MVP behavior (including why strict “mobile line type” checks are deferred in favor of E.164 validation only).

### 2.3 Enriched APIs

- Subscription-enriched payloads may expose the subscriber’s number as **`user_mobile_number`** (from `user_info.mobile_number`).
- Payment-method-enriched payloads may include **`mobile_number`** on the linked user where applicable.

---

## 3. Username and email (lowercase)

**Applies to:** B2B (kitchen-web) and B2C (kitchen-mobile).

The backend **normalizes usernames and emails to lowercase** before storing and when looking up. That keeps login and uniqueness consistent (e.g. `User@example.com` and `user@example.com` are the same account).

| Operation | Field | Backend handling |
|-----------|-------|------------------|
| Signup (`POST /customers/signup/request`) | username, email | Lowercase before store |
| User creation (`POST /users/`) | username, email | Lowercase before store |
| Login (`POST /auth/token`) | username | Lowercase before lookup |
| Forgot username (`POST /auth/forgot-username`) | email | Lowercase before lookup |
| Forgot password (`POST /auth/forgot-password`) | email | Lowercase before lookup |
| User lookup (`GET /users/lookup`) | username, email | Lowercase before lookup |
| Email registered (`GET /leads/email-registered`) | email | Lowercase before lookup |

**Frontend (defense in depth):** Apply `.toLowerCase().trim()` before sending on signup, login, forgot-username, forgot-password, and B2B create-user forms.

```typescript
function normalizeUsernameEmail(value: string): string {
  return (value ?? "").trim().toLowerCase();
}
```

PostgreSQL **`citext`** on `username` and `email` also enforces case-insensitive equality at the database layer.

### 3.4 Email registered check (lead / pre-signup)

**Use case:** On a marketing / lead screen (e.g. user enters email and city and taps “See restaurants near you”), the app should route **login vs signup** before the full signup form.

**Endpoint:** **`GET /api/v1/leads/email-registered`**

| Item | Detail |
|------|--------|
| **Auth** | None (public lead endpoint). |
| **Query** | **`email`** (required). Backend normalizes to lowercase. |
| **200 body** | `{ "registered": true \| false }` |
| **Rate limit** | **10 requests / minute / IP**. Exceeded → **429** `{ "detail": "Rate limit exceeded." }` |
| **400** | Invalid or missing email (e.g. empty or no `@`) → `{ "detail": "Valid email is required" }` |

**Client behavior**

1. After city/zip metrics (e.g. `GET /api/v1/leads/city-metrics` or zipcode-metrics), call **`GET /api/v1/leads/email-registered?email=...`** with trimmed, lowercased email (see normalization above).
2. **`registered: true`** — Show “This email is already registered. Please log in.” and **only** the Login CTA (hide “Continue to register”).
3. **`registered: false`** — Show “Continue to register” and Login.
4. **429** — e.g. “Too many requests. Try again in about a minute.” (roadmap: human check after cooldown — see [LEAD_RATE_LIMIT_AND_HUMAN_CHECK.md](../../zArchive/roadmap/LEAD_RATE_LIMIT_AND_HUMAN_CHECK.md)).
5. If the endpoint errors or is unavailable, you may fall back to showing signup (treat as unknown).

**Security:** The response reveals whether an email exists (**enumeration**). Mitigation is rate limiting; do not call this in a tight loop.

**Broader lead API:** [LEADS_API_SCOPE.md](./LEADS_API_SCOPE.md).

### 3.5 Email verification on the account

Responses (**`UserResponseSchema`**, **`UserEnrichedResponseSchema`**, **`GET /users/me`**, lists/enriched lists) include:

| Field | Meaning |
|-------|---------|
| `email_verified` | `boolean` — the account’s email is considered verified for this product. |
| `email_verified_at` | `datetime` or null — when verification was last recorded. |

- **Do not send** `email_verified` or `email_verified_at` on create or update; the API does not accept client-controlled email verification state.

**When the backend sets `email_verified` to true (and timestamps `email_verified_at`)**

- **B2C:** Successful completion of signup email verification (see [CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md](../b2c_client/CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md)).
- **Password reset:** Successful **`POST /api/v1/auth/reset-password`** with a valid code (proves mailbox access).
- **Email change:** Successful **`POST /api/v1/users/me/verify-email-change`** after confirming the code sent to the **new** address.

**When `email_verified` becomes false**

- **`PUT /api/v1/users/me`** or **`PUT /api/v1/users/{user_id}`** with a **new** email (different from the stored address after normalization) starts the **pending email change** flow: the stored `email` is **not** updated yet, but the API sets **`email_verified = false`** and **`email_verified_at = null`** until the user verifies the new address (see §3.6).

New rows in `user_info` default to **`email_verified = false`** until one of the flows above runs (unless seed/admin data sets them).

### 3.6 Changing email (edit and verify flow)

Changing email is **two steps**: request via profile update (sends a code to the **new** address), then confirm with a dedicated endpoint.

**1) Request change — `PUT /api/v1/users/me` or `PUT /api/v1/users/{user_id}`**

- Send **`email`** set to the **new** address (normalized like §3).
- If the new value equals the current stored email (after trim/lowercase), the field is a no-op.
- If it **differs**, the API:
  - **Does not** write the new email to `user_info` yet.
  - Creates/updates a pending **`email_change_request`**, emails a **6-digit code** to the new address (valid **24 hours**).
  - Sets **`email_verified = false`**, **`email_verified_at = null`** on the user.
  - Applies any **other** fields in the same `PUT` as usual.
- The JSON response includes optional **`email_change_message`**, e.g. *“A verification code has been sent to new@…. Your email will be updated after verification.”* Use it for in-app banners (self-service and admin edits).

**2) Confirm — `POST /api/v1/users/me/verify-email-change`** (authenticated)

| Item | Detail |
|------|--------|
| **Body** | `{ "code": "<string>" }` — typically **6 digits** from the email (`min_length` 6, `max_length` 10 for compatibility). |
| **200** | e.g. `{ "message": "Email updated successfully" }` — `user_info.email` is updated; **`email_verified`** set **true**; confirmation may be sent to the old address. |
| **400** | Invalid, expired, or already-used code. |
| **409** | (On request) New email already belongs to another account, or is pending for another account. |

**503** on the `PUT` path if verification email could not be sent (no pending change is left in a bad state; user can retry).

**Admin (`PUT /users/{user_id}`):** Same rules for the **target** user; the code is sent to the **new** email. The verifying user must be logged in as **that** account when calling **`POST .../me/verify-email-change`** (the subject of the JWT is who completes verification).

---

## 4. Username is immutable

**Username cannot change** after account creation.

| Endpoint | If `username` is in the body |
|----------|------------------------------|
| `PUT /api/v1/users/me` | **Ignored** (stripped). No error. |
| `PUT /api/v1/users/{user_id}` | **400** — `"username is immutable and cannot be changed after user creation."` |

**Clients:** Show username as **read-only** in profile/settings. **Do not send** `username` in update payloads. If your form object still has it, delete it before `PUT`.

**Why:** Login identifier, forgot-username email content, support clarity, and abuse prevention.

### Allowed vs immutable profile fields (updates)

| Field | On `PUT /users/me` or `PUT /users/{user_id}` |
|-------|-----------------------------------------------|
| `username` | Immutable — ignore or 400; do not send. |
| `role_type` | Immutable — not in update schema or rejected if sent. |
| `institution_id` | Immutable — rejected if sent. |
| `email` | **Special:** A **new** address starts verification (§3.6); stored email updates only after **`POST .../verify-email-change`**. |
| `first_name`, `last_name` | Editable. |
| `locale` | Editable (`en` \| `es` \| `pt`). See [LANGUAGE_AND_LOCALE_FOR_CLIENTS.md](./LANGUAGE_AND_LOCALE_FOR_CLIENTS.md). |
| `mobile_number` | Editable (optional; E.164 after normalization). |
| `role_name` | Editable (subject to role rules). |
| `market_id` / `market_ids` | Editable (subject to role rules). |
| `employer_id` | Editable for Customers only. |
| `status` | Editable (subject to permissions). |
| `mobile_number_verified`, `mobile_number_verified_at` | **Read-only** on responses; never send on create/update. |
| `email_verified`, `email_verified_at` | **Read-only** on responses; never send on create/update. |
| `email_change_message` | **Response-only** — present when a change was requested in that response; not a request field. |

```typescript
interface UserUpdatePayload {
  /** New address triggers §3.6; omit if not changing email. */
  email?: string;
  /** UI language preference; ISO 639-1: en, es, pt */
  locale?: "en" | "es" | "pt";
  first_name?: string;
  last_name?: string;
  mobile_number?: string | null;
  role_name?: string;
  market_id?: string;
  market_ids?: string[];
  employer_id?: string;
  status?: "Active" | "Inactive";
  // username intentionally omitted; never send email_verified / email_change_message
}

function updateMyProfile(updates: Partial<UserUpdatePayload>) {
  const body = { ...updates };
  delete (body as Record<string, unknown>).username;
  return api.put("/api/v1/users/me", body);
}
```

Forgot-username still emails the **current** username; it remains stable for the life of the account (see [§8](#8-forgot-username)).

---

## 5. Who can update profiles (self vs admin)

| Context | Endpoint | Who |
|--------|----------|-----|
| **Self-update** | `PUT /api/v1/users/me` | Authenticated user updating own profile |
| **Update by others** | `PUT /api/v1/users/{user_id}` | Admins updating **another** user (e.g. backend portal) |

**Rule:** Use **`/me`** for self. Use **`/{user_id}`** only when an admin updates someone else. Using `PUT /users/{user_id}` with **your own** `user_id` returns **410 Gone** with guidance to use `PUT /api/v1/users/me`.

### Immutable fields (any update)

| Field | `PUT /users/me` | `PUT /users/{user_id}` |
|-------|-----------------|-------------------------|
| `username` | Stripped / ignored | **400** if sent |
| `role_type` | Not in schema | **400** if sent |
| `institution_id` | Rejected if sent | **400** if sent |

**B2B backend portal:** For “edit user” on **another** user, show username, `role_type`, and `institution_id` as read-only and omit them from the JSON body.

Other fields (email, names, **`mobile_number`**, role_name, markets, employer_id, status, etc.) follow API and permission rules. Changing **`mobile_number`** resets mobile verification flags (see [§2.2](#22-verification-flags-read-only-sms-is-post-mvp)). Changing **`email`** to a new value starts the email-change flow ([§3.6](#36-changing-email-edit-and-verify-flow)).

### Summary

| Operation | Endpoint | Username / role_type / institution_id |
|-----------|----------|----------------------------------------|
| Update my profile | `PUT /users/me` | Immutable — do not send |
| Update another user | `PUT /users/{user_id}` | Immutable — **400** if `username` sent |

---

## 6. Self-service: `/users/me` and 410 on self-use of `/{user_id}`

As of **March 2026**, self-operations must use **`/me`**. Calling **`GET` / `PUT` / `GET .../enriched`** on **`/users/{user_id}`** when `user_id` equals the current user returns **410 Gone** with a message to use `/users/me` instead.

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/users/me` | GET | Current user profile (enriched) |
| `/api/v1/users/me` | PUT | Update current user |
| `/api/v1/users/me/verify-email-change` | POST | Complete pending email change with code from email ([§3.6](#36-changing-email-edit-and-verify-flow)) |
| `/api/v1/users/me/terminate` | PUT | Terminate (archive) current user |
| `/api/v1/users/me/employer` | PUT | Assign employer (Customers only) |

### 410 for self-use of `/{user_id}`

| Endpoint | When `user_id` = current user | Use instead |
|----------|-------------------------------|-------------|
| `GET /users/{user_id}` | 410 | `GET /users/me` |
| `PUT /users/{user_id}` | 410 | `PUT /users/me` |
| `GET /users/enriched/{user_id}` | 410 | `GET /users/me` |

**Admins** still use `/{user_id}` for **other** users only.

### Usage by role (short)

- **Customers / Operators:** `/me` only for self; no admin user routes.
- **Employee Admin / Supplier Admin / Internal:** `/me` for self; `/{user_id}` for managing **other** users.

### TypeScript examples

```typescript
async function getMyProfile() {
  const res = await fetch("/api/v1/users/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}

async function updateMyProfile(updates: Record<string, unknown>) {
  const res = await fetch("/api/v1/users/me", {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(updates),
  });
  return res.json();
}

// Admin: another user only
async function updateOtherUser(userId: string, updates: Record<string, unknown>) {
  return fetch(`/api/v1/users/${userId}`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(updates),
  }).then((r) => r.json());
}
```

### Migration

Replace any call where the URL `user_id` equals the JWT’s user id with `/users/me` for GET/PUT/enriched-get.

Deprecation monitoring (when applicable): responses may include headers such as `X-Deprecated-Endpoint` during transition; prefer `/me` regardless.

**Related:** [API_DEPRECATION_PLAN.md](../../zArchive/roadmap/API_DEPRECATION_PLAN.md).

---

## 7. User and market (`market_id` / `market_ids`)

**Audience:** B2C and B2B. Describes backend storage and how to use **user–market** fields in API responses and writes.

### 7.1 What is stored where

| Storage | Meaning |
|---------|---------|
| **`user_info.market_id`** | **Primary** assigned market (UUID, NOT NULL). One per user. |
| **`user_market_assignment` (v2)** | All assigned markets: `(user_id, market_id, is_primary)`. `user_info.market_id` matches the primary row. |

- **Primary market** is always `user_info.market_id`.
- **Full list** (primary first) is `market_ids` on API responses; if there are no multi-market rows, the backend treats `market_id` as the only assignment.
- **Customers:** Typically one market (default at signup). B2C can treat `market_id` or `market_ids[0]` as the home market for plans/subscriptions.
- **B2B:** One or multiple markets. **Global** users (Admin, Super Admin, Supplier Admin, Global Manager) may be assigned the **Global Marketplace** (`00000000-0000-0000-0000-000000000001`) meaning “all markets.”

### 7.2 API responses

**`GET /api/v1/users/me`** (and user list/enriched list shapes) include:

- **`market_id`** — primary market.
- **`market_ids`** — all markets, **primary first** (v2; otherwise effectively `[market_id]`).

**B2C:** Use `market_id` / `market_ids[0]` to restore the market selector after login. See **[MARKET_AND_SCOPE_GUIDELINE.md](./MARKET_AND_SCOPE_GUIDELINE.md)**.

**B2B:** Use the same fields for market-scoped APIs. If `market_id` is the Global Marketplace UUID, treat as “no market filter” / all markets.

### 7.3 Create / update (sending market)

**`POST /api/v1/users/`**

- **`market_id`** (optional for Admin/Super Admin/Supplier Admin): primary; defaults to Global Marketplace for those roles when omitted. **Required** for Manager/Operator (with rules; typically not Global unless creator is Super Admin).
- **`market_ids`** (optional, v2): full set; first element is primary. Validates non-archived markets.

Customers are created via **customer signup**, not this endpoint; signup assigns a default market from `country_code`.

**`PUT /api/v1/users/me`** and **`PUT /api/v1/users/{user_id}`**

- **`market_id`**, **`market_ids`**: same semantics as create where allowed by role.

### 7.4 Global Marketplace and Global Manager

- **Global Marketplace:** `00000000-0000-0000-0000-000000000001`. Not returned by public **`GET /api/v1/leads/markets`** (assignment use). Means “see all markets” for allowed roles.
- **Global Manager** (v2): `role_name` `"Global Manager"` (Internal). Visibility similar to Admin with restricted admin powers; see backend roadmap docs.

### 7.5 B2C cheat sheet

| Need | Source |
|------|--------|
| Signup country list | `GET /api/v1/leads/markets` |
| After login, restore market | `GET /api/v1/users/me` → `market_id` / `market_ids[0]` |
| Plans | Valid `market_id`; see MARKET_AND_SCOPE_GUIDELINE |

### 7.6 B2B cheat sheet

| Need | Source |
|------|--------|
| Assigned market for scoping | `GET /api/v1/users/me` → `market_id` |
| Global user | `market_id === "00000000-0000-0000-0000-000000000001"` |

### 7.7 TypeScript example

```typescript
interface UserMe {
  user_id: string;
  email: string;
  email_verified?: boolean;
  email_verified_at?: string | null;
  /** Present when a PUT just requested an email change (§3.6). */
  email_change_message?: string | null;
  role_type: string;
  role_name: string;
  institution_id: string;
  market_id: string;
  market_ids: string[];
  mobile_number?: string | null;
  mobile_number_verified?: boolean;
  mobile_number_verified_at?: string | null;
}

async function restoreSelectedMarket(
  marketsFromAvailable: { market_id: string; country_code: string }[],
): Promise<{ market_id: string; country_code: string } | null> {
  const me: UserMe = await fetch("/api/v1/users/me", {
    headers: { Authorization: `Bearer ${token}` },
  }).then((r) => r.json());
  const primaryId = me.market_id ?? me.market_ids?.[0];
  if (!primaryId) return null;
  const found = marketsFromAvailable.find((m) => m.market_id === primaryId);
  return found ?? null;
}
```

**Also see:** [MARKET_AND_SCOPE_GUIDELINE.md](./MARKET_AND_SCOPE_GUIDELINE.md) (subscriptions and scope), roadmaps `USER_MARKET_ASSIGNMENT_DESIGN.md`, `USER_MARKET_AND_GLOBAL_MANAGER_V2.md`.

---

## 8. Forgot username

**`POST /api/v1/auth/forgot-username`** — no `Authorization` header. Rate limited (e.g. 429 per IP).

### Request body

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `email` | string | Yes | Normalized lowercase |
| `send_password_reset` | boolean | No | If `true`, also trigger password reset flow for that email. Default `false`. |

```json
{
  "email": "user@example.com",
  "send_password_reset": false
}
```

### Success

**200 OK** — generic body only (no username in JSON — avoid enumeration), e.g.:

```json
{
  "success": true,
  "message": "If an account exists for this email, we have sent your username to it."
}
```

### Security

- Do **not** return the username in the API response; email only.
- Same success shape whether or not the email exists.

---

## 9. Password recovery

**Status:** Backend implemented — clients implement forgot + reset UI.

### 9.1 Request reset code

**`POST /api/v1/auth/forgot-password`**

- **Auth:** none  
- **Body:** `{ "email": "user@example.com" }`  
- **Response:** Always **200** with a generic success message (even if email unknown — anti-enumeration).

```typescript
interface ForgotPasswordRequest {
  email: string;
}

interface ForgotPasswordResponse {
  success: boolean;
  message: string;
}
```

### 9.2 Reset password

**`POST /api/v1/auth/reset-password`**

- **Auth:** none  
- **Body:** `code` (6-digit from email) **or** legacy `token`, plus `new_password` (min 8 characters).

```typescript
interface ResetPasswordRequest {
  code?: string;
  token?: string;
  new_password: string;
}

interface ResetPasswordResponse {
  success: boolean;
  message: string;
  /** Present on success: JWT for auto-login; includes `locale` claim like login. */
  access_token?: string;
  /** e.g. `"bearer"` when `access_token` is set */
  token_type?: string;
}
```

- **Success:** The API may return **`access_token`** and **`token_type`** so the client can establish a session without a separate login. Token claims match login (including **`locale`**). See [LANGUAGE_AND_LOCALE_FOR_CLIENTS.md](./LANGUAGE_AND_LOCALE_FOR_CLIENTS.md).
- **Errors:** e.g. **400** `"Invalid or expired reset code."`  
- **Rules:** Code validity window and single-use behavior are enforced server-side.
- **Email verification:** On success, the API sets **`email_verified`** and **`email_verified_at`** for that user (proves control of the mailbox). See [§3.5](#35-email-verification-on-the-account).

### 9.3 Client checklist

- Normalize **email** with `.toLowerCase().trim()` before forgot-password (see [§3](#3-username-and-email-lowercase)).
- Use **HTTPS** in production.
- After success, clear sensitive fields and redirect to login.

### 9.4 Long-form UI samples

Extended React, SwiftUI, and Jetpack Compose examples (deep links, multi-device notes) live in the archived copy:  
**[PASSWORD_RECOVERY_CLIENT.md](../../zArchive/api/shared_client/PASSWORD_RECOVERY_CLIENT.md)**.

**Internal backend reference:** [PASSWORD_RECOVERY.md](../internal/PASSWORD_RECOVERY.md).

---

## 10. Related documentation

| Topic | Document |
|-------|----------|
| Language, locale, enums labels, JWT `locale` | [LANGUAGE_AND_LOCALE_FOR_CLIENTS.md](./LANGUAGE_AND_LOCALE_FOR_CLIENTS.md) |
| Permissions by role | [API_PERMISSIONS_BY_ROLE.md](./API_PERMISSIONS_BY_ROLE.md) |
| Lead endpoints (incl. email-registered index) | [LEADS_API_SCOPE.md](./LEADS_API_SCOPE.md) |
| B2C signup email verification | [CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md](../b2c_client/CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md) |
| Markets, scope, subscriptions (consolidated) | [MARKET_AND_SCOPE_GUIDELINE.md](./MARKET_AND_SCOPE_GUIDELINE.md) |
| Mobile verification roadmap (MVP vs Twilio) | [MOBILE_VERIFICATION_ROADMAP.md](../../roadmap/MOBILE_VERIFICATION_ROADMAP.md) |
| Enriched endpoints | [ENRICHED_ENDPOINT_PATTERN.md](./ENRICHED_ENDPOINT_PATTERN.md) |
| Scoping for UI | [SCOPING_BEHAVIOR_FOR_UI.md](./SCOPING_BEHAVIOR_FOR_UI.md) |
| Deprecation / `/me` rollout | [API_DEPRECATION_PLAN.md](../../zArchive/roadmap/API_DEPRECATION_PLAN.md) |
| Merged doc sources (archived) | [zArchive/api/shared_client/README.md](../../zArchive/api/shared_client/README.md) |

**Historical copies** of the per-topic client guides merged into this file are under **`docs/zArchive/api/shared_client/`** for reference.
