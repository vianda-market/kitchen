# B2C Integration: Employer Address Protection & Cities API

> **Archived.** Use [EMPLOYER_MANAGEMENT_B2C.md](../../../api/b2c_client/EMPLOYER_MANAGEMENT_B2C.md) for the consolidated B2C employer management guide.

**Audience:** B2C client (Customer role)  
**Last updated:** 2026-03

---

## Summary

This document describes integration changes for B2C clients:

1. **Employer address protection** — Customers cannot edit or delete employer-owned addresses (403).
2. **Cities API** — `GET /api/v1/cities/` for user profile and address scoping.
3. **User profile `city_id`** — Customer Comensals must have a city (required at signup); they can change it later but cannot remove it or set it to the Global city.
4. **Employer addresses `city_id` filter** — `GET /employers/{id}/addresses?city_id=...` filters by city.

---

## 1. Employer Address Protection

### Rule

**Customers cannot edit or delete addresses that belong to an employer.**  
An address is "employer-owned" when it has `employer_id` set (e.g. created via `POST /employers/` or `POST /employers/{id}/addresses`).

| Endpoint | Customer action | Result |
|----------|-----------------|--------|
| `PUT /api/v1/addresses/{address_id}` | Edit employer address | **403 Forbidden** |
| `DELETE /api/v1/addresses/{address_id}` | Delete employer address | **403 Forbidden** |

### 403 Response

```json
{
  "detail": "Customers cannot edit or delete employer addresses. Employer addresses are shared and managed by the employer."
}
```

### Why

Employer addresses are shared across multiple customers (Comensals) who work at the same company. Allowing one customer to edit or delete would affect others. Only Employees (backoffice) can manage employer addresses.

### UI Integration

- **Do not show** "Edit address" or "Delete address" for employer-owned addresses when the user is a Customer.
- Addresses returned from `GET /employers/{employer_id}/addresses` are employer-owned; treat them as read-only for Customers.
- If the user needs a different address: they can **add** a new address via `POST /employers/{employer_id}/addresses` or pick another existing address.
- For **Customer Home** and **Customer Billing** addresses (no `employer_id`), Edit/Delete remain allowed.

### How to detect employer-owned addresses

- Response from `GET /employers/{employer_id}/addresses` — all addresses in this list are employer-owned.
- Response from `GET /api/v1/addresses/{address_id}` or list endpoints — check `employer_id`; if non-null, the address is employer-owned.

---

## 2. Cities API

### Endpoint

```http
GET /api/v1/cities/?country_code={country_code}
```

**Auth:** Bearer token (Customer or Employee).

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `country_code` | string | No | ISO 3166-1 alpha-2 (e.g. `AR`, `US`). If omitted, returns all supported cities. |
| `exclude_global` | bool | No | If `true`, omits the Global city from results. Use for Customer signup/profile city picker (Customers cannot have Global city). Default `false`. |

**Response:** JSON array of city objects:

```json
[
  {
    "city_id": "uuid",
    "name": "Buenos Aires",
    "country_code": "AR",
    "is_archived": false,
    "status": "Active"
  },
  ...
]
```

### Use cases

- **User profile city picker** — Populate a "City" dropdown when the user sets their profile. Use `country_code` from the user's market.
- **Employer address filter** — Pass `city_id` to `GET /employers/{employer_id}/addresses?city_id=...` to show only addresses in that city.

---

## 3. User Profile `city_id`

### Endpoints

- **GET /api/v1/users/me** — Response includes `city_id` (UUID or null) and optionally `city_name`.
- **PUT /api/v1/users/me** — Request body can include `city_id` (UUID).

### Validation

- `city_id` must exist in `city_info` and not be archived.
- `city_id` must belong to a city whose `country_code` matches the user's market country.
- **Customer Comensal:** City is required at signup and cannot be removed. Customers cannot set `city_id` to null or to the Global city. They can change to another valid city in their market.

### UI Integration

- Add a "City" field to the user profile form.
- Populate options from `GET /api/v1/cities/?country_code={user_market_country}&exclude_global=true` for Customer Comensal (excludes Global city).
- On save, send `city_id` in `PUT /api/v1/users/me`.
- Use `city_id` when calling `GET /employers/{employer_id}/addresses?city_id=...` to filter addresses to the user's city.

---

## 4. Employer Addresses `city_id` Filter

### Endpoint

```http
GET /api/v1/employers/{employer_id}/addresses?city_id={city_id}
```

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `city_id` | UUID | No | Filter addresses to those in this city (address `city` must match `city_info.name`). |

### UI Integration

- When the user has set `city_id` in their profile, pass it to filter employer addresses:  
  `GET /employers/{employer_id}/addresses?city_id={user.city_id}`
- If the user has not set a city, omit `city_id` to get all addresses for the employer.

---

## Integration Checklist

- [ ] **Employer addresses:** Do not show Edit/Delete for addresses from `GET /employers/{id}/addresses` or with `employer_id` set.
- [ ] **403 handling:** If a Customer calls PUT/DELETE on an employer address, show a user-friendly message (e.g. "Employer addresses cannot be edited or deleted.").
- [ ] **Cities API:** Use `GET /api/v1/cities/?country_code=...` for the user profile city picker.
- [ ] **User profile:** Add `city_id` to profile form; persist via `PUT /users/me`.
- [ ] **Employer address list:** Pass `city_id` from user profile to `GET /employers/{id}/addresses?city_id=...` when available.

---

## References

- [EMPLOYER_ASSIGNMENT_FLOW_B2C.md](./EMPLOYER_ASSIGNMENT_FLOW_B2C.md) — Employer search, assign, add address flow
- [EMPLOYER_CREATE_B2C.md](./EMPLOYER_CREATE_B2C.md) — Create employer + address (new company)
- [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md) — Full address API (create, update, delete, types)
