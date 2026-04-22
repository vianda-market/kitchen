# Market, City & Country Selection

**Audience**: B2C app (React Native / mobile), vianda-platform (B2B admin), vianda-home (marketing site)
**Related**: [CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md](CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md) (full signup flow), [COUNTRY_CITY_DATA_STRUCTURE.md](/Users/cdeachaval/learn/vianda/kitchen/docs/api/internal/COUNTRY_CITY_DATA_STRUCTURE.md) (backend architecture)

---

## 1. Country (Market) Selection

### `GET /api/v1/leads/markets` (no auth, rate-limited 60/min)

Returns active markets for UI dropdowns. Response contains `country_code`, `country_name`, `language`, `phone_dial_code`, `phone_local_digits`, computed `locale`.

| Call | Returns | Use case |
|------|---------|----------|
| `GET /leads/markets` (no param) | Only markets with **active plate coverage** | B2C app signup dropdown, marketing site customer flow |
| `GET /leads/markets?audience=supplier` | All active non-global markets | Marketing site supplier/employer interest form |

**Default (no param) is restrictive.** Unrecognized `audience` values fall back to the customer list.

**Localization**: Pass `?language=es` (or `Accept-Language: es`) for localized country names. Supported: `en`, `es`, `pt`.

**Caching**: Backend caches 10 min. Frontend should call on screen open or use short-TTL cache. Do not hardcode country codes.

### Response shape

```json
[
  {
    "country_code": "AR",
    "country_name": "Argentina",
    "language": "es",
    "phone_dial_code": "+54",
    "phone_local_digits": 10,
    "locale": "es-AR"
  }
]
```

---

## 2. City Selection

### `GET /api/v1/leads/cities?country_code=AR` (no auth, rate-limited 20/min)

Returns city names for lead forms and signup. Supports `audience` parameter.

| Call | Returns | Use case |
|------|---------|----------|
| `GET /leads/cities?country_code=AR` (no param) | Cities with ≥1 active restaurant with plates + QR | B2C app signup, customer lead form |
| `GET /leads/cities?country_code=AR&audience=supplier` | All cities from GeoNames ∪ curated ∪ crowd-sourced | Marketing site supplier interest form |

**Supplier audience guarantee**: for any country returned by `/leads/markets?audience=supplier`, the supplier-audience cities response is guaranteed non-empty.

**Response**: `Cache-Control: public, max-age=3600`

```json
{
  "cities": ["Buenos Aires", "Córdoba", "La Plata", "Mendoza", "..."]
}
```

Supplier path: deduped case-insensitively, sorted alphabetically, capped at 1000.

### `GET /api/v1/cities?country_code=AR` (authenticated)

Returns city objects with `city_metadata_id` for use in address creation and signup forms. Requires auth token.

```json
[
  {
    "city_metadata_id": "019d7f05-22a2-72b4-...",
    "name": "Buenos Aires",
    "country_code": "AR",
    "is_archived": false,
    "status": "active"
  }
]
```

**This is the endpoint to call before creating an address.** The `city_metadata_id` from this response is required in `POST /addresses` (see §4 below).

---

## 3. Admin: Country / Province / City Picker

For the vianda-platform superadmin city/country promotion UI. All three require **Super Admin** auth.

### `GET /api/v1/admin/external/countries`

All 253 countries from GeoNames. Sorted by name.

```json
[{ "iso_alpha2": "AR", "name": "Argentina", "population": 45376763, "continent": "SA" }]
```

### `GET /api/v1/admin/external/provinces?country_iso=AR`

Admin1 regions (provinces/states) for a country. Sorted by name.

```json
[{ "admin1_full_code": "AR.01", "country_iso": "AR", "name": "Buenos Aires", "ascii_name": "Buenos Aires", "geonames_id": 3435907 }]
```

### `GET /api/v1/admin/external/cities?country_iso=AR&admin1_code=07&q=buen`

Cities in a country, optionally filtered by province (`admin1_code`) and search term (`q`). Sorted by population DESC. Limit 200.

```json
[{ "geonames_id": 3435910, "name": "Buenos Aires", "ascii_name": "Buenos Aires", "country_iso": "AR", "admin1_code": "07", "population": 2891082, "timezone": "America/Argentina/Buenos_Aires" }]
```

