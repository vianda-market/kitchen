# Ingredients API — B2B Client Guide

**Scope:** Supplier Admin and Internal users
**Base path:** `GET|POST /api/v1/ingredients/...` · `GET|POST /api/v1/products/{id}/ingredients`

---

## Overview

Products now support a structured ingredient list instead of a free-text field.
Ingredients come from the **Open Food Facts (OFF)** taxonomy — multilingual, covering ES / EN / PT — and are stored locally after the first lookup. Suppliers can also create custom ingredients when no match is found.

The old `ingredients` text field on `product_info` is **deprecated for new products**.
The `dietary` field has changed from a single string to a **multi-select array** — see §6.

---

## 1. Ingredient Search (`GET /api/v1/ingredients/search`)

Use this to power the ingredient autocomplete input while the supplier edits a product.

### Request

| Parameter | Type   | Required | Notes |
|-----------|--------|----------|-------|
| `query`   | string | ✅ | Min 2, max 100 chars. Debounce 300 ms. |
| `lang`    | string | ❌ | `es` \| `en` \| `pt`. Defaults to the user's locale language if omitted. |

```
GET /api/v1/ingredients/search?query=zanah&lang=es
Authorization: Bearer <token>
```

### Response

```json
[
  {
    "ingredient_id": "uuid",
    "name_display": "Zanahoria",
    "name_en": "Carrot",
    "off_taxonomy_id": "en:carrot",
    "image_url": null,
    "source": "off",
    "is_verified": false,
    "image_enriched": false
  }
]
```

### Field Notes

| Field | UI guidance |
|-------|-------------|
| `name_display` | Show this as the option label. May be a market-specific dialect alias. |
| `name_en` | English fallback label. Show as subtitle or tooltip when `name_display` differs. |
| `image_url` | `null` until Phase 5 (Wikidata image enrichment cron). Show a generic ingredient icon when `null`. |
| `is_verified` | Verified entries come from a curated catalog. Unverified entries come from OFF. Both appear. |
| `image_enriched` | `true` = image enrichment cron has run; `image_url` is present. |
| `source` | `"off"` or `"custom"`. Display-only; no behavior change needed. |

### UI Pattern

```
[ 🔍 Type an ingredient... ]
  ↓ (debounce 300ms, min 2 chars)
  → GET /ingredients/search?query=...
  ↓
  Zanahoria (Carrot)        [generic icon when image_url is null]
  Zapallo                   [generic icon]
  + Add "zap" as custom     ← show when < 3 results returned
```

When fewer than 3 results are returned, show an **"Add as custom"** affordance that calls `POST /ingredients/custom`.

---

## 2. Custom Ingredient Creation (`POST /api/v1/ingredients/custom`)

Use when the supplier cannot find their ingredient via search.

### Request

```json
{
  "name": "Rocoto",
  "lang": "es"
}
```

| Field  | Type   | Required | Notes |
|--------|--------|----------|-------|
| `name` | string | ✅ | 2–150 chars. |
| `lang` | string | ❌ | `es` \| `en` \| `pt`. Defaults to user locale. |

### Response

Same shape as search result (201 Created, or 200 if already exists by exact name).

```json
{
  "ingredient_id": "uuid",
  "name_display": "Rocoto",
  "name_en": null,
  "off_taxonomy_id": null,
  "image_url": null,
  "source": "custom",
  "is_verified": false,
  "image_enriched": false
}
```

---

## 3. Get Product Ingredients (`GET /api/v1/products/{id}/ingredients`)

Retrieve the current ordered ingredient list for a product.

```
GET /api/v1/products/550e8400-e29b-41d4-a716-446655440000/ingredients
Authorization: Bearer <token>
```

### Response

```json
[
  {
    "product_ingredient_id": "uuid",
    "ingredient_id": "uuid",
    "name_display": "Zanahoria",
    "name_en": "Carrot",
    "image_url": null,
    "sort_order": 0
  },
  {
    "product_ingredient_id": "uuid",
    "ingredient_id": "uuid",
    "name_display": "Papa",
    "name_en": "Potato",
    "image_url": null,
    "sort_order": 1
  }
]
```

