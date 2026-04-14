# Workplace Groups — B2C Client Guide

**Audience:** B2C client (Customer role). Search, create, and join workplace groups for coworker pickup coordination.  
**Last updated:** 2026-04

---

## Overview

Workplace groups are **lightweight, customer-created groupings** for coworker pickup coordination. They are completely separate from the employer benefits program — no billing, no tax entities. A customer at the same office as coworkers can join a group so they can see each other's orders and coordinate pickup.

A customer can have **both** an employer entity (B2B benefits) and a workplace group (B2C coworker pickup), or just one, or neither.

---

## User Flow

1. **Search** — User types a company name (e.g., "BigCorp") → fuzzy type-ahead returns matching groups with member count.
2. **Select or Create** — User picks an existing group, or creates a new one if none match.
3. **Pick Office Address** — User sees existing office addresses for that group. Selects one, or adds a new one.
4. **Assign** — `PUT /users/me/workplace` links the user to the group + address.

After assignment, coworker matching uses `workplace_group_id + employer_address_id` to show coworker offers/requests.

---

## Endpoints

### Search Workplace Groups

```http
GET /api/v1/workplace-groups/search?q=BigCorp&limit=10
Authorization: Bearer <token>
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | string | Yes | Search query (min 3 chars recommended). Uses fuzzy trigram matching. |
| `limit` | int | No | Max results (default 10). |

**200 OK:**

```json
[
  {
    "workplace_group_id": "019cc3e5-989d-79aa-847f-683c8b321175",
    "name": "BigCorp Buenos Aires",
    "member_count": 12,
    "similarity": 0.85
  }
]
```

Results are sorted by similarity score (highest first). Only active, non-archived groups are returned.

---

### Create Workplace Group

```http
POST /api/v1/workplace-groups
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "BigCorp Buenos Aires"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Group name, max 100 characters. |

**201 Created:**

```json
{
  "workplace_group_id": "019cc3e5-989d-79aa-847f-683c8b321175",
  "name": "BigCorp Buenos Aires",
  "email_domain": null,
  "require_domain_verification": false,
  "is_archived": false,
  "status": "active",
  "created_date": "2026-04-12T14:30:00Z"
}
```

Do not send `status` — backend sets it to `active`.

---

### Get Workplace Group

```http
GET /api/v1/workplace-groups/{workplace_group_id}
Authorization: Bearer <token>
```

**200 OK** — Returns the group object (same shape as create response).

---

### List Group Addresses

```http
GET /api/v1/workplace-groups/{workplace_group_id}/addresses
Authorization: Bearer <token>
```

Returns all non-archived office addresses linked to this group. Use this after the user selects a group to show available office locations.

**200 OK:**

```json
[
  {
    "address_id": "019cc3e5-9899-7489-95a6-0512f03067b7",
    "street_name": "Av. Corrientes 1234",
    "city": "Buenos Aires",
    "province": "Buenos Aires",
    "country_code": "AR",
    "formatted_address": "Av. Corrientes 1234, Buenos Aires, Argentina"
  }
]
```

---

### Add Address to Group

If the user's office is not in the list, they can add a new one.

```http
POST /api/v1/workplace-groups/{workplace_group_id}/addresses
Authorization: Bearer <token>
Content-Type: application/json

{
  "place_id": "mapbox-place-id-string"
}
```

Uses the same address creation flow as the general Address API — either `place_id` (recommended) or structured fields. See [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md) for details.

**201 Created** — Returns the new address object. The address is automatically linked to the workplace group.

---

### Assign Workplace to User

```http
PUT /api/v1/users/me/workplace
Authorization: Bearer <token>
Content-Type: application/json

{
  "workplace_group_id": "019cc3e5-989d-79aa-847f-683c8b321175",
  "address_id": "019cc3e5-9899-7489-95a6-0512f03067b7"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workplace_group_id` | UUID | Yes | Group to join. |
| `address_id` | UUID | Yes | Office address for pickup scoping. Must belong to the group. |

**200 OK** — Returns the updated user with `workplace_group_id` and `employer_address_id` set.

**Errors:**

| Status | Cause |
|--------|-------|
| 400 | Address does not belong to the specified workplace group. |
| 404 | Workplace group or address not found. |
| 422 | Missing required field. |

---

## User Response Fields

After assignment, `GET /api/v1/users/me` returns:

| Field | Description |
|-------|-------------|
| `workplace_group_id` | Assigned workplace group UUID (nullable). |
| `workplace_group_name` | Group name (enriched response only). |
| `employer_address_id` | Selected office address UUID (shared with employer entity flow). |

---

## What Customers Cannot Do

- Edit or delete workplace group addresses (only Internal/Employer roles can edit). Customers who want a different address simply add a new one.
- Archive or rename groups (admin-only via B2B platform).
- See member identities — only `member_count` is exposed in search results.

---

## Clearing Workplace Assignment

To leave a workplace group, the user assigns `null`:

```http
PUT /api/v1/users/me/workplace
Content-Type: application/json

{
  "workplace_group_id": null,
  "address_id": null
}
```

---

## Coworker Matching

After assignment, the existing coworker features work automatically:

- **Explore:** `has_coworker_offer` / `has_coworker_request` badges appear on restaurants where a coworker at the same group + office has an active offer/request.
- **Post-reservation:** "Offer to pick up" / "Request pickup" is scoped to the user's workplace group + office address.
- **Privacy:** Users who have `notify_peer_pickup = false` in their messaging preferences are excluded from coworker visibility.

---

## Integration Checklist

- [ ] Add "Where do you work?" step to onboarding (after account creation).
- [ ] Implement type-ahead search against `/workplace-groups/search`.
- [ ] Show "Create new" option when no search results match.
- [ ] After group selection, fetch `/workplace-groups/{id}/addresses` and show office picker.
- [ ] Allow "Add new address" if user's office is not listed.
- [ ] Call `PUT /users/me/workplace` with selected group + address.
- [ ] Display `workplace_group_name` in user profile (from enriched user response).
- [ ] Add "Change" / "Leave" button in profile to reassign or clear workplace.
- [ ] Read `workplace_group_id` from user response (nullable).

---

## References

- [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md) — Address suggest, create, and types
- [POST_RESERVATION_PICKUP_B2C.md](POST_RESERVATION_PICKUP_B2C.md) — Coworker pickup coordination flow
- [EMPLOYER_MANAGEMENT_B2C.md](EMPLOYER_MANAGEMENT_B2C.md) — Employer entity assignment (separate from workplace groups)
