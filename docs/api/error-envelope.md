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
    {"code": "validation.field_required", "message": "This field is required.", "params": {"field": "body.name", "msg": "Field required", "type": "missing"}},
    {"code": "validation.custom", "message": "...", "params": {...}}
  ]
}
```

All `params` objects include `field` (dot-joined location path), `msg` (raw Pydantic message), and `type` (raw Pydantic error type). Domain-specific params from `I18nValueError` are merged in as additional keys.

### Type → code mapping (K5, kitchen#67)

| Pydantic `type` | Code |
|---|---|
| `"missing"` | `validation.field_required` |
| `"string_too_short"` | `validation.value_too_short` |
| `"string_too_long"` | `validation.value_too_long` |
| `"string_pattern_mismatch"` | `validation.invalid_format` |
| `"value_error.email"` and other email variants | `validation.invalid_format` |
| `"value_error"` with `I18nValueError` in ctx | code from `I18nValueError.code` (domain-specific) |
| anything else | `validation.custom` |

### `I18nValueError` — custom validator integration

Custom Pydantic `field_validator` / `model_validator` functions that need a stable code must raise `I18nValueError` instead of plain `ValueError`:

```python
from app.i18n.envelope import I18nValueError

@model_validator(mode="after")
def validate_hold_dates(self):
    if self.hold_end_date <= self.hold_start_date:
        raise I18nValueError("validation.subscription.window_invalid")
    return self
```

The handler `isinstance`-checks `ctx["error"]` for `I18nValueError` and extracts `.code` and `.params`. Plain `ValueError` raises (not `I18nValueError`) still map to `validation.custom`; they should be migrated during the K6..KN sweep.

### Domain-specific validation codes (K5 schema migration)

| Code | Schema | Rule |
|---|---|---|
| `validation.user.invalid_role_combination` | `UserCreateSchema` | role_type + role_name combination |
| `validation.user.unsupported_locale` | `UserUpdateSchema` | locale not in supported list |
| `validation.user.passwords_do_not_match` | `ChangePasswordSchema`, `AdminResetPasswordSchema` | password confirm mismatch |
| `validation.user.new_password_same_as_current` | `ChangePasswordSchema` | new == current password |
| `validation.address.city_required` | `CustomerSignupSchema` | city_metadata_id or city_name required |
| `validation.address.invalid_address_type` | `AddressCreateSchema` | unknown address_type value |
| `validation.address.duplicate_address_type` | `AddressCreateSchema` | duplicate address_type values |
| `validation.address.invalid_street_type` | `AddressCreateSchema` | unknown street_type value |
| `validation.address.country_required` | `AddressCreateSchema` | country_code or country required when place_id absent |
| `validation.address.field_required` | `AddressCreateSchema` | address field required when place_id absent; `params.address_field` names the field |
| `validation.address.city_metadata_id_required` | `AddressCreateSchema` | city_metadata_id required when place_id absent |
| `validation.vianda.kitchen_days_empty` | `ViandaKitchenDayCreateSchema` | kitchen_days list is empty |
| `validation.vianda.kitchen_days_duplicate` | `ViandaKitchenDayCreateSchema` | duplicate days in kitchen_days |
| `validation.discretionary.recipient_required` | `DiscretionaryCreateSchema` | user_id or restaurant_id required |
| `validation.discretionary.conflicting_recipients` | `DiscretionaryCreateSchema` | both user_id and restaurant_id given |
| `validation.discretionary.restaurant_required` | `DiscretionaryCreateSchema` | category requires restaurant_id |
| `validation.holiday.recurring_fields_required` | `RestaurantHolidayCreateSchema`, `RestaurantHolidayUpdateSchema`, `NationalHolidayCreateSchema`, `NationalHolidayUpdateSchema` | recurring_month/day required when is_recurring=true |
| `validation.holiday.list_empty` | `RestaurantHolidayBulkCreateSchema`, `NationalHolidayBulkCreateSchema` | bulk list must not be empty |
| `validation.subscription.window_invalid` | `SubscriptionHoldRequestSchema` | hold_end_date must be after hold_start_date |
| `validation.subscription.window_too_long` | `SubscriptionHoldRequestSchema` | hold window exceeds 3 months |
| `validation.payment.conflicting_address_fields` | `PaymentMethodCreateSchema` | address_id and address_data both provided |
| `validation.payment.unsupported_brand` | `PaymentMethodCreateSchema` | method_type not in allowed list |

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

## 8. Postman collection assertions

The Postman collections under `docs/postman/collections/` are technically clients of this contract, so their assertions must move with the wire shape. K3 lands the contract change; the matching assertion updates ride with frontend Phase 3 adoption PRs.

Until each collection is updated, it is skipped in `scripts/run_newman.sh` (`SKIPPED_COLLECTIONS`). See **kitchen#83** for the current list and the structural gating rule:

> **No frontend Phase 3 adoption PR may merge until the matching Postman collection(s) for that frontend's flows have assertions updated and removed from the skip list.**

Adopting frontends update their slice's collections in the same PR, so the gate snaps back as adoption ships.

A separate sibling list of skipped collections (kitchen#79) covers PR #60 regressions and is unrelated to the envelope contract — different root cause, different remediation.

---

## 9. 5xx error handling (Decision 3) and exception-message redaction (Decision F)

### Why 5xx sites are treated differently

5xx errors are **operator-actionable, not user-actionable**. When a DB query fails or an unexpected exception escapes, there is nothing a user can do — the right audience for that information is ops (logs, alerting). Localizing 5xx messages would add catalog churn for strings no end user can act on. Worse, forwarding `str(e)` or traceback fragments to the client is a security and UX foot-gun: internal table names, SQL, stack paths, or exception details can leak sensitive system information.

The architecture resolves both concerns in one step: let the catch-all handler in `application.py` re-envelope all 5xx responses as `server.internal_error`, so the client sees a generic, localized message regardless of what the original `detail` string said.

### Decision 3 — 5xx raises are exempt from the bare-string lint

Routes and services **may** raise `HTTPException(status_code=500, detail=f"…{e}…")` with a raw English f-string. The AST scan in `app/tests/i18n/test_no_bare_string_raises.py` filters via `_extract_status_code()` against `_5XX_RANGE = range(500, 600)` and skips those sites entirely. No `envelope_exception` wrapping is required for 5xx.

Do **not** migrate existing 5xx f-string sites to `envelope_exception`. A future sweep that adds `envelope_exception(status=500, ...)` at these sites is wrong and must be reverted — see the context in this section for why.

### The catch-all handler normalizes 5xx responses (Decision 3 continued)

`_envelope_http_exception` in `application.py` intercepts all `StarletteHTTPException` instances. When `exc.status_code` is 5xx and the detail is a bare string, the handler replaces the original `detail` with the `server.internal_error` envelope. The client **never** sees the original f-string message — it receives the generic localized `server.internal_error` message only.

The `server.internal_error` code maps to `ErrorCode.SERVER_INTERNAL_ERROR` (K9). Clients should display it as "Something went wrong. Please try again." (locale-resolved via `messages.py`).

### Decision F — never put raw exception data into client-facing envelope `params`

When writing a 5xx raise or a catch block that raises for the client:

- **Log the detail server-side** via `log_error()` (or equivalent). This is where ops discovers the root cause.
- **Raise the generic envelope** — either let the catch-all handle a bare 5xx f-string raise, or raise `envelope_exception(ErrorCode.SERVER_INTERNAL_ERROR, status=500, locale=locale)` with no `params`.
- **Never** put `params={"reason": str(e)}`, `params={"detail": error_msg}`, or any traceback fragment into the `envelope_exception` call at a 5xx site. Such params flow through to the client response body, undoing the redaction that Decision 3 is designed to provide.

Example of correct pattern:

```python
except Exception as e:
    log_error(f"Failed to do X for {entity_id}: {e}")
    raise HTTPException(status_code=500, detail=f"Failed to do X: {e}") from None
    # Catch-all in application.py re-envelopes as server.internal_error — no leak.
