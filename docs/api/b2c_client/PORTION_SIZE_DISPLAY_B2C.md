# Portion size display (B2C)

**Audience:** B2C app developers  
**Purpose:** Display human-readable portion size feedback from customer reviews on explore vianda cards. Replaces opaque numeric values with explicit labels.

---

## Overview

The explore flow (`GET /api/v1/restaurants/by-city`) returns a `portion_size` field per vianda. Use it to show customers what others say about portion sizes (Light, Standard, Large) or to display a "not enough reviews" message when the vianda has fewer than 5 reviews.

---

## Field: portion_size

**Location:** `restaurants[].viandas[].portion_size` from `GET /api/v1/restaurants/by-city`

**Values:** `"light"` | `"standard"` | `"large"` | `"insufficient_reviews"`

| Value | Meaning | Client display |
|-------|---------|----------------|
| `light` | Customers rate portions as smaller than average | Label: "Light" (or localized equivalent) |
| `standard` | Customers rate portions as typical | Label: "Standard" |
| `large` | Customers rate portions as generous | Label: "Large" |
| `insufficient_reviews` | Fewer than 5 reviews — averages not shown | Show localized message such as "There are not enough reviews for this vianda yet" |

---

## Minimum review threshold (5)

Averages require at least **5 reviews**. When `review_count < 5`:

- `average_stars` is `null`
- `average_portion_size` is `null`
- `portion_size` is `"insufficient_reviews"`

**When `portion_size === "insufficient_reviews"`:** Display your localized "not enough reviews" message. Do not show star or portion ratings.

---

## UI options

### Text label

Map `portion_size` to display text (client handles i18n):

- `light` → "Light", "Liviano", etc.
- `standard` → "Standard", "Normal", etc.
- `large` → "Large", "Grande", etc.
- `insufficient_reviews` → "There are not enough reviews for this vianda yet"

### Icon (fill-up or bars)

When `portion_size` is `light`, `standard`, or `large`, you can show a 1–3 bar icon:

- `light` → 1 bar filled
- `standard` → 2 bars filled
- `large` → 3 bars filled

---

## Optional: average_portion_size

For custom visuals (e.g. partial fill), use `average_portion_size` (float 1–3). It is `null` when `review_count < 5`. Prefer `portion_size` for primary display.

---

## Enum

Valid values are available from `GET /api/v1/enums/` under the key `portion_size_display`:

```json
{
  "portion_size_display": ["light", "standard", "large", "insufficient_reviews"]
}
```

---

## Example response snippet

```json
{
  "viandas": [
    {
      "vianda_id": "uuid",
      "product_name": "Grilled Chicken",
      "price": 12.5,
      "credit": 8,
      "average_stars": 4.2,
      "average_portion_size": 2.1,
      "portion_size": "standard",
      "review_count": 15
    },
    {
      "vianda_id": "uuid",
      "product_name": "New Vianda",
      "average_stars": null,
      "average_portion_size": null,
      "portion_size": "insufficient_reviews",
      "review_count": 2
    }
  ]
}
```

---

## Related docs

- [VIANDA_RECOMMENDATION_AND_FAVORITES_B2C.md](./VIANDA_RECOMMENDATION_AND_FAVORITES_B2C.md) — explore flow, `is_favorite`, `is_recommended`
- [CREDIT_AND_CURRENCY_CLIENT.md](../shared_client/CREDIT_AND_CURRENCY_CLIENT.md) — savings, price, credit (B2C explore)
- [shared_client/VIANDA_API_CLIENT.md](../shared_client/VIANDA_API_CLIENT.md) — enriched vianda endpoint (B2C and B2B)
