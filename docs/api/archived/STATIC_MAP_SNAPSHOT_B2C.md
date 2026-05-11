> **ARCHIVED 2026-05-10 — dormant since the interactive-map cutover (vianda-app#214).**
>
> The active map doc is [`docs/api/b2c_client/MAPS_API.md`](../b2c_client/MAPS_API.md), which covers both `/maps/city-pins` (the live endpoint) and `/maps/city-snapshot` (the dormant endpoint this file documents in detail).
>
> This file is preserved as implementation reference if the static-image path is ever revived as a cost optimization. Do not delete without operator review.

# Static Map Snapshot — B2C Client Guide

**Document Version**: 1.0  
**Date**: April 2026  
**For**: vianda-app (React Native / Expo)

---

## Overview

The backend serves **static map images** with restaurant pin overlays via `GET /api/v1/maps/city-snapshot`. The client displays the image via `<Image>` and overlays invisible tap targets at each marker's `pixel_x`/`pixel_y` position. This replaces the native map SDK (`react-native-maps`) entirely.

**Key benefits:**
- No native map SDK dependency — works in Expo Go, web, and all platforms
- Mapbox token stays server-side — no client API key exposure
- Aggressively cached — ~1 Mapbox API call per grid cell per day, not per user
- Dark mode via `style=dark` parameter

---

## Endpoint

```http
GET /api/v1/maps/city-snapshot?city=...&country_code=...&center_lat=...&center_lng=...
```

**Auth:** Bearer token required (same as `/restaurants/by-city`).

**Query parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `city` | string | Yes | — | City name (same value used in `GET /restaurants/by-city`) |
| `country_code` | string | No | `US` | ISO 3166-1 alpha-2 |
| `center_lat` | float | Yes | — | Latitude of user's selected address |
| `center_lng` | float | Yes | — | Longitude of user's selected address |
| `width` | int | No | `600` | Image width in CSS pixels (100-1280) |
| `height` | int | No | `400` | Image height in CSS pixels (100-1280) |
| `retina` | bool | No | `true` | Return @2x image (double resolution) |
| `style` | string | No | `light` | `light` or `dark` |

**Response:**

```json
{
  "image_url": "https://storage.googleapis.com/...",
  "center": { "lat": -34.59, "lng": -58.40 },
  "zoom": 14,
  "width": 600,
  "height": 400,
  "retina": true,
  "markers": [
    {
      "restaurant_id": "abc-123",
      "name": "Green Bowl",
      "lat": -34.5880,
      "lng": -58.4023,
      "pixel_x": 273,
      "pixel_y": 173
    }
  ]
}
```

---

## Center of Gravity — Address Selection

The map is centered on the **user's selected address**. The client knows the user's addresses (from `GET /addresses`) and passes the lat/lng of the selected one.

**Address types for map center:**

| Type | Source | When to use |
|------|--------|-------------|
| **Work** | `employer_address_id` on user → address → geolocation | Default for lunch-ordering (near office) |
| **Home** | Customer Home address → geolocation | Evenings/weekends, pickup near home |
| **Other** | Address with `map_center_label = 'other'` on subpremise | Temporary — friend's house, travel, etc. |

**Client flow:**
1. User has a toggle: `[Work] [Home] [Other]`
2. On toggle, look up the selected address's lat/lng from cached address data
3. Pass `center_lat` and `center_lng` to the endpoint
4. If the user has no address of a selected type, gray out the toggle option

**"Other" address:** Users can set any address as "other" via `PUT /addresses/{id}` with `{ "map_center_label": "other" }`. Only one address should have this label at a time (client manages this). The label is stored in `address_subpremise`.

---

## Rendering the Map

### Image Display

```jsx
<Image
  source={{ uri: snapshot.image_url }}
  style={{ width: snapshot.width, height: snapshot.height }}
  resizeMode="contain"
/>
```

### Tap Target Overlay

Position invisible `<TouchableOpacity>` at each marker's `pixel_x`/`pixel_y`:

```jsx
{snapshot.markers.map(marker => (
  <TouchableOpacity
    key={marker.restaurant_id}
    style={{
      position: 'absolute',
      left: marker.pixel_x * (renderedWidth / snapshot.width) - 22,
      top: marker.pixel_y * (renderedHeight / snapshot.height) - 22,
      width: 44,
      height: 44,
    }}
    onPress={() => openPlateModal(marker.restaurant_id)}
  />
))}
```

**Responsiveness:** If the `<Image>` renders at a different size than the requested `width` x `height`, scale pixel positions proportionally:
```
rendered_x = pixel_x * (rendered_width / width)
rendered_y = pixel_y * (rendered_height / height)
```

Use `onLayout` to get the rendered dimensions.

### Tap target size

Minimum 44x44 points for accessibility (Apple HIG / WCAG 2.5.5). Center the tap target on the marker position.

---

## Integration with Existing Endpoints

Call in parallel with `GET /restaurants/by-city`:

```javascript
const [restaurants, mapSnapshot] = await Promise.all([
  getRestaurantsByCity(city, countryCode, { marketId, kitchenDay }),
  getCityMapSnapshot(city, countryCode, { centerLat, centerLng, width, height, style }),
]);
```

The by-city endpoint returns restaurant data (plates, kitchen days, etc.). The map snapshot returns only the visual map and pin positions. They complement each other.

---

## Fallback Behavior

| Scenario | Response | Frontend action |
|----------|----------|-----------------|
| No restaurants with coordinates | `image_url: null`, `markers: []` | Show "No restaurants in this area yet" text |
| Mapbox API error | `image_url: null` | Show text list (existing fallback) |
| GCS upload fails | `image_url: null` | Show text list |
| City not found | HTTP 404 | Same as `/restaurants/by-city` 404 handling |

---

## Dark Mode

Request `style=dark` to get the dark-themed image. The backend selects the corresponding Mapbox Studio style. Both light and dark images are cached independently.

---

## Caching Behavior

- Images are cached in GCS for 24 hours
- Users within ~500m share the same cached image (grid-cell cache key)
- When restaurants are added/removed/moved, the cache refreshes on next request
- The `image_url` is a time-limited signed URL (24h expiry) — do not persist it across sessions

---

## Fallback: Mapbox Maps SDK

The static image approach is experimental. Monitor:
- **Tap accuracy** — are users hitting the right restaurant pins across device sizes?
- **Image quality** — is zoom 14 the right level for all cities?
- **Engagement** — do users interact with the map, or do they prefer the text list?

**If static images prove insufficient**, the B2C app should be prepared to swap to `@rnmapbox/maps` (Mapbox Maps SDK for React Native):

- **No backend changes needed** — `GET /restaurants/by-city` already returns `lat`, `lng`, `name`, `restaurant_id` per restaurant. The SDK renders markers client-side from this existing data.
- **Mapbox access token** would need to be provisioned client-side for the SDK (unlike static images where it stays server-side). Coordinate with infra team.
- **The `/maps/city-snapshot` endpoint remains available** even if the SDK is adopted — useful as a lightweight preview, web fallback, or loading placeholder.
- **Evaluation doc:** `vianda-app/docs/plans/MAPBOX_MAPPING.md` already compares Option A (SDK), B (static images), and C (hybrid). Refer to it for migration guidance.

The decision to stay with static images or upgrade to the SDK should be based on real user feedback after launch, not hypothetical requirements.
