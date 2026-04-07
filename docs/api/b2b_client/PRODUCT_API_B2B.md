# Product API – B2B Client Guide

**Last Updated**: 2026-03  
**Audience**: kitchen-web (Suppliers, Employees) – product management and image upload

This document describes the Product API for B2B: CRUD, enriched endpoints, and the image upload process. Suppliers use products for menu management; Employees use them across institutions they manage.

---

## Overview

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/products/` | List products (institution-scoped) |
| `GET /api/v1/products/{product_id}` | Get single product |
| `POST /api/v1/products/` | Create product |
| `PUT /api/v1/products/{product_id}` | Update product |
| `POST /api/v1/products/{product_id}/image` | Upload or replace product image |
| `GET /api/v1/products/enriched/` | List products with institution_name |
| `GET /api/v1/products/enriched/{product_id}` | Get single product with institution_name (includes both image sizes) |

---

## Image Upload: One Upload → Two Stored Images

When a supplier uploads a product image, the backend generates **two versions** from the single uploaded file:

| Version | Purpose | Typical size |
|---------|---------|--------------|
| **Full-size** | B2B product detail, Explore Plate Modal (B2C), print/export | Max 1024px (configurable: `PRODUCT_IMAGE_MAX_DIMENSION`) |
| **Thumbnail** | B2C explore cards, list views | 300×300 (configurable: `PRODUCT_IMAGE_THUMBNAIL_DIMENSION`) |

**Client impact:**
- Upload once via `POST /products/{id}/image`
- Backend stores both files and persists both URLs in `product_info`
- B2B enriched responses return **both** `image_url` (full-size) and `image_thumbnail_url` (thumbnail) so suppliers can preview their product in both pixel sizes
- B2C by-city uses thumbnail only (smaller payload); Explore Plate Modal uses full-size

---

## POST /api/v1/products/{product_id}/image

**Auth:** Bearer token. Institution-scoped (Supplier: own institution; Employee: managed institutions).

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | Image file (PNG, JPEG, WEBP) |
| `client_checksum` | string | Yes | SHA-256 hex digest of the **original** file bytes (64 chars) |

**Flow:**
1. Client computes SHA-256 of the file **before** sending.
2. Client sends `file` + `client_checksum`.
3. Backend validates checksum; rejects with 400 if mismatch.
4. Backend resizes to full-size (max 1024px) and thumbnail (300×300).
5. Backend stores both files and updates `product_info`:
   - `image_url`, `image_storage_path` (full-size)
   - `image_thumbnail_url`, `image_thumbnail_storage_path` (thumbnail)
6. Response: updated product (standard `ProductResponseSchema`).

**Example (curl):**
```bash
curl -X POST "https://api.example.com/api/v1/products/{product_id}/image" \
  -H "Authorization: Bearer <token>" \
  -F "file=@product.png" \
  -F "client_checksum=<sha256_hex_of_file>"
```

---

## GET /api/v1/products/ and GET /api/v1/products/{product_id}

Standard CRUD responses. Include `image_url`, `image_storage_path`, `image_thumbnail_url`, `image_thumbnail_storage_path`, `image_checksum`.

**GCS signed URLs:** When using GCS storage, `image_url` and `image_thumbnail_url` are time-limited signed URLs (1h default). Handle 403 on image load by re-fetching the product from the API to get a fresh signed URL. See [IMAGE_STORAGE_GUIDELINES.md](../../guidelines/storage/IMAGE_STORAGE_GUIDELINES.md).

---

## GET /api/v1/products/enriched/ and GET /api/v1/products/enriched/{product_id}

**Auth:** Bearer token. Institution-scoped.

**Response fields (B2B-specific):**

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | UUID | Product identifier |
| `institution_id` | UUID | Institution owning the product |
| `institution_name` | string | Institution display name |
| `name` | string | Product name |
| `ingredients` | string \| null | Ingredients |
| `dietary` | string \| null | Dietary info |
| **`image_url`** | string \| null | **Full-size** image URL (e.g. 1024px) |
| `image_storage_path` | string | Full-size storage path |
| **`image_thumbnail_url`** | string \| null | **Thumbnail** image URL (e.g. 300×300) |
| `image_thumbnail_storage_path` | string | Thumbnail storage path |
| `image_checksum` | string | SHA-256 of original upload |
| `has_image` | bool | True if custom image; false if placeholder |
| `is_archived` | bool | Archived flag |
| `status` | string | Active, Inactive, etc. |
| `created_date` | datetime | Creation timestamp |
| `modified_date` | datetime | Last modification |

**B2B use:** Display product in list (thumbnail) and detail view (full-size). Both URLs are always present so suppliers can preview their images at both resolutions.

---

## PUT /api/v1/products/{product_id}

**Auth:** Bearer token. Institution-scoped.

**Editable fields:** `name`, `ingredients`, `dietary`, `institution_id` (Employees only). Image is updated via `POST /{product_id}/image`, not PUT.

---

## POST /api/v1/products/

**Auth:** Bearer token. Institution-scoped.

**Request body:** `institution_id`, `name`, optional `ingredients`, `dietary`. Image fields use placeholder until `POST /{product_id}/image` is called.

---

## Related Documentation

- [PLATE_API_CLIENT](../shared_client/PLATE_API_CLIENT.md) — Plates use products; enriched plates include `product_image_url` (full-size from product)
- [feedback_coworker_pickup_activity_explore](../b2c_client/feedback_coworker_pickup_activity_explore.md) — B2C thumbnail vs full-size usage (by-city uses thumbnail; modal uses full-size)
