# Explore and savings (B2C)

## GET /restaurants/by-city

Query params are unchanged: `city`, `country_code`, `market_id`, `kitchen_day`. When `market_id` and `kitchen_day` are present, the response includes `restaurants[].plates` with `plate_id`, `product_name`, `price`, `credit`, `kitchen_day`, `image_url`, and **`savings`** (integer 0–100).

## Meaning of `savings`

`savings` is the percentage discount: `(price - credit * credit_cost_local_currency) / price`, where `credit_cost_local_currency` is in local currency per credit. For a user with a subscription in the explored market, `credit_cost_local_currency` comes from their plan (JWT). When the user has no subscription in that market (or is unauthenticated), savings are computed using the **highest-priced plan** in the market (best possible savings as a teaser). The same plate can show different savings for different users (different plans).

## When it updates

Savings are computed from the current **price** and **credit** on the plate and the user's **credit_cost_local_currency** (from the JWT). Restaurants can change price and credit at any time. Clients should **refresh** when entering the explore tab or via pull-to-refresh so users see current values and recomputed savings.

## UI requirement

The discount **must** be shown as a **percentage of savings**. The API returns `savings` as an integer 0–100. The client must display this as a percentage per plate (e.g. "15% off", "15% savings", or "Save 15%"). Use `price` and `credit` for any secondary display (e.g. "X credits · $Y").

## GCS signed URLs (product images)

When the API uses GCS storage, `image_url` in plates is a time-limited signed URL (1h default). On 403 when loading an image, re-fetch the restaurant/plate data from the API to get a fresh signed URL. Do not cache signed URLs beyond their expiration. See [IMAGE_STORAGE_GUIDELINES.md](../../guidelines/storage/IMAGE_STORAGE_GUIDELINES.md).

## SLA summary

- **Order cutoff:** Orders are accepted until **1:30 PM local time** (market timezone) for that kitchen day. See [KITCHEN_DAY_SLA.md](../internal/KITCHEN_DAY_SLA.md) for full SLA.
- **Price/credit:** Restaurants can update plate price and credit at any time; changes are live. There is no "effective next day" for restaurant edits.
- **Client refresh:** The app should refresh when entering explore or on pull-to-refresh so users see current prices and savings.
