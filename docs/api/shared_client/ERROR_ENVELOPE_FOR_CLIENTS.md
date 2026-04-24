# Error response envelope (for client agents)

**Audience:** frontend agents wiring `vianda-platform` (B2B), `vianda-app` (B2C), and `vianda-home` (marketing) against Kitchen API error responses.
**Purpose:** One page. How to consume Kitchen's error response shape without reading the full implementation plan.
**Last updated:** 2026-04-24.

> **Deeper reading** (only if you need the implementation rationale): `docs/api/error-envelope.md` (contract specifics) and `~/learn/vianda/docs/plans/translation-phase-2-design.md` (design decisions + PR sequencing). This guide is the short version.

---

## 1. What changed on the wire

Every Kitchen HTTP error response — any non-2xx from `/api/v1/*` — now carries a structured `detail` envelope instead of a bare string.

**Before** (legacy, still present at mixed ratio during the rollout sweep):
```json
{"detail": "Invalid token."}
```

**After** (K3 onward, scalar cases):
```json
{"detail": {"code": "auth.invalid_token", "message": "Invalid token.", "params": {}}}
```

**After** (422 validation errors — per-error array):
```json
{"detail": [
  {"code": "validation.custom", "message": "field required", "params": {"field": "email", "msg": "field required", "type": "missing"}},
  {"code": "validation.custom", "message": "invalid format", "params": {"field": "phone", "msg": "invalid format", "type": "value_error"}}
]}
```

Fields:
- `code`: stable dotted-key identifier. Switch on this for control flow (e.g. show captcha widget when `code === "auth.captcha_required"`). Never parse `message` for logic.
- `message`: backend-localized text (`Accept-Language` or the authenticated user's profile locale decides the language). Render this directly for a working default UI.
- `params`: interpolation values if you want to override `message` via your own i18next translation keyed by `code`.

---

## 2. How to consume it (the one-liner)

**Pin `vianda-hooks ≥ 0.4.0` and call `resolveErrorMessage` in your API-client's error path.** It handles the polymorphic shape (string | envelope | envelope-array) so you don't branch.

```ts
import { resolveErrorMessage } from "@vianda-market/hooks";
import { useTranslation } from "react-i18next";

const { t } = useTranslation();

// Inside your API client error handler:
const userFacingText = resolveErrorMessage(responseBody.detail, t);
showToast(userFacingText);
```

**What it does**:
- `detail` is a legacy bare string → returned verbatim.
- `detail` is an envelope → checks `t.exists("errors:" + code)`; if yes, returns `t(...)` with params interpolation; else returns `detail.message`.
- `detail` is an envelope array (422) → maps each element, joins with `"; "` (or pass `{mode: "perField"}` to get `[{field, message}]` for form-field routing).

That is the entire integration surface. No new hook, no context — `resolveErrorMessage` is a pure function.

---

## 3. Handling the rollout (mixed shapes during sweep)

Between K3 landing (handlers flip) and K-last landing (bare-string raises forbidden), ~800 existing `raise HTTPException(detail="...")` sites migrate gradually. Your frontend sees **both** shapes during that window:

- Un-migrated site: `{"detail": "..."}` → Kitchen auto-wraps it into `{"code": "legacy.uncoded", "message": "...", "params": {}}` via the catch-all handler. **You never actually see a bare string during the window** — everything is already an envelope on arrival.
- Migrated site: `{"detail": {"code": "auth.invalid_token", ...}}`.

**Implication for you**: `resolveErrorMessage` handles both (including the theoretical bare-string case if middleware ever leaks one). Ship the helper on day one of K3; no additional shape logic needed.

---

## 4. Per-frontend wiring notes

- **`vianda-platform`** (`src/utils/apiErrors.ts:6`): replace the `getApiErrorMessage(error)` body with a single `resolveErrorMessage(detail, t)` call. The existing Array-detail branch (422) collapses into the same call.
- **`vianda-app`** (`src/api/client.ts:80-124`): `getErrorMessage` already special-cases `captcha_required` and `DUPLICATE_KITCHEN_DAY` on the legacy ad-hoc dict-detail. After the sweep, switch these on `detail.code` (now `auth.captcha_required` and `DUPLICATE_KITCHEN_DAY` — code names preserved; see §5) and fall through to `resolveErrorMessage` for everything else.
- **`vianda-home`** (`src/api/client.ts`): today discards `detail` and throws a generic `Error('API error N')`. Wire `resolveErrorMessage(detail, t)` into the throw path; home gets its first real error messages for free.

---

## 5. Code names you can switch on today

Seeded in K2 (more land per K6..KN sweep PR):

| Code | Status | When it fires |
|------|--------|---------------|
| `request.not_found` | 404 | Unknown path / auto-404 |
| `request.method_not_allowed` | 405 | Wrong HTTP verb |
| `request.too_large` | 413 | Oversize body |
| `request.rate_limited` | 429 | Rate-limited; `params.retry_after_seconds` carries the delay |
| `legacy.uncoded` | any | Transitional auto-wrapping of un-migrated raise sites; disappears at K-last |
| `validation.field_required` | 422 | Missing field (K5 refinement; K3 emits `validation.custom` for all) |
| `validation.invalid_format` / `.value_too_short` / `.value_too_long` | 422 | K5 refinements |
| `validation.custom` | 422 | Default/fallback validation code |
| `auth.invalid_token` | 401 | Bad/expired token |
| `auth.captcha_required` | 401 | Captcha challenge needed |
| `subscription.already_active` | 409 | Already-active subscription |

**Never switch on `legacy.uncoded`** — it is a transitional wrapper, not a contract. When you see it in the mixed-shape window, render `message` and move on.

**Rate limiting**: the 429 envelope replaces the prior flat `{"detail": "rate_limited", "retry_after_seconds": 60}`. The retry hint is now in `detail.params.retry_after_seconds`. See `RATE_LIMIT_HANDLING_CLIENT.md` — update any code that checks `detail === "rate_limited"` to `detail.code === "request.rate_limited"`.

---

## 6. Checklist

When wiring an adoption PR for your frontend:

- [ ] `package.json`: pin `@vianda-market/hooks` ≥ `0.4.0`.
- [ ] API client: import `resolveErrorMessage` and call it from the single error-extraction function.
- [ ] i18next: add an `errors` namespace (or whatever name you pass as `namespace`). Start empty — `message` is your fallback. Populate keys only for cases where you want to override Kitchen's wording.
- [ ] Control flow: any existing `if (detail === "captcha_required")` becomes `if (detail?.code === "auth.captcha_required")`. Same for `DUPLICATE_KITCHEN_DAY`.
- [ ] Rate-limit path: check `detail?.code === "request.rate_limited"`; read delay from `detail?.params?.retry_after_seconds`.
- [ ] Tests: add one unit test per error-code branch your app actually switches on.

No new service, no new context, no new hook. One helper, one dependency version bump.

---

## 7. Related

- `LANGUAGE_AND_LOCALE_FOR_CLIENTS.md` — how Kitchen decides which locale renders `detail.message`.
- `RATE_LIMIT_HANDLING_CLIENT.md` — updated for envelope shape (see §5 note above).
- `docs/api/error-envelope.md` — the full server-side contract (dispatch order, `request.*` namespace rules, code lifecycle).
- `vianda-hooks` docs: `docs/hooks/resolveErrorMessage.md`.
