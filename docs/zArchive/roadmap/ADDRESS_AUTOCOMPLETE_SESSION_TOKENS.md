# Address Autocomplete Session Token Cost Optimization

**Last Updated**: 2026-03-09  
**Purpose**: Describes how to add session tokens to suggest and create to reduce Google Places API cost.

---

## Executive Summary

Google Places Autocomplete bills by session. When using **session tokens**:

- Autocomplete requests 1–12 in a session: billed per request
- Autocomplete requests 13+ in a session: free when the session terminates with a Place Details call
- Place Details call that ends the session: billed once

**Benefit**: Heavy typers (many suggest calls before selecting) pay less; cost aligns with "one address created" not "N suggests + 1 create."

---

## Current State

- Suggest: `GET /api/v1/addresses/suggest?q=...` — no session token
- Create: `POST /api/v1/addresses` with `place_id` — fetches Place Details once
- Each suggest call is billed independently

---

## Target Behavior

1. Client generates a session token (UUID) when user focuses the address field
2. Client sends `session_token` on each suggest call: `GET /addresses/suggest?q=...&session_token=...`
3. Client sends same `session_token` on create: `POST /addresses` with `place_id` and `session_token`
4. Backend forwards `session_token` to Google Autocomplete and Place Details
5. After create, session is considered terminated; client generates a new token for next address

---

## API Changes

### Suggest

- Query param: `session_token: Optional[str] = None`
- Backend passes to `places:autocomplete` in request body

### Create

- Body field: `session_token: Optional[str] = None`
- Backend passes to `place_details` (or Autocomplete session end)

---

## Google API Details

- Places API (New) Autocomplete: `sessionToken` in request body
- Place Details: Use same session token as the last Autocomplete request to end the session
- Session ends after Place Details; next Autocomplete starts a new session

---

## Implementation Notes

- Session tokens are opaque; client can use UUIDs
- No server-side storage of sessions; stateless
- If create fails, client may retry with same token (session still open) or start fresh
- Consider TTL guidance: e.g. session expires after 10 minutes of inactivity (client-side)
