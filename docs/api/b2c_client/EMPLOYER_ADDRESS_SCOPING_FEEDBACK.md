# Employer Address Scoping for Coworker Search — Design Feedback

**Status:** Option A implemented (March 2026).  
**Audience:** Backend and product

---

## Problem

Currently, coworker search (GET /vianda-selections/{id}/coworkers) filters by **employer_id** only. Users at the same employer but in far-away offices (e.g. different city locations, different buildings in the same city) are all listed as potential coworkers. This is undesirable: a user in Office A should not expect someone in Office B to pick up viandas for them.

**Desired behavior:** Scope coworkers by **employer + same office**. Users in the same building/office should be grouped; users in different offices should not see each other.

**Additional constraint:** Avoid multiplying `employer_address_id` when only floor or apartment unit differs. People in the same building (e.g. 3rd floor vs 5th floor) should still be matched — they can meet at the lobby to collect viandas. For employer addresses, floor and apartment unit are not relevant for "same office" grouping.

---

## Current Schema

- **user_info**: `employer_id`, `employer_address_id` (references address_info)
- **address_info**: `floor`, `apartment_unit`, plus street/building/city/country
- **employer_info**: `address_id` (employer's primary address)

---

## Approaches

### Option A: Normalize at Storage — Omit Floor/Unit for Customer Employer Addresses

**Idea:** For address_type containing `Customer Employer`, do not store or accept `floor` and `apartment_unit`. All users at "123 Main St" (same building) share the same address_id.

**Pros:**
- Simple: one address per building per employer
- No schema change
- Coworker search: `WHERE employer_id = X AND employer_address_id = Y`

**Cons:**
- Loses floor/unit for employer addresses (may be needed for other use cases)
- Requires validation/UI to omit floor/unit when creating employer addresses

---

### Option B: Add employer_office_id (or employer_location_id)

**Idea:** New table `employer_office` (employer_id, address_id, name) where `address_id` points to a "building-level" address (no floor/unit). `user_info` gets `employer_office_id` instead of or in addition to `employer_address_id`.

**Pros:**
- Clear separation: office = building-level grouping
- Multiple offices per employer
- `user_info.employer_address_id` can still exist for display (with floor/unit) while `employer_office_id` drives coworker scoping

**Cons:**
- Schema change; migration
- More entities to manage

---

### Option C: Derive "Building Key" from Address

**Idea:** Create a computed key from address: `(country_code, province, city, postal_code, street_type, street_name, building_number)` — exclude floor, apartment_unit. Use this for grouping. Could be a generated column or a separate lookup table.

**Pros:**
- No need to change how addresses are stored
- Flexible: can group by building without new tables

**Cons:**
- Requires consistent address formatting
- Matching logic more complex (string comparison or hash)
- Edge cases: same building, different spellings

---

### Option D: employer_base_address_id (Parent Address)

**Idea:** Add `parent_address_id` or `base_address_id` to address_info. When user selects an employer address with floor/unit, we store the "base" (building-level) address_id. Multiple address rows (e.g. 3rd floor, 5th floor) map to the same base.

**Pros:**
- Keeps floor/unit for display
- Single field for scoping: `employer_base_address_id`

**Cons:**
- Need to define how base addresses are created/linked
- Possible duplication of address rows

---

## Recommendation

**Option A** was selected and implemented. Employer addresses omit floor/unit at create/update. Coworker search scopes by `employer_id` and `employer_address_id`.

---

## Implementation (Option A — Completed)

1. **Address API:** When creating an address with `employer_id` (employer flow), the backend strips `floor` and `apartment_unit` before saving. When updating an address that has Customer Employer type, the backend strips `floor` and `apartment_unit` from the update payload.
2. **Coworker query:** Coworkers are filtered by `employer_id` AND `employer_address_id` (same office). Users with `employer_address_id` see only coworkers with the same `employer_address_id`. Users with no `employer_address_id` see only coworkers who also have no `employer_address_id`.
3. **Client documentation:** See [ADDRESSES_API_CLIENT.md](../shared_client/ADDRESSES_API_CLIENT.md#customer-employer-floor-and-apartment_unit-omitted) — clients should not send floor/unit for Customer Employer addresses.
