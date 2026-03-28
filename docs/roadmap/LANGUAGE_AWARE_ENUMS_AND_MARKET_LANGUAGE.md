# Roadmap: Language-Aware Enums, Messages, and Locale Centralization

**Status**: Phase 1 shipped (backend scaffolding). **Post-MVP backlog**: Phases 2–8 below (i18n and locale); **Phase 9** (config-to-DB for ops without deploy) — see [CONFIG_TO_DB_MIGRATION.md](./CONFIG_TO_DB_MIGRATION.md).

**Depends on**: Street Type Enum Onboarding (completed)

---

## Phase 1 (complete)

- **Data model**: `market_info.language`, `user_info.locale` (CHECK `en`/`es`/`pt`), history/triggers/seed aligned.
- **Auth**: `build_token_data` / `merge_subscription_token_claims` for login, B2C verify, and successful password reset; JWT includes `locale` (DB still wins in `get_resolved_locale`).
- **API**: `GET /api/v1/enums` returns each enum as `{ "values": [...], "labels": { code: display } }` with `?language=` (`422` if unsupported). Public leads/minimal markets expose `language` for pre-auth UI.
- **Locale utilities**: `app/utils/locale.py`, `get_resolved_locale` / `get_resolved_locale_optional`, settings `DEFAULT_LOCALE` / `SUPPORTED_LOCALES`.
- **Middleware**: `ContentLanguageMiddleware` sets **header-only** `X-Content-Language` from `Accept-Language` (documented `add_middleware` order in `application.py`).
- **i18n package**: `app/i18n/enum_labels.py` (`get_label`: locale → `en` → code), `messages.py` stub for Phase 2.

## Phases 2–3 (pending) — summary

Wire `get_message` / localized `detail` for HTTP errors and validation; expand label maps and message catalog beyond MVP enums. **Canonical post-MVP plan**: see **Post-MVP Phases** (Phases 2–8) below; **Phase 9** (operational config in DB) is documented separately.

---

## Post-MVP Phases

Backlog for whoever picks up i18n after MVP. Phase 1 (scaffold) is done; these phases build on `app/i18n/messages.py`, `app/i18n/enum_labels.py`, `get_resolved_locale`, and `get_message`.

### Phase 2 — Spanish translations in messages.py + wire into error handlers

**First post-MVP priority.** The scaffold is in place but `es` (and `pt`) translation dicts are thin or empty in places.

- **`app/i18n/messages.py`**: Add Spanish translations for **all** keys in the `en` catalog (`error.user_not_found`, `error.duplicate_email`, `alert.email_verified`, etc.).
- **`app/i18n/enum_labels.py`**: Verify **all** enum types that need UI labels have Spanish entries (not only `street_type` and `address_type`).
- **Error plumbing**: Wire `get_message(key, locale)` into existing handlers in `app/utils/error_messages.py` and `handle_database_exception()` — replace hardcoded English with catalog lookups.
- **Routes**: Wire route-level `HTTPException(detail=...)` to use the catalog; pass `locale` from `get_resolved_locale` (or equivalent) where practical.
- **`pt` (Brazilian Portuguese)**: Same pattern as `es`, lower priority unless BR launch timing demands it.

### Phase 3 — Full message catalog coverage

- **Audit** every `detail=` string across routes and replace with `get_message()` where the string is user-facing.
- **Pydantic / validation**: Messages are often English-only from default validators — add custom error handlers or validators that look up translated messages.
- **`email_service.py`**: Localize subject lines and body text using recipient locale (from `user_info` or context).
- **Success strings**: e.g. “Email verified successfully”, “Password reset successfully” — route through the catalog.
- **Rate limiting**: `slowapi` default messages — override with localized strings if product requires.

### Phase 4 — User-level locale override in all response paths

`get_resolved_locale` is scaffolded but not injected into most routes yet.

- Inject **`get_resolved_locale`** as a dependency into routes that return user-facing messages.
- **`X-Content-Language`**: Today middleware uses **header-only** resolution. Phase 4 aligns header (or per-response header) with **DB-resolved** locale where required — e.g. pass resolved locale from the route into a response wrapper or custom middleware hook.
- **Email**: Ensure sends use the **recipient’s** locale, not the server default.

### Phase 5 — Additional languages

