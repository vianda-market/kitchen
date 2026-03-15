# Address Country Must Match Institution's Market – Backend Guardrail

**Date**: March 2026  
**From**: B2B Frontend  
**Context**: Address create/edit form now restricts the country dropdown to the selected institution's country (derived from the institution's market). We request a corresponding backend guardrail to prevent creating or updating addresses with a `country_code` outside the institution's market.

---

## 1. Business Rule

**An address's `country_code` must match the country of the institution's assigned market.**

- Each institution has a `market_id` (required).
- Each market has a `country_code` (e.g. `US`, `AR`, `PE`).
- Addresses belong to an institution via `institution_id`.
- Therefore: when creating or updating an address, `country_code` must equal the country of the institution's market.

**Rationale**: Institutions operate in specific countries. Allowing addresses in other countries would violate data integrity (e.g. a US institution with a restaurant address in Argentina).

---

## 2. Frontend Implementation (Done)

The B2B frontend now:

- Fetches institutions and markets to build `institution_id → country_code` map.
- Filters the country dropdown so that when an institution is selected, only that institution's country is shown.
- Clears the country field when the user changes the selected institution.
- For Supplier/Customer users (institution pre-filled from JWT), the dropdown shows only their institution's country.

---

## 3. Backend Guardrail Request

**Add validation to `POST /api/v1/addresses/` and `PUT /api/v1/addresses/{address_id}`:**

1. Resolve the address's `institution_id` to the institution record.
2. Resolve the institution's `market_id` to the market record.
3. Read the market's `country_code`.
4. If the request body's `country_code` (or derived from `country`) does **not** match the market's `country_code`, return:
   - **400 Bad Request**
   - Detail message: `"Address country must match the institution's market. Institution {institution_id} is scoped to {market_country_code}."`

**Edge cases:**

- **B2C (Customer):** If `institution_id` is omitted and derived from JWT, use that institution's market for the check.
- **Global Marketplace institution:** If the institution's market is Global Marketplace (e.g. `market_id = 00000000-0000-0000-0000-000000000001`), the market may not have a single country. Either:
  - Reject address creation for Global institution, or
  - Define a policy (e.g. allow any country) and document it.
- **Existing addresses:** For `PUT`, apply the same rule. If an address was created before this guardrail, updating it with a different `country_code` should be rejected if it no longer matches the institution's market.

---

## 4. Example

**Request:**
```json
POST /api/v1/addresses/
{
  "institution_id": "uuid-for-us-institution",
  "user_id": "...",
  "country_code": "AR",
  "province": "Buenos Aires",
  "city": "Buenos Aires",
  ...
}
```

**Institution's market has `country_code: "US"`.**

**Response:**
```
400 Bad Request
{
  "detail": "Address country must match the institution's market. Institution uuid-for-us-institution is scoped to US."
}
```

---

## 5. Summary

| Item | Value |
|------|-------|
| Endpoints | `POST /api/v1/addresses/`, `PUT /api/v1/addresses/{id}` |
| Rule | `address.country_code` must equal `institution.market.country_code` |
| Error | 400 Bad Request with descriptive message |
| Frontend | Implemented; country dropdown filtered by institution |
