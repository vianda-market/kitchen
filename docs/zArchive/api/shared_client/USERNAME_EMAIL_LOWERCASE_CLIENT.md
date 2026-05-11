# Username and Email Lowercase Normalization

**Applies to**: B2B (kitchen-web) and B2C (kitchen-mobile).

---

## Summary

The backend **normalizes all usernames and emails to lowercase** before storing and when looking up. This ensures:

- `User@example.com` and `user@example.com` are treated as the same account
- Login works regardless of case (e.g., signup with `TestUser`, login with `testuser`)
- No duplicate accounts for the same person due to different capitalization

---

## Backend Behavior

| Operation | Field | Backend Handling |
|-----------|-------|------------------|
| Signup (POST /customers/signup/request) | username, email | Normalized to lowercase before storing |
| User creation (POST /users/) | username, email | Normalized to lowercase before storing |
| Login (POST /auth/token) | username | Normalized to lowercase before lookup |
| Forgot username (POST /auth/forgot-username) | email | Normalized to lowercase before lookup |
| Forgot password (POST /auth/forgot-password) | email | Normalized to lowercase before lookup |
| User lookup (GET /users/lookup) | username, email | Normalized to lowercase before lookup |
| Email registered check (GET /leads/email-registered) | email | Normalized to lowercase before lookup |

---

## Frontend Recommendations (Defense in Depth)

Apply `.toLowerCase().trim()` (or equivalent) on the client before sending:

| Screen / Flow | Fields to Normalize |
|---------------|---------------------|
| Signup form | username, email |
| Login form | username |
| Forgot-username form | email |
| Forgot-password form | email |
| B2B create-user form | username, email |

**Why frontend normalization helps:**
- Consistent UX: user sees lowercase in the form after submit
- Avoids accidental duplicates if backend contract changes
- Better accessibility (screen readers, autocomplete)

---

## TypeScript / JavaScript Example

```typescript
function normalizeUsernameEmail(value: string): string {
  return (value ?? "").trim().toLowerCase();
}

// Before submitting signup
const signupPayload = {
  username: normalizeUsernameEmail(form.username),
  email: normalizeUsernameEmail(form.email),
  // ... other fields
};

// Before submitting login
const loginFormData = new URLSearchParams();
loginFormData.set("username", normalizeUsernameEmail(form.username));
loginFormData.set("password", form.password);

// Before submitting forgot-username / forgot-password
const email = normalizeUsernameEmail(form.email);
```

---

## Database Enforcement

The backend uses PostgreSQL `citext` (case-insensitive text) for `username` and `email` columns. Even if application code omits normalization, the database treats `User@x.com` and `user@x.com` as identical for uniqueness and lookups.
