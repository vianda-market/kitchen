# Portion size display (B2B)

**Audience:** B2B app developers (kitchen-web, Restaurant + Employee)  
**Purpose:** Show restaurants what customers say about portion sizes on their plates. Use for plate tables and detail views.

---

## Overview

The enriched plate endpoints return a `portion_size` field per plate. Use it to display portion feedback from customer reviews (Light, Standard, Large) or a "not enough reviews" message when a plate has fewer than 5 reviews.

---

## Endpoints

| Endpoint | Response location |
|----------|--------------------|
| `GET /api/v1/plates/enriched/` | Each plate has `portion_size` |
| `GET /api/v1/plates/enriched/{plate_id}` | Single plate has `portion_size` |

---

## Field: portion_size

**Values:** `"light"` | `"standard"` | `"large"` | `"insufficient_reviews"`

| Value | Meaning | B2B display |
|-------|---------|-------------|
| `light` | Customers rate portions as smaller | "Light" |
| `standard` | Customers rate portions as typical | "Standard" |
| `large` | Customers rate portions as generous | "Large" |
| `insufficient_reviews` | Fewer than 5 reviews | "There are not enough reviews for this plate yet" |

---

## Minimum review threshold (5)

Averages require at least **5 customer reviews**. When `review_count < 5`:

- `average_stars` is `null`
- `average_portion_size` is `null`
- `portion_size` is `"insufficient_reviews"`

**When `portion_size === "insufficient_reviews"`:** Display a message such as "There are not enough reviews for this plate yet" or "Not enough reviews yet". Averages are hidden to avoid misleading data from 1–2 outliers.

---

## Suggested UI

### Plate table

Add a **Portion Size** column:

- Show label (Light / Standard / Large) when `portion_size` is one of those values
- Show "Not enough reviews" when `portion_size === "insufficient_reviews"`

### Plate detail

- **With reviews:** "Customers rate portions as: Standard"
- **Without enough reviews:** "Not enough reviews yet" or "There are not enough reviews for this plate yet"

---

## average_portion_size and average_stars

Both are `null` when `review_count < 5`. When present, use for optional tooltips (e.g. "2.1 avg") if desired.

---

## Enum

Valid values from `GET /api/v1/enums/` under `portion_size_display`:

```json
["light", "standard", "large", "insufficient_reviews"]
```

---

## Related docs

- [shared_client/PLATE_API_CLIENT.md](../shared_client/PLATE_API_CLIENT.md) — enriched plate endpoint, full response structure
