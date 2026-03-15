# Debug Logging Strategy (shared)

**Audience**: Backend (kitchen), B2B (kitchen-web), B2C (kitchen-mobile)  
**Purpose**: One environment variable to turn optional debug logs on/off so all apps use the same mechanism and stay consistent.

---

## Single environment variable

Use **one** variable for password/username recovery (and any related auth) debug logging:

| Variable | Purpose |
|----------|---------|
| `DEBUG_PASSWORD_RECOVERY` | When enabled, extra **terminal/log** lines are emitted around the password and username recovery workflow (forgot-password, reset-password, forgot-username). Intended for debugging only; leave off in production. |

No other env vars are needed for this feature. Using a single name reduces typos and keeps config simple.

---

## Allowed values (typo-safe)

The variable is **off** unless it is set to one of these values (case-insensitive):

| Value | Example |
|-------|---------|
| `true` | `DEBUG_PASSWORD_RECOVERY=true` or `DEBUG_PASSWORD_RECOVERY=TRUE` |
| `1` | `DEBUG_PASSWORD_RECOVERY=1` |
| `yes` | `DEBUG_PASSWORD_RECOVERY=yes` |

**Any other value is treated as off** (e.g. `false`, `0`, empty, `ture`, random string). That avoids accidentally enabling debug logs because of a typo or a mistaken value.

**Recommendation**:
- Prefer **`true`** (or `TRUE`) in docs and `.env.example`: it’s explicit and readable.
- **`1`** is fine and shorter for scripts or one-off runs (e.g. `DEBUG_PASSWORD_RECOVERY=1 npm run dev`).

There is no meaningful performance difference between checking `"1"` vs `"true"`; both are a single string check. Choose based on clarity and convention per app.

---

## Backend (kitchen) behavior

- The backend reads `DEBUG_PASSWORD_RECOVERY` at log time (e.g. via `os.environ.get("DEBUG_PASSWORD_RECOVERY", "").strip().lower() in ("1", "true", "yes")`).
- When enabled, log lines are prefixed with `[PasswordRecovery]` and include only non-sensitive workflow steps (e.g. “request received”, “user found”, “token stored”, “email sent”). No passwords or tokens are logged.
- When disabled (default), those lines are not emitted.

---

## B2B and B2C: same mechanism

Both client apps should use the **same** env var and the same rule:

1. **One variable**: `DEBUG_PASSWORD_RECOVERY`.
2. **Same allowed values**: `1`, `true`, `yes` (case-insensitive); anything else = off.
3. **Usage**: If the app has its own debug logs for the forgot-password / reset-password / forgot-username flow (e.g. in the frontend or in a BFF), gate them with the same check so that turning `DEBUG_PASSWORD_RECOVERY=true` (or `1`) gives a consistent debugging experience across backend and clients.

Example (pseudo-code) for clients:

```ts
// Only log when DEBUG_PASSWORD_RECOVERY is 1, true, or yes (case-insensitive)
const val = (import.meta.env?.VITE_DEBUG_PASSWORD_RECOVERY ?? process.env?.DEBUG_PASSWORD_RECOVERY ?? "").toString().trim().toLowerCase();
const debugPasswordRecovery = ["1", "true", "yes"].includes(val);

if (debugPasswordRecovery) {
  console.info("[PasswordRecovery]", message);
}
```

Use the same prefix `[PasswordRecovery]` so logs can be filtered consistently across services.

---

## Production

- **Default**: Do not set `DEBUG_PASSWORD_RECOVERY` in production (or set it to `false` / `0`). Debug logs stay off.
- **Debugging**: Set `DEBUG_PASSWORD_RECOVERY=true` (or `1`) only in local or non-production environments when you need to trace the recovery flow.

---

## Summary

| Item | Choice |
|------|--------|
| Env var | `DEBUG_PASSWORD_RECOVERY` (single variable) |
| On | `1`, `true`, or `yes` (case-insensitive) |
| Off | Anything else (typo-safe) |
| Recommended value in docs | `true` (clarity); `1` is fine for scripts |
| Log prefix | `[PasswordRecovery]` |
