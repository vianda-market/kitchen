# Static Map City Snapshot — Backend Roadmap

**Last Updated**: 2026-04-04  
**Status**: Implemented  
**Purpose**: Backend endpoint that serves cached static map images with restaurant pins for the B2C Explore tab, personalized to the user's selected address (home, work, or other).  
**Origin**: B2C frontend proposal — `vianda-app/docs/frontend/feedback_for_backend/static-map-images.md`  
**Frontend roadmap**: `vianda-app/docs/roadmap/MAPBOX_MAPPING.md`  
**B2C integration guide**: `docs/api/archived/STATIC_MAP_SNAPSHOT_B2C.md`

---

## Executive Summary

The B2C app's Explore tab currently uses `react-native-maps` (Google Maps SDK) to show restaurant pins in a city. The map is non-interactive — users tap a pin to view a vianda modal but rarely pan or zoom. The backend now serves **personalized static map images** centered on the user's selected address, which:

- Eliminates the heaviest native dependency in the mobile app
- Works on all platforms (iOS, Android, web, Expo Go) as a plain `<Image>`
- Keeps the Mapbox token server-side (no client API key exposure)
- Caches aggressively via grid-cell keys — nearby users (~500m) share the same image, ~20 unique images per city per day
- Shows restaurants at zoom 14 (~3 km radius) where streets and blocks are distinguishable

