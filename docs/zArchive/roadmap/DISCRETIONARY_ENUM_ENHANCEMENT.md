# Discretionary process — enum enhancement (from enum fallback feedback)

**Date**: February 2026  
**Status**: Implemented (backend); frontend can adopt same pattern  
**Related**: [ENUM_FALLBACK_AND_LOGGING_FEEDBACK.md](./ENUM_FALLBACK_AND_LOGGING_FEEDBACK.md), [ENUM_FALLBACK_NEXT_STEPS.md](./ENUM_FALLBACK_NEXT_STEPS.md), [DISCRETIONARY_REQUEST_FORM_IMPROVEMENTS.md](./DISCRETIONARY_REQUEST_FORM_IMPROVEMENTS.md)

---

## 1. Requirements (from enum fallback feedback)

The same requirements that applied to the **user form** enum (`status_user`) apply to the **discretionary process**:

1. **API reliability**: `GET /api/v1/enums/` must include a **`discretionary_reason`** key with the canonical list of category values so the discretionary request form can rely on the API instead of a frontend fallback.
2. **Status for discretionary**: The same endpoint includes **`status_discretionary`** for discretionary request status (e.g. Pending, resolved statuses). Use it for any status dropdown on the discretionary flow.
3. **Visibility when fallback is used**: If the frontend uses a fallback (e.g. when the enums request fails or returns empty `discretionary_reason`), it should log a **console.warn** with a fixed prefix so developers and support can see whether the UI is using real API data or the fallback.
4. **Logging (medium/long term)**: Prefer infra-level and backend application logs to see when enums (or assignable) fail; no need for the frontend to send “fallback used” events to the backend unless product explicitly wants a client-originated metric (see ENUM_FALLBACK_AND_LOGGING_FEEDBACK.md Option B/C).

---

## 2. Backend implementation

- **Guaranteed `discretionary_reason` in enums response**  
  In `app/routes/enums.py`, the response from `GET /api/v1/enums/` now always includes `discretionary_reason`:
  - If the enum service provides it, that list is used.
  - If it is missing or empty, the route sets `enums["discretionary_reason"] = DiscretionaryReason.values()` so the response is never without it.

- **Canonical values**  
  Sourced from `app/config/enums/discretionary_reasons.py` (e.g. Marketing Campaign, Credit Refund, Order incorrectly marked as not collected, Full Order Refund). These match the DB enum `discretionary_reason_enum` and the discretionary request form category field.

- **`status_discretionary`**  
  Already set in the same enums route with `Status.get_by_context("discretionary")` for discretionary request status dropdowns.

---

## 3. Frontend recommendations

- **Category (and reason if product aligns)**  
  Use `enumType: 'discretionary_reason'` (or equivalent) and load options from `GET /api/v1/enums/` under the key `discretionary_reason`. Replace free-form `category` with this dropdown per [DISCRETIONARY_REQUEST_FORM_IMPROVEMENTS.md](./DISCRETIONARY_REQUEST_FORM_IMPROVEMENTS.md).

- **Fallback (optional but recommended)**  
  Mirror the `status_user` pattern: if the enums request fails or `discretionary_reason` is missing/empty, use a hardcoded list equal to the current `DiscretionaryReason.values()` and log:
  - `[EnumService] Using discretionary_reason fallback (Marketing Campaign, …) — API returned empty discretionary_reason`
  - or `— enums API request failed` / `— API did not include discretionary_reason` as appropriate.

- **Status dropdown**  
  Use `status_discretionary` from the same enums response for any discretionary request status field.

---

## 4. References

- [ENUM_FALLBACK_AND_LOGGING_FEEDBACK.md](./ENUM_FALLBACK_AND_LOGGING_FEEDBACK.md) — situation, fallback pattern, logging options (A/B/C).
- [ENUM_FALLBACK_NEXT_STEPS.md](./ENUM_FALLBACK_NEXT_STEPS.md) — backend response and next steps for user form and discretionary.
- [ENUM_SERVICE_API.md](../../shared_client/ENUM_SERVICE_API.md) — full enum API, including `discretionary_reason` and `status_discretionary`.
- [DISCRETIONARY_REQUEST_FORM_IMPROVEMENTS.md](./DISCRETIONARY_REQUEST_FORM_IMPROVEMENTS.md) — form fields and use of `discretionary_reason` for category.
