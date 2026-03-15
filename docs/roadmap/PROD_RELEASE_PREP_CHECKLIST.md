# Prod Release Prep Notes

## 1. Frontend URL Configuration

- Replace local/dev URLs with production values in env (or Secrets Manager):
  - `FRONTEND_URL` → B2C app production URL (e.g. `https://app.kitchen.com`)
  - `B2B_FRONTEND_URL` → B2B app production URL (e.g. `https://b2b.kitchen.com`)
  - `B2B_INVITE_SET_PASSWORD_URL` → Set explicitly in prod: `https://b2b.kitchen.com/set-password?code={code}` (recommended for invite links; falls back to `B2B_FRONTEND_URL` if unset)
- CORS: Restrict `allow_origins` in `application.py` to known frontend domains (B2C + B2B) instead of `["*"]`.

## 2. Environment & Provider Settings

- `PAYMENT_PROVIDER` and `SUPPLIER_PAYOUT_PROVIDER` → `stripe` (not `mock`) in production.
- `DEV_MODE` → `false` for real external APIs.
- Debug flags off: `LOG_EMAIL_TRACKING`, `LOG_EMPLOYER_ASSIGN`, `DEBUG_PASSWORD_RECOVERY` unset or false.
- SMTP: Use production email config (e.g. AWS SES) and verify deliverability for password reset and B2B invite links.
- `VIANDA_CUSTOMERS_INSTITUTION_ID` and `VIANDA_ENTERPRISES_INSTITUTION_ID` must match `seed.sql`.

## 3. Database

- Apply schema migrations (from `app/db/migrations/`) in order.
- Run `seed.sql` (or equivalent) per environment.
- Confirm archival config (`AUTO_ARCHIVAL_ENABLED`, retention periods) is appropriate.

## 4. Assets & Placeholders

- Ensure placeholder assets are in place:
  - `static/placeholders/product_default.png` checked into repo.
  - Product creation defaults to that image (path + checksum) when no upload is supplied.
- Verify teardown scripts clear generated assets alongside DB resets:
  - Remove contents of `static/qr_codes/`.
  - Remove contents of `static/product_images/` (once implemented).
- Confirm schema migrations include new image storage/checksum columns for `product_info` and `qr_code`.
- Update release checklist to confirm Postman collections cover image upload + checksum flows.

