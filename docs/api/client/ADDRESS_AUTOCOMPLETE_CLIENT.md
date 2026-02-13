# Address Autocomplete and Validation – Client Guide

## Overview

The backend exposes **suggest** (autocomplete) and **validate** (normalize) endpoints for addresses. All clients (React web, iOS, Android, React Native) use the **same API**; only the UI differs. No Google API keys or SDKs are required on the client.

## Endpoints

### 1. Suggest (autocomplete)

**GET** `/api/v1/addresses/suggest`

**Query parameters**

| Parameter | Type   | Required | Description |
|-----------|--------|----------|-------------|
| q         | string | Yes      | Partial address input (e.g. "Av. Corrientes 1") |
| country   | string | No       | ISO alpha-2 or alpha-3 to restrict results (e.g. "AR", "ARG") |
| limit     | int    | No       | Max suggestions (default 5, max 10) |

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
      "country_code": "ARG",
      "country_name": null,
      "formatted_address": "Av. Corrientes 1234, C1043 CABA, Argentina"
    }
  ]
}
```

- All fields match the address schema used for create/update. Use the selected suggestion to **pre-fill** the address form.
- **country_code** is always alpha-3 (e.g. ARG) for persistence.

### 2. Validate (normalize)

**POST** `/api/v1/addresses/validate`

**Request body** (address fields only)

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
  "country_code": "ARG"
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
    "country_code": "ARG"
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

- **normalized** has the same shape as the address create payload. Show “Use this address?” with `formatted_address`; on accept, submit **normalized** (plus `institution_id`, `user_id`, `address_type`, etc.) to `POST /api/v1/addresses/`.

## Recommended user flow

1. User focuses the address form or a single “Address” search field.
2. **Suggest**: On input, call `GET /api/v1/addresses/suggest?q=...&country=...`. Optionally pass `country` from the selected market.
3. User selects a suggestion → pre-fill the form with the suggestion’s structured fields. Optionally call **validate** for that selection.
4. Before submit (or after user edits), call `POST /api/v1/addresses/validate` with the current form data.
5. Show: “We recommend this address: [formatted_address]. Use this address?”
6. User accepts → submit the **normalized** object (plus required create fields) to `POST /api/v1/addresses/`. User can also edit and re-validate.

## Authentication

Both endpoints require the same authentication as other address endpoints (e.g. Bearer token). Use the same session/token as for address create/read.

## Same API for all platforms

- **Web (React)**: Call suggest/validate from your API client; bind suggestions to a dropdown or typeahead; show confirm step with `formatted_address`.
- **iOS / Android / React Native**: Same HTTP calls; only the UI (native or RN components) differs. No platform-specific address SDKs needed.

## Notes

- **Timezone** is not returned by suggest/validate; the backend sets it on create/update from `country_code` + `province`.
- **country_code** in requests and responses is always **alpha-3** (e.g. ARG, USA).
