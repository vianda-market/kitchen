# Product API – B2B Client Guide

**Last Updated**: 2026-05  
**Audience**: vianda-platform (Suppliers, Internal employees) – product management

This document describes the Product API for B2B: CRUD and enriched endpoints. Image upload is handled by the separate two-step pipeline documented in [API_CLIENT_UPLOADS.md](./API_CLIENT_UPLOADS.md).

---

## Overview

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/products/` | List products (institution-scoped) |
| `GET /api/v1/products/{product_id}` | Get single product |
| `POST /api/v1/products/` | Create product |
| `PUT /api/v1/products/{product_id}` | Update product |
| `GET /api/v1/products/enriched/` | List products with institution_name |
| `GET /api/v1/products/enriched/{product_id}` | Get single product with institution_name |

Image upload and status polling: `POST/GET/DELETE /api/v1/uploads` — see [API_CLIENT_UPLOADS.md](./API_CLIENT_UPLOADS.md).

---

## Image Upload

Product images are managed through an async two-step pipeline — not inline via multipart on the product endpoints.

**Flow:**

1. Call `POST /api/v1/uploads` with `{ product_id }` — kitchen returns a signed GCS PUT URL and an `image_asset_id`.
2. PUT the image file directly to GCS using the signed URL (no kitchen involvement).
3. Poll `GET /api/v1/uploads/{image_asset_id}` until `pipeline_status` is `ready`.
4. When ready, `signed_urls` contains `{ hero, card, thumbnail }` keys with time-limited GCS read URLs.

Full reference including endpoint contracts, status state machine, polling guidance, error codes, and moderation behavior: [API_CLIENT_UPLOADS.md](./API_CLIENT_UPLOADS.md).

### Migrating from the legacy upload

The former `POST /api/v1/products/{product_id}/image` multipart endpoint has been removed. The `image_url`, `image_thumbnail_url`, `image_storage_path`, `image_thumbnail_storage_path`, and `image_checksum` fields no longer exist on any product response — they were dropped as part of migration 0015. Image state now lives entirely in the `ops.image_asset` table and is accessed via `GET /api/v1/uploads/{image_asset_id}`. Update any client code that reads inline image fields from product responses or calls the old upload endpoint.

---

## GET /api/v1/products/ and GET /api/v1/products/{product_id}

Standard CRUD responses. No image fields are returned.

**Auth:** Bearer token. Institution-scoped.

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | UUID | Product identifier |
| `institution_id` | UUID | Owning institution |
| `name` | string | Product display name |
| `ingredients` | string \| null | Free-text ingredient list |
| `dietary` | list[string] \| null | Dietary attribute slugs |
| `is_archived` | bool | Archived flag |
| `status` | string | `active`, `inactive`, etc. |
| `created_date` | datetime | Creation timestamp |
| `modified_date` | datetime | Last modification |

To check whether a product has an image or to get image URLs, call `GET /api/v1/uploads/{image_asset_id}`. The `has_image` filter on list endpoints joins `ops.image_asset` (via the filter registry) — pass `?filters=has_image:true` to narrow to products with an uploaded image.

---

## GET /api/v1/products/enriched/ and GET /api/v1/products/enriched/{product_id}

**Auth:** Bearer token. Institution-scoped.

**Response fields (B2B-specific):**

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | UUID | Product identifier |
| `institution_id` | UUID | Owning institution |
| `institution_name` | string | Institution display name |
| `name` | string | Product name |
| `ingredients` | string \| null | Ingredients |
| `dietary` | list[string] \| null | Dietary info |
| `has_image` | bool | True if an `image_asset` row exists for this product |
| `is_archived` | bool | Archived flag |
| `status` | string | Active, Inactive, etc. |
| `created_date` | datetime | Creation timestamp |
| `modified_date` | datetime | Last modification |

`has_image` is derived from a JOIN to `ops.image_asset`. To get image URLs, call `GET /api/v1/uploads/{image_asset_id}` — the `image_asset_id` for a product can be retrieved by filtering `GET /api/v1/uploads` (future endpoint) or stored client-side after the upload flow.

---

## PUT /api/v1/products/{product_id}

**Auth:** Bearer token. Institution-scoped.

**Editable fields:** `name`, `ingredients`, `dietary`, `institution_id` (Internal employees only). Image is managed via `POST /api/v1/uploads`, not PUT.

---

## POST /api/v1/products/

**Auth:** Bearer token. Institution-scoped.

**Request body:** `institution_id`, `name`, optional `ingredients`, `dietary`. Image upload is a separate step via `POST /api/v1/uploads`.

---

## Related Documentation

- [API_CLIENT_UPLOADS.md](./API_CLIENT_UPLOADS.md) — Full image upload pipeline reference (endpoints, state machine, polling, moderation)
- [PLATE_API_CLIENT](../shared_client/PLATE_API_CLIENT.md) — Plates use products; enriched plates include `product_image_url` derived from the image pipeline
