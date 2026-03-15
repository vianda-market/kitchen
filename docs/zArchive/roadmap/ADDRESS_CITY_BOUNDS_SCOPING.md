# Address City Bounds Scoping

**Status**: Superseded (2026-03-09)  
**Last Updated**: 2026-03-09  
**Purpose**: (Historical) Add lat/lng bounds per supported city; use `locationBias` or `locationRestriction` with Google Autocomplete to constrain suggestions to our metro areas.

**Superseded by**: Loosen address search restrictions. Suggest no longer uses city bounds; suggestions return addresses anywhere in the country. See [ADDRESSES_API_CLIENT.md](../api/shared_client/ADDRESSES_API_CLIENT.md).

---

## Current State

- Suggest uses `includedRegionCodes` with supported country codes (e.g. AR, US, PE)
- Country-level restriction is coarse; many cities exist within each country
- API may return suggestions outside our supported cities

---

## Target State

- Config: `(lat_sw, lng_sw, lat_ne, lng_ne)` per supported city
- Metro area bounds are stable (city footprints rarely change)
- When opening new cities, define bounds as part of launch
- Suggest: Use `locationRestriction.rectangle` (or `locationBias`) with bounds for the user's selected city
- Optional: When no city selected, use country bounds (aggregate of city bounds) or skip

---

## Config Shape

```python
# Example: supported_cities_bounds.py
CITY_BOUNDS = {
    ("AR", "CABA"): {"south": -34.70, "west": -58.55, "north": -34.52, "east": -58.35},
    ("US", "WA"): {"south": 47.45, "west": -122.45, "north": 47.75, "east": -122.20},
    # ...
}
```

---

## Google API

- **locationRestriction**: `rectangle` with `low` (southwest) and `high` (northeast)
- **locationBias**: Soft bias; suggestions outside bounds still possible
- **locationRestriction**: Hard filter; only results within rectangle

---

## Use in Suggest

1. Client sends `city` (and optionally `province`, `country`) from dropdown
2. Backend resolves to supported city, gets bounds
3. Add `locationRestriction: { rectangle: { low: {...}, high: {...} } }` to Autocomplete request
4. If city not in bounds config, fall back to `includedRegionCodes` only

---

## New City Launches

When adding a city to `supported_cities`:

1. Define bounds: Use Google Maps or GeoJSON to get metro polygon/rectangle
2. Add to `CITY_BOUNDS` config
3. Test suggest with bounds; verify results are within city
