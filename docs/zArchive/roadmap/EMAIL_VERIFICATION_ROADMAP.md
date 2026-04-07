# Email verification roadmap

## Current state (implemented)

- **B2C signup:** `verify_and_complete_signup` creates users with `email_verified = TRUE` and `email_verified_at` set (inbox proven via 6-digit code).
- **Password reset / B2B invite completion:** `password_recovery_service.reset_password` sets `email_verified = TRUE` and `email_verified_at` on success (code sent to the email currently on the account).
- **Email change:** Changing `email` via `PUT /api/v1/users/me` or `PUT /api/v1/users/{user_id}` does **not** update `user_info.email` immediately. A row is stored in `email_change_request`, a code is sent to the **new** address, and the user completes the change with `POST /api/v1/users/me/verify-email-change`. Until then, `email_verified` is set to `FALSE` on the profile update that initiated the change. The old address receives a security notification after a successful verify.

## Security nuance: `email_verified` and forgot-password

Setting `email_verified = TRUE` on **every** successful `reset_password` means: we treat “received the code at the **current** `user_info.email`” as proof of control of that address.

**Edge case:** If an attacker changes `user_info.email` through a compromise (before the victim completes the email-change verification flow) and then triggers a password reset, the reset email goes to the **new** address; completing reset would mark that address as verified. Mitigations are product/security decisions for the future (e.g. do not set `email_verified` on forgot-password-only, require re-login after email change, or additional step-up).

## Future work

1. **Cron:** Schedule `email_change_service.cleanup_expired_requests(db)` (see [CRON_JOBS_CHEATSHEET.md](../../cron/CRON_JOBS_CHEATSHEET.md)). Not required for correctness of active codes (expiry is enforced on verify); keeps the table tidy for ops and archival.
2. **Feature gating:** Optionally require `email_verified = TRUE` for sensitive actions (payments, employer linking, etc.).
3. **Admin support:** Endpoint or internal tool to manually set/clear `email_verified` for support workflows (out of scope for initial delivery).
