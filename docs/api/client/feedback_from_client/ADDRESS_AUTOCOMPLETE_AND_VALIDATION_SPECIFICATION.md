# Address Autocomplete and Validation – Backend Specification

**Document Version**: 1.0  
**Date**: February 2026  
**For**: Backend Team  
**From**: Frontend Team  
**Status**: Request for Review and Implementation  

---

## 1. Problem Statement

### 1.1 Current Pain Points

- **Manual, error-prone input**: Users type full addresses into separate fields (street name, building number, city, province, postal code, country) with no guidance. This leads to:
  - Typos and inconsistent formatting (e.g. "Buenos Aires" vs "Buenos aires", "CABA" vs "Ciudad Autónoma de Buenos Aires").
  - Invalid or non-deliverable addresses.
  - Extra support and failed deliveries.

- **No validation before submit**: Addresses are persisted as entered. There is no check against a canonical or deliverable address, so bad data is stored.

- **Fragmented UX across platforms**: The web admin app and the future iOS client app would each need to implement autocomplete and validation independently, leading to duplicated logic and inconsistent behavior unless the backend provides a single source of truth.

### 1.2 Desired Behavior

1. **Suggest**: As the user types, the system suggests real, structured addresses (autocomplete).
2. **Normalize**: Before saving, the system validates the address against a trusted source and returns a **normalized, canonical address**.
3. **User confirmation**: The UI shows the normalized address and asks the user to confirm (“Use this address?”) before submitting. The user can accept or edit.
4. **Centralized**: All suggest and validate logic lives in the backend. Web and iOS clients call the same APIs, so behavior and data quality are consistent.

---

## 2. Proposed Solution: Backend-Owned Address Service

### 2.1 Principle

- **Backend** integrates with a single address provider (recommended: **Google**).
- **Backend** exposes two APIs:
  - **Suggest (autocomplete)**: returns a list of candidate addresses in a **normalized, structured format** that matches (or can be mapped to) the current address schema.
  - **Validate / normalize**: accepts the current address fields, calls the provider’s validation API, and returns **one recommended normalized address** for the user to accept or edit before submit.
- **Clients** (web admin, future iOS app) only call these backend APIs and render the structured response in the same way. No provider API keys or SDKs on the client.

### 2.2 Benefits

- Single place for provider key, billing, and rate limits.
- Same address quality and rules for web and iOS.
- Backend can enforce business rules (e.g. only countries where we operate, alignment with Markets).
- Frontend stays simple and consistent; no need to map provider-specific structures in each client.

### 2.3 Recommended Provider: Google

