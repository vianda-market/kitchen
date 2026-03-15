# Explore plate cards — B2C UI data needs

**Purpose:** The B2C Explore screen shows **plate-centric cards** (one card per plate). The client currently uses placeholders for several fields. This document asks the backend to provide the following so we can replace placeholders with real data.

**Context:** The Explore flow uses `GET /api/v1/restaurants/by-city` with `market_id` and `kitchen_day`. The response includes `restaurants[]` with `plates[]` per restaurant. Each plate card in the UI shows: thumbnail, plate name, restaurant name, cuisine, address, **savings %**, and **credits**. See [RESTAURANT_EXPLORE_B2C.md](../RESTAURANT_EXPLORE_B2C.md) for the existing by-city contract.

---

## 1. Plate thumbnail image

**Current UI:** A gray placeholder box (no image).

**Requested:** A URL for a plate/product image so the client can show a thumbnail to the left of each plate card.

**Suggested response shape:** Add to each item in `restaurants[].plates[]` (or to the plate/product resource used for by-city):

| Field           | Type   | Description |
|----------------|--------|-------------|
| `image_url`    | string | Optional. Full URL to a plate/product image (thumbnail preferred). If absent, client keeps showing placeholder. |

**Example:** `"image_url": "https://cdn.example.com/plates/abc123.jpg"`

---

## 2. Restaurant address (street type, street name, building number)

**Current UI:** The card shows "Address TBD" for the restaurant address line.

**Requested:** For each restaurant in the by-city response, include a single-line address so the user can see where the restaurant is (street type, street name, building number). Optionally city/postal_code if not redundant.

**Suggested response shape:** Add to each item in `restaurants[]` (RestaurantByCityItem):

| Field             | Type   | Description |
|-------------------|--------|-------------|
| `street_type`     | string | Optional. E.g. "Av", "Calle", "Street". |
| `street_name`     | string | Optional. Street name. |
| `building_number` | string | Optional. Building or street number. |

The client will display: `{street_type} {street_name} {building_number}` (e.g. "Calle Florida 123"). If any is missing, client can keep "Address TBD" or show what’s available.

---

## 3. Savings percentage for the customer

**Current UI:** A box in the top-right of each plate card showing "—% off" (placeholder).

**Requested:** A **savings percentage** (e.g. vs. non-subscription or list price) so the customer sees the benefit of using credits for that plate.

**Suggested response shape:** Add to each item in `restaurants[].plates[]`:

| Field           | Type   | Description |
|----------------|--------|-------------|
| `savings_pct`  | number | Optional. Integer or decimal (e.g. 15 for 15% off). If absent, client keeps "—% off" or hides the box. |

**Example:** `"savings_pct": 15` → client shows "15% off".

**Backend behavior:** Define how savings is computed (e.g. list price vs. credit price in the market). Client only displays the value.

---

## Summary

| Data              | Where (implemented)    | Placeholder today   |
|-------------------|------------------------|---------------------|
| Plate image       | `plates[].image_url`   | Gray box (optional; from product_info) |
| Restaurant address| `restaurants[].street_type`, `street_name`, `building_number` | "Address TBD" (from address_info) |
| Savings %         | `plates[].savings`     | "—% off" (integer 0–100 from plate_info) |

**Backend implementation:** `GET /api/v1/restaurants/by-city` now returns these fields. Data source: `image_url` from `product_info` (join via `plate_info.product_id`); address fields from `address_info` (join via `restaurant_info.address_id`); `savings` from `plate_info`. All fields optional except `savings` (default 0). Client can remove placeholders and use real data.
