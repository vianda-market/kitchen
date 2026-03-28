# Language, locale, and i18n scaffolding (for client agents)

**Audience:** B2B (kitchen-web) and B2C (kitchen-mobile) client developers and AI agents integrating the Kitchen API.  
**Purpose:** Single reference for how the backend exposes **language/locale**, what clients should send, and what is **not** localized yet.  
**Last updated:** March 2026

---

## Table of contents

1. [Supported locales](#1-supported-locales)  
2. [What clients should send](#2-what-clients-should-send)  
3. [Signals the backend exposes](#3-signals-the-backend-exposes)  
4. [Pre-authentication: markets and UI language](#4-pre-authentication-markets-and-ui-language)  
5. [Authenticated user: `locale` on the user model](#5-authenticated-user-locale-on-the-user-model)  
6. [JWT access token: `locale` claim](#6-jwt-access-token-locale-claim)  
7. [Password reset: new session token](#7-password-reset-new-session-token)  
8. [Enums API: labeled dropdowns](#8-enums-api-labeled-dropdowns)  
9. [Response header: `X-Content-Language`](#9-response-header-x-content-language)  
10. [What is not localized yet (MVP)](#10-what-is-not-localized-yet-mvp)  
11. [Implementation checklist for clients](#11-implementation-checklist-for-clients)  
12. [Related documentation](#12-related-documentation)

---

## 1. Supported locales

The API uses **ISO 639-1 short codes** only (no `en-US` / `es-AR` in v1):

| Code | Notes |
|------|--------|
| `en` | Default |
| `es` | Spanish |
| `pt` | Portuguese (Brazil-oriented copy where translated) |

Invalid locale values on write (e.g. `PUT /users/me` with `locale: "fr"`) return **422** validation errors.

The server configuration mirrors this (`DEFAULT_LOCALE`, `SUPPORTED_LOCALES` in backend settings). Adding a language later requires schema CHECKs, settings, and catalog updates together.

---

## 2. What clients should send

1. **`Accept-Language`** on requests (e.g. `es-AR,es;q=0.9,en;q=0.8`). The backend parses the first **supported** primary tag (`es`, `en`, `pt`). Used for unauthenticated flows and as a fallback when the user has no stored preference.
2. **Canonical enum codes** in request bodies (e.g. `street_type: "St"`, `address_type: ["Customer Home"]`). Never send translated labels to the API; labels are for display only.
3. After login, prefer **`user.locale`** from **`GET /api/v1/users/me`** (or enriched user) when choosing UI language, and refresh when the user changes locale via **`PUT`**.

---

## 3. Signals the backend exposes

| Signal | Source | Use on client |
|--------|--------|----------------|
| **`language`** on market objects | `market_info.language` (DB) | Default UI language for a **country/market** before signup |
| **`locale`** on user objects | `user_info.locale` (DB) | Persisted user preference |
| **`locale`** in JWT payload | Issued at login, B2C verify, password reset | Quick read without `/users/me`; **can be stale** after profile `PUT` — see [§6](#6-jwt-access-token-locale-claim) |
| **`?language=`** on `GET /api/v1/enums` | Query param | Which translation map to use for **labels** in that response |
| **`X-Content-Language`** response header | Middleware (header-based) | Hint only; **not** the same as DB-resolved user locale for authenticated users — see [§9](#9-response-header-x-content-language) |

**Authoritative order for “what language is this user using?”** when implementing server-driven copy later: resolved locale from backend dependencies is **`user_info.locale` (if authenticated)** → **`Accept-Language`** → **default `en`**. Clients should align UI with `user.locale` when available.

---

## 4. Pre-authentication: markets and UI language

**`GET /api/v1/leads/markets`** (no auth, rate-limited) returns a minimal list of markets available for signup country selection. Each item includes:

- `country_code`
- `country_name`
- **`language`** — ISO 639-1 code for that market (`es` for AR/PE/CL/MX, `en` for US/Global policy, `pt` for BR, etc.)

Use **`language`** from the row the user selects (or the app’s default market) to set **initial app UI language** before a `user_info` row exists.

Details and other lead endpoints: [LEADS_API_SCOPE.md](./LEADS_API_SCOPE.md).

---

## 5. Authenticated user: `locale` on the user model

User responses (including **`UserResponseSchema`** and **`UserEnrichedResponseSchema`**) include **`locale`**.

- **`PUT /api/v1/users/me`** and **`PUT /api/v1/users/{user_id}`** (where allowed) accept an optional **`locale`** field; invalid values → **422**.
- B2C signup: initial **`locale`** is set from the **market’s `language`** at **email verification / complete signup** time (pending signup stores `market_id`; locale is not duplicated on the pending row).

Profile and update rules: [USER_MODEL_FOR_CLIENTS.md](./USER_MODEL_FOR_CLIENTS.md).

---

## 6. JWT access token: `locale` claim

Access tokens include a **`locale`** string claim alongside `sub`, `role_type`, `role_name`, `institution_id`, and optional subscription-related claims.

**Important:** If the user updates **`locale`** via **`PUT /users/me`**, the **JWT is not rotated** automatically. The claim may be **stale** until the next login, B2C verify, or password reset that returns a new token. For accurate UI language after a settings change, **re-read `user.locale` from the user API** or **refresh the token** using a flow that reissues JWTs.

Older tokens without `locale` may still exist; the API tolerates missing claim; resolution logic prefers **database** `user_info.locale` for authenticated requests when using server-side `get_resolved_locale`.

---

## 7. Password reset: new session token

**`POST /api/v1/auth/reset-password`** on success returns:

- `success`, `message` (as before)
- **`access_token`** — new JWT (same claim shape as login, including **`locale`**)
- **`token_type`** — typically `bearer`

Clients may **log the user in** with this token instead of forcing a second login. See [USER_MODEL_FOR_CLIENTS.md §9](./USER_MODEL_FOR_CLIENTS.md#92-reset-password) for request/response types.

---

## 8. Enums API: labeled dropdowns

### `GET /api/v1/enums`

- **Query:** `language` (optional, default `en`). Must be one of **`en`**, **`es`**, **`pt`**. Unsupported value → **422**.
- **Response shape (breaking change on v1):** each enum key maps to an object:

```json
{
  "street_type": {
    "values": ["St", "Ave", "Blvd", "Rd", "Dr", "Ln", "Way", "Ct", "Pl", "Cir"],
    "labels": { "St": "Calle", "Ave": "Avenida", "Blvd": "Bulevar" }
  },
  "status_user": {
    "values": ["Active", "Inactive"],
    "labels": { "Active": "Active", "Inactive": "Inactive" }
  }
}
```

- **`values`:** canonical codes stored in the DB and sent in API requests.
- **`labels`:** human-readable strings for the requested `language`. For enums without a dedicated translation map, labels may equal the code (identity map). For **`street_type`** and **`address_type`**, Spanish/Portuguese labels are populated; missing per-locale strings **fall back to English labels**, then to the raw code.

Role keys (`role_type`, `role_name`, …) may still be **omitted for Customer** users — same rules as before; see [ENUM_SERVICE_API.md](./ENUM_SERVICE_API.md).

### `GET /api/v1/enums/{enum_name}`

Still returns a **JSON array of strings** (codes only). Use the **aggregate** `GET /api/v1/enums?language=…` when you need labels.

---

## 9. Response header: `X-Content-Language`

Many responses include **`X-Content-Language: en|es|pt`**, derived from **`Accept-Language`** in middleware (**no DB access**). That means for logged-in users it does **not** necessarily match **`user_info.locale`**.

Use it as a **rough hint** for formatting or fallback copy; prefer **`user.locale`** and **`GET /api/v1/enums?language=…`** for precise behavior.

---

## 10. What is not localized yet (MVP)

Phase 1 is **scaffolding** only:

- Most **`HTTPException` `detail`** strings and database error paths remain **English**.
- **`app/i18n/messages.py`** exists with a small **`get_message`** helper; widespread wiring is **post-MVP** (see [LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md](../../roadmap/LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md) — Post-MVP Phases 2–3).

Do not assume error bodies or Pydantic validation messages follow the user’s locale yet.

---

## 11. Implementation checklist for clients

1. Send **`Accept-Language`** on all API calls (match OS/browser/app language).
2. On signup country picker, read **`language`** from **`GET /api/v1/leads/markets`** and set initial UI locale.
3. After auth, sync UI from **`user.locale`**; after **`PUT /users/me`** with `locale`, refresh profile or token.
4. Load enums via **`GET /api/v1/enums?language={uiLocale}`**; render **`labels`** in UI; submit **`values`** to the API.
5. After password reset, if **`access_token`** is present, store it and decode **`locale`** (or fetch `/users/me`).
6. Do not rely on **`X-Content-Language`** alone for authenticated UX language.

---

## 12. Related documentation

| Topic | Document |
|-------|----------|
| Enum keys, role filtering, single-enum routes | [ENUM_SERVICE_API.md](./ENUM_SERVICE_API.md) |
| User profile, `PUT /users/me`, password reset body | [USER_MODEL_FOR_CLIENTS.md](./USER_MODEL_FOR_CLIENTS.md) |
| Lead endpoints (markets, cities, email-registered) | [LEADS_API_SCOPE.md](./LEADS_API_SCOPE.md) |
| Markets, subscriptions, scope | [MARKET_AND_SCOPE_GUIDELINE.md](./MARKET_AND_SCOPE_GUIDELINE.md) |
| Backend roadmap (Phase 1 done; Phases 2–8 backlog) | [LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md](../../roadmap/LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md) |
| B2C copy-specific notes | [MULTI_LANGUAGE_ROADMAP.md](../../roadmap/b2c_client/MULTI_LANGUAGE_ROADMAP.md) |