- **Rationale**: The platform already uses **Google for geolocation**. Using **Google Places API** (autocomplete) and **Address Validation API** (validation/normalization) keeps the stack consistent and simplifies operations.
- **Relevant APIs**:
  - [Places API (New) – Autocomplete](https://developers.google.com/maps/documentation/places/web-service/autocomplete) or [Places API (New) – Place Details](https://developers.google.com/maps/documentation/places/web-service/place-details) for structured address components.
  - [Address Validation API](https://developers.google.com/maps/documentation/addressvalidation) for validating and normalizing an address and receiving a canonical representation.

If the backend prefers another provider (e.g. HERE, Loqate) for cost or regional reasons, the same **suggest** and **validate** contract below can be implemented against that provider.

---

## 3. Current Address Schema (For Backend Review)

The frontend and API currently use the following structure. **We ask the backend to review whether this schema aligns with the normalized address format returned by Google (or the chosen provider), and to propose changes if needed.**

### 3.1 Current Address Model (Frontend / API)

```text
Address (and AddressEnriched) – relevant fields for autocomplete/validation:

- street_name: string           (required in UI)
- street_type: StreetType | null   (enum: 'St' | 'Ave' | 'Blvd' | 'Rd' | 'Dr' | 'Ln' | 'Way' | 'Ct' | 'Pl' | 'Cir')
- building_number: string | null
- apartment_unit: string | null
- floor: string | null
- city: string                  (required in UI)
- province: string | null       (state / province / administrative area)
- postal_code: string | null
- country: string | null        (in UI, from Markets; stored as country code or name per current API)
- timezone: string | null       (auto-derived by backend from country + province; not from address provider)
```

Other fields (`address_id`, `address_type`, `institution_id`, `user_id`, `is_archived`, `is_default`, `status`, `created_date`, `modified_date`) are unchanged and not in scope for normalization.

### 3.2 Typical Google Address Component Mapping (Reference)

Google returns address components with types such as:

- `street_number` → often maps to **building_number**
- `route` → often maps to **street_name** (and may contain or imply **street_type**, e.g. "Av. Corrientes")
- `locality` → **city**
- `administrative_area_level_1` → **province**
- `postal_code` → **postal_code**
- `country` (short name/code) → **country**

Subpremise (e.g. apartment, floor) often appears as a separate component and can map to **apartment_unit** / **floor**.

**Request to backend**: Confirm whether the current schema (especially `street_name`, `street_type`, `building_number`, `city`, `province`, `postal_code`, `country`) can be populated from Google’s normalized response without loss of information or awkward splitting. If Google’s structure suggests a different split (e.g. single “street_address” vs separate number/name/type), recommend schema changes so that the **normalized address** returned by the backend is the same structure we persist.

---

## 4. Proposed API Contract

### 4.1 Suggest (Autocomplete)

**Purpose**: Return a list of address suggestions as the user types, in a normalized structure that matches (or maps to) the address schema.

**Endpoint (suggestion)**:

```text
GET /api/v1/addresses/suggest
```

**Query parameters**:

| Parameter | Type   | Required | Description |
|-----------|--------|----------|-------------|
| q         | string | Yes      | User input (partial address). |
| country   | string | No       | ISO 3166-1 alpha-2 country code to bias or restrict results (e.g. from Markets). |
| limit     | int    | No       | Max number of suggestions (e.g. 5–10). Default 5. |

**Response (example)**:

```json
{
  "suggestions": [
    {
      "street_name": "Av. Corrientes",
      "street_type": "Ave",
      "building_number": "1234",
      "apartment_unit": null,
      "floor": null,
      "city": "Buenos Aires",
      "province": "CABA",
      "postal_code": "C1043AAZ",
      "country": "AR",
      "formatted_address": "Av. Corrientes 1234, C1043AAZ CABA, Argentina"
    }
  ]
}
```

- All fields in each suggestion should use the **same field names and types** as the current address schema (or the schema agreed after backend review), so the client can pre-fill the form without extra mapping.
- `formatted_address` is optional, for display in the dropdown only.

### 4.2 Validate / Normalize (Recommend Address)

**Purpose**: Take the current address fields from the user (or from a suggestion), validate them with the provider, and return **one** normalized address for the user to confirm before submitting.

**Endpoint (suggestion)**:

```text
POST /api/v1/addresses/validate
```

**Request body (example)**:

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
  "country": "AR"
}
```

**Response (example)**:

```json
{
  "is_valid": true,
  "normalized": {
    "street_name": "Av. Corrientes",
    "street_type": "Ave",
    "building_number": "1234",
    "apartment_unit": "2B",
    "floor": null,
    "city": "Buenos Aires",
    "province": "Ciudad Autónoma de Buenos Aires",
    "postal_code": "C1043AAZ",
    "country": "AR"
  },
  "formatted_address": "Av. Corrientes 1234, 2B, C1043AAZ CABA, Argentina",
  "confidence": "high",
  "message": null
}
```

For invalid or unverifiable addresses:

```json
{
  "is_valid": false,
  "normalized": null,
  "formatted_address": null,
  "confidence": "none",
  "message": "Address could not be validated. Please check and try again."
}
```

- **Request to backend**: Ensure `normalized` (when present) uses the same schema as the rest of the API and as the suggest response, so the client can show “Use this address?” and then submit the same object (plus `address_type`, `institution_id`, etc.) to create/update address.

---

## 5. User Flow (Client Side)

1. User focuses the address form (or a single “Address” search field that drives the rest).
2. **Suggest**: On input, client calls `GET /api/v1/addresses/suggest?q=...&country=...`. Backend calls Google (or chosen provider) and returns suggestions in the agreed schema.
3. User selects a suggestion → client fills the form with the suggested structured fields (and optionally calls validate for that selection).
4. Before submit (or after user edits), client calls `POST /api/v1/addresses/validate` with current form data.
5. Backend returns `normalized` (and `formatted_address`, `confidence`, `message`). Client shows: “We recommend this address: [formatted_address]. Use this address?”
6. User accepts → client submits the **normalized** address (plus any non-address fields) to the existing create/update address endpoint. User can also edit and re-validate.

This flow will be implemented the same way on **web admin** and **iOS client**; both rely only on the backend suggest and validate APIs.

---

## 6. Backend Review Requests

1. **Schema alignment**: Review the current address schema (Section 3) against Google’s (or the chosen provider’s) normalized address structure. Confirm if the current fields are sufficient or if the schema should be adjusted so that the normalized address returned by the backend is exactly what we persist.
2. **Country and markets**: Confirm how `country` is stored (code vs name) and how validate/suggest should interact with Markets (e.g. restrict suggest to countries we operate in).
3. **Timezone**: Timezone remains derived by the backend from country + province (existing timezone logic); no change expected from the address provider.
4. **API shape**: Confirm or adjust the suggest and validate endpoints and response shapes (Section 4) so they match backend implementation and the chosen provider.
5. **Provider choice**: Acknowledge recommendation to use Google (Places + Address Validation) given existing geolocation use, or state if another provider will be used and any impact on the contract above.

---

## 7. Out of Scope for This Document

- Changes to create/update address payloads beyond using the normalized structure returned by validate.
- Geocoding (lat/long) unless the backend decides to store it; can be a follow-up.
- Frontend implementation details (exact UI components); the frontend will consume the APIs described above.

---

## 8. Summary

- **Problem**: Manual, unvalidated address entry; risk of bad data and inconsistent behavior across web and iOS.
- **Solution**: Backend-owned address service that exposes **suggest** and **validate** APIs and returns a **normalized address** for the user to confirm before submit.
- **Provider**: Recommend **Google** (Places + Address Validation) to align with existing geolocation.
- **Action**: Backend to review address schema vs normalized format, confirm or adjust API contract, and implement the centralized suggest and validate endpoints.

---

**Document Status**: Ready for Backend Review  
**Next Steps**: Backend to respond on schema alignment, provider choice, and API details; then implementation.