- **`pt`**: Full translation pass (error messages differ from `es` even when enum codes overlap).
- **`fr`**: If a Canadian (`CA`) or other French-market row is added.
- **Schema**: Extend `CHECK (locale IN (...))` / `language IN (...)` and **`SUPPORTED_LOCALES`** in `app/config/settings.py` — single source propagates to validators and i18n.

### Phase 6 — Dynamic content localization

- **Markets**: `market_info` may expose `country_name` in one language — add `country_name_es`, `country_name_pt`, or a **`market_translations`** table.
- **Catalog**: Product names, ingredients — if restaurants need bilingual menus.
- **Plans**: Plan names today English-only.
- **Kitchen days**: Display names (`Monday` / `Lunes`, etc.) in API responses where the UI shows them.

### Phase 7 — Translation management

Static Python dicts require a deploy to change copy.

- **`message_translation`** (or similar) table: `(message_key, locale, text, is_active, ...)`.
- **Admin API**: e.g. `GET/PUT /api/v1/admin/translations` — Internal-only; update copy without deploy.
- **Caching**: In-memory cache with TTL so every request does not hit the DB.
- **Fallback chain**: DB translation → static file → `en` → raw key.

**Operational rollout** (staged migration, priority vs kitchen/location config): see **§9.4** in [CONFIG_TO_DB_MIGRATION.md](./CONFIG_TO_DB_MIGRATION.md).

### Phase 8 — Accept-Language full support (authenticated override)

Today `resolve_locale_from_header` applies most clearly to unauthenticated flows; authenticated resolution prefers **`user_info.locale`** (see Phase 1).

- **Session / request override**: When the client explicitly signals language (e.g. `Accept-Language` or a dedicated header), optionally treat it as **temporary override** for that request/session: e.g. user browsing in a different language than profile preference.
- **Suggested priority** (product-defined): explicit session/header override → **user DB preference** → market default → `en`.
- **Docs**: Document override behavior in `docs/api/shared_client/USER_MODEL_FOR_CLIENTS.md` (or successor).

### Phase 9 — Config-to-DB migration (operational settings without deploy)

Kitchen hours, billing timing, timezone/location maps, enum labels, message copy, and archival retention still live partly in **Python config**. Changing them currently implies a **code deploy**. For multi-market ops (AR, PE, US, …), Internal users need **database-backed** settings and **admin APIs/UI**.

This phase is **broader than i18n**. It includes:

- **9.1** `market_kitchen_config` — per market/day: kitchen open/close, billing run, reservations; cron reads DB; TTL cache; history; admin `GET/PUT .../admin/markets/{id}/kitchen-config`.
- **9.2** `location_info` — `location_id` → `market_id` + IANA `timezone`; Pulumi/scheduler or API consumers; new regions as DB rows.
- **9.3** `enum_label` — `(enum_type, code, locale)` → `label`; admin `GET/PUT .../admin/enum-labels`; aggressive cache.
- **9.4** **Message translations** — same as **Phase 7** above (`message_translation`, admin translations API); listed here for one operational-config backlog.
- **9.5** **Archival** — complete migration from `archival_config.py` + `archival_config_table.sql` toward full DB + admin UI for retention (remove remaining hardcoded policy where appropriate).

**Staged migration (each subsystem):** (1) add DB, keep file; (2) read DB with file fallback; (3) DB authoritative, remove file; (4) admin UI/endpoints.

**Post-MVP priority:** (1) market kitchen config, (2) location config, (3) message translation, (4) enum_label, (5) archival completion.

**Full specification:** **[CONFIG_TO_DB_MIGRATION.md](./CONFIG_TO_DB_MIGRATION.md)**

---

## Overview

Enable localized content across **all user-facing messages** sent to the UI: enums, error messages, alerts, and any other text displayed to the user. The backend must **know** what language the user is trying to use, **centralize** where that locale is assigned, and **signal** it to the UI so the UI can adapt (labels, formatting, fallbacks).

**Scope expansion**: Beyond enum labels, this roadmap covers:
- **Enum display labels** (e.g. "Calle" vs "Street" for street types)
- **Error messages** (validation errors, HTTP error details, `detail` in 4xx/5xx responses)
- **Alerts and notifications** (success toasts, warning banners, info messages)
- **Any message sent to the UI** (confirmation text, field hints, empty-state copy)

---

## Core Principle: Backend Owns Locale Resolution

The backend must:
1. **Resolve** the user's preferred language from a **centralized source**
2. **Use** that locale when generating any UI-bound message
3. **Include** the resolved locale in responses so the UI knows which language the backend used

