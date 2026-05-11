# Username Is Read-Only (Immutable)

**Applies to**: B2B (kitchen-web, including backend portal) and B2C (kitchen-mobile).

For the full user update pattern (self vs updates by others, and all immutable fields), see [USER_UPDATE_PATTERN.md](./USER_UPDATE_PATTERN.md).

---

## Summary

**Username cannot be changed** after account creation. The API treats `username` as immutable on all user update endpoints. Both client apps must show username as **read-only** in profile/settings and must **not** send `username` in update payloads (or accept that the backend will ignore or reject it).

---

## API Behavior

| Endpoint | Behavior when `username` is in the request body |
|----------|--------------------------------------------------|
| `PUT /api/v1/users/me` | **Ignored.** The server strips `username` from the payload before applying updates. No error; the field is simply not updated. |
| `PUT /api/v1/users/{user_id}` | **Rejected.** The server returns **400** with `detail: "username is immutable and cannot be changed after user creation."` |

### Why Immutable?

- **Login identifier**: Users sign in with username (and password). Allowing changes would require a dedicated flow (verification, uniqueness, rate limits).
- **Recovery**: "Forgot username" sends the current username to the user’s email; keeping it stable avoids confusion and support issues.
- **Impersonation / integrity**: Preventing username changes avoids abuse (e.g. support-like names) and keeps logs/support references consistent.

---

## Client Requirements

### B2B (kitchen-web) and B2C (kitchen-mobile)

1. **Profile / account settings**
   - Show **username** as **read-only** (display only, no input or edit control).
   - Do **not** include an "Edit username" or "Change username" action unless the backend later introduces a dedicated, documented flow for it.

2. **Update profile request body**
   - When calling `PUT /users/me` (or `PUT /users/{user_id}` for admins), **do not** include `username` in the JSON body.
   - If your form or type still has a `username` field, strip it before sending:
     - Either omit `username` from the payload, or
     - Delete `username` from the object you send (e.g. `delete updates.username` or build the payload from allowed fields only).

3. **Admin updates / backend portal (B2B only)**
   - When admins update another user via `PUT /users/{user_id}` (e.g. from the backend portal), do not send `username`. If sent, the API returns **400** with the message above. Username cannot be changed by others either – see [USER_UPDATE_PATTERN.md](./USER_UPDATE_PATTERN.md).

4. **Display and copy**
   - You may show the username anywhere it’s useful (e.g. profile header, "Signed in as …"). Use the value from `GET /users/me` or the enriched user response; it will not change for that account.

---

## Allowed vs Immutable User Profile Fields

| Field | On update (PUT /users/me or PUT /users/{user_id}) |
|-------|----------------------------------------------------|
| `username` | **Immutable** – ignored or rejected; do not send. |
| `role_type` | **Immutable** – not in update schema. |
| `institution_id` | **Immutable** – rejected if sent. |
| `email` | Editable (if your role and backend rules allow). |
| `first_name`, `last_name` | Editable. |
| `mobile_number` | Editable (E.164). |
| `role_name` | Editable (subject to role rules). |
| `market_id` / `market_ids` | Editable (subject to role rules). |
| `employer_id` | Editable for Customers only. |
| `status` | Editable (subject to permissions). |

---

## TypeScript / Request Example

```typescript
// When building the body for PUT /users/me, omit username (or strip it).
interface UserUpdatePayload {
  email?: string;
  first_name?: string;
  last_name?: string;
  mobile_number?: string;
  role_name?: string;
  market_id?: string;
  market_ids?: string[];
  employer_id?: string;
  status?: 'Active' | 'Inactive';
  // username is intentionally omitted – do not include
}

function updateMyProfile(updates: Partial<UserUpdatePayload>): Promise<UserResponse> {
  const body = { ...updates };
  delete (body as Record<string, unknown>).username; // ensure username never sent
  return api.put('/api/v1/users/me', body);
}
```

---

## Forgot-Username Flow

The **forgot-username** flow is unchanged. The user enters their email; the backend sends an email containing their **current** username. Because username does not change, that value remains correct for the life of the account. See [USERNAME_RECOVERY.md](./USERNAME_RECOVERY.md) for the endpoint and usage.

---

## If the Backend Adds Username Change Later

If the API later introduces a dedicated "change username" flow (with verification, uniqueness checks, and rate limits), it will be documented in the API and in a new or updated client doc. Until then, both B2B and B2C must treat username as **read-only** and must not send it on update.
