# B2C Employer Management – Complete Guide

**Audience:** B2C client (Customer role). For agents building the **"Register my employer"** flow: search existing employers, select or create new, pick or add address, and assign.  
**Last updated:** 2026-03

---

## Purpose

Customers can manage their employer (company) through several flows:

1. **Search & assign existing** — Search for an employer, pick an existing address, then **assign** it to themselves.
2. **Add address to existing** — Search for an employer, add a new address, and assign in one step.
3. **Register new company** — Create employer + first address in one call.

All endpoints require Bearer token (Customer). The backend enforces scoping, permissions, and business rules.

**Important:** A user's employer assignment always includes both `employer_id` and `employer_address_id`. There is no "default" address—users work at specific offices. The client must always send or trigger assignment of both.

---

## Endpoint Summary

| Capability | Method | Path | Purpose |
|------------|--------|------|---------|
| Search employers | GET | `/api/v1/employers/search?search_term=...&limit=...` | Typeahead search for company name |
| List employer addresses | GET | `/api/v1/employers/{employer_id}/addresses?city_id=...` | Addresses for selected employer (optional `city_id` filters by user's city) |
| **Assign employer to user** | **PUT** | **`/api/v1/users/me/employer`** | **Assign selected employer and address to current user. Body: `{ employer_id, address_id }`. Required when user picks existing employer + existing address.** |
| Add address to employer | POST | `/api/v1/employers/{employer_id}/addresses` | Add new address to existing employer; can include `assign_employer: true` |
| Create new employer | POST | `/api/v1/employers/` | Create employer + first address (new company path) |
| List cities | GET | `/api/v1/cities/?country_code=...&exclude_global=true` | Supported cities for profile and address scoping |

---

## Critical: Select Existing Employer + Existing Address

When the user **searches for an employer**, **selects it**, then **picks an existing address** from that employer's list, **the assignment does not happen automatically**. The B2C client **must** call the assign endpoint to complete the flow.

### Required API Call

```http
PUT /api/v1/users/me/employer
Content-Type: application/json

{ "employer_id": "{employer_id}", "address_id": "{address_id}" }
```

**Request body:** Both `employer_id` and `address_id` are required (UUIDs). The address must belong to the employer (from `GET /employers/{id}/addresses`). Query parameters are not supported—use the JSON body only.

**Example:**
```json
{
  "employer_id": "019cc3e5-989d-79aa-847f-683c8b321175",
  "address_id": "019cc3e5-9899-7489-95a6-0512f03067b7"
}
```

**Response (200 OK):** Returns the updated user with `employer_id` and `employer_address_id` set. Use `GET /users/me` to read `employer_id`, `employer_address_id`, and enriched employer/address details.

### Why This Matters

- Selecting an employer and an address in the UI **does nothing** until the client sends this PUT request.
- The PUT links the employer and the chosen address to the current user. The user's `employer_id` and `employer_address_id` are updated; the employer's addresses (including the one the user picked) become available as **Customer Employer** address type for that user.
- If the client does not call PUT, the user will see "nothing happened" — the employer is not assigned.

### UI Implementation

**Option A (recommended):** Show a **"Confirm"** or **"Assign"** button after the user selects the address. On tap, call `PUT /api/v1/users/me/employer` with body `{ "employer_id": "{employer_id}", "address_id": "{address_id}" }`.

**Option B:** Auto-submit when the user selects an address — immediately call the PUT with both IDs without a separate confirm step.

**Flow:**

1. User selects employer from search results.
2. Client calls `GET /api/v1/employers/{employer_id}/addresses` to list addresses.
3. User picks an existing address from the list.
4. **Client must call `PUT /api/v1/users/me/employer`** with body `{ "employer_id": "{employer_id}", "address_id": "{address_id}" }` — this completes the assignment.
5. On success (200), navigate to profile or "My employer" and show the assigned employer.

### API Calls for This Scenario

| Step | API | Purpose |
|------|-----|---------|
| 1 | `GET /employers/search?search_term=...` | Search for employer |
| 2 | `GET /employers/{id}/addresses?city_id=...` | List addresses for selected employer |
| 3 | **`PUT /users/me/employer`** (body: `employer_id`, `address_id`) | **Assign employer and address to user (required)** |

### Request and Response

**200 OK response:** Returns the updated user object with `employer_id` and `employer_address_id` set. Use `GET /users/me` to read the full profile including employer details.

**400 errors:**
- `"Address not found"` — The `address_id` does not exist or is archived.
- `"Address does not belong to the specified employer"` — The address's `employer_id` does not match. Use an address from `GET /employers/{id}/addresses`.

### Integration Checklist

- [ ] When user picks an **existing address**, call `PUT /users/me/employer` with **both** `employer_id` and `address_id` from the selection.
- [ ] Do **not** send only `employer_id` — the API requires both fields. Sending only `employer_id` returns 422.
- [ ] Use `address_id` from `GET /employers/{id}/addresses` response (each address has `address_id`).
- [ ] After success, `GET /users/me` returns `employer_id` and `employer_address_id` for display.

### Troubleshooting: "Nothing happened" when user selects address

If the user selects an employer and address but sees no change:

1. **Check the network tab** — Is `PUT /api/v1/users/me/employer` being called? If not, the client is not sending the assign request when the user confirms.
2. **Check the request body** — The body must include both `employer_id` and `address_id`. A body with only `employer_id` (or query params) will fail.
3. **Check for 400/422** — Address not belonging to employer, or missing `address_id`, returns an error. Surface the `detail` to the user.

---

## Flow: All Scenarios

### Scenario 1: Select existing employer + pick existing address

| Step | Action | API |
|------|--------|-----|
| 1 | Search employer | `GET /employers/search?search_term=...` |
| 2 | User selects employer | — |
| 3 | List addresses | `GET /employers/{id}/addresses?city_id=...` |
| 4 | User picks existing address | — |
| 5 | **Assign** | **`PUT /users/me/employer`** (body: `employer_id`, `address_id`) |

### Scenario 2: Select existing employer + add new address

| Step | Action | API |
|------|--------|-----|
| 1 | Search employer | `GET /employers/search?search_term=...` |
| 2 | User selects employer | — |
| 3 | List addresses | `GET /employers/{id}/addresses` |
| 4 | User taps "Add new address" | — |
| 5 | Address form (suggest/validate) | `GET /addresses/suggest`, `POST /addresses/validate` |
| 6 | Submit | `POST /employers/{id}/addresses` with `assign_employer: true` |

Assignment happens in the POST; no separate PUT needed.

### Scenario 3: Register new company

| Step | Action | API |
|------|--------|-----|
| 1 | (Optional) Search to avoid duplicates | `GET /employers/search?search_term=...` |
| 2 | Address form (suggest/validate) | `GET /addresses/suggest`, `POST /addresses/validate` |
| 3 | Submit | `POST /employers/` with `name`, `address`, `assign_employer: true` |

---

## Create New Employer (POST /employers/)

### Request

**Headers:** `Authorization: Bearer <token>`, `Content-Type: application/json`

**Body:** `EmployerCreateSchema`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Employer/company name. Max 100 characters. |
| `address` | object | Yes | Full address (see below). |
| `assign_employer` | boolean | No | If `true` (default), assign this employer to the current user after creation. |

**B2C:** Do not send `institution_id` or `user_id` inside `address`. The backend sets both from the JWT.

**Address object:** `country_code` or `country`, `province`, `city`, `postal_code`, `street_type`, `street_name`, `building_number`, optional `apartment_unit`, `floor`, `is_default`. Do not send `address_type`, `employer_id`, `institution_id`, or `user_id`.

### Address autocomplete

Use `GET /api/v1/addresses/suggest?q=...&country=...` for autocomplete, then `POST /api/v1/addresses/` with `place_id` (or full structured fields) on submit. See [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md).

### Response

**201 Created** — Employer with `employer_id`, `address_id`, `name`, etc.

---

## Add Address to Employer (POST /employers/{id}/addresses)

Same address body shape as create. Use suggest then create with place_id (or structured fields) for the new address. B2C omits `institution_id`/`user_id`. Set `assign_employer: true` to assign the employer to the user in the same call.

---

## Employer Address Protection

**Customers cannot edit or delete employer-owned addresses.** An address is employer-owned when it has `employer_id` set.

| Endpoint | Customer action | Result |
|----------|-----------------|--------|
| `PUT /api/v1/addresses/{address_id}` | Edit employer address | **403 Forbidden** |
| `DELETE /api/v1/addresses/{address_id}` | Delete employer address | **403 Forbidden** |

**UI:** Do not show "Edit address" or "Delete address" for addresses from `GET /employers/{employer_id}/addresses`. If the user needs a different address, they can add one via `POST /employers/{id}/addresses` or pick another existing address.

---

## Cities API and User Profile

### Cities

`GET /api/v1/cities/?country_code={country}&exclude_global=true` — Returns supported cities. Use for user profile city picker and to filter employer addresses.

### User profile city_id

- **GET /users/me** — Returns `city_id`, `city_name`.
- **PUT /users/me** — Can include `city_id`. Customer Comensals must have a city (required at signup); cannot set null or Global.
- Pass `city_id` to `GET /employers/{id}/addresses?city_id=...` to filter addresses to the user's city.

---

## What Customers Cannot Do

- **Edit employer name or address** — `PUT /employers/{id}` and `DELETE /employers/{id}` are Employee-only (403 for Customers).
- **Edit or delete employer-owned addresses** — `PUT /addresses/{id}` and `DELETE /addresses/{id}` return 403 when the address has `employer_id`.

---

## Error Handling

| Status | When | Client behavior |
|--------|------|-----------------|
| 400 | Validation error | Show `detail`; fix form. |
| 401 | Unauthorized | Redirect to login. |
| 403 | Not allowed (e.g. edit employer address) | Show "Not allowed." |
| 404 | Employer or address not found | Show "Not found"; allow retry. |
| 500 | Server error | Show generic error. |

---

## References

- [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md) — Suggest, create (place_id or structured); B2C omit institution_id/user_id; address types by role
- [feedback_for_backend_employer_search_and_assign.md](./feedback_for_backend_employer_search_and_assign.md) — Backend implementation status
