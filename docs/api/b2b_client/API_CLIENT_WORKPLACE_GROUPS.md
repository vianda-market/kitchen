# Workplace Groups — B2B Admin Guide

**Audience:** B2B platform (Internal Admin / Super Admin). Manage, curate, and bulk-create workplace groups.  
**Last updated:** 2026-04

---

## Overview

Workplace groups are lightweight, customer-created groupings for B2C coworker pickup coordination. They are **not** employer entities — no billing, no tax IDs, no benefit programs. Internal admins manage them for curation purposes: renaming offensive entries, archiving duplicates, pre-populating groups for launch campaigns, and managing group addresses.

---

## Admin Endpoints

### List All Groups (Paginated)

```http
GET /api/v1/admin/workplace-groups?page=1&page_size=20
Authorization: Bearer <token>
```

Returns all workplace groups (including archived). Standard pagination via `page` / `page_size` query params, `X-Total-Count` response header.

**200 OK:**

```json
[
  {
    "workplace_group_id": "019cc3e5-989d-79aa-847f-683c8b321175",
    "name": "BigCorp Buenos Aires",
    "email_domain": "bigcorp.com",
    "require_domain_verification": false,
    "is_archived": false,
    "status": "active",
    "created_date": "2026-04-12T14:30:00Z"
  }
]
```

---

### List Groups Enriched

```http
GET /api/v1/admin/workplace-groups/enriched?page=1&page_size=20
Authorization: Bearer <token>
```

Same as above but includes computed fields for the curation dashboard.

**200 OK:**

```json
[
  {
    "workplace_group_id": "019cc3e5-989d-79aa-847f-683c8b321175",
    "name": "BigCorp Buenos Aires",
    "email_domain": "bigcorp.com",
    "require_domain_verification": false,
    "is_archived": false,
    "status": "active",
    "created_date": "2026-04-12T14:30:00Z",
    "member_count": 12,
    "created_by_name": "Juan Perez"
  }
]
```

| Extra field | Description |
|-------------|-------------|
| `member_count` | Number of active users linked to this group. |
| `created_by_name` | Full name of the user who created the group (from `created_by` FK). |

---

### Update Group

```http
PUT /api/v1/admin/workplace-groups/{workplace_group_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "BigCorp Argentina",
  "status": "active"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | Rename the group (max 100 chars). |
| `status` | string | No | Set to `active` or `inactive`. |
| `email_domain` | string | No | Set or clear the email domain. |
| `require_domain_verification` | boolean | No | Enable/disable domain verification (Phase 2). |

**200 OK** — Returns the updated group.

Use this for:
- **Renaming** offensive or misspelled group names.
- **Deactivating** groups (set `status = inactive`).

---

### Archive Group (Soft Delete)

```http
DELETE /api/v1/admin/workplace-groups/{workplace_group_id}
Authorization: Bearer <token>
```

**200 OK** — Soft-archives the group (`is_archived = true`). Members keep their `workplace_group_id` until they change it — existing coworker matching continues to work. The group no longer appears in B2C search results.

---

### Bulk Create Groups

```http
POST /api/v1/admin/workplace-groups/bulk
Authorization: Bearer <token>
Content-Type: application/json

[
  { "name": "BigCorp Buenos Aires" },
  { "name": "MegaInc Lima" },
  { "name": "StartupCo Bogota" }
]
```

**201 Created** — Returns array of created groups. Atomic — all succeed or all fail.

Use this for **campaign pre-population** when launching in a new area. Upload a list of known companies so customers find them on first search.

---

## Group Address Management

Internal and Employer roles can edit workplace group addresses. Customers can only view and add addresses (not edit).

### List Group Addresses

```http
GET /api/v1/workplace-groups/{workplace_group_id}/addresses
Authorization: Bearer <token>
```

**200 OK** — Returns all non-archived addresses for this group.

### Add Address to Group

```http
POST /api/v1/workplace-groups/{workplace_group_id}/addresses
Authorization: Bearer <token>
Content-Type: application/json

{
  "place_id": "mapbox-place-id-string"
}
```

Uses the standard address creation flow. See [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md).

### Edit Group Address

```http
PUT /api/v1/workplace-groups/{workplace_group_id}/addresses/{address_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "street_name": "Av. Corrientes 1234",
  "city": "Buenos Aires"
}
```

**403 Forbidden** for Customer role. Only Internal and Employer roles can edit.

---

## Key Differences from Employer Entities

| Aspect | Workplace Group | Employer Entity |
|--------|----------------|-----------------|
| **Purpose** | Coworker pickup coordination | Benefits billing and enrollment |
| **Created by** | Any customer (or Internal admin) | Employer admin in B2B platform |
| **Has tax ID?** | No | Yes |
| **Has billing?** | No | Yes (benefit programs, invoices) |
| **Scoped to institution?** | No (global) | Yes (institution-scoped) |
| **User field** | `workplace_group_id` | `employer_entity_id` |

---

## Curation Workflow

1. **Monitor** — Use enriched list endpoint sorted by `created_date` to review new groups.
2. **Rename** — Fix misspellings or offensive names via `PUT`.
3. **Merge duplicates** — Archive the duplicate group. Reassign members to the canonical group (future: dedicated merge endpoint).
4. **Pre-populate** — Bulk create groups for known companies before launching in a new market.

---

## Integration Checklist

- [ ] Add "Workplace Groups" page under Admin navigation.
- [ ] Fetch enriched list with pagination for the main table view.
- [ ] Show `member_count` and `created_by_name` in table columns.
- [ ] Implement inline edit for `name` (or edit modal).
- [ ] Add archive button with confirmation dialog.
- [ ] Build bulk create form (or CSV upload) for campaign pre-population.
- [ ] Show group addresses in a detail/expand view with edit capability.
- [ ] Use standard pagination pattern. See [GENERIC_PAGINATION_CLIENT.md](../shared_client/GENERIC_PAGINATION_CLIENT.md).

---

## References

- [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md) — Address suggest, create, and types
- [API_CLIENT_INSTITUTIONS.md](API_CLIENT_INSTITUTIONS.md) — Institution model (workplace groups are NOT institutions)
- [BULK_API_PATTERN.md](../shared_client/BULK_API_PATTERN.md) — Atomic bulk create/update/delete pattern
- [ENRICHED_ENDPOINT_PATTERN.md](../shared_client/ENRICHED_ENDPOINT_PATTERN.md) — Enriched endpoint conventions
