# Backend feedback: Employer search and assign (B2C)

**Purpose:** Define the API contract required for the B2C “Register employer” flow where the user can **search existing employers**, select one, then **pick an existing address** or **add a new address** for that employer—or **register a new company** if no match. The B2C client implementation guide is [EMPLOYER_MANAGEMENT_B2C.md](./EMPLOYER_MANAGEMENT_B2C.md).

**Audience:** Backend team. The documented APIs are the source of truth for the B2C client.

---

## Implementation status (as of 2026-03)

The required endpoints are **implemented**. Current backend contract:

| Capability | Endpoint | Status | Notes |
|------------|----------|--------|-------|
| Search employers | `GET /api/v1/employers/search` | **Implemented** | Query: `search_term` (not `q`). Optional: `limit` (default 10, max 50). When empty, returns all employers. |
| List employer addresses | `GET /api/v1/employers/{employer_id}/addresses` | **Implemented** | Returns `List[AddressResponseSchema]`. Optional `city_id` filters by city (address_info.city matches city_info.name). B2C should pass user's `city_id` from profile when available. |
| List supported cities | `GET /api/v1/cities/?country_code=...` | **Implemented** | Returns cities for user profile and address filter. Optional `country_code` (e.g. AR, PE). Auth: Customer or Employee. |
| Assign employer | `PUT /api/v1/users/me/employer` (body: `employer_id`, `address_id`) | **Implemented** | Customers only. Both required. |
| Add address to employer | `POST /api/v1/employers/{employer_id}/addresses` | **Implemented** | B2C omits institution_id/user_id; supports `assign_employer`. |
| User profile city_id | `PUT /api/v1/users/me`, `GET /api/v1/users/me` | **Implemented** | User can set `city_id` (validated against market's country). Enriched response includes `city_id`, `city_name`. |
| Create new employer | `POST /api/v1/employers/` | **Implemented** | Name + address + `assign_employer`. |

See **Section 8** for optional backend improvements.

---

## 1. Context

Today, B2C has a single path: “Register employer” opens a form with **company name** (free text) and **one address**, then `POST /api/v1/employers/` with `assign_employer: true`. There is no way to:

- Search for an existing employer (e.g. “Acme” already in the system).
- Select an existing employer and then choose one of its addresses or add a new address for it.

The desired flow:

1. **Company step:** User types in a search box. Backend returns matching employers. User either **selects an existing employer** or chooses **“Register new company”**.
2. **Address step (existing employer only):** Backend returns **addresses for that employer**. User either **picks an existing address** or **adds a new address** for that employer (same validation as today; `POST /api/v1/employers/{employer_id}/addresses`).
3. **Assign:** User is assigned to the employer via `PUT /api/v1/users/me` with `employer_id` (and optionally a specific address if the product requires it).
4. **New company path:** If user did not select an existing employer, current behavior remains: free-text name + one address, then `POST /api/v1/employers/`.

All **scoping, permissions, and business rules** (who can see which employers/addresses, validation, assignment rules) must be enforced by the backend. The client will only call the documented endpoints and render the responses.

---

## 2. Required: Employer search

The client needs to call an endpoint that returns **existing employers** matching a search term (e.g. company name), so the user can select one instead of creating a duplicate.

### Suggested contract

| Item | Detail |
|------|--------|
| **Method / path** | `GET /api/v1/employers/search` (or equivalent; backend to confirm final path). |
| **Query parameters** | `search_term` (partial name search). **Current backend uses `search_term`** (not `q`). Optional: `limit` (default 10, max 50). Optional: `market_id` or other scope if needed. |
| **Auth** | Bearer token (Customer). |
| **Scoping** | Results must be limited to employers the current customer is allowed to assign themselves to (e.g. same institution, same market, or whatever the product rule is). Backend defines and enforces this. |
| **Response** | Array of employer summary objects. Suggested minimum: `employer_id` (UUID), `name` (string). Optional: first address summary, address count, or other fields useful for display. |
| **Errors** | 400 if missing/invalid query; 401/403 per standard auth; 500 with no assumption of partial data. |

**Example (suggestion):**

```http
GET /api/v1/employers/search?search_term=acme&limit=10
Authorization: Bearer <token>
```

```json
[
  { "employer_id": "uuid-1", "name": "Acme Corp" },
  { "employer_id": "uuid-2", "name": "Acme Argentina" }
]
```

**Current behavior:** When `search_term` is empty, backend returns all employers. **Recommendation:** Client should only call search when user has typed at least 2 characters. **Optional backend improvement:** Return 400 or empty array when `search_term` is empty/min length to prevent accidental full dumps.

---

## 3. Required: List addresses for an employer

When the user has selected an **existing employer**, the client needs to load the **addresses linked to that employer** so the user can pick one or choose “Add new address”.

### Suggested contract

| Item | Detail |
|------|--------|
| **Method / path** | `GET /api/v1/employers/{employer_id}/addresses` (or equivalent; backend to confirm). |
| **Path parameters** | `employer_id`: UUID of the employer. |
| **Query parameters** | Optional `city_id` (UUID): filter addresses to those in that city (address_info.city must match city_info.name). B2C should pass user's `city_id` from `GET /users/me` when available. |
| **Auth** | Bearer token (Customer). |
| **Scoping** | The customer must be allowed to see this employer (e.g. same institution/market). Return 403 or 404 if not allowed or not found. |
| **Response** | Array of address objects. **Current:** Returns full `AddressResponseSchema` (street_name, city, province, postal_code, country_code). Client builds display label (e.g. `street_name · city · postal_code`). **Optional:** Add `formatted_address` for picker UX. |
| **Errors** | 401/403/404 if not allowed or employer not found; 500 otherwise. |

**Example (suggestion):**

```http
GET /api/v1/employers/uuid-1/addresses
Authorization: Bearer <token>
```

```json
[
  {
    "address_id": "addr-uuid-1",
    "formatted_address": "Av. Santa Fe 2567, CABA, Argentina",
    "city": "CABA",
    "province": "Ciudad Autónoma de Buenos Aires",
    "country_code": "AR"
  }
]
```

Backend to confirm: exact path, response shape, and scoping.

---

## 4. Assign user to employer (existing; optional extension)

**Current:** The client uses **`PUT /api/v1/users/me/employer?employer_id=...`** to assign the current user to an employer. Customers only. No change required for the new flow.

### Optional: store “user’s employer address”

If the product needs to show **which office/address** the user is associated with (e.g. “Your office: Buenos Aires”), the backend could:

- Accept an optional **`address_id`** (or equivalent) on **`PUT /api/v1/users/me`** when setting **`employer_id`**, and
- Return that in **`GET /api/v1/users/me`** (or enriched user) so the client can display it.

**Current:** Only `employer_id` is supported. The optional `address_id` is **not implemented**. Backend to confirm if product needs it.

---

## 5. Add address to existing employer (existing)

**`POST /api/v1/employers/{employer_id}/addresses`** is already referenced in [EMPLOYER_MANAGEMENT_B2C.md](./EMPLOYER_MANAGEMENT_B2C.md). The client will use it when the user selects “Add new address for this employer”.

### What the client needs

| Item | Detail |
|------|--------|
| **Request body** | Same address object shape as in **POST /api/v1/employers/** (see EMPLOYER_MANAGEMENT_B2C.md). B2C must **not** send `institution_id`, `user_id`, or `address_type`; backend sets them. |
| **Response** | At least the created **`address_id`** (and ideally the full address or a link) so the client can, if needed, pass it to **PUT /users/me** (when optional `address_id` is supported) or simply complete the flow after assigning **`employer_id`**. |
| **Validation** | Address validation (suggest/validate) is already used by the client; backend continues to validate and normalize per existing rules. |

Backend to confirm: final path, request/response shape, and that B2C scope (no institution_id/user_id in body) is documented.

---

## 6. B2C client implementation

Backend is ready. The client implements the flow per [EMPLOYER_MANAGEMENT_B2C.md](./EMPLOYER_MANAGEMENT_B2C.md):

1. **Company step:** Call `GET /api/v1/employers/search?search_term=...` as user types; show results or "Register new company".
2. **Address step (existing employer):** Call `GET /api/v1/employers/{id}/addresses`; user picks existing or adds new via `POST /api/v1/employers/{id}/addresses`.
3. **Assign:** Call `PUT /api/v1/users/me/employer` with body `{ "employer_id": "...", "address_id": "..." }` when user picked existing address.
4. **New company:** `POST /api/v1/employers/` with name + address + `assign_employer: true`.

---

## 7. Summary table

| Capability | Endpoint | Status |
|------------|----------|--------|
| Search employers by name | `GET /api/v1/employers/search?search_term=...` | **Implemented** |
| List addresses for employer | `GET /api/v1/employers/{employer_id}/addresses?city_id=...` | **Implemented** – optional `city_id` filter |
| Assign user to employer | `PUT /api/v1/users/me/employer` (body: `employer_id`, `address_id`) | **Implemented** – both required |
| Add address to employer | `POST /api/v1/employers/{employer_id}/addresses` | **Implemented** |
| Create new employer | `POST /api/v1/employers/` | **Implemented** |

---

## 8. B2C client recommendations: Select existing employer + existing address

When the user selects an **existing employer** and an **existing address** and taps Save, the client must send `PUT /api/v1/users/me/employer` with both `employer_id` and `address_id`. If `address_id` is missing from the payload, the assignment fails. The following recommendations ensure the client correctly passes `address_id` from the address list to the assign call.

### Data flow to follow

1. **Store the full address object on selection.** When the user picks an address from `GET /employers/{id}/addresses`, store the **entire selected item** (including `address_id`). Do not store only display fields (e.g. `street_name`, `city`, `formatted_address`).
2. **Use `address_id` from the selected item.** The API returns `address_id` (not `id`). When building the assign payload, use `selectedAddress.address_id`. If your types or components expect `id`, map `address_id` → `id` on ingest, or explicitly use `address_id` when calling the assign endpoint.
3. **Keep `selectedAddress` separate from `selectedEmployer`.** The employer object has a single `address_id` (primary address). The user may pick a different address from the list. Always use the address the user selected, not the employer’s primary address.
4. **Pass the full item from the address picker.** Ensure the address picker’s `onSelect` callback receives and passes the full list item (including `address_id`) to the parent. Do not emit only a display string or a subset of fields.
5. **Call PUT when both IDs are available.** The Save handler should call `PUT /users/me/employer` with `{ "employer_id": "<uuid>", "address_id": "<uuid>" }` when the user confirms. Both fields are required; sending only `employer_id` returns 422.

### Checklist for B2C implementation

- [ ] Address picker passes the full selected address object (including `address_id`) to the parent on selection.
- [ ] Form state stores `selectedAddress` with `address_id` when the user picks an existing address.
- [ ] Save handler uses `selectedAddress.address_id` (not `selectedEmployer.address_id`) when building the assign payload.
- [ ] Assign payload uses the exact field name `address_id` (the API does not accept `id`).
- [ ] `PUT /api/v1/users/me/employer` is called when the user taps Save/Confirm, with both `employer_id` and `address_id` in the JSON body.

### Response shape reference

Each item from `GET /employers/{id}/addresses` includes `address_id` as the first field:

```json
{
  "address_id": "019cc3e5-9899-7489-95a6-0512f03067b7",
  "institution_id": "...",
  "street_name": "Av. Santa Fe 2567",
  "city": "CABA",
  "province": "...",
  "postal_code": "...",
  ...
}
```

Use `address_id` from this object when calling `PUT /users/me/employer`.

---

## 9. GET addresses: Customer address list logic (implemented)

**Frontend finding:** The address list (`GET /addresses/` and `GET /addresses/enriched/`) previously only returned addresses created by the user. When a Customer picked an employer address created by someone else, it did not appear in their list.

**Backend behavior (implemented):**

| Address type | Logic |
|--------------|-------|
| **Employer** | Only the address assigned as `employer_address_id` (from `user_info`). If the user picked an address created by someone else, it is included. If the user changed their employer address, the previous one is excluded (no longer shown). |
| **Home and billing** | Addresses created by the user (`user_id` = current user), as before. |

**Endpoints affected:** `GET /api/v1/addresses/`, `GET /api/v1/addresses/enriched/`, `GET /api/v1/addresses/{address_id}`. For Customers, the list and single-address endpoints apply this logic; `GET /addresses/{address_id}` allows access to the user's `employer_address_id` even when it was created by another user.

---

## 10. Optional backend improvements

| Change | Priority | Description |
|--------|----------|-------------|
| Empty `search_term` behavior | Medium | When `search_term` is empty or &lt; 2 chars, return 400 or empty array. Prevents accidental full employer list. |
| Add `formatted_address` to address list | Low | Add computed `formatted_address` to `GET /employers/{id}/addresses` response for picker display. |
| Alias `q` for `search_term` | Low | Accept both `q` and `search_term` for compatibility. |
| ~~Optional `address_id` on user~~ | ~~Low~~ | **Implemented:** `PUT /users/me/employer` now requires both `employer_id` and `address_id` in body. User's `employer_address_id` is stored and returned. |
| Employer search by city | Low | Optional `city_id` or `country_code` on `GET /employers/search` to filter employers with at least one address in that city/country. Document in feedback when needed. |

---

## 11. Troubleshooting: Client sends correct data but backend shows nothing / data not stored

**Testing finding (2026-03):** With the network tab open, the B2C client **does** send the correct payload (`employer_id` and `address_id`) when the user selects an existing employer + existing address and taps Save. However, the backend terminal shows no `PUT /api/v1/users/me/employer` request, and the data is not stored in Postgres.

### Likely cause: Request not reaching the local backend

If the network tab shows the PUT with the correct body but the backend terminal shows nothing, the request is likely going to a **different backend URL** than the one you are running locally (e.g. production, staging, or a different port).

**Verify in the network tab:**
- Request URL: Is it `http://localhost:8000/api/v1/users/me/employer` (or your local backend URL)?
- If the URL points to a different host (e.g. `https://api.example.com`), the B2C app is configured to hit that backend. Update the B2C base URL to point to your local backend when testing locally.

### Backend debug logging

The backend supports optional debug logging for the employer assign flow. Enable it to confirm whether the request reaches the route and whether the update succeeds.

**Enable:** Add to `.env`:
```
LOG_EMPLOYER_ASSIGN=1
```

Restart the backend, then trigger the flow (select employer + address, tap Save). Check the terminal for:

| Log message | Meaning |
|-------------|---------|
| `[EmployerAssign] PUT /users/me/employer received: user_id=... employer_id=... address_id=...` | Request reached the backend. Body was parsed correctly. |
| `[EmployerAssign] employer assignment SUCCESS: user_id=... employer_id=... employer_address_id=...` | Update succeeded. Check `user_info` in Postgres for `employer_id` and `employer_address_id`. |
| `[EmployerAssign] employer assignment FAILED: user_service.update returned None...` | Update failed (e.g. DB error, scope mismatch). Check full traceback in logs. |

**If you see no `[EmployerAssign]` logs at all** when you tap Save, the request is not reaching this backend. Confirm the B2C base URL matches the backend you are running.

**Disable:** Remove `LOG_EMPLOYER_ASSIGN` from `.env` or set `LOG_EMPLOYER_ASSIGN=0`, then restart.

---

**Document status:** Feedback for backend. Implementation complete; optional improvements above may be considered.
