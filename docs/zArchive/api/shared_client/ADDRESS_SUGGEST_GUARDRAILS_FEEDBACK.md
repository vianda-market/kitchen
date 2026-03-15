# Address Suggest – Backend Guardrails Feedback

**Source**: Frontend (B2B client)  
**Purpose**: Explain an observed client bug, document edge cases that can drive redundant suggest calls, and recommend backend guardrails to reduce unnecessary Google Maps API cost.

**See also**:
- [ADDRESS_AUTOCOMPLETE_CLIENT.md](ADDRESS_AUTOCOMPLETE_CLIENT.md) – API contract and client flow
- [../../infrastructure/UI_EVENTS_AND_PAID_API_LOGGING_PLAN.md](../../infrastructure/UI_EVENTS_AND_PAID_API_LOGGING_PLAN.md) – paid API logging

---

## 1. Situation and Root Cause

### Observed bug (March 2026)

In the B2B address form, when a user selected a suggestion from the address search dropdown, the dropdown closed but immediately reopened with a new set of results (often the selected address plus similar ones).

**Root cause**: After selection, the client updated the input field with the full `display_text` of the chosen suggestion (e.g. `"123 Main St, Springfield, IL 62701, USA"`). The suggest effect depends on the input value, so changing it triggered a new suggest request. The backend returned fresh results, and the client reopened the dropdown.

**Fix**: Client-side. The frontend now uses a "selection lock" ref to skip the suggest API call when the user has just selected an address. This document exists so the backend team can add complementary guardrails.

### Client vs backend responsibility

- **Client fix**: Do not send suggest requests after a selection. Implemented in `AddressSearchField.tsx`.
- **Backend guardrails**: Complementary. Clients can misbehave, bugs can slip through, or other platforms (iOS, Android, B2C) may not implement the same fix. Backend-side deduplication, rate limiting, and caching reduce cost and abuse risk regardless of client behavior.

---

## 2. Edge Cases and Risk Scenarios

| Scenario | Description | Why costly |
|----------|-------------|------------|
| **Post-selection re-search** | Client sends suggest with the full address string right after the user picked one (the bug we fixed). | Redundant; user already chose. |
| **Rapid typing / double debounce** | User types quickly; multiple clients or tabs debounce differently; two near-identical requests within 1–2 seconds. | Same intent, duplicate provider calls. |
| **Identical query repetition** | User re-focuses and retypes the same query; no cache on backend. | Same `q`+`country` hits Google again. |
| **Malicious or buggy clients** | Client loops or sends many requests per second. | Could burn through quotas. |
| **Multi-tab / multi-device** | Same user, multiple sessions, same address search. | Legitimate but duplicative. |

---

## 3. Recommended Backend Guardrails

- **Request deduplication (short window)**: For the same `q`+`country` (+ `province`/`city` if present) within e.g. 5–10 seconds, return a cached response or skip the provider call. Use in-memory cache (TTL) or Redis.
- **Rate limiting per user/tenant**: Throttle suggest calls per user or session to prevent abuse (e.g. 30/min or similar).
- **Logging and monitoring**: Log each suggest invocation (request id, params, no PII) per [UI_EVENTS_AND_PAID_API_LOGGING_PLAN.md](../../infrastructure/UI_EVENTS_AND_PAID_API_LOGGING_PLAN.md) to spot spikes or abuse.
- **Minimum query length**: Enforce `len(q) >= 3` on the backend even if clients relax it.
- **Optional: exact-match shortcut**: If `q` exactly matches a recent result’s `display_text` for the same country, consider returning that single result from cache without calling the provider.

---

## 4. API Contract (unchanged)

- No change to `GET /api/v1/addresses/suggest` parameters or response shape.
- Guardrails are implementation details; clients continue to call as documented in [ADDRESS_AUTOCOMPLETE_CLIENT.md](ADDRESS_AUTOCOMPLETE_CLIENT.md).
