# Roadmap: Language-Aware Enums, Messages, and Locale Centralization

**Status**: Phases 1–5, 7–8 shipped (Phase 6 blocked on push notification infrastructure). **Post-MVP backlog**: Phase 6 (push notifications, blocked), Phase 9 (translation management); **Phase 10** (config-to-DB for ops without deploy) — see [CONFIG_TO_DB_MIGRATION.md](./CONFIG_TO_DB_MIGRATION.md).

**Depends on**: Street Type Enum Onboarding (completed)

**Frontend requirements intake (2026-04-02):** This roadmap incorporates localization requirements from all three frontend agents:
- **vianda-home** (cross-client strategy): `docs/frontend/feedback_for_backend/localization-requirements.md`
- **vianda-platform** (B2B): `docs/frontend/feedback_for_backend/LOCALIZATION_B2B_REQUIREMENTS.md`
- **vianda-app** (B2C): `docs/frontend/feedback_for_backend/localization-requirements.md`

---

## Phase 1 (complete)

- **Data model**: `market_info.language`, `user_info.locale` (CHECK `en`/`es`/`pt`), history/triggers/seed aligned.
- **Auth**: `build_token_data` / `merge_subscription_token_claims` for login, B2C verify, and successful password reset; JWT includes `locale` (DB still wins in `get_resolved_locale`).
- **API**: `GET /api/v1/enums` returns each enum as `{ "values": [...], "labels": { code: display } }` with `?language=` (`422` if unsupported). Public leads/minimal markets expose `language` for pre-auth UI.
- **Locale utilities**: `app/utils/locale.py`, `get_resolved_locale` / `get_resolved_locale_optional`, settings `DEFAULT_LOCALE` / `SUPPORTED_LOCALES`.
- **Middleware**: `ContentLanguageMiddleware` sets **header-only** `X-Content-Language` from `Accept-Language` (documented `add_middleware` order in `application.py`).
- **i18n package**: `app/i18n/enum_labels.py` (`get_label`: locale → `en` → code), `messages.py` stub for Phase 2.

---

## Post-MVP Phases

Backlog for whoever picks up i18n after MVP. Phase 1 (scaffold) is done; these phases build on `app/i18n/messages.py`, `app/i18n/enum_labels.py`, `get_resolved_locale`, and `get_message`.

**Priority order rationale:** Phases 2–3 are quick wins (no schema changes, high client impact). Phase 4 is the largest deliverable (translation storage pattern) and unblocks B2B content authoring and B2C localized display. Phases 5–6 cover error/message localization. Phases 7–9 are lower-priority or longer-term.

---

### Phase 2 — Locales endpoint + market locale enrichment (complete)

**Shipped 2026-04-02.** Quick wins that unblocked all three clients with no schema changes.

#### 2.1 `GET /api/v1/locales` endpoint

Expose the backend's `SUPPORTED_LOCALES` and `DEFAULT_LOCALE` settings as a public, cacheable endpoint.

```http
GET /api/v1/locales
```

```json
{
  "supported": ["en", "es"],
  "default": "en"
}
```

- **Auth:** None (public). Long-TTL cache headers.
- **Consumers:**
  - vianda-home: locale toggle (currently hardcoded to `['en', 'es']`)
  - vianda-platform: `useLocales()` hook for multi-locale content authoring forms — determines how many locale inputs to render
  - vianda-app: language picker in profile screen
- **When Portuguese launches**, all three clients pick it up automatically — no frontend deployments.

#### 2.2 Locale-aware `country_name` and `currency_name`

Market responses currently store `country_name` as a fixed English string. Derive at response time using `Accept-Language` (or `?language=`).

