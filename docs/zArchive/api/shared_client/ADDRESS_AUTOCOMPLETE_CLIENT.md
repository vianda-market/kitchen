# Address Autocomplete and Validation – Client Guide

**For**: Frontend (Web, iOS, Android, React Native)

## Overview

The backend exposes **suggest** (autocomplete) and **validate** (normalize) for addresses. All clients use the **same API**; only the UI differs. No Google API keys or SDKs are required on the client.

---

## Endpoints

### 1. Suggest (autocomplete)

**GET** `/api/v1/addresses/suggest`

**Query parameters**

| Parameter | Type   | Required | Description |
|-----------|--------|----------|-------------|
| `q`       | string | Yes      | Partial address input (e.g. `"Av. Corrientes 1"`) |
| `country` | string | No       | Country **code** (ISO 3166-1 alpha-2, e.g. `AR`) or **country name** (e.g. `Argentina`) to bias or restrict results |
| `limit`   | int    | No       | Max suggestions (default 5, max 10) |

**Response**

```json
{
  "suggestions": [
    {
      "street_name": "Corrientes",
      "street_type": "Ave",
      "building_number": "1234",
      "apartment_unit": null,
      "floor": null,
      "city": "Buenos Aires",
      "province": "CABA",
      "postal_code": "C1043AAZ",
      "country_code": "AR",
      "country_name": null,
      "formatted_address": "Av. Corrientes 1234, C1043 CABA, Argentina"
    }
  ]
}
```

- Fields match the address schema for form pre-fill. **country_code** in the response is **ISO 3166-1 alpha-2** (e.g. `AR`). When you later create/update an address, send **country_code** as alpha-2. The API accepts case-insensitive input and normalizes to uppercase; stored and returned values are uppercase. **country_name** in address responses is resolved from market metadata (not stored on the address).

---

### 2. Validate (normalize)

**POST** `/api/v1/addresses/validate`

**Request body** (address fields; provide **either** `country_code` **or** `country_name`)

| Field          | Type   | Required | Description |
|----------------|--------|----------|-------------|
| `street_name`  | string | Yes      | Max 100 chars |
| `street_type`  | string | No       | Street type code from `GET /api/v1/enums/` (e.g. St, Ave, Blvd). Max 50. |
| `building_number` | string | No   | Max 20 |
| `apartment_unit`   | string | No   | Max 20 |
| `floor`        | string | No       | Max 50 |
| `city`         | string | Yes      | Max 50 |
| `province`     | string | No       | Default `""`, max 50 |
| `postal_code`  | string | No       | Default `""`, max 20 |
| `country_code` | string | No*      | ISO 3166-1 alpha-2 (e.g. `AR`). Case-insensitive; API normalizes to uppercase. |
| `country_name` | string | No*      | Country name (e.g. `Argentina`) when user types instead of dropdown |

\* At least one of `country_code` or `country_name` is required.

**Example (with country code – e.g. from dropdown)**

```json
{
  "street_name": "Corrientes",
  "street_type": "Ave",
  "building_number": "1234",
  "apartment_unit": "2B",
  "floor": null,
  "city": "Buenos Aires",
  "province": "CABA",
  "postal_code": "1043",
  "country_code": "AR"
}
```

**Example (with country name – e.g. user typed the country)**

```json
{
  "street_name": "Corrientes",
  "street_type": "Ave",
  "building_number": "1234",
  "city": "Buenos Aires",
  "province": "CABA",
  "postal_code": "1043",
  "country_name": "Argentina"
}
```

**Response (valid address)**

```json
{
  "is_valid": true,
  "normalized": {
    "street_name": "Corrientes",
    "street_type": "Ave",
    "building_number": "1234",
    "apartment_unit": "2B",
    "floor": null,
    "city": "Buenos Aires",
    "province": "Ciudad Autónoma de Buenos Aires",
    "postal_code": "C1043AAZ",
    "country_code": "AR"
  },
  "formatted_address": "Av. Corrientes 1234, 2B, C1043 CABA, Argentina",
  "confidence": "high",
  "message": null
}
```

