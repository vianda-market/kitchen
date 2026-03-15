# Multi-Language (i18n) Roadmap

**Last updated**: 2026-03-08  
**Status**: Planning

---

## Overview

**Goal**: Add Spanish support and allow users to toggle between English and Spanish. The user's language preference is stored in the backend and adjustable from the Profile.

**Current state**: All UI copy is in English.

---

## Scope

| Area | In scope |
|------|----------|
| **Static UI strings** | Buttons, labels, headings, error messages, placeholders — via i18n bundle |
| **User preference** | Locale stored in `user_info`; editable from Profile |
| **Languages** | English (`en`), Spanish (`es`) |
| **Dynamic content from API** | Backend returns locale-aware strings where applicable (error messages, enum labels, etc.) |

---

## Backend requirements

### User model

| Requirement | Details |
|-------------|---------|
| **Add `locale` to user_info** | New field: `locale` (e.g. `en`, `es`). ISO 639-1. Default `en` for new users. |
| **GET /api/v1/users/me** | Include `locale` in response. |
| **PUT /api/v1/users/me** | Accept `locale` in request body. Validate: must be a supported value (e.g. `en`, `es`). Return updated user with new locale. |

### Locale-aware responses (optional, phased)

| Area | Priority | Notes |
|------|----------|-------|
| **Error messages** | Medium | `detail` in 4xx/5xx could be keyed (e.g. `error_code`) with client doing lookup, or backend returns translated `detail` based on `Accept-Language` header. |
| **Enum labels** | Low | `GET /api/v1/enums/` could accept `Accept-Language` and return localized labels. Or client uses locale to pick from client-side translations. |
| **Dynamic content** | Low | Dishes, plans, market names — if stored in multiple languages, backend could return based on `Accept-Language`. |

**Recommendation**: Start with `locale` in user_info and PUT/GET. Client sends `Accept-Language: <user.locale>` on requests for future backend use. Static UI strings are client-side only initially.

### Questions for backend

- [ ] Confirm `user_info` (or equivalent) can add `locale` field. Schema change required?
- [ ] Valid values for `locale`: `en`, `es` only? Or allow more (e.g. `en-US`, `es-AR`) for future?
- [ ] Should backend use `Accept-Language` header for any responses today, or is that future work?

---

## Frontend requirements

### i18n setup

| Task | Details |
|------|---------|
| **Library** | Use `i18n-js`, `react-i18next`, or Expo's `expo-localization` + JSON bundles. |
| **Bundles** | `en.json`, `es.json` with keys for all UI strings. |
| **Locale provider** | Context or hook that provides current locale and `t()` function. |
| **Persistence** | On app load: fetch user (GET /users/me), use `locale` to set app language. On locale change: PUT /users/me, update context, re-render. |

### Profile integration

| Component | Description |
|-----------|-------------|
| **Language selector** | In Profile (or Preferences): dropdown or list — "English" / "Español". |
| **Save** | On selection change: `PUT /api/v1/users/me` with `{ locale: "es" }` (or `en`). Update AuthContext user; i18n provider switches language; UI updates. |

### Out-of-auth flow

For unauthenticated screens (login, signup, forgot password): use device locale or `en` as default until user logs in and we fetch their `locale`.

---

## Implementation phases

1. **Backend**: Add `locale` to user_info; GET/PUT users/me support.
2. **Frontend**: Add i18n library and `en.json` (extract existing strings); add `es.json` (translate).
3. **Frontend**: Locale provider; Profile language selector; wire to backend.
4. **Polish**: Ensure all screens use `t()`; add `Accept-Language` header from user.locale.

---

## References

- [B2C_ENDPOINTS_OVERVIEW.md](../api/backend/b2c_client/B2C_ENDPOINTS_OVERVIEW.md)
- [USER_SELF_UPDATE_PATTERN.md](../api/backend/shared_client/USER_SELF_UPDATE_PATTERN.md)
