# Mobile number verification roadmap

## Current state (MVP)

- **Field name**: API and database use **`mobile_number`** (E.164 string, optional).
- **Validation**: Numbers are parsed and normalized to **E.164** at write time using the **`phonenumbers`** library (offline; no external API). Invalid numbers return **422**.
- **`mobile_number_verified`**: Column exists on `user_info` (and history); always **`false`** until SMS verification ships. **`mobile_number_verified_at`** is **`NULL`**.
- **Mobile vs landline**: We do **not** enforce `phonenumbers.number_type() == MOBILE` in the API. For **US, AR, PE**, many valid numbers are classified as **`FIXED_LINE_OR_MOBILE`**; a strict mobile-only check would reject legitimate numbers. See the comment in [`app/utils/phone.py`](../../app/utils/phone.py).

## Backend behavior today (client contract)

- When a user **updates** **`mobile_number`** via **`PUT /api/v1/users/me`** or **`PUT /api/v1/users/{user_id}`**, if the value **changes** (including **clearing to `NULL`**), the API sets **`mobile_number_verified = false`** and **`mobile_number_verified_at = NULL`**. Clients must not send verification flags; they are read-only in responses.

## Post-MVP: UI and SMS

- **Re-verification prompt**: After SMS verification exists, when **`mobile_number_verified`** becomes **`false`** because the user changed their number, **B2C (mobile)** and **B2B (web)** clients should prompt the user to **verify the new number** via **SMS OTP**.
- **Twilio Verify** (preferred over Firebase for this stack): Use for send/confirm OTP; Twilio can **reject landlines and unreachable numbers at send time**, complementing our E.164 format check.
- **Feature gating**: Optionally require **`mobile_number_verified = true`** for sensitive flows (e.g. high-risk account actions).

## Future enhancements

- Optional stricter **`phonenumbers.number_type`** policy if product requirements change.
- No **unique** constraint on **`mobile_number`** in MVP; revisit if business rules require it.
