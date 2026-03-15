# Enum fallback and logging — feedback for backend

**Date**: February 2026  
**Status**: For backend / product review  
**Related**: Enum Service API (`GET /api/v1/enums/`), `GET /api/v1/enums/roles/assignable`, user form Status dropdown  

**→ Backend response and next steps**: [ENUM_FALLBACK_NEXT_STEPS.md](./ENUM_FALLBACK_NEXT_STEPS.md)  
**→ Discretionary process enum**: [DISCRETIONARY_ENUM_ENHANCEMENT.md](./DISCRETIONARY_ENUM_ENHANCEMENT.md)

---

## 1. Situation summary

### What the frontend needed

- **User form Status dropdown**: Only **Active** and **Inactive** (per `ENUM_SERVICE_API.md`). The frontend uses `enumType: 'status_user'` and expects `GET /api/v1/enums/` to return a `status_user` key with values `["Active", "Inactive"]`.
- **User form Role dropdowns**: Role type and role name come from **`GET /api/v1/enums/roles/assignable`**, which returns `{ role_type: string[], role_name_by_role_type: Record<string, string[]> }`.

### What was observed

- **Status dropdown empty**: When the enums API did not return `status_user` (or returned it empty), or when the enums request failed, the Status dropdown had no options.
- **Two “assignable” requests failing**: Requests to `GET /api/v1/enums/roles/assignable` showed “failed to load response data” in the browser (e.g. CORS, non-JSON response, or endpoint/backend issue). Role type/name dropdowns then had no options.

---

## 2. What the frontend did

### 2.1 Status dropdown resilience

- **Fallback for `status_user`**: If `GET /api/v1/enums/` does not include `status_user`, returns it empty, or the request fails, the frontend **EnumService** now returns a hardcoded fallback **`['Active', 'Inactive']`** so the user form Status dropdown always has options.
- **Where**: `src/services/enumService.ts` — in `getEnum('status_user')`, three cases trigger the fallback:
  1. Cache has `status_user` but the array is empty.
  2. `getAllEnums()` throws (e.g. network/API failure).
  3. After a successful enums load, `status_user` is missing or empty.

### 2.2 Visibility when fallback is used

- **Console warning**: Whenever the fallback is used, the frontend logs a **`console.warn`** with a fixed prefix and a short reason:
  - `[EnumService] Using status_user fallback (Active, Inactive) — API returned empty status_user`
  - `[EnumService] Using status_user fallback (Active, Inactive) — enums API request failed`
  - `[EnumService] Using status_user fallback (Active, Inactive) — API did not include status_user`
- **Purpose**: So developers (and support) can tell in the browser console whether the UI is using **real API data** (no message) or the **fallback** (message present).

### 2.3 Assignable endpoint

- No frontend fallback was added for assignable roles. The Role dropdowns stay empty when `GET /api/v1/enums/roles/assignable` fails. Fixing that requires a working backend endpoint and correct response shape (and CORS if applicable).

---

## 3. Backend actions to consider

- **`status_user`**: Ensure `GET /api/v1/enums/` includes a `status_user` key with `["Active", "Inactive"]` (or the canonical list) so the frontend can rely on the API instead of the fallback.
- **Assignable**: Ensure `GET /api/v1/enums/roles/assignable` exists, returns the documented JSON shape, and is reachable (including CORS) so the Role dropdowns populate without “failed to load response data”.

---

## 4. Logging: where should these warnings go?

Right now the fallback is only logged in the **browser console** (`console.warn`). Below are options and a recommendation.

### Option A: Keep logs in the browser only (current)

- **Pros**: No backend changes, no PII or extra traffic, simple. Developers and support can inspect DevTools during debugging.
- **Cons**: No central visibility; you don’t see fallback usage in production unless someone captures console output or you add a separate reporting mechanism.

### Option B: Send fallback events to the backend

- **Idea**: Frontend calls a small “client event” or “diagnostics” endpoint (e.g. `POST /api/v1/diagnostics/events` or similar) with a payload like `{ event: 'enum_fallback_used', enumType: 'status_user', reason: '...' }` (no PII, no user identity required if you don’t want it).
- **Pros**: Backend can aggregate how often the fallback is used (e.g. by env, build, or time). Helps confirm that after you add `status_user`, the fallback stops being used.
- **Cons**: Extra endpoint and payload; need a clear policy for production (see below). Risk of log volume if you add many such events later.

**Production behavior**: If you do send to the backend, it’s reasonable to **not** send these warnings in production, or only in a “diagnostics opted-in” or internal build. That keeps production logs cleaner and avoids exposing internal behavior.

### Option C: Infra-level logging (e.g. AWS CloudTrail) and cross-system logging

- **Idea**: Don’t send fallback usage from the frontend to the backend. Instead:
  - Rely on **backend/app logs** when the enums API is called (e.g. log request/response or at least “enums served”).
  - Use **AWS CloudTrail** (and/or application logs) to see when your APIs are invoked and whether they succeed or fail.
  - Build **cross-system logging** at the infra level (e.g. central log aggregation, request IDs across services) so you can correlate frontend issues (e.g. “user saw empty dropdown”) with backend failures (e.g. enums or assignable endpoint errors) without the frontend sending its own “fallback” events.
- **Pros**: Single place for “truth” (backend and infra); no frontend logging endpoint; aligns with a model where the backend is the source of truth and infra gives visibility. Matches the direction in docs like `UI_EVENTS_AND_PAID_API_LOGGING_PLAN.md` (CloudTrail + application logs for paid APIs and important operations).
- **Cons**: You don’t get an explicit “fallback was used” event; you infer it from “enums failed or didn’t return status_user” and possibly from support/user reports. So you lose a direct, client-side signal.

### Recommendation

- **Short term**: Keeping the **browser-only** `console.warn` is enough for development and support. No backend change required.
- **Medium/long term**:
  - Prefer **Option C (infra-level logging)** for production: ensure the enums and assignable endpoints are logged (and covered by CloudTrail if applicable), and use cross-system logging to correlate API failures with user impact. Then you don’t need the frontend to send fallback events to the backend.
  - If product or backend explicitly wants a **client-originated** “fallback used” metric, then **Option B** is possible with a small diagnostics endpoint and a rule that **production builds do not send** these warnings (or only when the user opts in). That keeps production logs internal and avoids noise.

**Summary**: Use the browser console for now; treat infra/CloudTrail and backend application logs as the long-term way to see when enums/assignable fail. Add a frontend→backend “fallback” event only if you need a direct client-side metric and are okay keeping it internal/opted-in in production.

---

## 5. References

- `docs/api/shared_client/ENUM_SERVICE_API.md` — Enum Service API, including `status_user` and assignable roles.
- `src/services/enumService.ts` — Enum cache, `getEnum('status_user')`, and fallback + `console.warn` logic.
- `docs/infra/UI_EVENTS_AND_PAID_API_LOGGING_PLAN.md` — CloudTrail and application logging approach.