- Use `babel` or `pycountry` to derive `country_name` from `country_code` and `currency_name` from `currency_code` per locale. Zero manual translation needed.
- Apply to: `GET /api/v1/markets/enriched/`, `GET /api/v1/leads/markets`
- **Requested by:** vianda-home (Section 1), vianda-app (endorsed cross-client #1)

#### 2.3 Full derived locale (BCP 47) on market responses

Add a `locale` field to market responses, derived from `language + country_code`:

```json
{
  "country_code": "AR",
  "language": "es",
  "locale": "es-AR"
}
```

- Computed at response time — no storage needed. Map: `(es, AR) → es-AR`, `(pt, BR) → pt-BR`, `(en, US) → en-US`.
- **Consumers:** All clients use this for `Intl.NumberFormat` and `Intl.DateTimeFormat`. Without it, a user with an English-language phone in Argentina sees US-style number formatting for ARS amounts.
- **Requested by:** vianda-home (Section 5), vianda-app (Gap 4 / B2), vianda-platform (Gap 4)

#### 2.4 `currency_code` on leads plan endpoints

Confirm all endpoints returning monetary values include `currency_code` (ISO 4217) alongside the numeric value. Enriched endpoints already do this. Verify `/leads/plans` does too.

- **Requested by:** vianda-home (Section 6), vianda-app (endorsed cross-client #6)

---

### Phase 3 — Cuisine localization strategy (complete)

**Shipped 2026-04-02.** JSONB column on `cuisine` table (Option B — translatable field). Resolved by [CUISINE_MANAGEMENT_ROADMAP.md](./CUISINE_MANAGEMENT_ROADMAP.md).

Cuisines are no longer a static Python list. They are DB-managed records in a `cuisine` lookup table with a supplier suggestion flow for adding new entries. Because the list grows at runtime (not at deploy time), a static label map in `enum_labels.py` would require a code deploy for every new cuisine — unacceptable.

**Schema** (defined in cuisine management roadmap):
```sql
cuisine_name VARCHAR(80) NOT NULL,       -- default / English name, fallback
cuisine_name_i18n JSONB,                 -- { "en": "Italian", "es": "Italiana", "pt": "Italiana" }
```

**Implementation** (owned by cuisine management roadmap, Phase 4):
- Seed records ship with `cuisine_name_i18n` for `en` + `es` + `pt` (covers the continent: US, AR, PE, BR)
- `GET /api/v1/cuisines/?language=es` resolves `cuisine_name_i18n->>'es'` with fallback to `cuisine_name`
- Enriched endpoints (`/leads/restaurants`, `/leads/featured-restaurant`, plate endpoints) resolve via `Accept-Language` header
- Admin CRUD accepts full locale map for authoring translations
- Supplier-submitted cuisines start with `cuisine_name_i18n = NULL`; Internal admins add translations after approval

**Gap**: When Phase 4 (translation storage for admin-authored content) ships JSONB locale maps on other entities (restaurant tagline, plan name, plate description), the `cuisine_name_i18n` column already follows the same pattern — no additional migration needed.

- Apply to: `/leads/restaurants`, `/leads/featured-restaurant`, enriched restaurant endpoints, `/api/v1/cuisines/`
- **Requested by:** vianda-home (Section 4), vianda-app (endorsed cross-client #5)
- **Full specification:** [CUISINE_MANAGEMENT_ROADMAP.md](./CUISINE_MANAGEMENT_ROADMAP.md)

---

### Phase 4 — Translation storage for admin-authored content (complete)

**Shipped 2026-04-02.** JSONB locale maps on Restaurant (tagline, featured fields), Plan (name, marketing_description, features, cta_label), and Product (name, ingredients, description). Dual response contract: enriched returns single value, edit endpoints return full map. Leads featured-restaurant endpoint added.

#### 4.1 Entities and translatable fields

| Entity | Translatable fields | Authored by | Displayed by |
|--------|-------------------|-------------|--------------|
| Restaurant | `tagline` | B2B admin (Supplier) | vianda-home, vianda-app |
| Plan | `name`, `marketing_description`, `features[]`, `cta_label` | B2B admin (Internal) | vianda-home, vianda-app |
| Featured restaurant | `spotlight_label`, `member_perks[]` | B2B admin (Internal) | vianda-home, vianda-app |
| Plate | `name`, `description`, `ingredients` | B2B admin (Supplier) | vianda-app |

**Note on Plates:** vianda-app identifies Plate fields as the **primary content users interact with daily** — these must not be overlooked despite not appearing on vianda-home today.

#### 4.2 Storage pattern — JSON column with locale keys

For a small, well-defined locale set (2–3 languages), use JSON columns:

```json
{
  "tagline": {
    "en": "Three-generation recipes...",
    "es": "Recetas de tres generaciones..."
  }
}
```

**Schema change per translatable field:** Convert `VARCHAR`/`TEXT` columns to `JSONB`. Follow the full [SCHEMA_CHANGE_GUIDE.md](../guidelines/SCHEMA_CHANGE_GUIDE.md) — schema → triggers → seed → DTOs → schemas.

**Alternative considered:** Separate `_translations` table with `(entity_id, field_name, locale, value)`. More normalized but adds JOINs to every content query. JSON columns are simpler for 2–3 locales and avoid the JOIN cost.

#### 4.3 Dual response contract

The same fields must serve two different shapes depending on the consumer:

| Context | Response shape | Example |
|---------|---------------|---------|
| Enriched / leads / B2C GET endpoints | **Single localized value** resolved from `Accept-Language` | `"tagline": "Recetas de tres generaciones..."` |
| Edit / non-enriched GET endpoints (B2B forms) | **Full locale map** | `"tagline": { "en": "Three-generation...", "es": "Recetas de..." }` |
| PUT / POST (B2B write) | **Full locale map** accepted | Missing locales fall back to `en` value |

**Implementation approach:**
- Enriched query functions extract the resolved locale's value from the JSON column in SQL: `tagline->>$locale AS tagline`
- Edit endpoints return the raw JSONB column
- Write endpoints validate the locale map shape (all keys must be in `SUPPORTED_LOCALES`)
- Pydantic schemas: `TaglineLocaleMap = Dict[str, str]` for write/edit; `str` for enriched read

**Requested by:** vianda-home (Section 2–3), vianda-platform (Gap 1a–1c), vianda-app (Gap 3)

#### 4.4 Rollout order

1. **Restaurant** (`tagline`) — smallest surface area, good test case
2. **Plan** (`name`, `marketing_description`, `features[]`, `cta_label`) — high visibility on vianda-home
3. **Featured restaurant** (`spotlight_label`, `member_perks[]`)
4. **Plate** (`name`, `description`, `ingredients`) — highest volume, impacts daily B2C experience

#### 4.5 Migration strategy for existing data

Existing single-language values must be wrapped in the new JSON structure during migration:

```sql
-- Example: migrate restaurant tagline
UPDATE restaurant_info
SET tagline = jsonb_build_object('en', tagline)
WHERE tagline IS NOT NULL AND tagline NOT LIKE '{%';
```

Run as part of `seed.sql` rebuild or a one-time migration script. All existing content becomes the `en` entry.

---

### Phase 5 — Error message and alert localization (complete — foundation + high-traffic)

**Shipped 2026-04-03.** Message catalog expanded to ~37 keys × 3 languages (en/es/pt). `get_message()` wired into `error_messages.py` helpers and `handle_database_exception()`. Email subjects localized via `get_message()` with locale parameter on all 8 send methods. High-traffic enum labels added (status, kitchen_days, subscription_status, discretionary_status, pickup_type). Route-by-route `detail=` audit (289 remaining hardcoded strings) deferred to incremental work.

#### 5.1 Spanish translations in `messages.py`

- Add Spanish translations for **all** keys in the `en` catalog (`error.user_not_found`, `error.duplicate_email`, `alert.email_verified`, etc.).
- Verify **all** enum types that need UI labels have Spanish entries in `app/i18n/enum_labels.py` (not only `street_type` and `address_type`).

#### 5.2 Error plumbing

- Wire `get_message(key, locale)` into `app/utils/error_messages.py` and `handle_database_exception()` — replace hardcoded English with catalog lookups.
- Wire route-level `HTTPException(detail=...)` to use the catalog; pass `locale` from `get_resolved_locale`.

#### 5.3 Full message catalog coverage

- Audit every `detail=` string across routes and replace with `get_message()` where user-facing.
- Pydantic / validation messages: add custom error handlers or validators with translated messages.
- `email_service.py`: Localize subject lines and body text using recipient locale.
- Success strings (e.g. "Email verified successfully") → route through catalog.

#### 5.4 `pt` (Brazilian Portuguese)

Same pattern as `es`, lower priority unless BR launch timing demands it.

**All three clients confirmed their pipelines are ready** — `Accept-Language` is already sent, error `detail` strings are displayed as-is. When the backend ships localized errors, clients benefit automatically.

---

### Phase 6 — Localized push notifications

B2C push notifications are currently English-only server-generated strings. When the backend generates notification content, it must use the **user's `locale`** to select the appropriate language.

**Notification types requiring localization:**
- Reservation reminders ("Your pickup window opens in 30 minutes")
- Plate availability alerts
- Subscription renewal reminders
- Coworker pickup coordination

**Implementation:**
- Notification templates stored server-side must support locale resolution (same pattern as `get_message`)
- Push payload `title` and `body` resolved using `user_info.locale`
- Fallback to `en` if translation missing

**Requested by:** vianda-app (Gap 5 / B3), vianda-home (endorsed as #10)

---

### Phase 7 — User-level locale in emails + middleware (complete — emails + middleware scope)

**Shipped 2026-04-03.** Added `get_user_locale(user_id, db)` helper. Wired locale into 6 of 7 email send call sites (signup stays default `en` — no user yet). `ContentLanguageMiddleware` upgraded to read DB-resolved locale from `request.state.resolved_locale` (set by `get_resolved_locale` dependency); falls back to `Accept-Language` for routes without locale injection. Remaining route-level `get_resolved_locale` injection deferred to incremental work.

---

### Phase 8 — Additional languages + Accept-Language full support (complete)

**8.1 — Additional languages:** `pt` (Brazilian Portuguese) shipped with full coverage in Phase 5 (messages, enum labels). `fr` deferred until a French-speaking market is added — at that point, extend `CHECK` constraints, `SUPPORTED_LOCALES`, and translation dicts.

**8.2 — Accept-Language authenticated override:** Deferred as a product decision. Current behavior (DB `user_info.locale` wins over `Accept-Language` for authenticated requests) is correct for the platform's use case. If a temporary session override is needed later, change the priority order in `get_resolved_locale` to: explicit `Accept-Language` → DB preference → market default → `en`.

---

### Phase 9 — Translation management

Static Python dicts require a deploy to change copy.

- **`message_translation`** (or similar) table: `(message_key, locale, text, is_active, ...)`.
- **Admin API**: e.g. `GET/PUT /api/v1/admin/translations` — Internal-only; update copy without deploy.
- **Caching**: In-memory cache with TTL so every request does not hit the DB.
- **Fallback chain**: DB translation → static file → `en` → raw key.

**Operational rollout** (staged migration, priority vs kitchen/location config): see **§10.4** in [CONFIG_TO_DB_MIGRATION.md](./CONFIG_TO_DB_MIGRATION.md).

---

### Phase 10 — Config-to-DB migration (operational settings without deploy)

Kitchen hours, billing timing, timezone/location maps, enum labels, message copy, and archival retention still live partly in **Python config**. Changing them currently implies a **code deploy**. For multi-market ops (AR, PE, US, …), Internal users need **database-backed** settings and **admin APIs/UI**.

This phase is **broader than i18n**. It includes:

- **10.1** `market_kitchen_config` — per market/day: kitchen open/close, billing run, reservations; cron reads DB; TTL cache; history; admin `GET/PUT .../admin/markets/{id}/kitchen-config`.
- **10.2** `location_info` — `location_id` → `market_id` + IANA `timezone`; Pulumi/scheduler or API consumers; new regions as DB rows.
- **10.3** `enum_label` — `(enum_type, code, locale)` → `label`; admin `GET/PUT .../admin/enum-labels`; aggressive cache.
- **10.4** **Message translations** — same as **Phase 9** above (`message_translation`, admin translations API); listed here for one operational-config backlog.
- **10.5** **Archival** — complete migration from `archival_config.py` + `archival_config_table.sql` toward full DB + admin UI for retention.

**Staged migration (each subsystem):** (1) add DB, keep file; (2) read DB with file fallback; (3) DB authoritative, remove file; (4) admin UI/endpoints.

**Post-MVP priority:** (1) market kitchen config, (2) location config, (3) message translation, (4) enum_label, (5) archival completion.

**Full specification:** **[CONFIG_TO_DB_MIGRATION.md](./CONFIG_TO_DB_MIGRATION.md)**

---

## Cross-client requirements traceability

This table maps every backend deliverable to the frontend agent(s) that requested it, with priority consensus.

| # | Backend deliverable | Priority | vianda-home | vianda-platform | vianda-app |
|---|---|---|---|---|---|
| 2.1 | `GET /api/v1/locales` endpoint | Medium | Section 3 | Gap 2 | Endorsed #4 |
| 2.2 | Locale-aware `country_name` / `currency_name` | High | Section 1 | — | Endorsed #1 |
| 2.3 | Full derived locale (BCP 47) on markets | Medium | Section 5 | Gap 4 | Gap 4 / B2 |
| 2.4 | `currency_code` on leads plan endpoints | High | Section 6 | — | Endorsed #6 |
| 3 | Cuisine localization (JSONB — see [CUISINE_MANAGEMENT_ROADMAP](./CUISINE_MANAGEMENT_ROADMAP.md)) | Medium | Section 4 | — | Endorsed #5 |
| 4 | Translation storage (JSON locale map) | High | Section 2 | Gap 1 | Gap 3 / B1 |
| 4.3 | Dual response contract (single vs map) | High | Section 3 | Gap 1b | Gap 3 |
| 5 | Localized error messages | Low | Section 7 | Gap 5 | Endorsed #7 |
| 6 | Localized push notifications | Medium | — | — | Gap 5 / B3 |
| 7 | `get_resolved_locale` in all response paths | Medium | — | — | — |
| — | Enum labels (`values`/`labels`) | **Done** | — | — | — |
| — | `Accept-Language` + `X-Content-Language` | **Done** | — | — | — |
| — | User `locale` field + JWT claim | **Done** | — | — | — |

---

## Frontend-only work (no backend dependency)

These items were documented by frontend agents but require **no backend changes**. Listed here for completeness and cross-agent visibility.

| Client | Deliverable | Priority |
|--------|-------------|----------|
| vianda-app | Install i18n framework (`i18next` + `react-i18next`), extract all static strings | High |
| vianda-app | Language picker UI in profile screen (uses existing `PUT /users/me` with `locale`) | Medium |
| vianda-app | Use derived locale in `Intl.NumberFormat` / `Intl.DateTimeFormat` (blocked on Phase 2.3) | Medium |
| vianda-platform | Multi-locale form authoring UX (locale tabs + FormConfig `translatable` flag) (blocked on Phase 4) | High |
| vianda-platform | `useLocales()` hook consuming `GET /api/v1/locales` (blocked on Phase 2.1) | Medium |
| vianda-platform | B2B UI language switcher (uses existing `PUT /users/me` with `locale`) | Low |
| vianda-home | Dynamic locale toggle from `/locales` endpoint (blocked on Phase 2.1) | Medium |

---

## Overview

Enable localized content across **all user-facing messages** sent to the UI: enums, error messages, alerts, admin-authored content, and any other text displayed to the user. The backend must **know** what language the user is trying to use, **centralize** where that locale is assigned, and **signal** it to the UI so the UI can adapt (labels, formatting, fallbacks).

**Scope (updated 2026-04-02):** Beyond the original enum labels and error messages, this roadmap now covers:
- **Enum display labels** (e.g. "Calle" vs "Street" for street types) — **Done**
- **Error messages** (validation errors, HTTP error details, `detail` in 4xx/5xx responses)
- **Alerts and notifications** (success toasts, warning banners, push notifications)
- **Admin-authored content** (restaurant taglines, plan names, plate descriptions) — **New, from frontend requirements**
- **Market metadata** (country names, currency names) — **New, from frontend requirements**
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
- **Endpoint**: `GET /api/v1/enums/?language={lang}` with label maps
- **Response**: `{ "street_type": { "values": [...], "labels": { "St": "Calle", "Ave": "Avenida" } }, ... }`

### 3.2 Error Messages

- **Current**: Hardcoded English strings in `error_messages.py`, `handle_database_exception()`, and route `detail=` values
- **Target**: All `detail` strings in HTTPException come from a lookup: `(message_key, locale) -> translated_string`
- **Keys**: Stable message keys (e.g. `error.user_not_found`, `error.duplicate_email`) instead of inline English
- **Fallback**: If translation missing for locale, use English

### 3.3 Alerts and Notifications

- **Examples**: "Address created successfully", "Too many requests. Please try again in 60 seconds.", "Payment method added"
- **Target**: Same lookup pattern: `(alert_key, locale) -> translated_string`
- **Push notifications**: B2C push notification `title`/`body` must also resolve using `user_info.locale` (see Phase 6)

### 3.4 Admin-authored content (NEW)

- **Entities**: Restaurant, Plan, Featured restaurant, Plate (see Phase 4 for full field inventory)
- **Storage**: JSONB columns with locale keys (`{ "en": "...", "es": "..." }`)
- **Display contract**: Enriched/leads endpoints resolve to single value via `Accept-Language`; edit endpoints return full locale map
- **Write contract**: PUT/POST accepts full locale map; missing locales fall back to `en`

### 3.5 Other UI-Bound Messages

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

### Option C: JSONB columns on entity tables (for admin-authored content)

- **Structure**: Translatable fields stored as `{ "en": "...", "es": "..." }` directly on the entity row
- **Pros**: No JOINs, co-located with entity data, natural for small locale sets
- **Cons**: Schema migration needed per field; not suitable for system messages

### Hybrid approach (recommended)

- **System messages** (errors, alerts, notifications): Static Python dicts (Option A) → DB table (Option B) in Phase 9
- **Admin-authored content** (restaurant taglines, plan names, plate descriptions): JSONB columns (Option C) in Phase 4

---

## Client (UI) Responsibilities

1. **Read `X-Content-Language`** from API responses
2. **Use it** for:
   - Date/number/currency formatting (e.g. `Intl.DateTimeFormat`, `Intl.NumberFormat`)
   - Client-side fallbacks when backend doesn't localize something yet
   - Ensuring UI language mode matches backend where applicable
3. **Send `Accept-Language`** header on requests (e.g. from browser or app locale) so backend can fall back when user/market don't specify
4. **Use `locale` from market responses** (Phase 2.3) for `Intl` formatting instead of device/browser locale

---

## Out of Scope (For Now)

- Translation management UI (admin UI to edit translations) — deferred to Phase 9
- Right-to-left (RTL) layout (handled purely by frontend)
- Pluralization rules (use simple translations first; add later if needed)

---

## References

- [LANGUAGE_AND_LOCALE_FOR_CLIENTS.md](../api/shared_client/LANGUAGE_AND_LOCALE_FOR_CLIENTS.md) — Backend i18n scaffolding (what's already shipped)
- [ENUM_SERVICE_API.md](../api/shared_client/ENUM_SERVICE_API.md) — Current enum API
- [CUISINE_MANAGEMENT_ROADMAP.md](./CUISINE_MANAGEMENT_ROADMAP.md) — Cuisine lookup table, supplier suggestions, localization (Phase 3 resolution)
- [SCHEMA_CHANGE_GUIDE.md](../guidelines/SCHEMA_CHANGE_GUIDE.md) — Required process for Phase 4 column changes
- [CONFIG_TO_DB_MIGRATION.md](./CONFIG_TO_DB_MIGRATION.md) — Phase 10 config-to-DB specification
- `app/utils/error_messages.py` — Current error message definitions
- `app/i18n/enum_labels.py` — Enum label translations
- `app/i18n/messages.py` — Message catalog stub
