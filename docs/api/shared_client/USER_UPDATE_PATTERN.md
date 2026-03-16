# User Update Pattern (Self and by Others)

**Applies to**: B2B (kitchen-web, including backend portal) and B2C (kitchen-mobile).

This document describes **who can update user profiles**, **which endpoints to use**, and **which fields are immutable on any update** (whether the user updates themselves or an admin updates them).

---

## Two update contexts

| Context | Endpoint | Who |
|--------|----------|-----|
| **Self-update** | `PUT /api/v1/users/me` | Any authenticated user updating their own profile |
| **Update by others** | `PUT /api/v1/users/{user_id}` | Admins (e.g. Employee Admin, Supplier Admin) updating another user’s profile (e.g. from the backend portal) |

**Rule**: Use `/me` for self; use `/{user_id}` only when an admin is updating **another** user. Using `PUT /users/{user_id}` for self-updates returns **410 Gone** with a message to use `PUT /api/v1/users/me`. See [USER_SELF_UPDATE_PATTERN.md](./USER_SELF_UPDATE_PATTERN.md) for details.

---

## Immutable fields (any update)

The following fields **cannot be changed** after user creation, whether the user updates themselves or an admin updates them via the backend portal:

| Field | Behavior on `PUT /users/me` | Behavior on `PUT /users/{user_id}` |
|-------|-----------------------------|-----------------------------------|
| **username** | Ignored (stripped from payload) | **400** – `"username is immutable and cannot be changed after user creation."` |
| **role_type** | Not in update schema | **400** if sent |
| **institution_id** | Rejected (immutable) | **400** if sent |

- **Backend portal (B2B)**: When an admin edits another user, the UI must show **username** (and role_type, institution_id) as **read-only** and must **not** send them in the request body. Sending `username` results in **400**.
- **B2C / B2B self-service profile**: Same rule – username is read-only; do not send it. See [USERNAME_IMMUTABLE_CLIENT.md](./USERNAME_IMMUTABLE_CLIENT.md).

So **updating a username by others (e.g. admin employee in the backend portal) is forbidden**: the API rejects it with 400.

---

## Self-updates: use `/me`

- **Endpoint**: `PUT /api/v1/users/me`
- **Who**: Any authenticated user (Customer, Employee, Supplier).
- **Immutable fields**: username, role_type, institution_id are stripped or rejected; do not send them.

Details, migration guide, and TypeScript examples: [USER_SELF_UPDATE_PATTERN.md](./USER_SELF_UPDATE_PATTERN.md).

---

## Updates by others (admin / backend portal)

- **Endpoint**: `PUT /api/v1/users/{user_id}`
- **Who**: Admins only (e.g. Employee Admin, Supplier Admin, Super Admin) when managing **other** users. Not for self-updates.
- **Immutable fields**: Same as above. **username**, **role_type**, and **institution_id** cannot be changed by anyone. If the request body includes `username`, the API returns **400** with `"username is immutable and cannot be changed after user creation."`

### Backend portal (B2B) requirements

1. When showing an edit form for **another** user (e.g. “Edit user” in the admin panel), treat **username**, **role_type**, and **institution_id** as **read-only** (display only, no input).
2. Do **not** include `username`, `role_type`, or `institution_id` in the JSON body of `PUT /users/{user_id}`. If they are included, the API will return **400** for `username` (and similarly for the other immutable fields).
3. All other updatable profile fields (email, first_name, last_name, cellphone, role_name, market_id / market_ids, employer_id, status, etc.) remain editable by admins as allowed by the API and role rules.

---

## Summary table

| Operation | Endpoint | Who | Username / role_type / institution_id |
|-----------|----------|-----|----------------------------------------|
| Update my profile | `PUT /users/me` | Any user | Immutable – do not send; ignored or rejected |
| Update another user’s profile | `PUT /users/{user_id}` | Admins only | Immutable – do not send; **400** if sent |

---

## Related docs

- [USER_SELF_UPDATE_PATTERN.md](./USER_SELF_UPDATE_PATTERN.md) – /me migration and self-update details
- [USERNAME_IMMUTABLE_CLIENT.md](./USERNAME_IMMUTABLE_CLIENT.md) – Username read-only rules and request examples
- [API_PERMISSIONS_BY_ROLE.md](./API_PERMISSIONS_BY_ROLE.md) – Who can call which endpoints
