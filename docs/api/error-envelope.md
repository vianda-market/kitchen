# Error Envelope Contract

**Audience**: kitchen agents, frontend integration agents (vianda-platform, vianda-app, vianda-home). Read before implementing error display logic or adding new `HTTPException` raises.

**Permanent doc.** Updated when the wire shape, code namespaces, or handler logic changes. Companion to `docs/api/i18n.md`.

---

## 1. Wire shape

Every user-facing HTTP error response carries a `detail` field. There are two shapes, and they are **intentionally polymorphic** (Q-S2 in design doc):

### Scalar — single-source errors (all non-422 responses)

```json
{
  "detail": {
    "code": "stable.dotted.key",
    "message": "<localized string>",
    "params": { "key": "value" }
  }
}
```

`code` is a stable machine-readable key from the `ErrorCode` registry (`app/i18n/error_codes.py`). Clients may switch on it. `message` is a localized human string; clients may display it directly. `params` contains the structured data used to format the message (empty dict `{}` when there are no params).

### Array — multi-source validation errors (422 only)

```json
{
  "detail": [
    {
      "code": "validation.custom",
      "message": "<localized string>",
      "params": { "field": "body.name", "msg": "Field required", "type": "missing" }
    }
  ]
}
```

One array element per Pydantic field error. The `params.field` is a dot-joined path of the error location (e.g. `"body.name"`, `"query.page_size"`).

