# Explore Filters Roadmap

**Last updated**: 2026-03-08  
**Status**: Planning  
**Related**: [CITY_MAP_VIEW_ROADMAP.md](CITY_MAP_VIEW_ROADMAP.md) — map view uses radius filter; both list and map use these filters

---

## Overview

**Goal**: Add filters to the Explore page so users can narrow restaurant results. Start simple with three filters: **radius** (distance in miles), **cuisine**, and **dietary attributes**. Filters apply to both list view and map view.

**Current state**: Explore shows restaurants by city (and market, kitchen day). No user-applied filters.

---

## Filters (initial scope)

| Filter | Type | Description |
|--------|------|--------------|
| **Radius** | Selectable (miles) | Distance from the user's focus address (home or work). Only show restaurants within this radius. Options TBD (e.g. 5, 10, 15, 25 miles). |
| **Cuisine** | Multi-select or single | Filter by restaurant cuisine. Values from `GET /api/v1/cuisines/`. |
| **Dietary attributes** | Multi-select | Filter by dietary tags (e.g. vegetarian, vegan, gluten-free, halal). Values TBD — backend must define source. |

---

## Backend requirements

### Data sources

| Filter | Source | Notes |
|--------|--------|-------|
| **Cuisine** | `GET /api/v1/cuisines/` | Already exists. Restaurants have `cuisine` field. |
| **Dietary** | TBD | Viandas/restaurants may have dietary info (see VIANDA_API_CLIENT: `dietary` on vianda). Backend must define: (a) enum or list of supported dietary attributes, (b) where they live (vianda, restaurant, or both), (c) filtering logic (e.g. show restaurants that have at least one vianda with selected dietary). |
| **Radius** | Computed | Backend computes distance from focus address; filters restaurants by `radius_miles`. |

### Endpoint changes

**Extend `GET /api/v1/restaurants/by-city`** (or equivalent) to accept:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `radius_miles` | number | No | Max distance in miles from focus address. Omit = no distance filter (or default). |
| `cuisine` | string or string[] | No | Filter by cuisine. Single value or comma-separated. Values from cuisines API. |
| `dietary` | string or string[] | No | Filter by dietary attributes. Single value or comma-separated. Values from dietary enum/API (to be defined). |

**Response**: Same shape as today; `restaurants` array is filtered by the applied criteria.

**Logic (backend)**:
- **Radius**: Haversine or PostGIS distance from focus address; exclude restaurants beyond `radius_miles`.
- **Cuisine**: Filter restaurants where `cuisine` matches (exact or in list).
- **Dietary**: Filter restaurants/viandas that have the selected dietary attribute(s). Backend defines whether filter is at restaurant level (restaurant has any vianda with dietary) or vianda level (only show restaurants that have viandas matching all selected dietary).

### Questions for backend

- [ ] **Dietary attributes**: Where are they stored? Enum? Separate table? Existing `dietary` field on vianda — what values are valid?
- [ ] **Dietary filter semantics**: Filter by restaurants that have at least one vianda with selected dietary? Or require all selected dietary attributes to match?
- [ ] **Radius options**: What values should we support (5, 10, 15, 25 miles)? Should these be configurable (e.g. market-specific)?
- [ ] **Filter persistence**: Should we persist user's last filter selections (e.g. in user preferences or `address_info`) so they persist across sessions? Or always start with defaults?

---

## Frontend requirements

### UI components

| Component | Description |
|-----------|-------------|
| **Filters bar / sheet** | Expandable filters area (or modal on mobile). Shows: Radius dropdown, Cuisine multi-select, Dietary multi-select. |
| **Apply / Clear** | Apply filters → refetch from backend. Clear → reset to defaults, refetch. |
| **Active filters indicator** | Show count or chips when filters are applied (e.g. "3 filters active"). |

### Data flow

1. User opens filters; selects radius, cuisine(s), dietary attribute(s).
2. On Apply: Call `GET /api/v1/restaurants/by-city` with `radius_miles`, `cuisine`, `dietary` (plus existing `city`, `country_code`, `market_id`, `kitchen_day`, `focus_address_id`).
3. Display filtered results in list and map.

### Integration with City Map View

- Radius filter feeds into CITY_MAP_VIEW_ROADMAP: both list and map use the same `radius_miles` when fetching.
- Focus address (home/work) is the center; radius is the max distance from that center.

---

## Implementation phases

1. **Backend**: Define dietary attributes source; extend by-city with `radius_miles`, `cuisine`, `dietary`; implement filter logic.
2. **Frontend**: Add filters UI (radius, cuisine, dietary); wire to backend; show active filter state.
3. **Persistence** (optional): Save last-used filters to user preferences if product wants it.

---

## References

- [RESTAURANT_EXPLORE_B2C.md](../api/backend/b2c_client/RESTAURANT_EXPLORE_B2C.md)
- [CUISINES_API_CLIENT.md](../api/backend/shared_client/CUISINES_API_CLIENT.md)
- [VIANDA_API_CLIENT.md](../api/backend/shared_client/VIANDA_API_CLIENT.md) — dietary field on vianda
