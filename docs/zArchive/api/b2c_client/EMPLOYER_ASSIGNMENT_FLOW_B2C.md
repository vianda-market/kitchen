# B2C Employer Assignment Flow – Implementation Guide

> **Archived.** Use [EMPLOYER_MANAGEMENT_B2C.md](../../../api/b2c_client/EMPLOYER_MANAGEMENT_B2C.md) for the consolidated B2C employer management guide.

**Audience:** B2C client (Customer role). For agents building the **"Register my employer"** flow where the user can search existing employers, select or register new, pick or add an address, and assign.  
**Last updated:** 2026-03

---

## Purpose

Customers can assign themselves to an employer through a **multi-step flow**:

1. **Company:** Search for existing employers by name; select one or register a new company.
2. **Address (existing employer only):** Pick an existing address for that employer, or add a new one.
3. **Assign:** Link the employer to the current user.

All endpoints require Bearer token (Customer). The backend enforces scoping, permissions, and business rules.

---

## Endpoint Summary

| Capability | Method | Path | Purpose |
|------------|--------|------|---------|
| Search employers | GET | `/api/v1/employers/search?search_term=...&limit=...` | Typeahead search for company name |
| List employer addresses | GET | `/api/v1/employers/{employer_id}/addresses?city_id=...` | Addresses for selected employer (optional `city_id` filters by user's city) |
| List cities | GET | `/api/v1/cities/?country_code=...` | Supported cities for profile and address scoping |
| Assign employer to user | PUT | `/api/v1/users/me/employer?employer_id=...` | Assign selected employer to current user |
| Add address to employer | POST | `/api/v1/employers/{employer_id}/addresses` | Add new address to existing employer |
| Create new employer | POST | `/api/v1/employers/` | Create employer + first address (new company path) |

---

## Flow: Step by Step

### Step 1 – Company Selection

**UI:** Search input (typeahead) with debounce (e.g. 300ms).

**Behavior:**

- Call `GET /api/v1/employers/search?search_term={user_input}&limit=10` as the user types.
- **Best practice:** Only call when user has typed at least 2 characters. When `search_term` is empty, the backend may return all employers; avoid calling with empty/minimal input.
- Display results as a selectable list: `employer_id`, `name`.
- Always show option **"Register new company"** at the bottom (or when no results).

**User actions:**

- **Select existing employer** → go to Step 2a (Address).
- **Select "Register new company"** → go to Step 2b (New company).

---

### Step 2a – Address (existing employer)

**UI:** List of addresses for the selected employer + "Add new address" option.

**Behavior:**

- On entry, call `GET /api/v1/employers/{employer_id}/addresses`. **Best practice:** Pass `city_id` from the user's profile (`GET /users/me` returns `city_id`) to filter addresses to the user's city.
- Each item in the response has: `address_id`, `street_name`, `city`, `province`, `postal_code`, `country_code`, `country_name`.
- Build a display label client-side: e.g. `street_name · city · postal_code` or `street_name, city, province`.
- If no addresses exist, show only "Add new address".

**User actions:**

- **Pick existing address** → go to Step 3 (Assign).
- **Pick "Add new address"** → show address form (suggest/validate), then `POST /api/v1/employers/{employer_id}/addresses` with `assign_employer: true`. Flow completes (assign happens in that POST).

---

### Step 2b – Address (new company)

**UI:** Address form using suggest/validate as per [EMPLOYER_CREATE_B2C.md](./EMPLOYER_CREATE_B2C.md).

**Behavior:**

- Use `GET /api/v1/addresses/suggest` and `POST /api/v1/addresses/validate` for the address block.
- Submit `POST /api/v1/employers/` with `name`, `address`, `assign_employer: true`. Flow completes.

---

### Step 3 – Assign (existing employer, picked existing address)

**UI:** Confirm or auto-submit.

**Behavior:**

- Call `PUT /api/v1/users/me/employer?employer_id={employer_id}`.
- Flow completes.

---

## API Usage by Scenario

| Scenario | API Calls |
|----------|-----------|
| Select existing employer + pick existing address | `GET /employers/search`, `GET /employers/{id}/addresses`, `PUT /users/me/employer` |
| Select existing employer + add new address | `GET /employers/search`, `GET /employers/{id}/addresses`, `POST /employers/{id}/addresses` (with `assign_employer: true`) |
| Register new company | `GET /employers/search` (optional, to avoid duplicates), `POST /employers/` (with `assign_employer: true`) |

---

## Address Display

`GET /api/v1/employers/{employer_id}/addresses` returns `AddressResponseSchema` with: `street_name`, `city`, `province`, `postal_code`, `country_code`, `country_name`.

**Optional `city_id` query param:** When the user has set their city in their profile (`PUT /users/me` with `city_id`), pass `city_id` to filter addresses to that city. Use `GET /api/v1/cities/?country_code=...` to populate the city picker in the profile form.

Build a short label for pickers, e.g.:

- `street_name · city · postal_code`
- `street_name, city, province`

---

## Error Handling

| Status | When | Client behavior |
|--------|------|------------------|
| 400 | Validation error (missing/invalid fields) | Show `detail` from response; fix form. |
| 401 | Unauthorized | Redirect to login. |
| 403 | Not allowed | Show "Not allowed." Customers cannot edit or delete employer addresses (PUT/DELETE `/addresses/{id}`) when the address has `employer_id` set—employer addresses are shared. |
| 404 | Employer or address not found | Show "Not found"; allow retry or go back. |
| 500 | Server or DB error | Show generic error; do not assume partial success. |

---

## References

- [EMPLOYER_CREATE_B2C.md](./EMPLOYER_CREATE_B2C.md) – Create employer + address (new company path)
- [feedback_for_backend_employer_search_and_assign.md](./feedback_for_backend_employer_search_and_assign.md) – Backend implementation status and clarifications
- Address suggest/validate: [ADDRESS_AUTOCOMPLETE_CLIENT.md](../shared_client/ADDRESS_AUTOCOMPLETE_CLIENT.md)