**Frontend consumers** handle both shapes via the `resolveErrorMessage` helper in `vianda-hooks` (issue #44). See §6.

---

## 2. Code namespaces

All codes are members of `ErrorCode` (StrEnum) in `app/i18n/error_codes.py`. Codes are **append-only** — once a code ships, it is never renamed or removed (clients may switch on it). See §3 of `docs/api/i18n.md` for the full lifecycle rule.

| Namespace | When emitted | Examples |
|-----------|-------------|---------|
| `request.*` | Pre-route errors: auto-404/405/413, rate limiting. Never raised directly by route handlers. | `request.not_found`, `request.method_not_allowed`, `request.too_large`, `request.rate_limited` |
| `legacy.*` | **Transitional only.** Auto-applied by the catch-all handler to unmigrated bare-string `detail=` raises. NOT for new code. Removed in K-last. | `legacy.uncoded` |
| `validation.*` | Pydantic validation failures (422). K3 ships minimal mapping; detailed type→code mapping lands in K5. | `validation.custom`, `validation.field_required`, `validation.invalid_format` |
| `auth.*` | Authentication and authorization errors. Seeded in K2; fully wired in K6. | `auth.invalid_token`, `auth.captcha_required` |
| `subscription.*` | Subscription lifecycle errors. | `subscription.already_active` |
| Domain codes | Business-rule errors added incrementally during the K6..KN sweep. | `billing.*`, `restaurant.*`, etc. |

---

## 3. How to raise

### New code in a route handler

```python
from app.i18n.envelope import envelope_exception
from app.i18n.error_codes import ErrorCode

# locale comes from the route's DI dependency:
locale: str = Depends(get_resolved_locale)

raise envelope_exception(ErrorCode.AUTH_INVALID_TOKEN, status=401, locale=locale)

# With params:
raise envelope_exception(
    ErrorCode.REQUEST_RATE_LIMITED,
    status=429,
    locale=locale,
    retry_after_seconds=60,
)
```

`envelope_exception` returns an `HTTPException` whose `detail` is already a well-formed envelope dict. The catch-all handler detects `"code"` in `detail` and passes it through unchanged (dispatch branch 1 in §4).

### Getting `locale` inside a route

```python
# Authenticated routes:
from app.auth.dependencies import get_resolved_locale
locale: str = Depends(get_resolved_locale)

# Anonymous-capable routes:
from app.auth.dependencies import get_resolved_locale_optional
locale: str = Depends(get_resolved_locale_optional)
```

Both write the resolved value to `request.state.resolved_locale`. The exception handler reads it back from there (§4).

### Using the lower-level factory directly

```python
from app.i18n.envelope import build_envelope
envelope = build_envelope(ErrorCode.AUTH_INVALID_TOKEN, locale)
raise HTTPException(status_code=401, detail=envelope)
```

This is equivalent to `envelope_exception` but splits construction and raising.

---

## 4. Pre-route errors: catch-all handler

The handler `_envelope_http_exception` (registered in `application.py`) intercepts every `StarletteHTTPException` before FastAPI's default handler. Dispatch order:

1. **`isinstance(exc.detail, dict)` and `"code"` in detail** — already enveloped by `envelope_exception`. Passed through with the same `status_code`. No re-wrapping.

2. **`exc.status_code` in {404, 405, 413}** — pre-route error where FastAPI generated the exception itself (unknown path, wrong method, body too large). Emits the corresponding `request.*` code via the status→code map. Checked before the bare-string branch because FastAPI auto-404/405/413 carries a plain string detail (`"Not Found"`, `"Method Not Allowed"`) that must be replaced, not wrapped in `legacy.uncoded`.

3. **`isinstance(exc.detail, str)`** — bare string from an unmigrated `raise HTTPException(detail="...")` site. Wrapped as `{code: "legacy.uncoded", message: exc.detail, params: {}}`. **Transitional; removed in K-last.**

4. **Fallback** — anything else (e.g. list detail). Wrapped as `legacy.uncoded` with `str(detail)`. **Transitional; removed in K-last.**

### Locale inside the handler

Exception handlers receive only `(request, exc)` — no DI graph. Locale is resolved in two stages:

```python
locale = getattr(request.state, "resolved_locale", None) \
    or resolve_locale_from_header(request.headers.get("Accept-Language"))
```

Stage 1 is populated for in-route raises (DI ran before the exception). Stage 2 fires for pre-route errors (auto-404/405/413) where DI never ran.

---

## 5. Validation handling

The `_envelope_validation_error` handler intercepts `RequestValidationError` (422). It emits one `ErrorEnvelope` per Pydantic field error in a list:

```json
{
  "detail": [
    {"code": "validation.custom", "message": "Field required", "params": {"field": "body.name", "msg": "Field required", "type": "missing"}},
    {"code": "validation.custom", "message": "...", "params": {...}}
  ]
}
```

**K3 mapping**: all Pydantic errors map to `validation.custom`. `params.type` carries the raw Pydantic error type string for debugging.

**K5 mapping** (kitchen#67): detailed type→code mapping will ship with K5. The handler will be extended to map:
- `"missing"` → `validation.field_required`
- `"string_too_short"` → `validation.value_too_short`
- `"string_too_long"` → `validation.value_too_long`
- `"string_pattern_mismatch"` / `"value_error.email"` → `validation.invalid_format`
- `"value_error"` with `I18nValueError` → domain-specific code from the error itself

---

## 6. Frontend contract

Frontends consume both wire shapes via `resolveErrorMessage` from `vianda-hooks` (issue #44):

```typescript
import { resolveErrorMessage } from "vianda-hooks";

// Scalar (single error):
const msg = resolveErrorMessage(error.detail, t);  // string

// Array (422):
const msgs = resolveErrorMessage(error.detail, t, { mode: "perField" });
// → [{field: "body.name", message: "..."}, ...]
```

Algorithm: for each envelope, if `t.exists('errors:' + code)` → use `t(key, params)` (frontend override); else use `envelope.message` verbatim (server-localized string). Bare string `detail` is passed through as-is (pre-K3 legacy compatibility).

`resolveErrorMessage` is the **only** frontend surface for consuming this contract. Frontends must not switch on `code` directly for display — use the helper.

Pointer: `vianda-hooks/docs/hooks/resolveErrorMessage.md` (ships with H1 PR).

---

## 7. Legacy transition

`legacy.uncoded` is **not for new code**. It exists to make unmigrated bare-string `detail=` raises visible in a structured way while the K6..KN sweep runs.

| Phase | State |
|-------|-------|
| K3 (now) | `legacy.uncoded` handler active; all bare-string raises produce it |
| K6..KN | Each sweep PR removes bare-string raises from its scope; `legacy.uncoded` count shrinks |
| K-last | `test_no_bare_string_raises.py` flipped to enforcing; `isinstance(exc.detail, str)` branch removed from handler; `ErrorCode.LEGACY_UNCODED` kept as an alias (codes are append-only) but never raised |

Frontends should treat `legacy.uncoded` as a temporary code — its `message` field carries the original developer string, which may contain ops-jargon not suitable for end users. The K6..KN content audit will replace each site with a properly worded, translated code.

---

*Last updated: K3 — catch-all handlers, minimal validation mapping, and this doc. Next updates: K5 (detailed Pydantic type mapping), K6..KN (sweep), K-last (enforcement).*
