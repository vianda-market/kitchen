# Restaurant Address Picker – Enriched Addresses and Optional Search

**Date**: February 2026  
**Context**: When creating or editing a restaurant, the B2B client lets users pick an address. We need addresses scoped to the restaurant’s institution and a clear display label.

---

## Address types when creating addresses (B2B)

When **creating** or **editing** addresses (e.g. for a restaurant or employer), restrict **address_type** to what the current user’s role allows. See [ADDRESSES_API_CLIENT.md](../../shared_client/ADDRESSES_API_CLIENT.md#address-types-by-role-form-ux): **Supplier** (Admin/Manager) may only use **Restaurant**, **Entity Billing**, **Entity Address** (and **Customer Employer** in employer-address flows). Do not offer or send other types in the form; the backend returns **403** for disallowed types.

---

## Current B2B behavior

1. **Address field**
   - Uses `GET /api/v1/addresses/enriched/` to load options.
   - We store and send `address_id`; the value is correct.

2. **Display**
   - Previously we showed only `city`. We now build a label from existing enriched fields: `street_name · city · postal_code` (any of these may be empty in the response).

3. **Institution scope**
   - We filter options by the restaurant’s institution: only addresses where `institution_id` matches the restaurant’s `institution_id` are shown. This requires `institution_id` (or equivalent) on each item from the addresses enriched endpoint.

4. **UX**
   - The field is a type-to-search (autocomplete) list over the institution-filtered options, so users can quickly find an address when there are many.

---

## Backend contract / suggestions

### Enriched endpoint `GET /api/v1/addresses/enriched/`

- **Must**
  - Return `institution_id` (or equivalent) on each address so the client can filter to “addresses for this restaurant’s institution.” The B2B client already expects this on `AddressEnriched`.

- **Should (optional but helpful)**
  - Return enough fields for a readable label, e.g.:
    - `street_name`, `city`, `postal_code` (we already use these to build `street_name · city · postal_code`).
  - Optionally add a single **formatted_address** (or **address_line**) so the client can show one consistent line without concatenating (and so other clients can reuse it).

### Optional: address search by institution

- If you add a search endpoint, e.g. `GET /api/v1/addresses/search/` (or under enriched), with:
  - `institution_id` (required or optional) to restrict to an institution.
  - `q` (or similar) for a text query.
- then the B2B client could later switch to server-side search instead of loading all institution addresses and filtering in the UI. Not required for current behavior.

---

## Summary

| Item | Status |
|------|--------|
| Client filters by restaurant’s institution | Done (using `institution_id` from enriched). |
| Client shows richer label (street · city · postal_code) | Done (using existing enriched fields). |
| Enriched must expose `institution_id` per address | **Done** – enriched responses include `institution_id`. |
| Optional `formatted_address` / `address_line` | **Done** – each enriched address includes `formatted_address` (street_name · city · postal_code). |
| Optional search endpoint by institution + q | **Done** – `GET /api/v1/addresses/search/` with `institution_id`, `q`, `limit`. |

---

## Backend implementation (done)

- **`GET /api/v1/addresses/enriched/`** and **`GET /api/v1/addresses/enriched/{address_id}`**  
  Response includes `institution_id`, `formatted_address` (single display line), plus existing fields.

- **`GET /api/v1/addresses/search/`**  
  Query params: `institution_id` (optional), `q` (optional text search), `limit` (default 50), `include_archived`.  
  Same auth/scoping as enriched list. Returns same enriched shape including `formatted_address`.