The UI receives the locale signal and can:
- Apply consistent formatting (dates, numbers, currency) for that language
- Use the backend-provided localized messages directly
- Optionally provide fallbacks or overrides for edge cases

---

## Part 1: Locale Assignment Centralization

### Where Does Locale Come From?

Locale must be assigned in **one** place and flow consistently. The following resolution order is proposed:

| Priority | Source | Description | When Applicable |
|----------|--------|-------------|-----------------|
| 1 | **User preference** | `user_info.locale` or `user_info.language` (future column) | User has explicitly set language (e.g. settings) |
| 2 | **Market language** | `market_info.language` from the user's assigned market | User has market (B2C signup, B2B institution) |
| 3 | **Request header** | `Accept-Language` HTTP header | Fallback when user/market don't specify |
| 4 | **Default** | `en` (or system default) | Last resort |

### Centralization Points

1. **Database**
   - `market_info.language` VARCHAR(5) (ISO 639-1: `en`, `es`, `pt`)
   - Optional: `user_info.locale` VARCHAR(10) for user override (e.g. `es-AR`, `en-US`)

2. **Service Layer**
   - Single function: `resolve_user_locale(current_user, db) -> str`
   - Resolves from: user preference → user's market language → `Accept-Language` (from request) → default `en`
   - Called by any service or route that needs to generate localized content

3. **Request Context**
   - Locale resolution needs `current_user` and optionally `Request` (for `Accept-Language`)
   - FastAPI dependency: `get_resolved_locale(request, current_user, db) -> str`
   - Injected into routes that return localized content

### Migration: Assigning Locale to Users

- **Existing users**: Locale is **derived** (not stored) from market language on each request until `user_info.locale` exists
- **New users**: At signup, locale can be set from:
  - Client-sent preference (e.g. from browser or app locale)
  - Market language of selected market
- **B2B users**: Locale derived from institution's market(s); primary market language wins

---

## Part 2: Backend Sending Locale Signal to UI

The backend must communicate the resolved locale so the UI can adapt.

### Option A: Response Header (Recommended)

```
X-Content-Language: es
```

- Include in all API responses (or at least those returning user-facing content)
- UI reads header and applies formatting / uses it for client-side fallbacks
- Simple, non-invasive, works with existing response bodies

### Option B: Meta Object in JSON Responses

```json
{
  "meta": { "locale": "es" },
  "data": { ... }
}
```

- Only for endpoints that already return wrapper objects
- Inconsistent for 4xx/5xx error responses (which may not have a wrapper)

### Option C: Both

- **Success responses**: Include `X-Content-Language` header; optional `meta.locale` for wrapped responses
- **Error responses**: Include `X-Content-Language` in error response headers (FastAPI allows custom headers on `HTTPException` via a custom exception handler)

**Recommendation**: Use **`X-Content-Language` header** on all responses. Add an exception handler so 4xx/5xx responses also include it.

---

## Part 3: Localized Content Types

### 3.1 Enum Display Labels

- **Storage**: Backend stores and accepts **codes only** (St, Ave, Blvd, Active, Pending)
- **Display**: Labels vary by language (`St` → "Calle" in Spanish, "Street" in English)
- **Endpoint**: `GET /api/v1/enums/labels?language={lang}` or extended `GET /api/v1/enums/?language={lang}` with label maps
- **Response**: `{ "street_type": { "St": "Calle", "Ave": "Avenida" }, ... }`

### 3.2 Error Messages

- **Current**: Hardcoded English strings in `error_messages.py`, `handle_database_exception()`, and route `detail=` values
- **Target**: All `detail` strings in HTTPException come from a lookup: `(message_key, locale) -> translated_string`
- **Keys**: Stable message keys (e.g. `error.user_not_found`, `error.duplicate_email`) instead of inline English
- **Fallback**: If translation missing for locale, use English

### 3.3 Alerts and Notifications

- **Examples**: "Address created successfully", "Too many requests. Please try again in 60 seconds.", "Payment method added"
- **Target**: Same lookup pattern: `(alert_key, locale) -> translated_string`
- **Context**: Alerts may be returned in response body (`detail`, `message`) or as separate notification structures

### 3.4 Other UI-Bound Messages

- Field validation messages, empty-state copy, confirmation dialogs
- Any string in API responses that is displayed to the user
- Centralize in a **message catalog** (key → translations per language)

---

## Part 4: Translation Storage

