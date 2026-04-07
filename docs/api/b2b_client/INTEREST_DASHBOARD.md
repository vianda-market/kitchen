# Lead Interest Dashboard — B2B Internal View

**Audience:** vianda-platform (B2B) agent  
**Auth required:** Internal role (Employee) — `get_employee_user` dependency  
**Section:** Dashboard & Core area, Internal employees only

---

## Overview

The marketing site and B2C app collect "notify me" interest from prospective customers, employers, and suppliers. This endpoint exposes that data as a read-only table for Internal employees to track demand by geography and interest type.

---

## Endpoint

```
GET /api/v1/admin/leads/interest
Authorization: Bearer {token}
```

### Query Parameters

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `country_code` | string | No | Filter by country (e.g. "US", "AR") |
| `city_name` | string | No | Filter by city name |
| `interest_type` | string | No | `customer`, `employer`, or `supplier` |
| `status` | string | No | `active`, `notified`, or `unsubscribed` |
| `cuisine_id` | UUID | No | Filter by cuisine UUID |
| `employee_count_range` | string | No | Filter by company size range (e.g. `51-100`) |
| `created_after` | datetime | No | Filter: created on or after this date (ISO 8601, e.g. `2026-04-01T00:00:00Z`) |
| `created_before` | datetime | No | Filter: created on or before this date (ISO 8601, e.g. `2026-04-30T23:59:59Z`) |
| `page` | int | No | Page number (default 1) |
| `page_size` | int | No | Results per page (default 50, max 200) |

### Response

**Status:** 200  
**Headers:** `X-Total-Count: {total}` — total matching records for pagination

**Body:** Array of interest records:
```json
[
  {
    "lead_interest_id": "uuid",
    "email": "user@example.com",
    "country_code": "US",
    "city_name": "Austin",
    "zipcode": "78701",
    "zipcode_only": false,
    "interest_type": "customer",
    "business_name": null,
    "message": null,
    "status": "active",
    "source": "marketing_site",
    "created_date": "2026-04-05T12:00:00Z"
  }
]
```

### Field Reference

| Field | Description |
|-------|-------------|
| `lead_interest_id` | UUID primary key |
| `email` | Contact email (case-insensitive) |
| `country_code` | ISO 3166-1 alpha-2 |
| `city_name` | City from dropdown (null if employer/supplier didn't specify) |
| `zipcode` | Optional zipcode |
| `zipcode_only` | If `true`, user only wants alerts for their specific zipcode |
| `interest_type` | `customer` / `employer` / `supplier` |
| `business_name` | Company/restaurant name (employer and supplier types) |
| `message` | Free-text context from the user |
| `cuisine_id` | UUID reference to a cuisine (nullable). For customer/supplier interest. |
| `employee_count_range` | Company size range string, e.g. `"51-100"` (nullable). For employer interest. |
| `status` | `active` (new), `notified` (alert sent), `unsubscribed` |
| `source` | `marketing_site` or `b2c_app` |
| `created_date` | When the interest was submitted |

---

## UI Requirements

### Table
- **Columns:** email, country, city, zipcode, zipcode_only, interest_type, business_name, cuisine_id, employee_count_range, source, created_date, status
- **Sortable:** by date (default newest first), by city, by country, by interest_type
- **Filterable:** country, city, interest_type, cuisine_id, employee_count_range, date range (`created_after`/`created_before`), status
- **Pagination:** Use `page` / `page_size` params + `X-Total-Count` header

### Visibility
- **Internal employees only** — not visible to Suppliers or Employers
- Place in the Dashboard & Core section of the B2B platform

### Phase 1: Read-only
No actions in Phase 1. Future enhancements (not in scope now):
- Bulk export to CSV
- "Mark as contacted" action
- Aggregate charts (interest by city, interest over time)
- Trigger manual notification to a cohort

---

## Error Responses

| Status | When |
|--------|------|
| 401 | Missing or invalid JWT |
| 403 | Non-Internal role (Supplier, Customer, Employer) |