```

Example of incorrect pattern (Decision F violation — do not copy):

```python
# WRONG: str(e) leaks to client via params
raise envelope_exception(
    ErrorCode.SOME_ERROR, status=500, locale=locale, reason=str(e)
)
```

### Implication for future sweeps

A `grep` for `HTTPException(.*detail=f"` in `app/` will return non-zero matches — that is intentional, not a sweep gap. Only 4xx f-string and bare-string sites are lint violations. The 5xx f-string sites are documented and expected.

### Known 5xx f-string sites (as of K16)

These sites are deliberately left as bare 5xx f-strings per Decision 3. Do not migrate them during future K-series sweeps:

| File | Line | Detail |
|------|------|--------|
| `app/utils/db.py` | 812 | `"Error executing query: {e}"` |
| `app/utils/db.py` | 929 | `"Error deleting record: {e}"` |
| `app/services/enriched_service.py` | 159 | `"Failed to execute enriched query: {str(e)}"` |
| `app/services/enriched_service.py` | 275 | `"Failed to get enriched {self.base_table}: {str(e)}"` |
| `app/services/enriched_service.py` | 353 | `"Failed to get enriched {self.base_table}: {str(e)}"` |
| `app/services/market_service.py` | 252 | `"Error retrieving markets: {str(e)}"` |
| `app/services/market_service.py` | 560 | `"Error updating market: {str(e)}"` |
| `app/services/entity_service.py` | 3777 | `"Failed to get enriched vianda pickups: {error_msg}"` |
| `app/services/entity_service.py` | 4108–4109 | `"Failed to retrieve enriched restaurant holidays: {str(e)}"` |

If lines shift during future refactors, re-anchor against the function names rather than line numbers.

**Enforcement cross-reference:** `app/tests/i18n/test_no_bare_string_raises.py` (5xx exemption via `_5XX_RANGE`), `app/i18n/error_codes.py` (`ErrorCode.SERVER_INTERNAL_ERROR` — K9).

---

*Last updated: K16 — added §9 (Decision 3 + Decision F policy; 5xx exemption rationale; known sites); dropped d8b0e78 (envelope_exception wrapping of 5xx sites with str(e) params, which violated Decision F). Prior: K5 — detailed Pydantic type→code mapping, I18nValueError subclass, domain-specific validation codes.*
