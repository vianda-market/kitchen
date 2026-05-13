# Maps API — B2C Client Guide

**Document Version**: 2.0
**Date**: May 2026
**For**: vianda-app (React Native / Expo)

---

## Overview

The backend exposes two map endpoints under `GET /api/v1/maps/`. Both require Bearer auth.

| Endpoint | Status | Purpose |
|----------|--------|---------|
| `GET /api/v1/maps/city-pins` | **Active** | Returns restaurant markers + recommended viewport + centroid anchor for client-side interactive Mapbox rendering |
| `GET /api/v1/maps/city-snapshot` | **Dormant** | Returns a cached Mapbox Static Images PNG with pin pixel positions |

> **Note on `/city-snapshot`:** This endpoint is preserved as a future cost optimization. It generates a server-side static PNG with pre-computed pixel positions, which eliminates client-side Mapbox SDK calls entirely if interactive-map MAU economics deteriorate. The active path for all clients is `/city-pins`. See plan: `~/learn/vianda/docs/plans/interactive-map-cluster-centering.md`.

---

## Active Endpoint — `GET /api/v1/maps/city-pins`

### Purpose

Returns active restaurant pins for a city together with a recommended NE/SW viewport bounding box and a centroid anchor point. The client passes the viewport to Mapbox `fitBounds()` on first paint so no projection math is needed client-side. No image is generated; no Mapbox API call is made by the server.

Markers are ordered by distance from the user's anchor (if provided) or from the city centroid (if not). The `centroid` field tells the client where to center the camera before `fitBounds` runs.

### Request

```http
GET /api/v1/maps/city-pins?city=Lima&country_code=PE
Authorization: Bearer {token}
```

**Query parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `city` | string | Yes | — | City name (same value used in `GET /restaurants/by-city`) |
| `country_code` | string | Yes | — | ISO 3166-1 alpha-2 (e.g. `PE`, `AR`). Must be exactly 2 characters, uppercase. |
| `center_lat` | float | No | null | Latitude of the user's selected address. **Required together with `center_lng`**. When provided, markers are ordered by distance from this point. |
| `center_lng` | float | No | null | Longitude of the user's selected address. **Required together with `center_lat`**. |
| `limit` | int | No | 20 | Maximum markers to return. Range: 1–50. |

**Errors:**

| Condition | Status | Code |
|-----------|--------|------|
| `country_code` is not 2 characters | 400 | `validation.invalid_format` |
| Only one of `center_lat`/`center_lng` provided | 400 | `validation.custom` |
| `limit` > 50 | 422 | FastAPI validation error |
| `city` or `country_code` omitted | 422 | FastAPI validation error |
| No auth token | 401 | — |

### Response

```json
{
  "markers": [
    {
      "restaurant_id": "019e1315-fff4-7775-ad48-cd8d4de5c41d",
      "name": "Anticuchería Don Tomás",
      "lat": -12.094425,
      "lng": -77.029649
    }
  ],
  "recommended_viewport": {
    "ne": { "lat": -12.094148, "lng": -77.022491 },
    "sw": { "lat": -12.150905, "lng": -77.040202 }
  },
  "centroid": {
    "lat": -12.094425,
    "lng": -77.029649,
    "source": "city"
  },
  "more_available": false,
  "omitted_count": 0
}
```

**When the city has no active restaurants with coordinates:**

```json
{
  "markers": [],
  "recommended_viewport": null,
  "centroid": null,
  "more_available": false,
  "omitted_count": 0
}
```

### `centroid` field

The `centroid` field is the recommended camera anchor point. It is `null` only when the city has zero geocoded restaurants.

| `source` | When | Meaning |
|---|---|---|
| `"city"` | No `center_lat`/`center_lng` provided | Precomputed city centroid (mean of all active restaurant coords, refreshed weekly). Camera should anchor here and call `fitBounds`. |
| `"user_nearest"` | User anchor provided AND nearest restaurant ≤ 10 km away | Nearest restaurant to the user's address. Camera anchors on an actual restaurant — guarantees at least one pin under the camera. |
| `"city_fallback"` | User anchor provided BUT nearest restaurant > 10 km away | User is outside the restaurant cluster. City centroid used instead; response still returns restaurants sorted from city center. Show a caption like "No viandas near you yet — showing Miraflores". |

### `more_available` and `omitted_count` fields

When the city has more restaurants than the requested `limit`:

- `more_available: true`
- `omitted_count` = (total restaurants in city) − (returned markers count)

