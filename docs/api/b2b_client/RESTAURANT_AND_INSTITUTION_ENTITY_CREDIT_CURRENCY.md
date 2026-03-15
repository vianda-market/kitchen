# Restaurant and Institution Entity: credit_currency from entity

**Audience:** B2B (supplier portal) and any client that creates restaurants or institution entities.

Credit currency is owned by the **institution entity** (tied to market via address country). Restaurants inherit `credit_currency` from their institution entity. Clients do **not** send `credit_currency_id` on restaurant or institution entity create.

---

## Restaurant create and update

- **POST /api/v1/restaurants/** (create): Request body includes `institution_id`, `institution_entity_id`, `address_id`, `name`, `cuisine`. **No `credit_currency_id` field.** Do not send `credit_currency_id`; the backend derives it from the institution entity. Use **GET /api/v1/cuisines/** to populate the Cuisine dropdown; `cuisine` must be from that list (or null).
- **PUT /api/v1/restaurants/{restaurant_id}** (update): Same fields, all optional. **No `credit_currency_id` field.** Currency cannot be changed on the restaurant; it is fixed by the institution entity.

The restaurant response may still include `credit_currency_id` for API compatibility (populated from the entity). The client should not send it on create or update.

---

## Institution entity create and update

- **POST /api/v1/institution-entities/** (create): Request body includes `institution_id`, `address_id`, `tax_id`, `name`, etc. **No `credit_currency_id` field.** The backend **derives** `credit_currency_id` from the entity's address: `address.country_code` → market → `market.credit_currency_id`. Clients do not send it.
- **PUT /api/v1/institution-entities/{entity_id}** (update): Same fields, all optional. If `address_id` changes, the backend recomputes `credit_currency_id` from the new address’s market. Clients do not send `credit_currency_id`.

---

## UI instruction (B2B)

- **Restaurant form**: Do not add a credit currency selector. The currency is determined by the institution entity (chosen via `institution_entity_id`). The entity’s currency comes from its address’s market.
- **Institution entity form**: Do not add a credit currency selector. The entity’s address determines the market, and the market’s currency is applied automatically. Ensure the address has a valid `country_code` so the backend can resolve the market.

---

## Related documentation

- [PLAN_API_MARKET_CURRENCY.md](./PLAN_API_MARKET_CURRENCY.md) — Plans also derive currency from market; no `credit_currency_id` on create.
- [RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md](../shared_client/RESTAURANT_STATUS_AND_PLATE_KITCHEN_DAYS.md) — Restaurant create and status.
- [CUISINES_API_CLIENT.md](../shared_client/CUISINES_API_CLIENT.md) — Cuisine dropdown: GET /api/v1/cuisines/ for restaurant form.