---

## 4. Address Creation: `city_metadata_id` Required

As of PR4c, `POST /api/v1/addresses` requires `city_metadata_id` in the body when creating an address via the manual/structured path (i.e., when `place_id` is not provided).

### Flow

```
1. GET /cities?country_code=AR → pick a city → get city_metadata_id
2. POST /addresses with { city_metadata_id, country_code, province, city, street_name, ... }
```

When `place_id` IS provided (production path via address search), the backend resolves `city_metadata_id` server-side from the Mapbox place details. No client-side city resolution needed.

### What happens if `city_metadata_id` is missing

- **No `place_id`**: Pydantic returns 422 `"city_metadata_id is required when place_id is not provided"`
- **With `place_id`**: backend resolves it from the Mapbox-derived `(country_code, city)` against `core.city_metadata` + `external.geonames_city`. Falls back to any seeded city_metadata for the country if no exact name match.

### What the backend derives from `city_metadata_id`

- **Timezone** — `external.geonames_city.timezone` via `city_metadata.geonames_id` FK
- **Country validation** — `city_metadata.country_iso` must match the address's `country_code`

---

## 5. B2C Signup Flow

```
1. Country dropdown    → GET /leads/markets → user picks country
2. City dropdown       → GET /leads/cities?country_code=X → user picks city name
3. Email + password
4. Submit              → POST /customers/signup/request with { country_code, city_name, ... }
```

**`country_code`** is required. Backend returns 400 if missing, invalid, or Global.

**City**: send **either** `city_name` (string from `/leads/cities`) **or** `city_metadata_id` (UUID from `/cities`). At least one is required.
- **`city_name`** (recommended for B2C): the backend resolves it server-side to `city_metadata_id` via a case-insensitive match against `core.city_metadata` + `external.geonames_city`. No auth needed — the name comes from the public `/leads/cities` endpoint.
- **`city_metadata_id`**: if the app already has it (e.g., from the authenticated `/cities` endpoint), send it directly to skip server-side resolution.

This avoids a chicken-and-egg problem: `GET /leads/cities` (no auth) returns city name strings, while `GET /cities` (auth) returns UUIDs. Since the user hasn't signed up yet, the B2C app should use `city_name`.

> **Note**: `city_metadata_id` is required for **address creation** (`POST /addresses`, §4 above), not for signup. The signup endpoint is more lenient and accepts city by name.

---

## 6. "Notify Me" Fallback

The B2C app must show near the country/city dropdowns:

> "Don't see your country or city? [Let us know](https://vianda.market/interest) and we'll notify you when we launch in your area."

The link points to the marketing site's interest form which uses `?audience=supplier` to show all markets.

---

## 7. Error Cases

| Condition | Response |
|-----------|----------|
| Missing `country_code` in signup | 400 `"country_code is required"` |
| Invalid country (no market) | 400 `"No market found for country XX"` |
| Market archived | 400 `"Market for XX is archived"` |
| Country resolves to Global | 400 `"Global Marketplace cannot be assigned to B2C customers"` |
| Missing both `city_metadata_id` and `city_name` in signup | 400 `"Either city_metadata_id or city_name is required"` |
| `city_name` not found in country | 400 `"City 'X' not found for country YY"` |
| Missing `city_metadata_id` in address create (no place_id) | 422 `"city_metadata_id is required when place_id is not provided"` |
| `city_metadata_id` country mismatch | 400 `"city_metadata_id country (XX) does not match address country_code (YY)"` |
| Rate limit exceeded | 429 `{"detail": "rate_limited", "retry_after_seconds": 60}` + `Retry-After: 60` header |

---

## 8. Best Practices

- **Single source of truth**: Use `GET /leads/markets` for the signup country dropdown. Do not hardcode country codes.
- **City picker before address create**: Always resolve `city_metadata_id` via `GET /cities?country_code=X` before submitting an address.
- **Never pass `?audience=supplier`** from the B2C app — that param is for the marketing site only.
- **Enum values are lowercase**: `active`, `supplier`, `customer_home`, `ave` — not Title Case.
- **`market.timezone` is null**: Do not read timezone from market data. Use `address.timezone` (per-restaurant) or the restaurant's address details.
