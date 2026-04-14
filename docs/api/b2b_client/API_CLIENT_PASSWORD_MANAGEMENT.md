# Backend: Change Password and Admin Password Reset (Client Guide)

## Purpose

- **Change my password:** The user opens a "Change Password" modal, enters their **current password** and **new password** (twice). Only a dedicated endpoint is used; the standard "Edit user" API does **not** support password changes.
- **Resend invite:** An admin can resend the B2B invite email (set-password link) when the original had wrong URL or expired. Primary flow for onboarding.
- **Admin reset (Postman only):** Kept for Postman collection testing; deprecation planned. B2B site uses invite flow only.

## Base URL and auth

- Base URL: your API base (e.g. `https://api.example.com` or `http://localhost:8000`).
- All requests require **Bearer token** in the `Authorization` header: `Authorization: Bearer <access_token>`.
- Content-Type: `application/json`.

---

## 1. Change my password (modal on Users page / profile)

**Endpoint:** `PUT /users/me/password`

**Who can call:** Any authenticated user (for themselves only).

**Request body:**

| Field                   | Type   | Required | Rules                       |
| ----------------------- | ------ | -------- | --------------------------- |
| `current_password`      | string | Yes      | User's current password     |
| `new_password`          | string | Yes      | Min length 8                |
| `new_password_confirm` | string | Yes      | Must equal `new_password`   |

**Example:**

```json
{
  "current_password": "OldPass123!",
  "new_password": "NewPass456!",
  "new_password_confirm": "NewPass456!"
}
```

**Success:** `200 OK` with body like:

```json
{
  "detail": "Password updated successfully"
}
```

**Errors:**

| Status | Meaning |
| ------ | ------- |
| 401    | Current password is incorrect. Show a message like "Current password is incorrect." |
| 400    | Validation error (e.g. new password too short, "New password and confirmation do not match", or "New password must differ from current password"). Body has `detail` (string) or Pydantic `detail` array. |
| 422    | Request body invalid (missing fields, wrong types). Check `detail` in response. |

**Frontend notes:**

- Use a single "Change Password" modal with three inputs: current password, new password, confirm new password.
- Do **not** send password (or any password field) in the standard "Edit user" request (`PUT /users/me` or `PUT /users/{user_id}`). The backend will ignore or reject it; password changes go only through this endpoint.
- After a successful change, you may want to keep the user on the same page or show a short success message; no need to log out unless your product requires it.

---

## 2. Admin reset another user's password (Postman/testing only)

**Endpoint:** `PUT /users/{user_id}/password`

**Status:** Kept for Postman collection testing. The B2B site uses the invite flow only and does not allow admins to set passwords on behalf of users. **Roadmap:** Deprecate once Postman is enhanced to not depend on it. Prefer `POST /users/{user_id}/resend-invite` (Section 4) for onboarding.

**Who can call:** Same as "Edit user" for that `user_id`:

- **Employees:** Can reset password for users they are allowed to manage (same scope as editing users).
- **Suppliers:** Admin and Manager only (Operator cannot reset other users' passwords); only for users in their own institution.
- **Customers / Employee Operator:** Only for themselves (i.e. `user_id` must equal the current user's id); otherwise 403.

**Request body:**

| Field                   | Type   | Required | Rules                       |
| ----------------------- | ------ | -------- | --------------------------- |
| `new_password`          | string | Yes      | Min length 8                |
| `new_password_confirm`  | string | Yes      | Must equal `new_password`   |

**Example:**

```json
{
  "new_password": "TempPass123!",
  "new_password_confirm": "TempPass123!"
}
```

**Success:** `200 OK` with body like:

```json
{
  "detail": "Password reset successfully"
}
```

**Errors:**

| Status | Meaning |
| ------ | ------- |
| 403    | Caller is not allowed to reset this user's password (e.g. wrong institution, Supplier Operator, or not Admin/Manager). |
| 404    | User not found or not accessible. |
| 400    | Validation (e.g. passwords don't match, too short). |
| 422    | Invalid body (missing/wrong fields). |

**Frontend notes:**

- Use a separate "Reset password" action/modal for another user (e.g. from a user list or user detail page). Only two fields: new password and confirm.
- Do **not** send password in the standard `PUT /users/{user_id}` edit-user request. Password changes for another user go only through this endpoint.

---

## 3. Standard edit user (no password)

**Endpoints:** `PUT /users/me` and `PUT /users/{user_id}`

- These endpoints do **not** accept `password`, `hashed_password`, or any password-related field.
- The "Edit user" form/modal should **not** include a password field. To change password, the user (or admin) must use the dedicated endpoints above.

---

## 4. Resend B2B invite email (set-password link)

**Endpoint:** `POST /users/{user_id}/resend-invite`

**Who can call:** Same as "Edit user" and Admin reset for that `user_id`:

- **Employees:** Can resend invite for users they are allowed to manage.
- **Suppliers:** Admin and Manager only; only for users in their own institution.
- **Customers / Employee Operator:** Only for themselves.

**Request body:** None.

**When to use:** When the original invite had the wrong URL (e.g. misconfigured `B2B_INVITE_SET_PASSWORD_URL`) or expired. Generates a new 6-digit code, invalidates prior codes, sends the invite email with the correct set-password link.

**Success:** `200 OK` with body like:

```json
{
  "detail": "Invite email sent successfully"
}
```

**Errors:**

| Status | Meaning |
| ------ | ------- |
| 400 | User has no email address. Cannot send invite. |
| 403 | Caller is not allowed to resend invite for this user. |
| 404 | User not found or not accessible. |

**Frontend notes:**

- Add a "Resend invite" action on the user list/detail for users who were invited but haven't set their password yet (e.g. when the first email had wrong URL).
- No request body required. User receives a new email with link valid for 24 hours.

---

## 5. Summary for integration

| Action                    | Method | Path                          | Body (password-related)                                    |
| ------------------------- | ------ | ----------------------------- | ----------------------------------------------------------- |
| Change my password        | PUT    | `/users/me/password`          | `current_password`, `new_password`, `new_password_confirm`  |
| Resend B2B invite         | POST   | `/users/{user_id}/resend-invite` | None                                                     |
| Admin reset user password | PUT    | `/users/{user_id}/password`   | `new_password`, `new_password_confirm` (Postman/testing)    |
| Edit my profile           | PUT    | `/users/me`                   | No password fields                                          |
| Edit another user         | PUT    | `/users/{user_id}`            | No password fields                                          |

All password hashing is done on the backend; the client only sends plain passwords over HTTPS to these endpoints and never receives or displays hashes.
