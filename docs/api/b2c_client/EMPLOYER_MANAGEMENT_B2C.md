# B2C Employer Management

**Audience:** B2C client (Customer role). Employer entity selection and assignment flow.  
**Last updated:** 2026-04

---

## Overview

Employers are now managed as **employer entities** created by employer admins in the B2B platform. The B2C app no longer searches for or creates employers. Customers only **select an existing employer entity** and assign it to themselves.

---

## What Changed

| Before | Now |
|--------|-----|
| `GET /employers/search`, `POST /employers/`, `POST /employers/{id}/addresses` | **Removed (404).** All `/employers/` routes are gone. |
| `PUT /users/me/employer` with `employer_id` + `address_id` | `PUT /users/me/employer` with `employer_entity_id` + `address_id` |
| User response field `employer_id` | Now `employer_entity_id` |
| Enriched user response field `employer_name` | Now `employer_entity_name` |
| Address type auto-derived from context | User-selected: **Home**, **Work**, **Other** |

---

## Endpoint

### Assign Employer Entity to User

```http
PUT /api/v1/users/me/employer
Authorization: Bearer <token>
Content-Type: application/json

{
  "employer_entity_id": "019cc3e5-989d-79aa-847f-683c8b321175",
  "address_id": "019cc3e5-9899-7489-95a6-0512f03067b7"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `employer_entity_id` | UUID | Yes | Must reference an existing employer entity (created by employer admin in B2B). |
| `address_id` | UUID | Yes | Must belong to the employer entity's institution. |

**200 OK** — Returns the updated user with `employer_entity_id` set.

**Errors:**

| Status | Cause |
|--------|-------|
| 400 | Address does not belong to the entity's institution. |
| 404 | Employer entity or address not found. |
| 422 | Missing required field. |

---

## User Response Fields

After assignment, `GET /api/v1/users/me` returns:

| Field | Description |
|-------|-------------|
| `employer_entity_id` | Assigned employer entity UUID |
| `employer_entity_name` | Employer entity name (enriched response) |

---

## Address Types

Address types are now **user-selected** rather than auto-derived. Valid values: `Home`, `Work`, `Other`.

---

## What Customers Cannot Do

- Search or create employers (all `/employers/` routes return 404).
- Edit or delete employer-entity-owned addresses (403).
- Assign an employer entity that does not exist (must be created by employer admin in B2B first).

---

## Integration Checklist

- [ ] Remove all calls to `/employers/` routes (search, create, add address).
- [ ] Update assign call to send `employer_entity_id` (not `employer_id`).
- [ ] Read `employer_entity_id` and `employer_entity_name` from user response (not `employer_id` / `employer_name`).
- [ ] Let users choose address type (Home, Work, Other) instead of auto-deriving it.
- [ ] Ensure the employer entity list is sourced from a different mechanism (e.g., pre-populated picker, not typeahead search against `/employers/`).

---

## References

- [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md) — Address suggest, create, and types
