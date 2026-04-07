# Supported Cuisines API – Client Guide

**Document Version**: 1.1  
**Date**: April 2026  
**For**: Frontend Team (Web, iOS, Android)

---

## Overview

The backend exposes **GET /api/v1/cuisines/** to list supported cuisines for restaurant create/edit forms. Use this endpoint to populate the Cuisine dropdown. The same values are valid for the `cuisine` field on `POST /api/v1/restaurants/` and `PUT /api/v1/restaurants/{id}`. If a non-supported cuisine is sent, the backend returns 422 with a validation error.

**Key principle**: Use the Cuisines API to populate the dropdown; restrict selection to returned values. Do not allow free-text cuisine when creating or updating restaurants.

---

## Endpoint

### GET /api/v1/cuisines

**Description**: List supported cuisines for restaurant create/edit dropdown. Cuisine names are localized based on `?language=` or `Accept-Language` header.

**Authorization**: Customer, Employee, or Supplier (JWT required).

**Query parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `search` | string | — | Optional partial match on cuisine name or slug |
| `language` | string | — | Locale for display names (`en`, `es`, `pt`). Falls back to `Accept-Language` header, then `en`. Invalid values return 422. |

**Examples**

```http
GET /api/v1/cuisines
GET /api/v1/cuisines?language=es
GET /api/v1/cuisines?search=ita&language=es
```

**Response** (with `?language=es`)

```json
[
  { "cuisine_id": "...", "cuisine_name": "Italiana", "slug": "italian", ... },
  { "cuisine_id": "...", "cuisine_name": "Japonesa", "slug": "japanese", ... },
  { "cuisine_id": "...", "cuisine_name": "Mexicana", "slug": "mexican", ... }
]
```

**Response fields**

| Field | Type | Description |
|-------|------|-------------|
| `cuisine_id` | UUID | Unique identifier for the cuisine |
| `cuisine_name` | string | Localized cuisine name for display. When `language` is not `en`, resolved from `cuisine_name_i18n` JSONB with fallback to English. |
| `slug` | string | URL-safe identifier |
| `parent_cuisine_id` | UUID? | Parent cuisine for hierarchical display |
| `description` | string? | Optional description |
| `display_order` | int? | Sort order hint |

**Localization behavior**: Enriched restaurant and plate endpoints also resolve `cuisine_name` per the user's locale (via `Accept-Language` header). The localized name appears wherever cuisine is displayed — no client-side resolution needed.

---

## Restaurant Create/Update

When creating or updating a restaurant:

- **POST /api/v1/restaurants/** – `cuisine` optional. If provided, must be from `GET /api/v1/cuisines/`.
- **PUT /api/v1/restaurants/{id}** – `cuisine` optional. If provided, must be from `GET /api/v1/cuisines/`.

Validation is case-insensitive. `null` or empty string are allowed (cuisine is optional).

### Related endpoints

| Endpoint                      | Purpose |
|------------------------------|---------|
| `GET /api/v1/cuisines/`      | List supported cuisines for dropdown |
| `POST /api/v1/restaurants/`  | Create restaurant (cuisine from cuisines list) |
| `PUT /api/v1/restaurants/{id}` | Update restaurant (cuisine from cuisines list) |

---

## Integration Example

### React/TypeScript

```typescript
// Load cuisines on mount for restaurant form
const [cuisines, setCuisines] = useState<string[]>([]);

useEffect(() => {
  fetch('/api/v1/cuisines/', {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then((res) => res.json())
    .then((data) => setCuisines(data.map((c: { cuisine_name: string }) => c.cuisine_name)));
}, []);

// Submit with selected cuisine
const restaurantPayload = {
  institution_id: institutionId,
  institution_entity_id: entityId,
  address_id: addressId,
  name: restaurantName,
  cuisine: selectedCuisine || null,  // null if not selected
  // ...
};
```

### Swift (iOS)

```swift
func fetchCuisines() async throws -> [String] {
  let url = URL(string: "\(baseURL)/api/v1/cuisines/")!
  var request = URLRequest(url: url)
  request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
  let (data, _) = try await URLSession.shared.data(for: request)
  let items = try JSONDecoder().decode([[String: String]].self, from: data)
  return items.compactMap { $0["cuisine_name"] }
}
```

---

## Error Handling

### 422 Unprocessable Entity – Invalid cuisine

```json
{
  "detail": [
    {
      "loc": ["body", "cuisine"],
      "msg": "Cuisine 'Fusion' is not supported. Use GET /api/v1/cuisines/ for valid values.",
      "type": "value_error"
    }
  ]
}
```

**Frontend action**: Restrict cuisine selection to values from `GET /api/v1/cuisines/`. If allowing custom input, validate against the API response before submit.

---

## Related Documentation

- [CREDIT_AND_CURRENCY_CLIENT](CREDIT_AND_CURRENCY_CLIENT.md) – Restaurant create/update, institution context, currency from market
- [PROVINCES_API_CLIENT](PROVINCES_API_CLIENT.md) – Similar pattern for address cascading dropdowns

---

**Document Status**: Ready for Frontend Implementation  
**Backend Implementation**: Complete
