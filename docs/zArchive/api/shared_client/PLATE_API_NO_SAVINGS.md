# Plate API: no savings in create/update or B2B UI

> **Superseded by:** [PLATE_API_CLIENT.md](PLATE_API_CLIENT.md) — Combined plate API guide including enriched endpoint, plate selection, and plate pickup pending.

**Audience:** B2B (supplier/employee portal) and any client that implements plate create/update and plate tables or modals.

Savings are **not stored** on plates. They are computed on the fly for B2C explore using the user's plan `credit_worth`, plate price, and plate credit. The plate API does **not** accept or return `savings` for create/update or for the enriched plate list/detail used by B2B.

---

## Create and update

- **POST /api/v1/plates/** (create): Request body includes `product_id`, `restaurant_id`, `price`, `credit`, `no_show_discount`, `delivery_time_minutes`. **No `savings` field.**
- **PUT /api/v1/plates/{plate_id}** (update): Same fields, all optional. **No `savings` field.**

Do not send `savings` in the request body; the backend schema does not accept it.

---

## Responses

- **GET /api/v1/plates/** and **GET /api/v1/plates/enriched/** do **not** include `savings`. B2B plate tables and detail views must not display or edit savings.
- **Savings** appear only in the **B2C** endpoint **GET /api/v1/restaurants/by-city**, in `restaurants[].plates[].savings` (integer 0–100), where they are computed per user/plan. See [b2c_client/EXPLORE_AND_SAVINGS.md](../b2c_client/EXPLORE_AND_SAVINGS.md).

---

## UI instruction (B2B)

For plate management (tables and create/edit modals): **do not** add a savings column or input. Only use: product, restaurant, price, credit, no_show_discount, delivery_time_minutes (and any other fields returned by the plate API that are not savings). Update existing tables and modals to remove any savings field so the agent and UI stay aligned with the API.
