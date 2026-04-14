# B2B Integration: Employer Address Protection & Cities API

**Audience:** B2B client (Employee, Supplier)  
**Last updated:** 2026-03

---

## Summary

This document describes integration changes for B2B clients (backoffice):

1. **Employer address protection** — Only **Customers** are restricted; Employees and Suppliers can edit/delete employer addresses.
2. **Cities API** — `GET /api/v1/cities/` for city dropdowns and address scoping.
3. **Employer addresses `city_id` filter** — `GET /employers/{id}/addresses?city_id=...` filters by city.

---

## 1. Employer Address Protection (Role-Based)

### Rule by role

| Role | PUT /addresses/{id} | DELETE /addresses/{id} |
|------|---------------------|------------------------|
| **Employee** (Admin, Super Admin, Management, Operator) | ✅ Allowed | ✅ Allowed |
| **Supplier** (Admin, Manager) | ✅ Allowed | ✅ Allowed |
| **Supplier Operator** | ❌ 403 (read-only) | ❌ 403 |
| **Customer** | ❌ 403 for employer addresses | ❌ 403 for employer addresses |

**Employer address** = address with `employer_id` set (e.g. from `POST /employers/` or `POST /employers/{id}/addresses`).

### Customer 403 (if B2B ever has Customer flows)

If a Customer calls PUT or DELETE on an employer-owned address:

```json
{
  "detail": "Customers cannot edit or delete employer addresses. Employer addresses are shared and managed by the employer."
}
```

**B2B backoffice** is typically used by Employees and Suppliers. If your B2B app has any flow where a Customer can reach address edit/delete (e.g. shared portal), hide Edit/Delete for employer addresses when the user is a Customer.

### Employee and Supplier

Employees and Suppliers (Admin, Manager) can edit and delete employer addresses. No change to existing backoffice employer management flows.

---

## 2. Cities API

### Endpoint

```http
GET /api/v1/cities/?country_code={country_code}
```

**Auth:** Bearer token (Employee or Customer; B2B typically uses Employee).

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `country_code` | string | No | ISO 3166-1 alpha-2 (e.g. `AR`, `US`). If omitted, returns all supported cities. |

**Response:** JSON array:

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

### Use cases (B2B)

- **Employer address form** — City dropdown when creating/editing employer addresses (optional; `city` is still a text field, but you can validate against supported cities).
- **Address filter** — Pass `city_id` to `GET /employers/{id}/addresses?city_id=...` to filter addresses by city.

---

## 3. Employer Addresses `city_id` Filter

### Endpoint

```http
GET /api/v1/employers/{employer_id}/addresses?city_id={city_id}
```

**Query params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `city_id` | UUID | No | Filter addresses to those in this city. |

### UI Integration

- Optional: Add a city filter to the employer address list in the backoffice.
- Use `GET /api/v1/cities/?country_code=...` to populate the filter dropdown.

---

## Integration Checklist

- [ ] **Employees/Suppliers:** No change — Edit/Delete employer addresses remain allowed.
- [ ] **Customer flows (if any):** Hide Edit/Delete for employer addresses when user is Customer; show 403 message if they somehow trigger it.
- [ ] **Cities API:** Use `GET /api/v1/cities/?country_code=...` for city dropdowns where needed.
- [ ] **Employer address list:** Optionally add `city_id` filter to `GET /employers/{id}/addresses`.

---

## References

- [API_CLIENT_EMPLOYER_ASSIGNMENT.md](./API_CLIENT_EMPLOYER_ASSIGNMENT.md) — Backoffice employer management
- [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md) — Full address API