Items are returned ordered by `sort_order` ascending (matching the order the supplier set them).

---

## 4. Set Product Ingredients (`POST /api/v1/products/{id}/ingredients`)

**Full replacement:** the entire ingredient list is replaced in a single call. Send all selected ingredient IDs in display order.

```
POST /api/v1/products/550e8400-e29b-41d4-a716-446655440000/ingredients
Authorization: Bearer <token>
Content-Type: application/json

{
  "ingredient_ids": [
    "uuid-zanahoria",
    "uuid-papa",
    "uuid-cebolla"
  ]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `ingredient_ids` | `UUID[]` | Ordered list. Max 30 items. Send empty array `[]` to clear all ingredients. |

### Response

Same as GET — the updated list in `sort_order` order (200 OK).

### Auth

- **Supplier Admin**: can only modify products belonging to their institution.
- **Internal**: can modify any product.

---

## 5. Suggested Component: Multi-Select Tag Input

Use a tag-style multi-select (e.g. `react-select` with `isMulti`) backed by the search endpoint.

```tsx
// Pseudo-code — adapt to your component library
<AsyncSelect
  isMulti
  loadOptions={(inputValue) =>
    fetch(`/api/v1/ingredients/search?query=${inputValue}&lang=${userLang}`)
      .then(r => r.json())
      .then(items => items.map(i => ({ value: i.ingredient_id, label: i.name_display })))
  }
  debounceTimeout={300}
  minInputLength={2}
  noOptionsMessage={({ inputValue }) =>
    inputValue.length >= 2
      ? <span>Not found — <button onClick={() => createCustom(inputValue)}>Add "{inputValue}"</button></span>
      : "Type to search…"
  }
  onChange={(selected) => {
    // On save, call POST /products/{id}/ingredients with selected.map(s => s.value)
  }}
/>
```

**On save:** call `POST /products/{id}/ingredients` with the full ordered list of selected `ingredient_ids`. Do not call the endpoint on every tag add/remove — batch on explicit save.

---

## 6. Dietary Multi-Select (`dietary` field)

The `dietary` field on products has changed from a free-text string to an array of validated flags.

### Accepted values

Fetch the canonical list from the Enum Service:

```
GET /api/v1/enums?language=es
```

Response includes a `DietaryFlag` key with translated labels per language.

Hardcoded reference (use Enum Service for display labels):

| Value | ES Label | EN Label |
|-------|----------|----------|
| `vegan` | Vegano | Vegan |
| `vegetarian` | Vegetariano | Vegetarian |
| `gluten_free` | Sin Gluten | Gluten Free |
| `dairy_free` | Sin Lactosa | Dairy Free |
| `nut_free` | Sin Frutos Secos | Nut Free |
| `halal` | Halal | Halal |
| `kosher` | Kosher | Kosher |

### Create / Update

```json
{
  "name": "Ensalada de Quinoa",
  "dietary": ["vegan", "gluten_free"]
}
```

- Sending an unrecognized value returns **422 Unprocessable Entity**.
- Sending `null` or omitting the field leaves dietary unchanged on update.
- Sending `[]` clears dietary flags.

### Read

```json
{
  "product_id": "uuid",
  "name": "Ensalada de Quinoa",
  "dietary": ["vegan", "gluten_free"],
  ...
}
```

**Phase 2 note:** In a future phase, the backend cron will validate dietary flags against USDA food group classifications. For now, the supplier's declaration is authoritative.

---

## 7. Migration Notes for Existing Products

Existing products with free-text `ingredients` data will continue to render normally — the old field is still present but deprecated. New products should use the structured endpoint. The B2B product form should display both old and new:

- If `product.ingredients` (old text field) is non-empty and `GET /products/{id}/ingredients` returns `[]`, show the old value in a read-only "Legacy ingredients" section with a prompt to migrate.
- Once the supplier saves via the new endpoint, the old field can be left as-is (it is not cleared automatically).

---

## 8. Error Reference

| Status | Cause |
|--------|-------|
| 404 | One or more `ingredient_ids` not found in catalog |
| 422 | Invalid `dietary` value or validation error |
| 500 | Internal error (log correlation via `X-Request-ID` header) |