Use these to render an overflow chip on the map (e.g. `+{omitted_count} more nearby — open list to see all`).

### Anchor behavior (three branches)

**Branch A — user anchor inside cluster** (`center_lat`/`center_lng` both provided, nearest restaurant ≤ 10 km):
- Markers ordered by distance from user address.
- `centroid.lat`/`lng` = nearest restaurant's coordinates.
- `centroid.source = "user_nearest"`.
- Viewport = bounding box of returned markers.

**Branch B — user anchor outlier** (`center_lat`/`center_lng` provided, nearest restaurant > 10 km):
- Markers ordered by distance from city centroid.
- `centroid` = city centroid coords.
- `centroid.source = "city_fallback"`.
- Viewport = bounding box of returned markers (city-centered).

**Branch C — no user anchor** (`center_lat`/`center_lng` both null):
- Markers ordered by distance from city centroid.
- `centroid` = city centroid coords.
- `centroid.source = "city"`.
- Viewport = bounding box of returned markers.

### Viewport logic (server-side)

| Marker count | `recommended_viewport` |
|---|---|
| 0 | `null` |
| 1 | Tight box ±0.01° around the single marker (~1 km per axis) |
| ≥ 2 | Tight bounding box over all `(lat, lng)` pairs — no server-side padding |

For ≥ 2 markers, add UI-aware padding on the client via Mapbox `fitBounds` options (e.g. `padding: { top: 80, bottom: 80, left: 40, right: 40 }`).

### Integration pattern

```typescript
// No user anchor — city-centered
const pinsResp = await getCityPins(city, countryCode);

// User anchor — pass address coords
const pinsResp = await getCityPins(city, countryCode, {
  centerLat: selectedAddress.lat,
  centerLng: selectedAddress.lng,
  limit: 20,
});

// Anchor map camera on centroid
if (pinsResp.centroid) {
  mapRef.current?.setCamera({ centerCoordinate: [pinsResp.centroid.lng, pinsResp.centroid.lat] });
}

// Fit viewport to markers
if (pinsResp.recommended_viewport) {
  mapRef.current?.fitBounds(
    [pinsResp.recommended_viewport.sw, pinsResp.recommended_viewport.ne],
    { padding: { top: 80, bottom: 80, left: 40, right: 40 }, animated: false }
  );
}

// Overflow chip
if (pinsResp.more_available) {
  renderOverflowChip(`+${pinsResp.omitted_count} more nearby — open list to see all`);
}

// Caption by source
const captions = {
  city: `Showing restaurants in ${cityName}`,
  user_nearest: `Showing restaurants near you`,
  city_fallback: `No viandas near you yet — showing ${cityName}`,
};
renderCaption(captions[pinsResp.centroid?.source ?? 'city']);

// Render markers
pinsResp.markers.forEach(pin => {
  // Add Mapbox marker at [pin.lng, pin.lat]
  // On tap: open restaurant detail / vianda modal using pin.restaurant_id
});
```

---

## Dormant Endpoint — `GET /api/v1/maps/city-snapshot`

> This endpoint is preserved as a future cost optimization; the active path for clients is `/city-pins`. See plan: `~/learn/vianda/docs/plans/interactive-map-cluster-centering.md`.

Full documentation for the static snapshot approach (pixel positions, tap target overlay, caching behavior, dark mode) is in [`STATIC_MAP_SNAPSHOT_B2C.md`](../archived/STATIC_MAP_SNAPSHOT_B2C.md).

**Do not call this endpoint in new client code.** It remains available on the server; resume it only if interactive-map MAU economics require it (operator decision).

---

## Postman Collection

`docs/postman/collections/022 MAPS_CITY_PINS.postman_collection.json`

Run via:
```sh
bash scripts/run_newman.sh 022
```

Covers: city-anchored, user-anchor inside cluster, user-anchor outlier, only one center param → 400, limit clamp → 422, overflow chip data, empty city, auth.

---

## Architecture Note

Neither endpoint calls Mapbox from the server side for pin data. `/city-pins` is pure PostgreSQL + bounding-box math (`app/utils/map_projection.compute_bounding_box`). Centroid coordinates are read from `core.city_metadata.centroid_lat/lng` (precomputed weekly by `app/services/cron/city_centroid_job.weekly_entry`). `/city-snapshot` (dormant) calls the Mapbox Static Images API and caches in GCS. See `CLAUDE_ARCHITECTURE.md` Maps subsystem section for the full module map.
