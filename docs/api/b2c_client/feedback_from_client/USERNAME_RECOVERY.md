# Username Recovery (Forgot Username)

**B2C client expectation** for the "Forgot your username?" flow. Optionally, the client can request that the backend also send a password-reset link to the same email (checkbox "Also send password reset link").

**Purpose:** Allow users who forgot their username to receive it by email; optionally also send a password-reset link in the same flow. Login uses username + password; account recovery is by email (consistent with TAKEOUT_APP_SPEC: "Account recovery is by email; backend looks up user by email").

---

## Endpoint (suggestion)

```http
POST /api/v1/auth/forgot-username
Content-Type: application/json
```

(Alternative: `POST /api/v1/customers/username-recovery`. Client will use whatever path the backend documents.)

**No `Authorization` header.**

---

## Request body

| Field                 | Type    | Required | Notes                                                                 |
| --------------------- | ------- | -------- | --------------------------------------------------------------------- |
| `email`               | string  | Yes      | Email of the account (normalized lowercase).                          |
| `send_password_reset` | boolean | No       | When `true`, also send a password-reset link to this email. Default: `false`. |

**Example (username only):**

```json
{
  "email": "user@example.com",
  "send_password_reset": false
}
```

**Example (username + password reset):**

```json
{
  "email": "user@example.com",
  "send_password_reset": true
}
```

---

## Response (success)

- **Status:** `200 OK` or `201 Accepted`.
- **Body:** Generic message only, to avoid email enumeration. Example:

```json
{
  "message": "If an account exists for this email, we have sent your username to it."
}
```

---

## Backend behavior

1. Look up the user by email (e.g. in `user_info` or equivalent).
2. If a user exists:
   - Always send an email containing the **username** (or a link to a secure page that shows the username). Do not include the password in plain text.
   - If `send_password_reset` is `true`: also send a **password-reset link** (or token/link that leads to the existing forgot-password reset flow) in the same email or in a second email. The client expects the user to receive both username and a way to reset password when the checkbox was checked.
3. If no user exists: do **not** indicate that in the response; return the same HTTP status and a similar generic message so the client cannot infer whether the email is registered.
4. **Rate limiting:** Strongly recommended (e.g. by IP and/or by email) to prevent abuse and email flooding. Return `429 Too Many Requests` when exceeded; client will show "Too many requests. Please try again later."
5. **No authentication:** This endpoint must be callable without a Bearer token.

---

## Error responses (suggested)

| Status | When                  | Client behavior                            |
| ------ | --------------------- | ------------------------------------------ |
| 400    | Invalid/missing email | Show validation message from `detail`.     |
| 429    | Rate limit            | Show "Too many requests. Please try again later." |
| 500    | Server error          | Show generic error message.                |

When the endpoint is not yet implemented, the backend may return **404** or **501**; the client will show: "Username recovery is not available right now. Please try again later or contact support."

---

## Security / privacy

- Do **not** return the username in the API response body. Send it only via email.
- Same generic response whether the email exists or not (no enumeration).
