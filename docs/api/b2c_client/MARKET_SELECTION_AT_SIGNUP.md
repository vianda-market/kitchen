# Market selection at B2C signup

**Audience**: B2C app (React Native / mobile), vianda-home (marketing site)
**Related**: [CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md](CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md) (full signup flow)

## Endpoint

**`GET /api/v1/leads/markets`** (no auth, rate-limited 60/min, reCAPTCHA required)

Returns active markets for UI dropdowns. The response contains **`country_code`** and **`country_name`** only (no `market_id`).

### Audience parameter

| Call | Returns | Use case |
|------|---------|----------|
| `GET /leads/markets` (no param) | Only markets with **active plate coverage** (product + kitchen_day published) | B2C app registration dropdown, marketing site customer flow |
| `GET /leads/markets?audience=supplier` | All active non-global markets | Marketing site supplier/employer interest form |

**The default (no param) is intentionally restrictive.** If the parameter is missing, stripped, or unrecognized, the caller gets only served countries. This prevents customers from registering in markets where we cannot serve them.

### Localization

Pass `?language=es` (or send `Accept-Language: es`) to get localized country names. Supported: `en`, `es`, `pt`.

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

### Caching

Backend caches for 10 minutes. Frontend should call on signup screen open or use a short-TTL cache. Do not hardcode country codes.

---

## City dropdown

After the user selects a country, call **`GET /api/v1/leads/cities?country_code=AR`** to populate the city dropdown. This endpoint already returns only cities with active restaurant coverage (restaurants + plates + kitchen_days).

---

## Registration flow

```
1. Country dropdown (GET /leads/markets) → only served countries
2. City dropdown (GET /leads/cities?country_code=X) → only served cities
3. Email + password
4. Submit → POST /api/v1/customers/signup/request with country_code + city_id
```

**`country_code` is required** in the signup request body. The backend returns 400 if it is missing, invalid, or resolves to an archived or Global market.

---

## "Notify me" fallback

**The B2C app must include a visible note** near the country/city dropdowns for users who don't find their location:

> "Don't see your country or city? [Let us know](https://vianda.market/interest) and we'll notify you when we launch in your area."

The link points to the marketing site's interest form, where users can submit their email + location for all countries (the marketing site uses `?audience=supplier` to show all markets). This ensures no dead end for users who downloaded the app directly from the store.

---

## Why country_code instead of market_id

The public endpoint returns only `country_code` and `country_name`. This keeps the unauthenticated response minimal. The backend resolves `country_code` to `market_id` internally at signup time. This avoids exposing internal UUIDs to pre-auth flows and prevents issues when the database is rebuilt (UUIDs change; country codes do not).

---

## Error cases

| Condition | Typical response |
|-----------|------------------|
| Missing `country_code` | `{ "detail": "country_code is required. Use GET /api/v1/leads/markets for valid country codes." }` |
| Invalid country (no market) | `{ "detail": "No market found for country XX. Use GET /api/v1/leads/markets for supported countries." }` |
| Market archived | `{ "detail": "Market for XX is archived. Use GET /api/v1/leads/markets for active countries." }` |
| Country resolves to Global | `{ "detail": "Global Marketplace cannot be assigned to B2C customers. Use a country from GET /api/v1/leads/markets." }` |

---

## Best practices

- **Single source of truth:** Use **GET /api/v1/leads/markets** as the only source for the signup country dropdown. Do not hardcode country codes.
- **Refresh when entering signup:** Call GET /leads/markets when the user opens the signup screen (or use a short-TTL cache).
- **Default selection:** Default to the first country or one matching the device/browser locale (match `country_code` from the available list).
- **Never pass `?audience=supplier`** from the B2C app — that param is for the marketing site only. The B2C app should always use the default (coverage-filtered) response.
