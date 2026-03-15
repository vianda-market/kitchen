# Market Country Flag UI Pattern

**Audience:** B2B (vianda-platform/backoffice) and B2C (mobile app) frontend teams  
**Purpose:** Shared pattern for displaying country flags and active market selection with behavior tied to the selected country.

---

## Overview

Both B2B and B2C clients need a consistent way to:

1. Display the active country (market) with a flag
2. Let users change the active market via a dropdown or modal
3. Drive downstream behavior (Address form `country_code`, plan filtering, timezone, market-scoped API calls) from the selected market

This document describes the recommended implementation for both clients.

---

## Data Source

- **API (recommended for market selector):** `GET /api/v1/markets/available` — **public, no auth.** Returns active, non-archived markets only. Rate-limited (e.g. 60 req/min). Use as the single source of truth for the country dropdown (pre-login or first load).
- **Response:** Array of `{ market_id, country_code, country_name, timezone, currency_code, currency_name }` (ISO 3166-1 **alpha-2** for `country_code`, e.g. `AR`, `US`).
- **Authenticated flows:** For full market details (e.g. admin), use `GET /api/v1/markets/enriched/`.

See [MARKET_SCOPE_FOR_CLIENTS.md](./MARKET_SCOPE_FOR_CLIENTS.md) for full API details.

---

## Flag Source

**Recommended:** Use `country-flag-icons` (web) or flag emoji (mobile) with Markets API `country_code` directly. No mapping needed since the API returns alpha-2.

| Client | Option | Notes |
|--------|--------|-------|
| B2B (web) | `country-flag-icons` | Import by alpha-2: `import US from 'country-flag-icons/react/3x2/US'` or use the package's component API |
| B2C (React Native) | Flag emoji or `country-flag-icons` | Emoji: `String.fromCodePoint(...countryCode.split('').map(c => 0x1F1E6 - 65 + c.charCodeAt(0))).join('')` yields 🇺🇸 for "US" |

The backend schema uses **alpha-2 only** everywhere (Markets, Addresses, Address Autocomplete). See [ADDRESSES_API_CLIENT.md](./ADDRESSES_API_CLIENT.md) and [ADDRESS_AUTOCOMPLETE_CLIENT.md](./ADDRESS_AUTOCOMPLETE_CLIENT.md).

---

## UI Pattern

1. **Display:** Show one flag in the header (or app bar) representing the active market.
2. **Picker:** Tapping/clicking the flag opens a dropdown or modal listing markets from the API, each with flag + country name.
3. **Selection:** On select, update the active market and close the picker. Persist selection if desired (see State).

---

## State

- **Context:** Store `selectedMarket` as `{ market_id, country_code, country_name }` (or equivalent from Markets API).
- **Persistence:**
  - **B2C (mobile):** AsyncStorage or SecureStore (e.g. key `selected_market_id` or `selected_country_code`)
  - **B2B (web):** localStorage (e.g. key `selected_market_id`)

---

## Behavior Tied to Active Country

The active market drives:

| Behavior | B2B | B2C |
|----------|-----|-----|
| Address form `country_code` pre-fill | Supplier/restaurant address creation | Customer address, checkout |
| Plan filtering | Plans by market | Plans by market |
| Timezone for date/time displays | Market timezone | Market timezone |
| Market-scoped API calls | Any API that filters by `market_id` or `country_code` | Same |

Both clients should read the active market from the same pattern (MarketContext or equivalent) so behavior is consistent.

---

## Default Selection

1. **Device locale:** Use device region (e.g. `expo-localization` `getLocales()[0].regionCode` on mobile; `navigator.language` or `Intl` on web) and map to a market in the list.
2. **Fallback:** If no match or API fails, default to USA (`US`) or the first market in the list.

---

## References

- [MARKET_SCOPE_FOR_CLIENTS.md](./MARKET_SCOPE_FOR_CLIENTS.md) – Markets API endpoints and types
- [ADDRESSES_API_CLIENT.md](./ADDRESSES_API_CLIENT.md) – Address API uses alpha-2 `country_code`
- [ADDRESS_AUTOCOMPLETE_CLIENT.md](./ADDRESS_AUTOCOMPLETE_CLIENT.md) – Suggest/validate with alpha-2
