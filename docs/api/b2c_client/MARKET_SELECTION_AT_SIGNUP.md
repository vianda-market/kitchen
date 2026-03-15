# Market selection at B2C signup

**Audience**: B2C app (React Native / mobile)  
**Related**: [CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md](CUSTOMER_SIGNUP_EMAIL_VERIFICATION.md) (full signup flow)

## Quick implementation

To show a country/market selector at registration:

1. Call **`GET /api/v1/markets/available`** (no auth) to get the list of markets. See [Markets API](../shared_client/MARKETS_API_CLIENT.md) or B2C overview for the endpoint.
2. Let the user select one market (country) in the UI.
3. Send the selected market’s **`market_id`** (UUID) in the **`POST /api/v1/customers/signup/request`** request body.

**`market_id` is required** in the signup request body. Do not submit signup without it; the backend returns 400 if it is missing, invalid, archived, or Global Marketplace.

---

## Issue: deprecated or archived market_id

If the B2C client stores `market_id` (e.g. in app state, localStorage, or AsyncStorage) and reuses it later for signup, users can see:

```json
{ "detail": "Invalid or archived market_id. Use GET /api/v1/markets/available to get valid market UUIDs." }
```

This happens when the stored UUID refers to a market that has since been archived, or when the backend was rebuilt and UUIDs changed. The backend only accepts **active, non-archived** markets for B2C signup and rejects Global Marketplace.

### After a DB tear-down and rebuild

When the database is torn down and rebuilt, **all primary keys (including `market_id`) are new UUIDs**. Any `market_id` the client had stored from before the rebuild no longer exists. Submitting signup with that stored value causes the backend to return **400 Bad Request**. The client may show a message such as **"Your selected country is no longer available. Please select your country again."** — that is the correct user-facing response. Fix it by clearing the stored selection and having the user choose from the **current** GET /markets/available list (which will contain the new UUIDs).

---

## Long-term solution

- **Single source of truth for signup:** Use **GET /api/v1/markets/available** as the *only* source for the signup market/country dropdown. Do not hardcode market UUIDs or reuse a list from another endpoint (e.g. GET /users/me returns the logged-in user's market and can be Global — not valid for signup).
- **Do not persist `market_id` for signup:** Avoid saving the user's "selected market" for signup across sessions or app restarts. If you persist a market for explore/plans, treat that separately; for the signup flow, always build the selector from a fresh or short-TTL response from GET /markets/available.
- **Refresh when entering signup:** When the user opens the signup screen, call GET /markets/available (or use a cache with a short TTL, e.g. 5–15 minutes) and populate the dropdown from that response. Before submitting signup, ensure the selected `market_id` is in the current list; if not, refresh the list and have the user pick again.
- **Validate stored selection (if you do persist):** If the app persists a "selected country" (e.g. for convenience), **validate** it when loading the signup screen: fetch GET /markets/available and check whether the stored `market_id` is in the response. If it is **not** in the list (e.g. after a DB rebuild or because the market was archived), **clear** the stored value and show a prompt such as "Your selected country is no longer available. Please select your country again." so the user picks from the current list. Do not send the stale `market_id` to signup.
- **Default selection:** You may default to the first market or to one matching the device/browser locale (e.g. match `country_code` from the available list); the default must be one of the entries returned by GET /markets/available.

Following this ensures the client never sends an invalid or archived `market_id` and avoids the error above.
