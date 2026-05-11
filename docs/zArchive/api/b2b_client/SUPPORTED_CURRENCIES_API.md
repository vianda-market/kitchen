# Supported Currencies API (B2B)

**Status**: Implemented.  
**Audience**: B2B client (kitchen-web, Employee back-office).

The backend exposes a **supported currencies** list (single source of truth). Use it to drive the Currency dropdown; when creating a credit currency, send **currency name** only — the backend assigns `currency_code`.

---

## Client integration overview

| Step | Action |
|------|--------|
| 1 | Call `GET /api/v1/currencies/` (Employee auth) to load the supported list. |
| 2 | Build the **Currency** dropdown from the response (e.g. options = `currency_name` as label; value = same `currency_name` for submit). Optionally show `currency_code` next to the name (e.g. "US Dollar (USD)"). |
| 3 | **Create Credit Currency**: On submit, send `currency_name`, `credit_value_local_currency`, and `currency_conversion_usd`. Do **not** send `currency_code`. |
| 4 | Use the created `credit_currency_id` from the response when creating a market or elsewhere. |

**Where to use**: Create Credit Currency form; Create Market flow (when creating or choosing a credit currency). Do **not** hardcode currency names or codes — the list is backend-controlled and may change.

---

## Supported currencies list (dropdown)

Use this endpoint to populate the **Currency** dropdown when creating a credit currency or in the Create Market flow (where a credit currency is chosen or created first).

### Endpoint

- **Method/Path**: `GET /api/v1/currencies/`
- **Auth**: Employee only (Bearer token). Same as other back-office endpoints (e.g. countries, credit-currencies).

### Response

JSON array of objects:

- `currency_name` (string) – display name, e.g. `"US Dollar"`, `"Argentine Peso"`
- `currency_code` (string) – ISO 4217 code, e.g. `"USD"`, `"ARS"`

**Ordering**: Sorted by `currency_name` (case-insensitive) for consistent dropdown UX.

**Example**:

```json
[
  { "currency_name": "Argentine Peso", "currency_code": "ARS" },
  { "currency_name": "Canadian Dollar", "currency_code": "CAD" },
  { "currency_name": "US Dollar", "currency_code": "USD" }
]
```

### Use in the UI

- Call `GET /api/v1/currencies/` to build the Currency dropdown (e.g. Create Credit Currency form, or before creating a market).
- Show `currency_name` as the label; when the user selects a currency, use that **exact** `currency_name` when creating a credit currency (see below). Do **not** send `currency_code` on create — the backend assigns it.

---

## Credit currency create (name only; backend assigns code)

When creating a new credit currency, the client sends **currency name**, **credit_value_local_currency**, and **currency_conversion_usd**. The backend resolves `currency_code` from the supported list and stores it.

### Endpoint

- **Method/Path**: `POST /api/v1/credit-currencies/`
- **Auth**: Employee only (Bearer token).

### Request body

| Field           | Type     | Required | Description |
|----------------|----------|----------|-------------|
| `currency_name`| string   | Yes      | Must match a name from `GET /api/v1/currencies/` (exact match). |
| `credit_value_local_currency` | number   | Yes      | Must be > 0. Local currency monetary value per credit. |
| `currency_conversion_usd` | number   | Yes      | Must be > 0. Local units per 1 USD (for plan pricing). |

**Do not send** `currency_code`. The backend assigns it from the supported list.

**Example**:

```json
{
  "currency_name": "US Dollar",
  "credit_value_local_currency": 1.0,
  "currency_conversion_usd": 1.0
}
```

### Response

201 Created. Response body is the created credit currency (includes `credit_currency_id`, `currency_name`, `currency_code`, `credit_value_local_currency`, `currency_conversion_usd`, etc.). Use `credit_currency_id` when creating a market or linking to other resources.

### Validation

- If `currency_name` is not in the supported list, the API returns **400** with detail:  
  `"Currency name not supported. Use GET /api/v1/currencies/ for the list."`
- Use the **exact** `currency_name` returned by `GET /api/v1/currencies/` (e.g. `"US Dollar"` not `"USD"`).

---

## Breaking change / migration

- **Previous behavior**: `POST /api/v1/credit-currencies/` accepted `currency_name`, `currency_code`, and `credit_value_local_currency`.
- **Current behavior**: `currency_code` is **no longer accepted** on create. The backend assigns it from the supported list based on `currency_name`.

**Client migration**:

1. Use `GET /api/v1/currencies/` to populate the Currency dropdown (display `currency_name`, optionally show `currency_code` for clarity).
2. When creating a credit currency, send only `currency_name`, `credit_value_local_currency`, and `currency_conversion_usd`. Remove any code that sends `currency_code` in the create payload.
3. The response of `POST /api/v1/credit-currencies/` still includes `currency_code`; the backend sets it from the supported list.

Clients will be updated after backend implementation; this document is the source of truth for the new contract.

---

## Summary

| Item | Value |
|------|--------|
| List endpoint | `GET /api/v1/currencies/` |
| List response | Array of `{ currency_name, currency_code }` sorted by name |
| Create endpoint | `POST /api/v1/credit-currencies/` |
| Create body | `currency_name` (required), `credit_value_local_currency` (required), `currency_conversion_usd` (required). Do **not** send `currency_code`. |
| Auth | Employee only (Bearer token) |

---

## UI implementation notes

- **Single source of truth**: The list comes from backend config (`app/config/supported_currencies.py`). Use it for all currency dropdowns; avoid hardcoding currency names or codes.
- **Caching**: You can cache the response of `GET /api/v1/currencies/` (e.g. same TTL as supported countries) and invalidate on 401/403 or when the user opens the Create Credit Currency / Create Market form.
- **Dropdown value**: Store the **exact** `currency_name` as the option value so the same string is sent on create. If you display "US Dollar (USD)", the submitted value must still be `"US Dollar"`.
- **400 on create**: If the user somehow submits a name not in the list, the API returns 400 with detail pointing to `GET /api/v1/currencies/`. Show that message and ensure the dropdown is built from the supported list to avoid this.
