# Supported Provinces API – Client Guide

**Document Version**: 1.0  
**Date**: March 2026  
**For**: Frontend Team (Web, iOS, Android)

---

## Overview

The backend exposes **GET /api/v1/provinces/** to list supported provinces/states for address forms. Use this endpoint to populate the Province/State dropdown in a **cascading flow**: Country → Province → City. All three values must form a valid combination; invalid combinations (e.g. Florida + Seattle) are rejected with a 400 error when creating or updating addresses.

**Key principle**: Use the APIs for Country, Province, and City in a cascading sequence so users only see valid options. Send `province_code` (e.g. `WA`, `CABA`) when submitting addresses to avoid validation errors.

---

## Endpoint

### GET /api/v1/provinces/

**Description**: List supported provinces for address forms and cascading dropdowns.

**Authorization**: Customer or Employee (JWT required).

**Query parameters**

| Parameter       | Type   | Required | Description |
|-----------------|--------|----------|-------------|
| `country_code`  | string | No       | ISO 3166-1 alpha-2 (e.g. `US`, `AR`). When provided, returns only provinces for that country. Omit to get all provinces. |

**Example (filtered by country)**

```http
GET /api/v1/provinces/?country_code=US
```

**Example (all provinces)**

```http
GET /api/v1/provinces/
```

**Response**

```json
[
  {
    "province_code": "WA",
    "province_name": "Washington",
    "country_code": "US"
  },
  {
    "province_code": "FL",
    "province_name": "Florida",
    "country_code": "US"
  },
  {
    "province_code": "CA",
    "province_name": "California",
    "country_code": "US"
  }
]
```

**Response fields**

| Field           | Type   | Description |
|-----------------|--------|-------------|
| `province_code` | string | Short code for the province/state (e.g. `WA`, `FL`, `CABA`). Use this value when submitting addresses. |
| `province_name` | string | Full name for display (e.g. `Washington`, `Ciudad Autónoma de Buenos Aires`). |
| `country_code`  | string | ISO 3166-1 alpha-2 country code. |

---

## Cascading Dropdown Flow

Use the following sequence for address forms:

1. **Country**: Load from `GET /api/v1/markets/enriched/ or GET /api/v1/leads/markets` or `GET /api/v1/countries/` (Employee-only). User selects a country.
2. **Province**: On country change, call `GET /api/v1/provinces/?country_code={code}`. Populate province dropdown; clear province and city.
3. **City**: On province change, call `GET /api/v1/cities/?country_code={code}&province_code={code}`. Populate city dropdown; clear city.

This ensures users only select valid combinations (e.g. Washington + Seattle, not Florida + Seattle).

### Related endpoints

| Endpoint                    | Purpose |
|----------------------------|---------|
| `GET /api/v1/countries/`   | List supported countries (Employee-only; for Create Market). |
| `GET /api/v1/markets/enriched/ or GET /api/v1/leads/markets`     | List markets with `country_code`, `country_name` (for address country dropdown). |
| `GET /api/v1/provinces/`   | List provinces, optionally filtered by `country_code`. |
| `GET /api/v1/cities/`      | List cities, optionally filtered by `country_code` and `province_code`. |

---

## Cities API – Province Filter

**GET** `/api/v1/cities/`

**Query parameters**

| Parameter       | Type   | Required | Description |
|-----------------|--------|----------|-------------|
| `country_code`  | string | No       | Filter by ISO 3166-1 alpha-2. |
| `province_code` | string | No       | Filter by province/state code. Use with `country_code` for cascading. |
| `exclude_global`| bool   | No       | Exclude Global city (default `false`). Use `true` for Customer signup picker. |

**Example (cascading after province selected)**

```http
GET /api/v1/cities/?country_code=US&province_code=WA
```

**Response** (each item includes `province_code`)

```json
[
  {
    "city_id": "uuid",
    "name": "Seattle",
    "country_code": "US",
    "province_code": "WA"
  }
]
```

---

## Address Validation – Valid Combinations

When creating or updating an address via `POST /api/v1/addresses/` or `PUT /api/v1/addresses/{id}`, the backend validates that **country + province + city** form a supported combination.

**Invalid example** (returns 400):

```json
{
  "country_code": "US",
  "province": "Florida",
  "city": "Seattle"
}
```

Error: `"Seattle is in Washington, not Florida."`

**Valid example**:

```json
{
  "country_code": "US",
  "province": "WA",
  "city": "Seattle"
}
```

The backend accepts province as **code** (`WA`, `FL`, `CABA`) or **name** (`Washington`, `Florida`, `Ciudad Autónoma de Buenos Aires`). Use `province_code` from the Provinces API when submitting to ensure consistency.

---

## Address Suggest – Narrow by Location

**GET** `/api/v1/addresses/suggest` accepts optional `province` and `city` to narrow results when the user has already selected from cascading dropdowns:

```http
GET /api/v1/addresses/suggest?q=123 Main&country=US&province=WA&city=Seattle&limit=5
```

This biases suggestions toward addresses in that area.

---

## Integration Example

### React/TypeScript

```typescript
// 1. Load provinces when country changes
const [provinces, setProvinces] = useState<Province[]>([]);
const [cities, setCities] = useState<City[]>([]);

useEffect(() => {
  if (!selectedCountry) {
    setProvinces([]);
    setCities([]);
    return;
  }
  fetch(`/api/v1/provinces/?country_code=${selectedCountry}`)
    .then(res => res.json())
    .then(setProvinces);
  setCities([]); // Clear cities when country changes
}, [selectedCountry]);

// 2. Load cities when province changes
useEffect(() => {
  if (!selectedCountry || !selectedProvince) {
    setCities([]);
    return;
  }
  fetch(`/api/v1/cities/?country_code=${selectedCountry}&province_code=${selectedProvince}`)
    .then(res => res.json())
    .then(setCities);
}, [selectedCountry, selectedProvince]);

// 3. Submit address with province_code
const addressPayload = {
  country_code: selectedCountry,
  province: selectedProvince, // Use province_code from dropdown (e.g. "WA")
  city: selectedCity,
  // ... street, postal_code, etc.
};
```

### Swift (iOS)

```swift
// Fetch provinces for country
func fetchProvinces(countryCode: String) async throws -> [Province] {
  let url = URL(string: "\(baseURL)/api/v1/provinces/?country_code=\(countryCode)")!
  let (data, _) = try await URLSession.shared.data(from: url)
  return try JSONDecoder().decode([Province].self, from: data)
}

// Fetch cities for country + province
func fetchCities(countryCode: String, provinceCode: String) async throws -> [City] {
  let url = URL(string: "\(baseURL)/api/v1/cities/?country_code=\(countryCode)&province_code=\(provinceCode)")!
  let (data, _) = try await URLSession.shared.data(from: url)
  return try JSONDecoder().decode([City].self, from: data)
}
```

---

## Supported Countries and Provinces (Reference)

Provinces are available for countries that have at least one supported city:

| Country | Provinces (examples) |
|---------|----------------------|
| **AR** (Argentina) | CABA, BA, CO, MN, MI, SF, TF |
| **BR** (Brazil)    | RJ, SP |
| **CL** (Chile)     | RM |
| **MX** (Mexico)    | CDMX, NL |
| **PE** (Peru)      | ARE, LIM, LAL |
| **US** (United States) | TX, IL, CA, FL, NY, WA |

Province codes (e.g. `CABA`, `WA`) are stable; province names may be localized. Prefer `province_code` when submitting addresses.

---

## Error Handling

### 400 Bad Request – Invalid country-province-city

```json
{
  "detail": "Seattle is in Washington, not Florida."
}
```

**Frontend action**: Ensure the address form uses cascading dropdowns populated from the Provinces and Cities APIs. Do not allow free-text city when province is selected, or validate before submit.

### 400 Bad Request – City not in supported list

```json
{
  "detail": "City 'Springfield' is not in the supported cities list for this country."
}
```

**Frontend action**: Restrict city selection to values from `GET /api/v1/cities/`. If your form allows free-text city, add validation or call the Address Validate endpoint before submit.

---

## Related Documentation

- [Addresses API Client](ADDRESSES_API_CLIENT.md) – Address CRUD, timezone auto-deduction
- [Addresses API Client](ADDRESSES_API_CLIENT.md) – Suggest and create endpoints
- [Market and Scope Guideline](MARKET_AND_SCOPE_GUIDELINE.md) – Markets API, country selection

---

**Document Status**: Ready for Frontend Implementation  
**Backend Implementation**: Complete
