# Enum fallback — backend response and next steps

**Date**: February 2026  
**Status**: Backend response  
**Related**: [ENUM_FALLBACK_AND_LOGGING_FEEDBACK.md](./ENUM_FALLBACK_AND_LOGGING_FEEDBACK.md), [DISCRETIONARY_REQUEST_FORM_IMPROVEMENTS.md](./DISCRETIONARY_REQUEST_FORM_IMPROVEMENTS.md)

---

## 1. Backend actions taken

### 1.1 `GET /api/v1/enums/` — guaranteed keys

- **`status_user`**: Already set explicitly in the enums route with `Status.get_by_context("user")` so the response always includes `["Active", "Inactive"]` for the user form Status dropdown.
- **`status_discretionary`**, **`status_plate_pickup`**, **`status_bill`**: Likewise set explicitly for context-scoped status dropdowns.
- **`discretionary_reason`**: Now **guaranteed** in the response. The enums route sets:
  - `enums["discretionary_reason"] = enums.get("discretionary_reason") or DiscretionaryReason.values()`
  so the discretionary request form category dropdown always receives the canonical list (e.g. Marketing Campaign, Credit Refund, Order incorrectly marked as not collected, Full Order Refund) even if the enum service omits it.

This matches the feedback: the API is the reliable source for `status_user` and `discretionary_reason`, so the frontend can rely on the API instead of fallbacks when the request succeeds.

### 1.2 Assignable roles

- **`GET /api/v1/enums/roles/assignable`** exists and returns the documented shape:
  - `role_type: string[]`
  - `role_name_by_role_type: Record<string, string[]>`
- Backend does not alter CORS; if the frontend sees “failed to load response data”, check CORS configuration for the API base URL and that the response is valid JSON (no 500/HTML).

### 1.3 Logging

- **Short term**: No backend change for “fallback used” events; frontend keeps browser `console.warn` only (as in the feedback doc).
- **Medium/long term**: Prefer **infra-level logging** (Option C): enums and assignable endpoints are already logged on success (`Enums served successfully`, assignable roles request). Use application logs (and CloudTrail if applicable) to correlate API failures with user impact; no frontend→backend “fallback” event unless product explicitly requests a client-originated metric (then Option B with diagnostics endpoint, non-production or opted-in only).

---

## 2. Frontend next steps

- **User form**: Use `status_user` from `GET /api/v1/enums/` for the Status dropdown; keep existing fallback and `console.warn` for resilience when the enums request fails or returns empty.
- **Discretionary request form**: Use `discretionary_reason` from `GET /api/v1/enums/` for the category (and, per product decision, reason) dropdown. Optionally apply the same fallback pattern as `status_user`: if `discretionary_reason` is missing or empty (or enums request fails), use a hardcoded list matching `DiscretionaryReason.values()` and log a `console.warn` with a fixed prefix (e.g. `[EnumService] Using discretionary_reason fallback — …`) so support can see when the UI is using fallback vs API.
- **Assignable roles**: Ensure the request to `GET /api/v1/enums/roles/assignable` is sent with correct auth and base URL; fix any CORS or non-JSON response so Role dropdowns populate without “failed to load response data”.

---

## 3. References

- [ENUM_FALLBACK_AND_LOGGING_FEEDBACK.md](./ENUM_FALLBACK_AND_LOGGING_FEEDBACK.md) — situation, frontend fallback, logging options.
- [ENUM_SERVICE_API.md](../shared_client/ENUM_SERVICE_API.md) — Enum Service API, including `status_user`, `status_discretionary`, `discretionary_reason`, assignable roles.
- [DISCRETIONARY_REQUEST_FORM_IMPROVEMENTS.md](./DISCRETIONARY_REQUEST_FORM_IMPROVEMENTS.md) — discretionary form and use of `discretionary_reason` for category/reason.
