# Address APIs: Country Input and Google API Flow

## Who provides the country?

The **client** (frontend) sends the country to our backend. Our API does **not** type the country; it receives it in the request and passes a **country code (alpha-2)** to Google. **Normalization** (uppercase, alpha-2) is applied at the API boundary; clients may send case-insensitive alpha-2 or country name where supported.

- **GET /api/v1/addresses/suggest**  
  Query param `country` (optional): client sends either a **country code** (ISO 3166-1 alpha-2, e.g. `AR`) or a **country name** (e.g. `Argentina`). We resolve name → code and send **alpha-2** to Google Places Autocomplete as `includedRegionCodes`.

- **POST /api/v1/addresses/validate**  
  Body can include **country_code** (alpha-2, e.g. `AR`) or **country_name** (e.g. `Argentina`). We resolve to alpha-2 and send it to the Address Validation API as `regionCode`.

So: **user/frontend** → **our API** (we resolve name → code if needed; we normalize country_code to uppercase at the API boundary) → **Google** (we always send alpha-2). Clients may send alpha-2 case-insensitive; stored and returned values are uppercase.

---

## Dropdown vs free-text: how to support both

### Option A: Dropdown (recommended when possible)

- **Where does the list come from?**
  - **From our DB (recommended):** We already have **market_info** with `country_name` and `country_code` (Argentina, Peru, Chile, etc.). The frontend can call **GET /api/v1/markets** (or a dedicated GET /countries if we add one) and use the response to build a dropdown. User picks e.g. "Argentina" → frontend sends **country_code: "AR"** (alpha-2) to suggest/validate. No need for the user to type a code; we can keep the API **country_code-only** for this flow.
  - **From a frontend library:** The app can use a package (e.g. `country-list`, `react-country-select`) for a full list. To align with our markets, the frontend can filter that list to the same countries we support (e.g. from GET /markets) and send the selected **country_code** to our API.

- **Conclusion:** If the UX is a **dropdown** (from our markets or a library), the frontend always sends **country_code**. The user never types a code; the API can stay code-only for that flow.

### Option B: User types the country (free-text)

- If the user types the country in a text field (e.g. "Argentina", "Peru"), they are more likely to type the **name** than the code. So we support **country_name** in addition to **country_code**:
  - **Suggest:** query param `country` can be a name (e.g. `Argentina`) or a code; we resolve name → alpha-2 and send that to Google.
  - **Validate:** body can include **country_name** (e.g. `"Argentina"`) or **country_code** (e.g. `"AR"`); we resolve name → code and then call Google with alpha-2.

So: **dropdown** → send **country_code**; **free-text** → send **country_name** (or code); backend resolves name to code before calling Google.

---

## Where to store the list for a dropdown

- **In our DB:** Use **market_info**. It already has `country_name` and `country_code` for each market (Argentina, Peru, Chile, etc.). Expose this via **GET /markets** (or a thin GET /countries that returns `{ country_name, country_code }` for dropdowns). Pros: one source of truth, only “we operate here” countries, no extra table. Cons: adding a new country requires a new market (which you need anyway for subscriptions).
- **Frontend library:** Use a static list (e.g. from npm). Pros: full world list, no backend change for new countries. Cons: you must keep it in sync with “countries we support” (e.g. filter by GET /markets) if you want to restrict the dropdown.

**Recommendation:** Use **market_info** and GET /markets (or GET /countries) for the dropdown so the list is “countries we operate in” and the frontend always sends **country_code**. If you later need a free-text country field, the backend accepts **country_name** and resolves it before calling Google.

---

## Summary

| Who writes the country code? | The **client** sends it (or a country name) in the request. The **backend** resolves name → code and **always sends alpha-2** to Google. |
| Dropdown list source          | **DB:** use **market_info** via GET /markets (or GET /countries). **Frontend:** optional library, filtered by our markets if you want restriction. |
| If user picks from dropdown   | Frontend sends **country_code** (alpha-2, e.g. `AR`). No need for country_name in the API for this flow. |
| If user types the country     | Backend accepts **country_name** (e.g. "Argentina") and resolves to alpha-2 before calling Google. |