**Response (invalid / unverifiable)**

```json
{
  "is_valid": false,
  "normalized": null,
  "formatted_address": null,
  "confidence": "none",
  "message": "Address could not be validated. Please check and try again."
}
```

- **normalized** has the same shape as the address create payload. **country_code** in `normalized` is **alpha-2** (e.g. `AR`). On accept, submit **normalized** plus `address_type`, `institution_id`, `user_id`, `is_default` to `POST /api/v1/addresses/`. Use alpha-2 for **country_code** in all address requests.

---

## Country: how to send it

- **Dropdown (recommended)**  
  - Get the list from **GET /api/v1/markets** (each market has `country_name` and `country_code`). Build a dropdown; when the user picks e.g. "Argentina", send **country_code** `"AR"` (alpha-2) in suggest (`country` query param) and in validate (body `country_code`).  
- **Free-text (user types country)**  
  - For **suggest**, send the typed value as the `country` query param (e.g. `country=Argentina`).  
  - For **validate**, send **country_name** in the body (e.g. `"country_name": "Argentina"`).  
  The backend resolves names to codes; you never need to convert names to codes on the client.

---

## Recommended user flow

1. User focuses the address form or a single “Address” search field.
2. **Suggest**: Call `GET /api/v1/addresses/suggest?q=...` and optionally `&country=...` (code or name from dropdown or typed).
3. User selects a suggestion → pre-fill the form with the suggestion’s fields. Optionally call **validate** with that data.
4. Before submit (or after user edits), call `POST /api/v1/addresses/validate` with the current form (including `country_code` or `country_name`).
5. Show: “We recommend this address: [formatted_address]. Use this address?”
6. User accepts → submit **normalized** (plus `address_type`, `institution_id`, `user_id`, `is_default`) to `POST /api/v1/addresses/`. User can also edit and re-validate.

---

## Authentication

Both endpoints require the same auth as other address endpoints (e.g. Bearer token).

---

## Same API for all platforms

- **Web (React)**: Call suggest/validate from your API client; bind suggestions to a dropdown or typeahead; show confirm step with `formatted_address`.
- **iOS / Android / React Native**: Same HTTP calls; only the UI differs. No platform-specific address SDKs needed.

---

## How we derive country code from “country” (name)

If your form has a **country** field (e.g. the user selects or types "Argentina") and no **country_code** field, you can send **`country`** (the country name) on create/update address. The backend **deduces `country_code`** from it so you don’t need a separate code field or client-side mapping.

- **Where it’s done:** Backend only (no frontend logic required).
- **How:** We use a **hardcoded mapping** (country name → alpha-2) in the gateway, shared with suggest/validate. No extra library and no DB table for the list. Supported names include Argentina, Peru, Chile, United States, Brazil, Mexico, Canada, etc.; adding a new market means adding one entry to that map.
- **Create/update:** Send either **`country_code`** (alpha-2, e.g. `"AR"`) or **`country`** (e.g. `"Argentina"`). If you send **`country`**, we resolve it to alpha-2, look up the market for timezone, and store alpha-2. `country_name` in responses is resolved from `market_info`. If the name is not recognized, the API returns 400 with a message to use a supported country name or send `country_code`.

So: form shows “country” only → send **`country`** in the request body; we derive **country_code** and the rest of the flow is unchanged.

---

## Notes

- **Timezone** is not returned by suggest/validate; the backend sets it on create/update from `country_code` and province.
- **country_code** is **ISO 3166-1 alpha-2 only** everywhere: suggest/validate responses, address create/update, and DB storage. Alpha-3 (e.g. ARG) is not accepted. **country_name** in address API responses is resolved from `market_info` (not stored on address tables).
