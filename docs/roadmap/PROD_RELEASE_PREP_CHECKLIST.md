# Prod Release Prep Notes

- Ensure placeholder assets are in place:
  - `static/placeholders/product_default.png` checked into repo.
  - Product creation defaults to that image (path + checksum) when no upload is supplied.
- Verify teardown scripts clear generated assets alongside DB resets:
  - Remove contents of `static/qr_codes/`.
  - Remove contents of `static/product_images/` (once implemented).
- Confirm schema migrations include new image storage/checksum columns for `product_info` and `qr_code`.
- Update release checklist to confirm Postman collections cover image upload + checksum flows.

