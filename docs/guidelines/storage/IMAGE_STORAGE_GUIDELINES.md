# Image Storage Guidelines

Images (product photos, QR codes, placeholders) use local storage for development and GCS (Google Cloud Storage) for Cloud Run deployments.

## Storage Modes

| Mode  | When                         | Product Images                 | QR Codes                     | Placeholder                    |
|-------|------------------------------|--------------------------------|------------------------------|--------------------------------|
| Local | `GCS_SUPPLIER_BUCKET` empty  | `static/product_images/`       | `static/qr_codes/`           | `static/placeholders/product_default.png` |
| GCS   | `GCS_*_BUCKET` set (Cloud Run)| `products/{institution_id}/{product_id}/` | `qrcodes/{restaurant_id}/{qr_code_id}.png` | `placeholder/product_default.png` (internal bucket) |

## Development (local)

| Path | Purpose |
|------|---------|
| `static/product_images/<YYYY>/<MM>/` | Product images (full-size + thumbnail) |
| `static/qr_codes/<YYYY>/<MM>/` | QR code images |
| `static/placeholders/` | Default product placeholder (`product_default.png`) |

**Config (optional):**

- `PRODUCT_IMAGE_LOCAL_PATH=static/product_images`
- `PRODUCT_IMAGE_BASE_URL=http://localhost:8000/static/product_images`
- `QR_LOCAL_STORAGE_PATH=static/qr_codes`
- `QR_BASE_URL=http://localhost:8000/static/qr_codes`

**Teardown:** `app/db/build_kitchen_db.sh` clears `static/product_images` and `static/qr_codes` before schema rebuild.

## Production (GCS)

- **Product images:** `GCS_SUPPLIER_BUCKET` set → upload to `products/{institution_id}/{product_id}/image` and `.../thumbnail`.
- **QR codes:** `GCS_INTERNAL_BUCKET` set → upload to `qrcodes/{restaurant_id}/{qr_code_id}.png`.
- **Placeholder:** Uploaded to internal bucket at `placeholder/product_default.png` during Pulumi apply (infra).
- **Serving:** Signed URLs generated at API response time; URLs expire (1h images, 24h QR codes).

## Signed URL Expiry — Client Handling

**When displaying product images or QR codes from GCS signed URLs, handle 403 responses by re-fetching the image URL from the API and retrying. Do not cache signed URLs for longer than their expiration period.**

- **Product images:** `GCS_SIGNED_URL_EXPIRATION_SECONDS` (default 3600 = 1 hour)
- **QR codes:** `GCS_QR_SIGNED_URL_EXPIRATION_SECONDS` (default 86400 = 24 hours)

**Implementation guidance:**

- On `img` load error (403): call the API to get a fresh product/QR response (which includes a new signed URL) and update the image source.
- Do not store signed URLs in long-lived caches (localStorage, long TTL) — they will expire.
