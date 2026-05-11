# City Map View Roadmap

**Last updated**: 2026-03-08  
**Status**: Planning  
**Related**: [EXPLORE_FILTERS_ROADMAP.md](EXPLORE_FILTERS_ROADMAP.md) — radius and other filters for Explore

---

## Overview

**Goal**: Offer both list view and map view on the Explore tab. The map centers on the user's chosen focus address (home or work) and shows restaurant pins within a configurable radius. Logic lives in the backend where possible; the UI mainly displays precomputed data.

**Current state**: Explore tab has city selection (dropdown), list view, and a map section. The map uses city-level data. We need:
- Address-based focus (home vs work)
- Toggle between list and map view
- Radius filtering (from Filters roadmap)
- Cost-efficient pin serving (use stored geolocation, not per-load external APIs)

---

## User flow

1. User selects a **city** from the existing dropdown.
2. User chooses **focus address**: Home or Work (employer address). This is the anchor point for both map and list.
3. User sets **radius** (miles) — from Filters roadmap; applies to both views.
4. User toggles **list view** vs **map view**.
5. **Map view**: Centers on the focus address; shows user marker + restaurant pins within radius.
6. **List view**: Same filtered restaurants, shown as list. Both views use the same backend response.

**Default focus**: The user's default address (via `address_info.is_default` or equivalent) is used for both map and list when no override is set. User can toggle focus and optionally persist as new default.

---

## Backend requirements

### Data and storage

| Requirement | Details |
|-------------|---------|
| **Address geolocation** | Backend already stores lat/lng for addresses (geocoding on create/update). No real-time geocoding for map loads. |
| **Default address** | Use existing `address_info.is_default` (or equivalent) for the user's default focus address. One address can be marked default; used for Explore when user has not explicitly toggled. |
| **Focus type** | Backend must know whether to use home or work as center. Options: (a) derive from default address's `address_type` (Customer Home vs Customer Employer), or (b) add `explore_focus_address_id` / `explore_focus_type` to user preferences if product needs explicit control. Confirm with product. |

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| **Extend `GET /api/v1/restaurants/by-city`** (or new variant) | Accept `focus_address_id` (or `focus_type` = home/work), `radius_miles`. Return: (1) `center` = lat/lng of focus address, (2) `restaurants` = list filtered by distance from center (≤ radius_miles). Each restaurant: `restaurant_id`, `name`, `lat`, `lng`, `cuisine`, `distance_miles` (optional). |
| **User addresses** | `GET /api/v1/addresses/` (or `/users/me/addresses`) already returns user addresses with `lat`, `lng`, `address_type`, `is_default`. Client uses this to get home and work addresses and their coordinates. |

### Logic to implement (backend)

1. **Focus address resolution**: Given `focus_address_id` or `focus_type` (home/work), resolve the user's home address (Customer Home) or employer/work address (Customer Employer). If user has no employer, only home is valid.
2. **Distance filtering**: Filter restaurants by distance from focus address center. Use Haversine or PostGIS `ST_DWithin`; avoid external geocoding APIs on each request.
3. **Pin data**: Restaurant pins use stored `address_info` lat/lng (or restaurant geolocation). No Google Places or similar per-request lookups.
4. **City scoping**: Continue to scope by city (and market) so we only return restaurants in the selected city. Radius is an additional filter within that city.

### Questions for backend

- [ ] How is default address stored? `address_info.is_default` per user? Per institution?
- [ ] Should we add `explore_focus_address_id` or `explore_focus_type` (home/work) to user preferences, or derive from default address?
- [ ] Confirm `GET /api/v1/restaurants/by-city` (or new endpoint) can accept `focus_address_id`, `radius_miles` and return distance-filtered results with center from that address.
- [ ] Restaurant addresses: Confirm all restaurant/institution addresses have lat/lng stored for pin display.

---

## Frontend requirements

### UI components

| Component | Description |
|-----------|-------------|
| **List / Map toggle** | Switch between list view and map view. Both show the same filtered data. |
| **Focus address toggle** | "Home" vs "Work" — which address to center on. Disabled "Work" if user has no employer address. |
| **Default focus** | Option to "Use as default for Explore" — persists via address `is_default` or user preferences (per backend contract). |
| **Map** | Center on focus address; show user marker + restaurant pins. Use `react-native-maps` (existing). Tap pin → restaurant detail or plate modal. |

### Data flow

1. On city select + focus + radius: Call backend with `city`, `country_code`, `focus_address_id` (or `focus_type`), `radius_miles`, `market_id`, `kitchen_day`.
2. Backend returns `center` (lat/lng), `restaurants` (with lat, lng, distance).
3. Map: Set region to center; render user marker at center; render restaurant pins from `restaurants`.
4. List: Render same `restaurants` as list (existing list UI).

### Edge cases

- **No employer**: Only home address available; Work toggle hidden or disabled.
- **No addresses**: Show empty state; prompt user to add home address.
- **Address without lat/lng**: Backend should not return such addresses as valid focus; or exclude and show error.

---

## Dependencies

- **EXPLORE_FILTERS_ROADMAP**: Radius is a filter; Filters roadmap defines radius options and persistence.
- **Existing**: `GET /api/v1/restaurants/cities`, `GET /api/v1/restaurants/by-city`, `GET /api/v1/addresses/` (or equivalent).

---

## Implementation phases

1. **Backend**: Extend by-city (or new endpoint) with focus_address_id, radius_miles; implement distance filter; return center + filtered restaurants.
2. **Frontend**: Add focus toggle (home/work), wire to backend; add list/map toggle; map centers on focus, shows pins.
3. **Polish**: Default focus persistence; loading states; error handling when address has no coordinates.

---

## References

- [RESTAURANT_EXPLORE_B2C.md](../api/backend/b2c_client/RESTAURANT_EXPLORE_B2C.md)
- [EXPLORE_TAB_BACKEND_SPEC.md](../api/backend/b2c_client/EXPLORE_TAB_BACKEND_SPEC.md)
- [ADDRESSES_API_CLIENT.md](../api/backend/shared_client/ADDRESSES_API_CLIENT.md)
