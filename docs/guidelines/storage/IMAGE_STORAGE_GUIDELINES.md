# Image Storage Guidelines

Images (product photos, QR codes, placeholders) live under the `static/` folder. The app mounts `static/` at `/static` for serving.

## Development (local)

| Path | Purpose |
|------|---------|
| `static/product_images/<YYYY>/<MM>/` | Product images (full-size + thumbnail) |
| `static/qr_codes/<YYYY>/<MM>/` | QR code images |
| `static/placeholders/` | Default product placeholder (`product_default.png`) |

**Config (optional):**

- `PRODUCT_IMAGE_STORAGE_MODE=local` (default)
- `PRODUCT_IMAGE_LOCAL_PATH=static/product_images`
- `QR_STORAGE_MODE=local`
- `QR_BASE_URL=http://localhost:8000/static/qr_codes`

**Teardown:** `app/db/build_kitchen_db_dev.sh` clears `static/product_images` and `static/qr_codes` before schema rebuild.

## Production (S3)

For production, move images to S3:

- **Product images:** Use `PRODUCT_IMAGE_STORAGE_MODE=s3` (or similar) when implemented. Path layout should stay `YYYY/MM/<product_id>.png` for easy migration.
- **QR codes:** Use `QR_STORAGE_MODE=s3`; same layout under the bucket.
- **Serving:** Serve via pre-signed URLs or CDN in front of the bucket.

The `ProductImageService` and `QRCodeGenerationService` are designed so the storage backend can be swapped (local vs S3) without changing callers.
