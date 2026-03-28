# B2B User Invite Flow — Client Integration Guide

**Status**: Implemented  
**Version**: v1  
**Last Updated**: 2026-03-09

---

## Overview

When an authorized admin creates a B2B user, they can omit the password. The invited user receives an email with a link to set their own password, then logs in. This replaces the previous flow where the admin set or shared a password.

**Key points**:
- Users set their own password (no credentials shared)
- Email contains a link to a set-password page
- Same security as forgot-password (6-digit code, 24h expiry, single-use)
- Backward compatible: sending `password` still works (admin-set password)
- **Status**: Users created via invite flow are `status = Inactive` until they set their password. When they successfully complete `POST /auth/reset-password`, their status becomes `Active`. **Inactive users cannot log in** — login returns 403 for users with `status = Inactive`. Admins can filter users by `status = Inactive` to see who has not completed setup.

---

## Flow Diagram

```
Admin (B2B portal)                    Backend                         Invited user
       |                                  |                                  |
       | POST /users/ (no password)        |                                  |
       |--------------------------------->|                                  |
       |                                  | Create user (random hash)         |
       |                                  | Store 6-digit code in DB         |
       |                                  | Send invite email with link      |
       | 201 + user (no password)         |                                  |
       |<---------------------------------|                                  |
       |                                  |                                  |
       |                                  |                    Email received |
       |                                  |<---------------------------------|
       |                                  |                                  |
       |                                  |    Click link -> /set-password?code=123456 |
       |                                  |<---------------------------------|
       |                                  |                                  |
       |                                  | POST /auth/reset-password {code, new_password} |
       |                                  |<---------------------------------|
       |                                  | Validate, update password,      |
       |                                  | set status = Active             |
       |                                  |--------------------------------->|
       |                                  | 200 OK                           |
       |                                  |                                  |
       |                                  |    Login with username + new password |
       |                                  |<---------------------------------|
```

---

## API Changes

### POST /api/v1/users/ (create user)

**Restriction**: Customer users cannot be created via this endpoint. They must self-register via `POST /customers/signup/request` and `POST /customers/signup/verify`. Sending `role_type: Customer` returns 400.

**`password` is now optional.**

| Field      | Type   | Required | Description                                                                 |
|------------|--------|----------|-----------------------------------------------------------------------------|
| password   | string | **No**   | Omit to trigger invite flow. If provided (min 8 chars), admin-set password. |

**When `password` is omitted**:
- User is created with `status = Inactive` and a placeholder hash (cannot log in — login returns 403 for Inactive users)
- Invite email is sent automatically with a link to set password
- When user completes `POST /auth/reset-password`, their status becomes `Active` and they can log in
- Response: 201 with user object (no password field in response)

**When `password` is provided**:
- User is created with `status = Active`; user can log in immediately with that password
- No invite email sent

### POST /api/v1/users/{user_id}/resend-invite

**Resend the invite email** when the original had the wrong URL (e.g. misconfigured `B2B_INVITE_SET_PASSWORD_URL`) or expired.

| Aspect | Details |
|--------|---------|
| Method | POST |
| Auth | Same as edit user (Admin, Manager, etc.) |
| Body | None |
| Success | 200 — `{"detail": "Invite email sent successfully"}` |
| 400 | User has no email address |
| 403/404 | Access denied / user not found |

Generates a new 6-digit code, invalidates prior unused codes, sends a new invite email. User sets password via the link → `POST /auth/reset-password`. See [CHANGE_PASSWORD_AND_ADMIN_RESET.md](./CHANGE_PASSWORD_AND_ADMIN_RESET.md#4-resend-b2b-invite-email-set-password-link) for full details.

---

## Frontend Requirements

### 1. Create User Form

- **Option A (invite flow)**: Do not send `password` in the create payload. Show a message: "An invite email will be sent to the user."
- **Option B (admin-set password)**: Send `password` as before for backward compatibility.

### 2. Set-Password Page

Implement a route that the invite link opens, for example:

- `/set-password`
- Query param: `?code=123456` (6-digit code from the link)

**Page behavior**:
1. Read `code` from the URL query string
2. Show a form: new password, confirm password
3. On submit, call `POST /api/v1/auth/reset-password` with body:
   ```json
   {
     "code": "123456",
     "new_password": "YourNewPassword123!"
   }
   ```
4. On success: redirect to login with message "Password set. Please log in."
5. On error (invalid/expired code): show "This link has expired or is invalid. Ask your admin to resend the invite."

The admin can resend via `POST /users/{user_id}/resend-invite` (add "Resend invite" action on user list/detail).

### 3. Link Format

The email contains a link in this form:
```
{BASE_URL}/set-password?code={code}
```

Configure `B2B_INVITE_SET_PASSWORD_URL` (env) as:
```
https://your-b2b-app.example.com/set-password?code={code}
```

The backend replaces `{code}` with the 6-digit code.

---

## Email Content (User Receives)

**Subject**: You've been invited to Vianda – Set your password

**Body**: The user sees:
- A greeting with their first name (or "there")
- An explanation that they were invited
- A "Set your password" button linking to the set-password page
- Note that the link expires in 24 hours
- Note to ignore the email if they did not expect the invitation

---

## Token Validity

- **Expiry**: 24 hours
- **Use**: Single-use (invalidated after password is set)
- **Format**: 6-digit numeric code

---

## Configuration

| Env Variable                | Description                                                                 |
|-----------------------------|-----------------------------------------------------------------------------|
| B2B_INVITE_SET_PASSWORD_URL | URL template for the set-password link. Use `{code}` placeholder. Optional. |
| B2B_FRONTEND_URL            | B2B app base URL. When `B2B_INVITE_SET_PASSWORD_URL` is not set, the link is `{B2B_FRONTEND_URL}/set-password?code={code}`. Local dev: `http://localhost:5173`. In production, set `B2B_INVITE_SET_PASSWORD_URL` explicitly. |

---

## Backward Compatibility

- Sending `password` in `POST /api/v1/users/` still works; the user is created with that password and can log in immediately.
- Existing B2B clients that always send a password are unaffected.

---

## Related Documentation

- [USER_MODEL_FOR_CLIENTS.md](../shared_client/USER_MODEL_FOR_CLIENTS.md) — Password reset (`§9`), user create/update, `market_id` / `market_ids`. Long-form password UI samples: [PASSWORD_RECOVERY_CLIENT.md](../../zArchive/api/shared_client/PASSWORD_RECOVERY_CLIENT.md)
