# Product Images & QR Code Checksum Roadmap (Planning)

## 1. Product Image Enhancements
- **Single asset model**: keep one image per `product_info` row; history stays in existing `_history` table (no new table needed).
- **Schema additions**: add `image_storage_path`, `image_checksum` (SHA-256), and make `image_url` required once upload succeeds.
- **Storage flow**:
  - Local dev: `static/product_images/<YYYY>/<MM>/<product_id>.png`.
  - Production-ready: structure path so we can swap local storage for S3 later.
- **Upload API changes**:
  - Prefer a dedicated `POST /products/{product_id}/image` (multipart) endpoint so product creation stays simple.
  - Response returns hosted URL + checksum so clients can verify.
- **Postman collection**: new step that uploads a sample image (store assets under `docs/assets/products/`).
- **Default handling**: seed every product with a shared placeholder asset (`static/placeholders/product_default.png`) so even “empty” products return a valid image; creation/update logic uses this path when uploads are missing and customers replace it when ready (keeps clients dumb).

## 2. Image Processing Recommendations
- **Validation**: enforce max dimensions (e.g. 1024×1024) and allowed formats (JPEG/PNG/WebP).
- **Resizing/compression**: generate a display-friendly size (e.g. 800px max) and optionally store a small thumbnail for list views.
- **Checksum pipeline**: compute SHA-256 after image processing; persist alongside metadata.

## 3. QR Code Checksum Backfill
- **Schema update**: add `qr_code_checksum` (SHA-256) to `qr_code`.
- **Generation flow**: after creating the QR image, compute and save the checksum (same algorithm as product images).
- **Deletion flow**: ensure checksum cleanup when QR code is archived/deleted (keeps schema consistent).
- **Verification**: expose checksum in API responses for audit/S3 integrity checks later.

## 4. Security & Transport
- **Dev**: remain on HTTP but keep endpoints behind auth.
- **Prod**: enforce HTTPS (reverse proxy / load balancer); for future S3 uploads consider pre-signed HTTPS URLs.

## 5. Open Follow-ups
- Decide whether to store resized images only, or both original + resized.
- Confirm retention/archive rules for image blobs on product archival.
- Ensure local teardown includes deleting generated QR/product image assets (e.g. `static/qr_codes/`, future `static/product_images/`) alongside DB resets.

## Next Steps Checklist
- [ ] Apply schema updates (`product_info`, `qr_code`) with storage path & checksum columns.
- [ ] Implement product image upload service (storage, resize, checksum, placeholder defaults).
- [ ] Ensure product creation/update pipeline injects placeholder paths/checksum when no image payload is supplied.
- [ ] Extend QR code generation to persist checksum.
- [ ] Update Postman collections to cover image uploads and checksum assertions.


