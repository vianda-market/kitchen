# Maps API — B2C Client Guide

**Document Version**: 1.0
**Date**: May 2026
**For**: vianda-app (React Native / Expo)

---

## Overview

The backend exposes two map endpoints under `GET /api/v1/maps/`. Both require Bearer auth.

| Endpoint | Status | Purpose |
|----------|--------|---------|
| `GET /api/v1/maps/city-pins` | **Active** | Returns restaurant markers + recommended viewport for client-side interactive Mapbox rendering |
| `GET /api/v1/maps/city-snapshot` | **Dormant** | Returns a cached Mapbox Static Images PNG with pin pixel positions |

> **Note on `/city-snapshot`:** This endpoint is preserved as a future cost optimization. It generates a server-side static PNG with pre-computed pixel positions, which eliminates client-side Mapbox SDK calls entirely if interactive-map MAU economics deteriorate. The active path for all clients is `/city-pins`. See plan: `~/learn/vianda/docs/plans/interactive-map-cluster-centering.md`.

---

## Active Endpoint — `GET /api/v1/maps/city-pins`

### Purpose

Returns all active restaurant pins for a city together with a recommended NE/SW viewport bounding box. The client passes the viewport to Mapbox `fitBounds()` on first paint so no projection math is needed client-side. No image is generated; no Mapbox API call is made by the server.

### Request

```http
GET /api/v1/maps/city-pins?city=Lima&country_code=PE
Authorization: Bearer {token}
```

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `city` | string | Yes | City name (same value used in `GET /restaurants/by-city`) |
| `country_code` | string | Yes | ISO 3166-1 alpha-2 (e.g. `PE`, `AR`). Must be exactly 2 characters, uppercase. |

**Errors:**

| Condition | Status | Code |
|-----------|--------|------|
| `country_code` is not 2 characters | 400 | `validation.invalid_format` |
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
  }
}
```

**When the city has no active restaurants with coordinates:**

```json
{
  "markers": [],
  "recommended_viewport": null
}
```

### Viewport logic (server-side)

| Marker count | `recommended_viewport` |
|---|---|
| 0 | `null` |
| 1 | Tight box ±0.01° around the single marker (~1 km per axis) |
| ≥ 2 | Tight bounding box over all `(lat, lng)` pairs — no server-side padding |

For ≥ 2 markers, add UI-aware padding on the client via Mapbox `fitBounds` options (e.g. `padding: { top: 80, bottom: 80, left: 40, right: 40 }`).

### Integration pattern

```javascript
// Fetch markers and restaurants in parallel
const [restaurants, pinsResp] = await Promise.all([
  getRestaurantsByCity(city, countryCode, { marketId, kitchenDay }),
  getCityPins(city, countryCode),
]);

// On first map load
if (pinsResp.recommended_viewport) {
  mapRef.current?.fitBounds(
    [pinsResp.recommended_viewport.sw, pinsResp.recommended_viewport.ne],
    { padding: { top: 80, bottom: 80, left: 40, right: 40 }, animated: false }
  );
}

// Render markers
pinsResp.markers.forEach(pin => {
  // Add Mapbox marker at [pin.lng, pin.lat]
  // On tap: open restaurant detail / plate modal using pin.restaurant_id
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

---

## Architecture Note

Neither endpoint calls Mapbox from the server side for pin data. `/city-pins` is pure PostgreSQL + bounding-box math (`app/utils/map_projection.compute_bounding_box`). `/city-snapshot` (dormant) calls the Mapbox Static Images API and caches in GCS. See `CLAUDE_ARCHITECTURE.md` Maps subsystem section for the full module map.
