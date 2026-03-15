# Credit Currency – Edit: Immutable Currency Identity

**Date**: February 2026  
**Purpose**: Backend guardrails for `PUT /api/v1/credit-currencies/{id}` so only **credit_value** and **status** are editable; currency identity (`currency_name`, `currency_code`) is immutable after creation.  
**Status**: Recommendation for backend implementation

---

## Summary

Once a credit currency is created, the **currency identity** should not change. We recommend:

- **Immutable on update**: `currency_name`, `currency_code` (the record refers to one currency from the supported list).
- **Editable on update**: `credit_value`, `status` (and any other lifecycle/attribute fields the API already allows).

Backend should enforce this so that even if a client sends `currency_name` or `currency_code` on PUT, the server ignores or rejects them.

---

## Rationale

1. **Single source of truth**  
   Credit currencies are created from the supported currencies list (`GET /api/v1/currencies/`). The same currency should not be “morphed” into another by editing name/code; that would break references (e.g. markets, plans) that depend on a stable `credit_currency_id` and currency meaning.

2. **Correct flow for a different currency**  
   If a different currency is needed, the correct flow is: create a new credit currency (with the new `currency_name` from the supported list) and use it for new markets/plans; archive or deprecate the old one. No need to allow editing `currency_name` / `currency_code` on an existing record.

3. **Editable vs identity**  
   - **Editable**: `credit_value` (conversion rate / value per credit), `status` (e.g. Active / Inactive). Same logical currency, clear audit: “credit_value changed from 1.0 to 1.5” or “status changed to Inactive.”  
   - **Immutable**: `currency_name`, `currency_code` — changing them would make the record represent a different currency, which is a new entity, not an edit.

4. **Consistency with create**  
   Create already uses `currency_name` only (backend assigns `currency_code` from the supported list). Edit should not allow overriding that identity.

---

## Recommended Backend Behavior

### PUT `/api/v1/credit-currencies/{id}`

- **Accept for update**: `credit_value`, `status` (and any other fields that are explicitly defined as updatable in your API spec).
- **Ignore or reject**: `currency_name`, `currency_code` (and any other identity fields that should not change after creation).

Concrete options:

- **Option A – Ignore**: Do not read `currency_name` or `currency_code` from the request body on update; never change them after insert.
- **Option B – Reject**: If `currency_name` or `currency_code` is present in the body, return `400 Bad Request` with a message such as: `"currency_name and currency_code cannot be changed on an existing credit currency; only credit_value and status are editable."`

Option B is stricter and makes the contract obvious to API consumers.

---

## Frontend Alignment

The B2B frontend (kitchen-web) will:

- On **edit**: Show `currency_name` (and `currency_code` if displayed) as **read-only** in the form. Only `credit_value` and `status` are editable in the UI.
- On **PUT**: Send only `credit_value` and `status`. It will **not** send `currency_name` or `currency_code` on update.

Backend guardrails are still recommended so that:

- Misbehaving or legacy clients cannot change currency identity by mistake.
- The rule is enforced in one place (backend) and documented for all consumers.

---

## References

- Supported currencies: [SUPPORTED_CURRENCIES_API.md](../SUPPORTED_CURRENCIES_API.md) — create uses `currency_name` only; backend assigns `currency_code`.
- Create: `POST /api/v1/credit-currencies/` with `currency_name` + `credit_value` (no `currency_code` on create).
- Edit: this document defines the desired behavior for `PUT /api/v1/credit-currencies/{id}`.