The endpoint `GET /api/v1/maps/city-snapshot` requires `center_lat`/`center_lng` (from the user's selected address) and:

1. Queries restaurant coordinates within the city, filters to those visible in the zoom 14 frame (max 30 pins)
2. Calls the **Mapbox Static Images API** to generate a map image with branded pin overlays
3. Stores the image in GCS (overwrite in place, versioned) and serves via signed URL
4. Returns the image URL plus pre-computed CSS pixel positions for each pin (so the frontend can overlay tap targets)

**Center-of-gravity:** Users choose which address to center on — Work (employer), Home, or Other (new flexible address type). The client passes coordinates from the selected address. Address endpoints now return `latitude`/`longitude` to support this.

**Fallback:** If static images prove insufficient (tap accuracy, zoom level, engagement), the B2C app can switch to Mapbox Maps SDK (`@rnmapbox/maps`) with no backend changes — `GET /restaurants/by-city` already returns lat/lng per restaurant.

---

## Current State vs Target

| Aspect | Current | Target |
|--------|---------|--------|
| Map rendering | Client-side Google Maps SDK (`react-native-maps`) | Backend-served static image (`<Image>` tag) |
| Map center | City center (same for all users) | User's selected address (home, work, or other) |
| Map SDK on client | Required (Google Maps on Android, Apple Maps on iOS) | None — removed entirely |
| Platform support | iOS + Android only (web = text fallback, Expo Go = placeholder) | All platforms including web and Expo Go |
| Mapbox token | N/A (uses Google) | Server-side only — never exposed to client |
| API calls per user | Every user loads map tiles | ~20 Mapbox calls per city per day (grid-cell cached) |
| Zoom level | Variable (user pan/zoom) | Fixed zoom 14 (~3 km radius, streets visible) |
| Dark mode | Limited (Google tinting only) | Full dark theme via Mapbox Studio custom style |
| Pin tap | Native marker tap events | Overlay `<TouchableOpacity>` at pre-computed pixel positions |
| Address coordinates | Not returned on address endpoints | `latitude`/`longitude` on all address responses |

---

## Open Questions — Answers

The B2C team raised 5 questions. Here are the backend answers:

### 1. Cloud Storage bucket

**Answer:** Use the existing `GCS_INTERNAL_BUCKET`. Map images are internally generated assets (not user-uploaded content). Store under path `maps/city-snapshots/{city_slug}-{country_code}-{style}-{width}x{height}{retina}.png`. The bucket already has CDN and signed URL infrastructure via `app/utils/gcs.py`.

### 2. Mapbox account

**Answer:** Already created as part of the Mapbox address migration (Phase 1). The same account and access token (`MAPBOX_ACCESS_TOKEN_*`) work for the Static Images API — Mapbox uses one token for all APIs. No additional account setup needed.

### 3. Pin customization

**Answer:** Start with Mapbox's **built-in `pin-l` markers** with custom hex color and first-letter label. This requires no Studio setup and is embedded in the Static Images API URL. If branding needs evolve, we can later upload a custom pin sprite to Mapbox Studio — the endpoint parameter stays the same (`style` controls it).

### 4. Endpoint grouping

**Answer:** New route group `GET /api/v1/maps/city-snapshot`. Maps are a distinct concern from restaurants — grouping under `/restaurants/` would conflate data and rendering. The new group also accommodates future map endpoints (e.g., delivery zones, coverage areas).

### 5. Cache invalidation

**Answer:** Yes, hooks exist. Restaurant address changes flow through `address_service.create_address_with_geocoding()` and `address_service.update_address_with_geocoding()`. We can add a post-commit signal that busts the map cache for the affected city. Additionally, restaurant create/archive in `CRUDService` can trigger invalidation. Implementation: a lightweight `invalidate_city_map_cache(city, country_code)` function called after these operations.

---

## Implementation Plan

### Phase 1: Core Endpoint + GCS Storage

#### 1.1 — Mapbox Static Images Gateway

**Create `app/gateways/mapbox_static_gateway.py`:**

Extends `BaseGateway` following the same pattern as `mapbox_search_gateway.py`.

```
MapboxStaticGateway(BaseGateway)
├── generate_static_map(center, zoom, width, height, markers, style, retina) → bytes (PNG)
```

**Mapbox Static Images API call:**
```
GET https://api.mapbox.com/styles/v1/{style_id}/static/
    {marker_overlays}/
    {center_lng},{center_lat},{zoom}/
    {width}x{height}{@2x}
    ?access_token={token}
```

**Marker overlay format** (embedded in URL path):
```
pin-l-G+4a7c59(-73.9921,40.7338),pin-l-N+4a7c59(-73.9801,40.7365)
```

Where `G` and `N` are first letters of restaurant names, `4a7c59` is the brand color hex.

**URL length constraint:** 8,192 chars max. With `pin-l-X+XXXXXX(-XXX.XXXX,XX.XXXX)` at ~40 chars per marker, supports ~150 markers per request. Sufficient for any city (we operate in urban areas with ~3-20 restaurants per city).

#### 1.2 — City Snapshot Service

**Create `app/services/city_map_service.py`:**

```python
class CityMapService:
    def get_city_snapshot(city, country_code, width, height, retina, style) -> dict:
        # 1. Query restaurant coordinates for city
        # 2. Check cache (GCS) — return cached URL if fresh
        # 3. On cache miss: compute center/zoom, call Mapbox, store in GCS
        # 4. Compute pixel positions for each marker
        # 5. Return { image_url, center, zoom, width, height, retina, markers[] }
```

**Restaurant coordinate query:** Reuse logic from `restaurant_explorer_service.py` which already JOINs `restaurant_info → address_info → geolocation_info` and computes city center via `AVG(g.latitude), AVG(g.longitude)`.

**Center and zoom computation:**
- Center: average of all restaurant lat/lng in the city (already computed in `get_restaurants_by_city`)
- Zoom: compute from bounding box of all restaurant coordinates to fit all markers within the image dimensions. Start at zoom 13 (typical urban area), decrease if markers overflow.

**Pixel position computation** (Mercator projection):
```python
def lat_lng_to_pixel(lat, lng, center_lat, center_lng, zoom, width, height):
    scale = 256 * (2 ** zoom)
    pixel_x = width / 2 + (lng - center_lng) * scale / 360
    lat_rad = math.radians(lat)
    center_lat_rad = math.radians(center_lat)
    mercator_y = math.log(math.tan(math.pi / 4 + lat_rad / 2))
    center_mercator_y = math.log(math.tan(math.pi / 4 + center_lat_rad / 2))
    pixel_y = height / 2 - (mercator_y - center_mercator_y) * scale / (2 * math.pi)
    return round(pixel_x), round(pixel_y)
```

Pixel coordinates are in **CSS pixels** (not physical pixels), so the frontend can position overlays using standard layout units regardless of `@2x` retina.

**Responsiveness contract:** The backend returns `pixel_x`/`pixel_y` relative to the requested `width` x `height` (in CSS pixels). If the frontend renders the image at a different size (e.g., the image is 600x400 but the `<Image>` is laid out at 375x250 on a smaller screen), the frontend must scale tap target positions proportionally: `rendered_x = pixel_x * (rendered_width / width)`. The backend does not need to know the rendered size — it returns coordinates in the canonical requested dimensions.

**Pin count limit:** If a city has more than 30 restaurants with coordinates, the service returns only the 30 nearest to the computed center. This prevents visual clutter on the static image and keeps the Mapbox API URL well within the 8,192-character limit. The `markers` array in the response only includes the pins actually rendered on the image. The full restaurant list is still available from `GET /restaurants/by-city`.

#### 1.3 — GCS Storage and Caching

**Bucket:** `GCS_INTERNAL_BUCKET` — map images are internally generated assets.

**Object path:** `maps/city-snapshots/{city_slug}-{country_code}-{style}-{width}x{height}{retina}.png`

Example: `maps/city-snapshots/buenos-aires-AR-light-600x400@2x.png`

**Overwrite-in-place strategy:** Each city+style+size combination maps to exactly one GCS object path. On regeneration, the backend **overwrites** the same path — no accumulation of stale images. This keeps the bucket clean and storage cost flat regardless of how often images are regenerated.

**GCS object versioning** (enabled on the bucket) retains prior versions automatically. If a Mapbox API call returns a corrupted image, the previous version is recoverable via GCS console or API. A **lifecycle rule** deletes non-current (superseded) versions after 7 days to prevent unbounded version growth.

```
# Lifecycle rule for infra-kitchen-gcp to set on the internal bucket
{
  "rule": [{
    "action": { "type": "Delete" },
    "condition": { "isLive": false, "daysSinceNoncurrentTime": 7 }
  }]
}
```

**Freshness check:** Before serving a cached image, the service compares the GCS object's `updated` timestamp against a freshness threshold (24 hours). If stale, it regenerates. Additionally, if the set of restaurant coordinates for the city has changed since the image was generated (checked via a lightweight DB query), it regenerates immediately regardless of age.

**CDN headers:** `Cache-Control: public, max-age=86400` on the GCS object.

**Storage cost:** A 600x400 `@2x` PNG is ~100-300KB. 100 cities x 2 styles = ~60MB total. At $0.02/GB/month, annual storage cost is effectively zero. The overwrite strategy keeps this flat — no daily accumulation.

#### 1.4 — Route and Schema

**Create `app/routes/maps.py`:**

```python
@router.get("/city-snapshot", response_model=CitySnapshotResponseSchema)
def get_city_map_snapshot(
    city: str = Query(...),
    country_code: str = Query("US"),
    market_id: Optional[UUID] = Query(None),
    width: int = Query(600, ge=100, le=1280),
    height: int = Query(400, ge=100, le=1280),
    retina: bool = Query(True),
    style: str = Query("light", regex="^(light|dark)$"),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
):
```

**Register in `application.py`:**
```python
v1_maps_router = create_versioned_router("api", ["Maps"], APIVersion.V1)
v1_maps_router.include_router(maps_router)
app.include_router(v1_maps_router)
```

**Response schema** (`app/schemas/consolidated_schemas.py`):

```python
class CitySnapshotMarkerSchema(BaseModel):
    restaurant_id: UUID
    name: str
    lat: float
    lng: float
    pixel_x: int
    pixel_y: int

class CitySnapshotResponseSchema(BaseModel):
    image_url: Optional[str]  # None when no restaurants have coordinates
    center: Optional[dict]    # { lat, lng }
    zoom: Optional[int]
    width: int
    height: int
    retina: bool
    markers: List[CitySnapshotMarkerSchema]
```

#### 1.5 — Mapbox Studio Styles

**Configuration** (add to `app/config/settings.py`):

```python
# Mapbox Static Images — custom style IDs from Mapbox Studio
MAPBOX_STYLE_LIGHT: str = "mapbox/light-v11"   # Default until custom style created
MAPBOX_STYLE_DARK: str = "mapbox/dark-v11"      # Default until custom style created
MAPBOX_PIN_COLOR: str = "4a7c59"                 # Brand primary (earthy green)
```

Start with Mapbox's built-in `light-v11` and `dark-v11` styles. Replace with custom Studio style IDs once the design team creates the earthy-wellness palette styles (`vianda-light`, `vianda-dark`). The backend reads the style ID from config — no code change needed when styles are swapped.

#### 1.6 — Fallback Behavior

| Scenario | Response |
|----------|----------|
| City has 0 restaurants with coordinates | `image_url: null`, `markers: []`, HTTP 200 |
| Mapbox API error / timeout | Return cached version if available; otherwise `image_url: null`, HTTP 200 |
| City not found in any market | HTTP 404 |
| GCS upload fails | Log error, return Mapbox URL directly (Option B fallback) |

---

### Phase 2: Cache Invalidation Hooks

Add lightweight invalidation triggers when restaurant addresses change, so the next request regenerates immediately instead of waiting for the 24-hour TTL.

**Trigger points:**
- `address_service.create_address_with_geocoding()` — after creating geolocation for a restaurant address
- `address_service.update_address_with_geocoding()` — after updating a restaurant address
- `CRUDService` operations on `restaurant_info` — create, archive, unarchive

**Implementation:** `mark_city_map_stale(city, country_code)` sets a flag (in-memory or lightweight DB/Redis) indicating the city's map needs regeneration. The next `GET /maps/city-snapshot` request for that city detects the flag and regenerates, overwriting the GCS object in place. GCS versioning preserves the prior image as a non-current version (auto-deleted after 7 days by lifecycle rule).

**Without Phase 2:** Maps still self-heal via the 24-hour freshness check and the coordinate-change detection in Phase 1. Phase 2 just makes invalidation instant rather than eventual.

---

### Phase 3: Performance Optimizations (if needed)

- **Precompute on cron**: Generate snapshots for all active cities daily during off-peak hours, so user requests always hit cache
- **Redis metadata cache**: Store the marker list and pixel positions in Redis (fast) separately from the image (GCS). The metadata changes more often than needed (e.g., restaurant name change doesn't affect the image)
- **Batch generation**: When multiple styles/sizes are requested, batch the Mapbox API calls

---

## Affected Files

| Action | File |
|--------|------|
| **Create** | `app/gateways/mapbox_static_gateway.py` |
| **Create** | `app/services/city_map_service.py` |
| **Create** | `app/routes/maps.py` |
| **Create** | `app/mocks/mapbox_static_mocks.json` |
| Modify | `app/schemas/consolidated_schemas.py` — add `CitySnapshotResponseSchema`, `CitySnapshotMarkerSchema` |
| Modify | `app/config/settings.py` — add `MAPBOX_STYLE_LIGHT`, `MAPBOX_STYLE_DARK`, `MAPBOX_PIN_COLOR` |
| Modify | `application.py` — register maps router |
| Modify | `CLAUDE_ARCHITECTURE.md` — add maps route group and static gateway |

---

## Pricing Impact

| Current (per user) | Static image (per city per day) |
|--------------------|---------------------------------|
| Google Maps SDK: tile loads per session | Mapbox Static Images: ~1 call per city per day |
| ~$70-100/mo at 10k MAU | ~$2-5/mo (all cities combined) |

At current scale (handful of cities), this is **well within Mapbox's free tier** (50,000 static image loads/month). Even at 100 cities with light/dark styles = 200 API calls/day = 6,000/month.

---

## Cross-Repo Impact

### vianda-app (B2C)

The B2C team will:
1. Replace `RestaurantMap` and `RestaurantMapPlaceholder` with `<Image source={{ uri: image_url }}>`
2. Overlay `<TouchableOpacity>` at each marker's `pixel_x`/`pixel_y`
3. Remove `react-native-maps` dependency and Google Maps API keys entirely
4. Call the new endpoint in parallel with `GET /restaurants/by-city`

**Action:** Once the backend endpoint is implemented, share the API doc with the vianda-app agent.

### infra-kitchen-gcp

- No new secrets needed (reuses existing `MAPBOX_ACCESS_TOKEN_*`)
- GCS bucket already exists (`GCS_INTERNAL_BUCKET`)
- **Enable object versioning** on the internal bucket (if not already enabled)
- **Add lifecycle rule**: delete non-current versions after 7 days (`isLive: false, daysSinceNoncurrentTime: 7`)
- May need CDN cache rule for `maps/city-snapshots/*` path prefix with 24h TTL

### vianda-platform (B2B)

No impact — the B2B dashboard does not display maps.

---

## Related Documents

| Document | Relationship |
|----------|-------------|
| `docs/roadmap/MAPBOX_MIGRATION_ROADMAP.md` | Mapbox is already the default provider; this feature uses the same account and token |
| `docs/api/infrastructure/MAPBOX_CONFIGURATION_INFRASTRUCTURE.md` | Token is already provisioned; Static Images API included in same token |
| `vianda-app/docs/frontend/feedback_for_backend/static-map-images.md` | Original frontend spec with detailed requirements |
| `vianda-app/docs/roadmap/MAPBOX_MAPPING.md` | Frontend evaluation of Options A/B/C; recommends Option B (static images) |