### Option A: Static (Python Modules / JSON)

- **Structure**: `{ "en": { "error.user_not_found": "User not found", ... }, "es": { ... } }`
- **Pros**: Simple, no DB, fast
- **Cons**: Requires code deploy to add/change translations

### Option B: Database Table

- **Table**: `message_translation` (message_key, locale, text)
- **Pros**: Runtime management, no deploy for content changes
- **Cons**: More infra, caching required for performance

### Option C: Hybrid

- **Phase 1**: Static for enums + high-traffic error messages
- **Phase 2**: Add DB for user-editable copy (marketing, alerts) if product needs it

**Initial recommendation**: Static (Option A) for predictability and simplicity.

---

## Roadmap Steps

### Phase 1: Locale Centralization

1. **Add `language` to `market_info`**
   - Schema: `language VARCHAR(5)` (ISO 639-1)
   - History: Mirror in `market_history`
   - Seed: Populate for existing markets (AR/PE/CL → `es`, US → `en`, etc.)
   - API: Include `language` in market responses

2. **Create `resolve_user_locale()`**
   - Input: `current_user`, `db`, optional `accept_language_header`
   - Logic: user preference → market language → Accept-Language → `en`
   - Location: `app/utils/locale.py` or `app/services/locale_service.py`

3. **FastAPI dependency `get_resolved_locale`**
   - Depends on `get_current_user`, `get_db`, `Request`
   - Returns locale string for use in routes
   - Use in all routes that return user-facing content (or apply globally via middleware)

4. **Add `X-Content-Language` to responses**
   - Success: Add header in a response middleware or per-route
   - Errors: Custom exception handler that injects header based on `get_resolved_locale` (from request context)
   - Ensure UI can read this to know "backend is responding in Spanish"

### Phase 2: Enum Labels

5. **Enum labels endpoint**
   - `GET /api/v1/enums/labels?language={lang}` or extend `GET /api/v1/enums/?language={lang}`
   - Return per-enum label maps: `{ "street_type": { "St": "Calle", ... }, ... }`
   - If `language` omitted: use default `en`

6. **Translation storage for enums**
   - Static maps: `(enum_type, code, language) -> label`
   - Start with `street_type`, `address_type`; expand as needed

7. **Client flow**
   - Resolve market → get `language`
   - Call enum endpoints with `?language={lang}` (or use labels endpoint)
   - Render dropdowns with labels; submit codes

### Phase 3: Error Messages and Alerts

8. **Message catalog**
   - Create `app/i18n/messages.py` (or similar) with `MESSAGES[locale][key]`
   - Define keys for: `error.user_not_found`, `error.duplicate_email`, `alert.address_created`, etc.
   - Add `get_message(key: str, locale: str, **params) -> str` for interpolation

9. **Refactor error_messages.py**
   - Replace hardcoded strings with `get_message(key, locale)`
   - Routes and exception handlers pass `locale` from `get_resolved_locale`

10. **Refactor route-level `detail` and alerts**
    - All `HTTPException(detail=...)` and success messages use message catalog
    - Ensure `X-Content-Language` matches locale used for messages

### Phase 4: Expand Scope (Optional)

11. **User-level locale override**
    - Add `user_info.locale` for users who want a different language than market
    - Update `resolve_user_locale()` to check user preference first

12. **Additional message types**
    - Field hints, empty states, confirmation dialogs
    - Expand catalog as product demands

---

## Client (UI) Responsibilities

1. **Read `X-Content-Language`** from API responses
2. **Use it** for:
   - Date/number/currency formatting (e.g. `Intl.DateTimeFormat`, `Intl.NumberFormat`)
   - Client-side fallbacks when backend doesn't localize something yet
   - Ensuring UI language mode matches backend where applicable
3. **Send `Accept-Language`** header on requests (e.g. from browser or app locale) so backend can fall back when user/market don't specify

---

## Out of Scope (For Now)

- Translation management UI (admin UI to edit translations)
- Right-to-left (RTL) layout (handled purely by frontend)
- Pluralization rules (use simple translations first; add later if needed)
- Full i18n of every string (prioritize enums, errors, and high-traffic alerts)

---

## References

- [ENUM_SERVICE_API.md](../api/shared_client/ENUM_SERVICE_API.md) – Current enum API
- Street Type Enum Plan (Section 11) – follow-up design for language-aware enums
- `app/utils/error_messages.py` – Current error message definitions
