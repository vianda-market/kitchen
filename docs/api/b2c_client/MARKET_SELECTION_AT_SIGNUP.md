# Market selection at B2C signup

**Audience**: B2C app (React Native / mobile)  
**Related**: [CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md](CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md) (full signup flow)

## Quick implementation

To show a country selector at registration:

1. Call **`GET /api/v1/markets/available`** (no auth) to get the list of countries. The response returns **`country_code`** and **`country_name`** only (no `market_id`).
2. Let the user select one country in the UI.
3. Send the selected country's **`country_code`** (ISO 3166-1 alpha-2, e.g. `US`, `AR`) in the **`POST /api/v1/customers/signup/request`** request body.

**`country_code` is required** in the signup request body. Do not submit signup without it; the backend returns 400 if it is missing, invalid, or resolves to an archived or Global market.

---

## Why country_code instead of market_id

The public **GET /api/v1/markets/available** endpoint returns only `country_code` and `country_name`. This keeps the unauthenticated response minimal. The backend resolves `country_code` to `market_id` internally at signup time. This avoids exposing internal UUIDs to pre-auth flows and prevents issues when the database is rebuilt (UUIDs change; country codes do not).

---

## Error cases

| Condition | Typical response |
|-----------|------------------|
| Missing `country_code` | `{ "detail": "country_code is required. Use GET /api/v1/markets/available for valid country codes." }` |
| Invalid country (no market) | `{ "detail": "No market found for country XX. Use GET /api/v1/markets/available for supported countries." }` |
| Market archived | `{ "detail": "Market for XX is archived. Use GET /api/v1/markets/available for active countries." }` |
| Country resolves to Global | `{ "detail": "Global Marketplace cannot be assigned to B2C customers. Use a country from GET /api/v1/markets/available." }` |

---

## Best practices

- **Single source of truth:** Use **GET /api/v1/markets/available** as the only source for the signup country dropdown. Do not hardcode country codes.
- **Refresh when entering signup:** Call GET /markets/available when the user opens the signup screen (or use a short-TTL cache). Populate the dropdown from that response.
- **Default selection:** Default to the first country or one matching the device/browser locale (match `country_code` from the available list).
