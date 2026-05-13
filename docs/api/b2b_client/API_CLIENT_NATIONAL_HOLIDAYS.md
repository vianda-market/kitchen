# National holidays management (B2B / backoffice)

**Audience**: kitchen-web **Internal** users (Vianda operators: Admin, Super Admin, etc.).  
**Not for restaurant suppliers**: all `/api/v1/national-holidays` routes require `role_type === "Internal"`. Suppliers receive **403** — hide this section from supplier-only navigation.

**Last updated**: 2026-03-19

---

## What national holidays are

National holidays are **country-scoped** calendar dates stored in `national_holidays`. They affect product behavior platform-wide for that country:

- **Vianda selection / kitchen days**: customers generally cannot pick a kitchen day that falls on a national holiday for their country (see validation in vianda-selection flows).
- **Billing**: institution billing can skip entities when the bill date is a national holiday for that country.

They are separate from **restaurant-specific** closures (`restaurant_holidays`), which are per restaurant.

---

## Two ways data gets into the system

| Source | Purpose |
|--------|---------|
| **Automated import (Nager.Date)** | Loads **public** holidays for every **configured market** `country_code`. Rows are stored as **`source = nager_date`**, always non-recurring; re-running the job **UPSERTs** those rows so **holiday_name** can refresh if Nager corrects a label. **Active manual rows** for the same `(country_code, holiday_date)` are **never** overwritten by sync. |
| **Manual CRUD (B2B UI)** | Add, edit, bulk upload, or archive holidays when the provider is wrong, late, or missing regional exceptions. Use normal create / bulk / update / delete APIs. |

Recommendation for UX:

- Show the holiday **list** with country filter (ISO alpha-2, e.g. `AR`, `US`).
- Offer an **“Import public holidays”** (or **“Sync from provider”**) button for **Internal** users only; call the sync endpoint and display the JSON summary (**inserted** / **updated** / **skipped** / **errors** per country) in a modal or toast for support visibility.
- Keep **Add** / **Bulk import** / **Edit** / **Archive** for gaps and corrections.

---

## API base path

All routes are under **`/api/v1/national-holidays`** (no trailing slash on collection paths per API convention).

**Authorization**: `Authorization: Bearer <jwt>` for an **Internal** user.

---

## List holidays

```http
GET /api/v1/national-holidays?country_code=AR
```

- `country_code` (optional): filter by ISO country code (alpha-2).
- Returns only **non-archived** rows, ordered by `country_code`, `holiday_date`.

---

## Import public holidays (manual / button)

Use this for **mid-year refresh** or after deploy when you want the same run as the cron job without waiting for the scheduler.

```http
POST /api/v1/national-holidays/sync-from-provider
Content-Type: application/json
```

**Body (optional)**:

```json
{}
```

or omit body entirely for **default years**: current **UTC** calendar year and next year, clamped to the allowed window (see below).

**Body with explicit years** (must each fall in the allowed window):

```json
{ "years": [2026, 2027] }
```

**Year rules (UTC)**:

- Allowed range: **`[2024, current_utc_year + 2]`** inclusive.
- **Default** (no `years`): backend uses `{now, now+1}` then clamps into that range — safe for normal operations.
- **Explicit `years`**: if any year is out of range, API responds **400** with a clear `detail` message (no silent clamp on operator input).

**Success (200)**: response body is the sync summary object (useful as-is for logs or admin UI):

```json
{
  "status": "ok",
  "years": [2026, 2027],
  "inserted": { "AR": 2, "BR": 0, "CL": 1, "MX": 0, "PE": 0, "US": 1 },
  "updated": { "AR": 13, "BR": 0, "CL": 11, "MX": 11, "PE": 12, "US": 9 },
  "skipped": { "AR": 2, "BR": 0, "CL": 0, "MX": 0, "PE": 0, "US": 1 },
  "errors": []
}
```

- **`inserted`**: new **`nager_date`** rows created for that country in this run.
- **`updated`**: existing **`nager_date`** rows for that date had **`holiday_name`** (and audit fields) refreshed from Nager on conflict.
- **`skipped`**: no change applied — e.g. an **active `manual`** row already owns that `(country_code, holiday_date)`, or other cases where the upsert did not apply (see `holiday_refresh.py`).
- **`errors`**: strings such as `"BR: HTTP 404 for 2026"` when a country/year request fails; **`status`** can still be **`ok`** if other countries succeeded — show `errors` visibly so ops know partial failure.

**Failures**:

- **400**: invalid `years` (out of bounds). Show `detail` from response.
- **500**: server/database failure after validation. Show `detail`; suggest retry or check logs.

**Provider note**: Data comes from **[Nager.Date](https://date.nager.at/)** (public holidays). Coverage ahead of time varies by country; manual entries remain the fallback.

---

## Other endpoints (manual management)

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/api/v1/national-holidays/{holiday_id}` | Single row |
| `POST` | `/api/v1/national-holidays` | Create one |
| `POST` | `/api/v1/national-holidays/bulk` | Atomic bulk create |
| `PUT` | `/api/v1/national-holidays/{holiday_id}` | Update |
| `DELETE` | `/api/v1/national-holidays/{holiday_id}` | Soft delete (archive) |

Payloads and fields match **`NationalHoliday*`** schemas (`country_code`, `holiday_name`, `holiday_date`, optional recurring fields, `status`, etc.). Responses include **`source`** (`manual` for API-created rows). Clients **cannot** set **`nager_date`** via create/update. See also [BULK_API_PATTERN.md](../shared_client/BULK_API_PATTERN.md) if you use bulk create.

---

## UI checklist for the sync button

1. **Visibility**: Only render for **Internal** role (same as Plans / discretionary admin areas).
2. **Action**: `POST` to `sync-from-provider`; optional advanced field “Years (optional)” → JSON `years` array.
3. **Loading**: Request can take several seconds (many HTTP calls to Nager per country × year).
4. **Result**: On 200, parse `inserted`, `updated`, `skipped`, `errors`; if `errors.length > 0`, use a warning state even when `status === "ok"`.
5. **After success**: Refresh the holiday list (`GET` with current `country_code` filter).

---

## Related internal docs

- [HOLIDAY_TABLES_ANALYSIS.md](../internal/HOLIDAY_TABLES_ANALYSIS.md) — table purpose, automation, indexes, cron entry points.
