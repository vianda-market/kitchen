# Address Autocomplete and Validation – Backend

## Overview

The backend provides a **centralized** address suggest (autocomplete) and validate (normalize) service. All clients (React web, iOS, Android, React Native) call the same REST API; no Google API keys or SDKs on the client.

## Provider and APIs

- **Provider**: Google
- **APIs used**:
  - **Places API (New) – Autocomplete**: `POST https://places.googleapis.com/v1/places:autocomplete` – address suggestions from partial input
  - **Places API (New) – Place Details**: `GET https://places.googleapis.com/v1/places/{placeId}` – structured address components for a selected suggestion
  - **Address Validation API**: `POST https://addressvalidation.googleapis.com/v1:validateAddress` – validate and normalize an address

**API key**: Same `GOOGLE_MAPS_API_KEY` as geocoding. Ensure **Places API (New)** and **Address Validation API** are enabled for that key in Google Cloud Console.

## Schema alignment

- Suggest and validate responses use the **same field names** as `address_info` / `AddressCreateSchema`: `street_name`, `street_type`, `building_number`, `apartment_unit`, `floor`, `city`, `province`, `postal_code`, `country_code`.
- **country_code** is always **ISO 3166-1 alpha-2** (e.g. AR, US) for persistence. Normalization to uppercase is done at the API boundary; services receive already-normalized values. The suggest endpoint accepts optional `country` in query (alpha-2) to restrict results.
- **Timezone** is not returned by suggest/validate; it is derived on address create/update from `country_code` + `province` via the existing timezone service.

## Implementation

- **Gateway**: [app/gateways/google_places_gateway.py](app/gateways/google_places_gateway.py) – Places Autocomplete, Place Details, Address Validation; DEV_MODE uses [app/mocks/address_autocomplete_mocks.json](app/mocks/address_autocomplete_mocks.json).
- **Mapping**: [app/services/address_autocomplete_mapping.py](app/services/address_autocomplete_mapping.py) – Google address components to backend schema (route → street_type + street_name, country → alpha-2, etc.). `street_type` output values are enum codes: St, Ave, Blvd, Rd, Dr, Ln, Way, Ct, Pl, Cir.
- **Service**: [app/services/address_autocomplete_service.py](app/services/address_autocomplete_service.py) – `suggest(q, country, limit)` and `validate(body)`.
- **Routes**: [app/routes/address.py](app/routes/address.py) – `GET /api/v1/addresses/suggest`, `POST /api/v1/addresses/validate`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/addresses/suggest?q=...&country=...&limit=5 | Address autocomplete suggestions |
| POST | /api/v1/addresses/validate | Validate and normalize address; returns is_valid, normalized, formatted_address, confidence, message |

Both require authentication (same as other address endpoints).
