# Feedback: Address formatting per market (B2C)

**Purpose:** Request that the by-city (and related) responses include a pre-formatted address string for display in the Explore Plate Modal and elsewhere, scoped by `market_id`.

**Audience:** Backend team.

---

## 1. Address display format by market

Street block order differs by market:

| Market | Order | Example |
|--------|-------|---------|
| US | building_number, street_name, street_type | `123 Main St` |
| Argentina, Peru | street_type, street_name, building_number | `Av Santa Fe 100` |

**Ask:** Add `address_display?: string` (or equivalent) to `RestaurantByCityItem` in `GET /api/v1/restaurants/by-city` (and related endpoints). The client will display it as-is and stop building address from `street_type`, `street_name`, `building_number` parts.

---

## 2. Additional fields for Explore Plate Modal

If not already in scope, the B2C client also needs:

- **Ingredients** — `ingredients` or `ingredients_text` on plates for the Explore Plate Modal Section B. Display as comma-separated or formatted list.
- **Pickup instructions** — `pickup_instructions` (string) at plate or restaurant level for Section E. Restaurants can add special instructions (e.g. "Pick up at side entrance after 12pm").

---

## 3. Related docs

- [RESTAURANT_EXPLORE_B2C.md](./RESTAURANT_EXPLORE_B2C.md) — by-city response shape
- [PLATE_RECOMMENDATION_AND_FAVORITES_B2C.md](./PLATE_RECOMMENDATION_AND_FAVORITES_B2C.md) — plate fields including `average_stars`, `average_portion_size`
