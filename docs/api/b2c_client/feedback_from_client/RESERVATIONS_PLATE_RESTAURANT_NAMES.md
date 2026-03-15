# Reservations page: Plate and restaurant names showing fallbacks

**Status**: Resolved (client workaround)  
**Reported**: B2C app (vianda-app)  
**Context**: Reservations tab — booked plates list

---

## Symptom

On the Reservations page, a booked plate card shows:
- **Plate name**: "Plate" (fallback) instead of the actual product name
- **Restaurant name**: "Restaurant" (fallback) instead of the actual restaurant name
- **Days and pickup time**: Correct (from `pickup_date` / `pickup_time_range` in plate-selections response)

This indicates the client is falling back to placeholder text because `product_name` and `restaurant_name` are missing or null in the enriched plate response.

---

## Client flow

1. **List reservations**
   - `GET /api/v1/plate-selections/` returns plate selections with `plate_id`, `target_kitchen_day`, `pickup_date`, `pickup_time_range`, etc.
   - The list endpoint does **not** include plate or restaurant names.

2. **Enrich each selection**
   - For each unique `plate_id`, the client calls:
     `GET /api/v1/plates/enriched/{plate_id}` **(do not pass `?kitchen_day=`)** — see resolution below.
   - The client displays:
     - `product_name` → Plate name (fallback: `"Plate"` when null/undefined/empty)
     - `restaurant_name` → Restaurant name (fallback: `"Restaurant"` when null/undefined/empty)
   - If the enriched call **fails** (4xx/5xx), the client receives no data for that selection and also shows the fallbacks.

3. **API contract (PLATE_API_CLIENT.md)**
   - The enriched plate response is documented to include `product_name` (string) and `restaurant_name` (string).
   - Example: `"product_name": "Grilled Chicken Bowl"`, `"restaurant_name": "La Cocina"`.

---

## Possible causes

1. **Missing fields in enriched response**
   - `GET /api/v1/plates/enriched/{plate_id}` returns null, undefined, or empty for `product_name` and/or `restaurant_name` for some plates.
   - May be scoping- or role-related (e.g. certain plates not returning full product/restaurant info).

2. **Enriched call failing**
   - For certain `plate_id` + `kitchen_day` combinations, the enriched endpoint returns 404, 500, or another error.
   - The client uses `Promise.allSettled`; failed calls result in no enriched data for that selection, so fallbacks are shown.

3. **Kitchen day parameter** ✅ Root cause
   - The client was passing `?kitchen_day=` when calling the enriched endpoint. This triggers a backend bug (500 Internal Server Error), so the client received no data and showed fallbacks.
   - **Resolution:** Do not pass `kitchen_day` when calling `GET /api/v1/plates/enriched/{plate_id}` for the Reservations page. The endpoint does not require it for `product_name` and `restaurant_name`; omit the query parameter entirely.

---

## Request for backend

Please review and verify:

| Check | Description |
|-------|--------------|
| Response shape | Ensure `GET /api/v1/plates/enriched/{plate_id}` (called **without** `?kitchen_day=`) always includes non-empty `product_name` and `restaurant_name` for plates that can appear in `GET /api/v1/plate-selections/`. |
| Failed calls | Backend bug: passing `kitchen_day` causes 500. Client workaround: omit `kitchen_day` for Reservations. Backend should fix the handler to accept or ignore the param. |
| Contract alignment | Per [PLATE_API_CLIENT.md](../../shared_client/PLATE_API_CLIENT.md#enriched-plate-endpoint), `product_name` and `restaurant_name` should be populated. |

---

## Client action required

**For the Reservations page:** Do **not** pass the `kitchen_day` query parameter when calling `GET /api/v1/plates/enriched/{plate_id}`. Call:

```
GET /api/v1/plates/enriched/{plate_id}
```

instead of `GET /api/v1/plates/enriched/{plate_id}?kitchen_day=Monday` (or similar).

Passing `kitchen_day` causes the backend to return 500, which results in the fallbacks ("Plate", "Restaurant") being shown. For the Reservations use case, `product_name` and `restaurant_name` do not require `kitchen_day`; omit the parameter so the endpoint can succeed once the backend fix is deployed.
