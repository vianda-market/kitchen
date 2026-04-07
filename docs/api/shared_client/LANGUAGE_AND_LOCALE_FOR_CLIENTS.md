# Language, locale, and i18n scaffolding (for client agents)

**Audience:** B2B (kitchen-web) and B2C (kitchen-mobile) client developers and AI agents integrating the Kitchen API.  
**Purpose:** Single reference for how the backend exposes **language/locale**, what clients should send, and what is **not** localized yet.  
**Last updated:** April 2026

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
9. [Locales discovery endpoint](#9-locales-discovery-endpoint)  
10. [Market locale enrichment](#10-market-locale-enrichment)  
11. [Response header: `X-Content-Language`](#11-response-header-x-content-language)  
12. [What is not localized yet (MVP)](#12-what-is-not-localized-yet-mvp)  
13. [Implementation checklist for clients](#13-implementation-checklist-for-clients)  
14. [Related documentation](#14-related-documentation)

---

## 1. Supported locales

The API uses **ISO 639-1 short codes** only. There is no locale selector exposed to users — clients offer a **language picker** and the full locale is derived automatically by the backend.

| Code | Language | Market(s) | Derived locale |
|------|----------|-----------|---------------|
| `en` | English (default) | US | `en-US` |
| `es` | Spanish | AR, PE | `es-AR` / `es-PE` (per user's market) |
| `pt` | Portuguese | BR | `pt-BR` |

**Design decision — no locale selector:**
Users select a language (3 options: English, Español, Português). The full locale — which governs number/date/currency formatting and regional dialect display (e.g. "palta" vs "aguacate") — is derived server-side from `language + user's market_id`. There is no reason to expose a locale picker: vianda operates in a small, well-defined set of markets where language and market together fully determine locale. OS locale is used to pre-select the language on first launch; the user can override it.

**Internal users** (who manage entities across markets) inherit locale from the entity or market currently being viewed for dialect-sensitive content.

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
| **`locale`** (BCP 47) on market objects | Computed from `language` + `country_code` | Full locale for `Intl.NumberFormat` / `Intl.DateTimeFormat` (e.g. `es-AR`) — see [§10](#10-market-locale-enrichment) |
| **`locale`** on user objects | `user_info.locale` (DB) | Persisted user preference |
| **`locale`** in JWT payload | Issued at login, B2C verify, password reset | Quick read without `/users/me`; **can be stale** after profile `PUT` — see [§6](#6-jwt-access-token-locale-claim) |
| **`?language=`** on `GET /api/v1/enums` | Query param | Which translation map to use for **labels** in that response |
| **`?language=`** on `GET /api/v1/leads/markets` | Query param (or `Accept-Language` fallback) | Localized `country_name` — see [§10](#10-market-locale-enrichment) |
| **`?language=`** on `GET /api/v1/cuisines` | Query param (or `Accept-Language` fallback) | Localized `cuisine_name` from `cuisine_name_i18n` JSONB |
| **`GET /api/v1/locales`** | Backend settings | Discover supported locales dynamically — see [§9](#9-locales-discovery-endpoint) |
| **`X-Content-Language`** response header | Middleware (header-based) | Hint only; **not** the same as DB-resolved user locale for authenticated users — see [§11](#11-response-header-x-content-language) |

**Authoritative order for “what language is this user using?”** when implementing server-driven copy later: resolved locale from backend dependencies is **`user_info.locale` (if authenticated)** → **`Accept-Language`** → **default `en`**. Clients should align UI with `user.locale` when available.

---

## 4. Pre-authentication: markets and UI language

**`GET /api/v1/leads/markets`** (no auth, rate-limited) returns a minimal list of markets available for signup country selection. Each item includes:

- `country_code`
- `country_name` — localized when `?language=` or `Accept-Language` is provided (see [§10](#10-market-locale-enrichment))
- **`language`** — ISO 639-1 code for that market (`es` for AR/PE/CL/MX, `en` for US/Global policy, `pt` for BR, etc.)
- **`locale`** — BCP 47 tag derived from `language + country_code` (e.g. `es-AR`). Use for `Intl.NumberFormat` / `Intl.DateTimeFormat`.
- `phone_dial_code`, `phone_local_digits` — phone input defaults

Use **`language`** from the row the user selects (or the app’s default market) to set **initial app UI language** before a `user_info` row exists. Use **`locale`** for number/date/currency formatting.

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

## 9. Locales discovery endpoint

### `GET /api/v1/locales`

Public, cacheable endpoint that exposes which locales the platform supports. No authentication required.

**Response:**

```json
{
  "supported": ["en", "es"],
  "default": "en"
}
```

- **Cache:** `Cache-Control: public, max-age=86400` (24 hours). Locales change only on deploy.
- **Use cases:**
  - **vianda-home:** Render locale toggle dynamically (no hardcoded locale list in frontend)
  - **vianda-platform (B2B):** `useLocales()` hook — determines how many locale inputs to render in multi-locale content authoring forms
  - **vianda-app (B2C):** Language picker in profile screen
- When a new language launches (e.g. Portuguese), all clients pick it up automatically — no frontend deployment needed.

---

## 10. Market locale enrichment

### BCP 47 `locale` field on all market responses

All market response schemas now include a computed **`locale`** field — a BCP 47 tag derived from `language + country_code`:

```json
{
  "country_code": "AR",
  "language": "es",
  "locale": "es-AR"
}
```

Use this for `Intl.NumberFormat` and `Intl.DateTimeFormat` instead of device/browser locale. Without it, a user with an English-language phone in Argentina sees US-style number formatting for ARS amounts.

**Present on:** `MarketResponseSchema`, `MarketPublicMinimalSchema`, `MarketPublicResponseSchema`.

### Locale-aware `country_name` and `currency_name`

Market display names are localized at response time based on the user's locale:

| Endpoint | How locale is resolved | Fields localized |
|----------|----------------------|-----------------|
| `GET /api/v1/leads/markets` (no auth) | `?language=` query param → `Accept-Language` header → `en` | `country_name` |
| `GET /api/v1/markets/enriched` (auth) | User's resolved locale (`user.locale` → `Accept-Language` → `en`) | `country_name`, `currency_name` |
| `GET /api/v1/markets/enriched/{id}` (auth) | Same as above | `country_name`, `currency_name` |

**Examples:**

| country_code | `en` | `es` | `pt` |
|---|---|---|---|
| AR | Argentina | Argentina | Argentina |
| US | United States | Estados Unidos | Estados Unidos |
| BR | Brazil | Brasil | Brasil |

| currency_code | `en` | `es` | `pt` |
|---|---|---|---|
| ARS | Argentine Peso | Peso argentino | Peso argentino |
| USD | US Dollar | Dólar estadounidense | Dólar dos Estados Unidos |

Non-enriched admin CRUD endpoints (`GET /markets`, `GET /markets/{id}`) return canonical English names.

---

## 11. Response header: `X-Content-Language`

All responses include **`X-Content-Language: en|es|pt`**. For routes that inject `get_resolved_locale` (enriched endpoints, market endpoints), the header reflects the **DB-resolved user locale** (`user_info.locale`). For other routes, it falls back to **`Accept-Language`** header parsing.

This means for authenticated enriched endpoints, `X-Content-Language` matches the locale used to resolve localized content (cuisine names, taglines, etc.). For routes without locale injection, it remains a rough hint based on the request header.

---

## 12. What is localized and what is not

**Localized (Phases 1–5):**
- Enum labels: 9 enum types have es/pt labels via `GET /api/v1/enums?language=` (status, kitchen_days, subscription_status, discretionary_status, pickup_type, bill_resolution, bill_payout_status, street_type, address_type)
- Entity CRUD error messages (`entity_not_found`, `creation_failed`, etc.) — localized via `get_message()` on routes with `get_resolved_locale`
- Database constraint errors (`handle_database_exception`) — localized when `locale` param is passed
- Email subject lines — all 8 email types resolve subject via `get_message()` with user’s locale
- Market names (`country_name`, `currency_name`) — localized at response time via `pycountry`
- Cuisine names — localized via `cuisine_name_i18n` JSONB
- Admin-authored content (tagline, plan name, product name, etc.) — JSONB `_i18n` columns with locale resolution

**Not yet localized:**
- ~289 route-level `HTTPException(detail=...)` strings remain hardcoded English (incremental adoption in progress)
- Email body text (8 templates) — subjects localized, bodies still English
- Pydantic validation error messages — still English defaults
- Push notification content — not yet implemented

---

## 13. Implementation checklist for clients

1. Send **`Accept-Language`** on all API calls (match OS/browser/app language).
2. On signup country picker, read **`language`** from **`GET /api/v1/leads/markets`** and set initial UI language. Do not build a locale picker — locale is derived from language + market on the backend.
3. Use **`locale`** (BCP 47) from market responses for `Intl.NumberFormat` and `Intl.DateTimeFormat` instead of device/browser locale.
4. After auth, sync UI from **`user.locale`**; after **`PUT /users/me`** with `locale`, refresh profile or token.
5. Load enums via **`GET /api/v1/enums?language={uiLocale}`**; render **`labels`** in UI; submit **`values`** to the API.
6. Fetch **`GET /api/v1/locales`** to discover supported locales dynamically — use for language pickers and multi-locale authoring forms.
7. For localized country names on pre-auth screens, pass **`?language=`** to `GET /api/v1/leads/markets`.
8. After password reset, if **`access_token`** is present, store it and decode **`locale`** (or fetch `/users/me`).
9. Do not rely on **`X-Content-Language`** alone for authenticated UX language.

---

## 14. Related documentation

| Topic | Document |
|-------|----------|
| Enum keys, role filtering, single-enum routes | [ENUM_SERVICE_API.md](./ENUM_SERVICE_API.md) |
| User profile, `PUT /users/me`, password reset body | [USER_MODEL_FOR_CLIENTS.md](./USER_MODEL_FOR_CLIENTS.md) |
| Lead endpoints (markets, cities, email-registered) | [LEADS_API_SCOPE.md](./LEADS_API_SCOPE.md) |
| Markets, subscriptions, scope | [MARKET_AND_SCOPE_GUIDELINE.md](./MARKET_AND_SCOPE_GUIDELINE.md) |
| Backend roadmap (Phase 1 done; Phases 2–10 backlog) | [LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md](../../roadmap/LANGUAGE_AWARE_ENUMS_AND_MARKET_LANGUAGE.md) |
| B2C copy-specific notes | [MULTI_LANGUAGE_ROADMAP.md](../../roadmap/b2c_client/MULTI_LANGUAGE_ROADMAP.md) |
