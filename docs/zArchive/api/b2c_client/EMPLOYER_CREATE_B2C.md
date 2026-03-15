# B2C Create Employer + Address (UI Guide)

> **ARCHIVED (2026-03):** Consolidated into [EMPLOYER_MANAGEMENT_B2C.md](../../../api/b2c_client/EMPLOYER_MANAGEMENT_B2C.md).

**Audience:** B2C client (Customer role). For agents building the **“Register my employer”** UI where the user enters their company name and one address in a single step.  
**Last updated:** 2026-03

---

## Purpose

Customers can register **their employer** (company) together with **one address** in a single API call. The backend creates the employer, creates the address, links them, and optionally assigns this employer to the current user so it appears as “my employer.” The address is stored as a **Customer Employer** address under the Vianda Customers institution; the B2C app does **not** send `institution_id` or `user_id` — the backend sets them from the JWT.

---

## B2C employer-related endpoints (what the Customer can do)

Use this table to align UI options with the API. All require Bearer token (Customer).

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/employers/` | Create a new employer with one address; optionally assign it to the current user (`assign_employer`). |
| POST | `/api/v1/employers/{employer_id}/addresses` | Add another address to an existing employer. Same address body shape as create; use suggest/validate for the new address. B2C omits `institution_id`/`user_id`. |
| PUT | `/api/v1/users/me/employer` | Assign an existing employer to the current user (e.g. after searching and choosing one). Query param: `employer_id`. |
| GET | `/api/v1/employers/enriched/` | List employers with enriched address data. Use e.g. for “My employer” or to pick an employer to assign. |
| GET | `/api/v1/employers/search?search_term=...` | Search employers by name. Use before create (avoid duplicates) or to let the user pick an existing employer and assign it via PUT /users/me/employer. |

---

## What the Customer cannot do (limitations)

- **Customers cannot edit their existing employer’s name or address.**  
  **PUT /api/v1/employers/{employer_id}** (update employer name or `address_id`) and **DELETE /api/v1/employers/{employer_id}** (archive employer) are **Employee-only**. The API returns **403 Forbidden** if a Customer calls them.

- **UI implication:** Do **not** offer an “Edit my employer” or “Edit employer details” flow that changes the employer’s name or main address. If the user needs different details, they can:
  - **Create a new employer** (POST /employers/) with the new name/address and assign it to themselves (PUT /users/me/employer with the new `employer_id`), or
  - **Add another address** to the same employer (POST /employers/{id}/addresses) if they only need an additional location.

- There is no B2C endpoint to update or delete a single address on an employer; address update/delete is handled elsewhere and may be restricted by role. For B2C, the supported pattern is create employer + address, add addresses to employer, and assign employer to self.

---

## Endpoint

| Method | Path | Auth |
|--------|------|------|
| POST   | `/api/v1/employers/` | Bearer token (Customer) |

---

## Request

**Headers**

- `Authorization: Bearer <token>`
- `Content-Type: application/json`

**Body:** `EmployerCreateSchema`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Employer/company name. Max 100 characters. |
| `address` | object | Yes | Full address for the employer location (see below). |
| `assign_employer` | boolean | No | If `true` (default), assign this employer to the current user after creation so it shows as “my employer.” Set to `false` to create the employer + address without linking it to the user. |

**B2C: Do not send** `institution_id` or `user_id` inside `address`. The backend sets both from the authenticated user (Vianda Customers institution and current user).

**Address object** (`address`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `country_code` | string | One of country_code or country | ISO 3166-1 alpha-2 (e.g. `AR`). API normalizes to uppercase. |
| `country` | string | One of country_code or country | Country name (e.g. Argentina); can be used instead of `country_code` so backend can derive code. |
| `province` | string | Yes | Max 50 chars. |
| `city` | string | Yes | Max 50 chars. |
| `postal_code` | string | Yes | Max 20 chars. |
| `street_type` | string | Yes | Code from **GET /api/v1/enums/** (street types), e.g. `St`, `Ave`, `Blvd`. |
| `street_name` | string | Yes | Max 100 chars. |
| `building_number` | string | Yes | Max 20 chars. |
| `apartment_unit` | string | No | Max 20 chars. |
| `floor` | string | No | Max 50 chars. |
| `is_default` | boolean | No | Default `false`. |

Do **not** send `address_type`, `employer_id`, `institution_id`, or `user_id` in `address`; the backend derives or sets them.

---

## Address validation and autocomplete (employer address)

The same **suggest** and **validate** APIs used for other address inputs (e.g. Customer Home, Customer Billing) apply to the employer address. Use them so customers benefit from autocomplete and normalized addresses when inserting the employer address.

| Endpoint | Purpose |
|----------|---------|
| **GET /api/v1/addresses/suggest** | As the user types (e.g. in a single “Address” field or street + number), call with `q=<partial input>` and optionally `country=<code or name>`, `limit=5`. Returns structured **suggestions** that match the address schema. Pre-fill the employer address form from the selected suggestion. |
| **POST /api/v1/addresses/validate** | Before submitting the employer form, send the current address fields (street_name, street_type, building_number, city, province, postal_code, country_code or country_name, etc.) in the request body. Backend returns `is_valid`, `normalized` (canonical fields), `formatted_address`, and optional `message`. Use **normalized** as the `address` object when calling **POST /api/v1/employers/** so the stored employer address is validated and consistent. |

**Auth:** Both suggest and validate require the same Bearer token as **POST /api/v1/employers/**.

**Recommended flow for the employer address block**

1. **Suggest:** User types address (or street + number). Client calls `GET /api/v1/addresses/suggest?q=...&country=...`. Show suggestions in a dropdown or typeahead.
2. **Pre-fill:** On suggestion select, fill employer address fields from the suggestion (street_name, street_type, building_number, city, province, postal_code, country_code). Optionally call validate with that data.
3. **Validate before submit:** Before calling **POST /api/v1/employers/**, call `POST /api/v1/addresses/validate` with the current address form (include `country_code` or `country_name`).
4. **Confirm (optional but recommended):** If `is_valid === true`, show “We recommend this address: [formatted_address]. Use this address?” User accepts → use **normalized** as the `address` in the employer create payload. If user edits, re-validate or submit as-is.
5. **Submit:** Send **POST /api/v1/employers/** with `name`, `assign_employer`, and `address` set to the validated **normalized** object (or current form if you skip confirm). Do **not** add `institution_id` or `user_id` to `address`; backend sets them for B2C.

Full contract (query params, request/response shapes, country handling): [Address Autocomplete and Validation – Client Guide](../shared_client/ADDRESS_AUTOCOMPLETE_CLIENT.md).

**Example (B2C)**

```json
{
  "name": "Acme Corp",
  "assign_employer": true,
  "address": {
    "country_code": "AR",
    "province": "Ciudad Autónoma de Buenos Aires",
    "city": "CABA",
    "postal_code": "1414",
    "street_type": "Ave",
    "street_name": "Santa Fe",
    "building_number": "2567",
    "apartment_unit": "1A",
    "floor": null,
    "is_default": false
  }
}
```

---

## Response

**Success: 201 Created**

Response body is the created employer (e.g. `EmployerResponseSchema`):

- `employer_id` (UUID)
- `name` (string)
- `address_id` (UUID) — the created address linked to this employer
- `is_archived` (boolean)
- `status`
- `created_date`, `modified_date`

Use `employer_id` and `address_id` for navigation or follow-up (e.g. “My employer” screen or add another address later via **POST /api/v1/employers/{employer_id}/addresses**).

---

## Errors

| Status | When | Client behavior |
|--------|------|-----------------|
| 400 | Validation error (missing/invalid fields, invalid `street_type`, etc.) | Show `detail` to the user; fix form. |
| 403 | User is a Supplier without permission to create addresses (e.g. Supplier Operator) | B2C Customers are not restricted; if 403 appears for a Customer, show generic “Not allowed.” |
| 500 | Server or DB error during creation | Show generic error; do not assume employer or address was created. |

---

## UI Implementation Guide

1. **Screen / flow**  
   - One form: “Register my employer” with **Employer name** and **Address** (one section or two steps).  
   - Submit once to **POST /api/v1/employers/** with `name` + `address` + `assign_employer`.

2. **Employer name**  
   - Single text input, required, max 100 characters.

3. **Address fields and validation**  
   - Use the **same address suggest/validate flow** as other B2C address inputs so customers get autocomplete and normalized addresses for the employer address. See **Address validation and autocomplete (employer address)** above and [ADDRESS_AUTOCOMPLETE_CLIENT.md](../shared_client/ADDRESS_AUTOCOMPLETE_CLIENT.md).  
   - **Suggest:** Call **GET /api/v1/addresses/suggest?q=...&country=...** as the user types; pre-fill the employer address form from the selected suggestion.  
   - **Validate:** Before submit, call **POST /api/v1/addresses/validate** with the current address fields; use the returned **normalized** object as the `address` in **POST /api/v1/employers/** (optionally after showing “Use this address?” with `formatted_address`).  
   - **Country:** Send `country_code` (alpha-2) or `country` (name); for suggest use the `country` query param.  
   - **Street type:** From **GET /api/v1/enums/** (street types).  
   - **Province, city, postal_code, street_name, building_number** required; **apartment_unit**, **floor** optional.  
   - Do **not** include `institution_id`, `user_id`, or `address_type` in the payload.

4. **“Use as my employer” (optional)**  
   - Checkbox mapped to `assign_employer`. Default **checked** (true) so that after creation the employer is set as the current user’s employer. Uncheck to create employer + address without assigning.

5. **After success (201)**  
   - Store or use `employer_id` and `address_id` from the response.  
   - Navigate to “My employer” or profile, or show success and the new employer name.  
   - If the user needs to add another address later, use **POST /api/v1/employers/{employer_id}/addresses** (same auth; body is address only; see employer routes).

6. **Optional: search before create**  
   - To avoid duplicates, the UI can call **GET /api/v1/employers/search?search_term=...** or **GET /api/v1/employers/enriched/** so the user can see existing employers before creating a new one. Creation remains **POST /api/v1/employers/**.

---

## References

- **Address autocomplete and validation (suggest/validate):** [ADDRESS_AUTOCOMPLETE_CLIENT.md](../shared_client/ADDRESS_AUTOCOMPLETE_CLIENT.md) — Use these endpoints for the employer address block so customers get the same validation as other address inputs.  
- Address create (B2C omit institution_id/user_id): [ADDRESS_CREATE_B2C.md](./ADDRESS_CREATE_B2C.md)  
- Countries list for dropdown: **GET /api/v1/countries/** (Employee-only; if B2C has a static list or another source, use that for country selection.)  
- Enums (street types, etc.): **GET /api/v1/enums/**  
- Add another address to an employer: **POST /api/v1/employers/{employer_id}/addresses** (same body shape for `address`; B2C still omits institution_id/user_id). For that flow too, use suggest/validate for the address being added.
