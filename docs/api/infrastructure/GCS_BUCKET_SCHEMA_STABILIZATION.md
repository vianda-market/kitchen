# GCS Bucket Schema Stabilization — Feedback for Infrastructure

**Source**: Kitchen backend agent
**Audience**: infra-kitchen-gcp agent (Pulumi)
**Last Updated**: 2026-04-01
**Priority**: High — stabilize before adding new object types

**Important**: Interview the user before starting work on each section. This document contains analysis, recommendations, and open questions. The user should confirm the path forward at each decision point before you implement.

---

## Context

The Kitchen backend currently writes objects to 2 of the 4 private GCS buckets (internal, supplier). Two more (customer, employer) are provisioned but empty. Object path conventions are defined only in backend code (`app/utils/gcs.py`) with no single canonical reference. This creates drift risk: new prefixes can appear in backend code without corresponding lifecycle rules in infra, and infra lifecycle rules can silently delete objects the backend expects to persist.

This document proposes a stabilization strategy. It covers:
1. Canonical blob schema (all buckets, all prefixes)
2. Lifecycle policy gaps and fixes
3. Architectural questions requiring user input
4. Cross-reference updates

---

## 1. Canonical Blob Schema — All Buckets

This is the complete inventory of every blob path the backend writes or plans to write. The infra agent should use this to create a `GCS_BLOB_SCHEMA.md` document in the infra repo and align lifecycle rules accordingly.

### `vianda-{stack}-internal`

| Prefix | Full path pattern | Content type | Lifecycle expectation | Status |
|--------|-------------------|--------------|----------------------|--------|
| `qrcodes/` | `qrcodes/{restaurant_id}/{qr_code_id}.png` | `image/png` | **Permanent** — printed on physical materials | Active |
| `placeholder/` | `placeholder/product_default.png` | `image/png` | **Permanent** — seeded by Pulumi on stack creation | Active (seeded) |

### `vianda-{stack}-supplier`

| Prefix | Full path pattern | Content type | Lifecycle expectation | Status |
|--------|-------------------|--------------|----------------------|--------|
| `products/` | `products/{institution_id}/{product_id}/image` | varies (image/*) | **Permanent** — replaced on update, deleted on product delete | Active |
| `products/` | `products/{institution_id}/{product_id}/thumbnail` | varies (image/*) | **Permanent** — same lifecycle as full image | Active |
| `invoices/AR/` | `invoices/AR/{entity_id}/{invoice_id}/document` | `application/pdf`, `text/xml`, `application/xml` | **10 years (3650 days)** — AFIP | Active |
| `invoices/PE/` | `invoices/PE/{entity_id}/{invoice_id}/document` | `application/pdf`, `text/xml`, `application/xml` | **5 years (1825 days)** — SUNAT | Active |
| `invoices/US/` | `invoices/US/{entity_id}/{invoice_id}/document` | `application/pdf`, `text/xml`, `application/xml` | **7 years (2555 days)** — IRS | Active |
| `w9/` | `w9/{entity_id}/{w9_id}/document` | `application/pdf` | **7 years (2555 days)** — IRS | Active |

### `vianda-{stack}-customer`

| Prefix | Full path pattern | Content type | Lifecycle expectation | Status |
|--------|-------------------|--------------|----------------------|--------|
| `profile/` | `profile/{user_id}/picture` | varies (image/*) | **Permanent** — replaced on update | **Stub** (code exists, no route yet) |

### `vianda-{stack}-employer`

| Prefix | Full path pattern | Content type | Lifecycle expectation | Status |
|--------|-------------------|--------------|----------------------|--------|
| `logos/` | `logos/{employer_id}/logo` | varies (image/*) | **Permanent** — replaced on update | **Stub** (code exists, no route yet) |

---

## 2. Lifecycle Policy Issues

### CRITICAL: Internal bucket lifecycle may delete QR codes

**Current infra state** (from `storage.py`): The internal bucket has auto-delete lifecycle rules:
- Dev/staging: 90-day retention
- Prod: 365-day retention

**Problem**: QR codes are printed on physical labels and menus. They must persist indefinitely. A QR code uploaded to the internal bucket in prod will be auto-deleted after 365 days, breaking printed materials.

**Options for the infra agent to present to the user:**

- **Option A**: Remove the blanket lifecycle rule from the internal bucket entirely. Both current prefixes (`qrcodes/`, `placeholder/`) need permanent storage. If a "temp" prefix is added later, add a prefix-scoped rule then.
- **Option B**: Change the lifecycle rule to target only a specific `temp/` or `cache/` prefix (doesn't exist yet), leaving `qrcodes/` and `placeholder/` untouched.
- **Option C**: Move QR codes to the supplier bucket under a `qrcodes/` prefix. This keeps the internal bucket as a short-lived cache but mixes QR codes with supplier data.

**Recommendation**: Option A is simplest and safest. The internal bucket has only 2 prefixes today and both need permanence.

### Products prefix has no lifecycle rule (by design, but undocumented)

The `products/` prefix in the supplier bucket intentionally has no lifecycle rule — product images are replaced or deleted by the application. This is correct but should be explicitly documented in infra so a future contributor doesn't add a blanket supplier bucket rule.

---

## 3. Architectural Questions for User

The infra agent should ask the user about these before implementing:

### Q1: Should product images stay in the supplier bucket?

**Current**: Product images (`products/`) share the supplier bucket with compliance documents (`invoices/`, `w9/`).

**Argument to move**: Product images are high-churn operational assets (uploaded, replaced, deleted frequently). Compliance documents are write-once, legally-retained. Mixing them means:
- A misconfigured lifecycle rule on the supplier bucket could delete product images
- Product image operations (bulk delete, CDN, public serving) affect the compliance bucket

**Argument to keep**: Prefix-based lifecycle rules already isolate them. Moving creates a migration task for existing objects. The current scheme works.

**If moving**: The natural destination is the internal bucket (operational assets, internal to the platform). The path would stay `products/{institution_id}/{product_id}/{image|thumbnail}`.

**Impact if moved**: Backend changes in `app/utils/gcs.py` (change bucket from `GCS_SUPPLIER_BUCKET` to `GCS_INTERNAL_BUCKET` for product functions), plus a one-time object migration script for existing objects in deployed environments.

### Q2: Should empty buckets (customer, employer) be deferred?

Customer and employer buckets are provisioned but have zero objects. Options:
- **Keep provisioned** — ready when needed, zero cost, avoids a future infra deploy to create them
- **Remove until needed** — fewer resources to manage, cleaner `pulumi stack output`

**Recommendation**: Keep them. They're free and already wired into Cloud Run env vars.

### Q3: CORS on private buckets

No CORS configuration exists on private buckets. This is fine for the current signed-URL pattern (backend generates URL, client fetches directly from GCS). But if the platform ever needs browser-based direct uploads (e.g., resumable upload for large invoice PDFs), CORS must be added.

**Question for user**: Is browser-based direct upload planned? If so, which buckets need CORS?

---

## 4. Deliverables for the Infra Agent

After confirming the path forward with the user, the infra agent should:

### 4.1 Create `docs/infrastructure/GCS_BLOB_SCHEMA.md` in infra-kitchen-gcp

A canonical document listing every prefix, its path pattern, lifecycle expectation, and status (active/stub). Use the table in Section 1 above as the starting content. This document should be:
- Indexed from `docs/infrastructure/AGENT_INDEX.md`
- Cross-referenced from `CLAUDE_ARCHITECTURE.MD` in the Storage section
- Referenced by the backend's `SUPPLIER_INVOICE_STORAGE_INFRASTRUCTURE.md` (as the authoritative lifecycle source)

### 4.2 Fix internal bucket lifecycle in `src/components/storage.py`

Based on user's answer to the lifecycle question (Section 2), either:
- Remove the blanket lifecycle rule, or
- Convert it to a prefix-scoped rule that excludes `qrcodes/` and `placeholder/`

### 4.3 Add explicit "no lifecycle" documentation for `products/` prefix

In `storage.py` (as a code comment) and in `GCS_BLOB_SCHEMA.md`, document that the `products/` prefix intentionally has no lifecycle rule.

### 4.4 Update `CLAUDE_ARCHITECTURE.MD` Storage section

Add a reference to the new blob schema doc. Current architecture doc mentions "4 private GCS buckets: internal, supplier (with invoice lifecycle rules), customer, employer" — expand this to reference the blob schema for prefix details.

### 4.5 Update `docs/infrastructure/AGENT_INDEX.md`

Add the new blob schema doc to the index so all repo agents can find it.

### 4.6 (Conditional) Move product images to internal bucket

Only if user confirms Q1. This requires:
- Infra: Remove `products/` prefix documentation from supplier bucket, add to internal bucket
- Infra: No lifecycle rule changes needed (products have none)
- Backend team will handle code changes and migration separately

---

## 5. Backend Code Reference

These are the exact functions in `app/utils/gcs.py` that write to each bucket, so the infra agent can trace every object path:

### Internal bucket writers
- `upload_qr_code()` → `qrcodes/{restaurant_id}/{qr_code_id}.png`
- `download_internal_bucket_blob_bytes()` → reads from internal bucket
- `get_placeholder_signed_url()` → `placeholder/product_default.png` (read-only, seeded by Pulumi)
- `resolve_qr_code_image_url()` → generates signed URLs for QR codes

### Supplier bucket writers
- `upload_product_image()` → `products/{institution_id}/{product_id}/{image,thumbnail}`
- `delete_product_image()` → deletes both image and thumbnail
- `upload_supplier_invoice_document()` → `invoices/{country_code}/{entity_id}/{invoice_id}/document`
- `upload_supplier_w9_document()` → `w9/{entity_id}/{w9_id}/document`
- `resolve_product_image_urls()` → generates signed URLs for product images

### Customer bucket writers (stubs)
- `upload_profile_picture()` → `profile/{user_id}/picture`
- `get_profile_picture_signed_url()` → generates signed URL

### Employer bucket writers (stubs)
- `upload_employer_logo()` → `logos/{employer_id}/logo`
- `get_employer_logo_signed_url()` → generates signed URL

---

## 6. Signed URL Expiration Reference

For the infra agent's awareness when setting env vars or reviewing security:

| Use case | Env var | Current value | Notes |
|----------|---------|---------------|-------|
| Product images, invoices, W-9, profile pics, logos | `GCS_SIGNED_URL_EXPIRATION_SECONDS` | `3600` (1 hour) | Standard for on-demand viewing |
| QR codes | `GCS_QR_SIGNED_URL_EXPIRATION_SECONDS` | `86400` (24 hours) | Longer TTL because QR code URLs are embedded in print-ready PDFs |

---

## 7. Validation Convention (Process Proposal)

To prevent future drift, propose that any new prefix added to `app/utils/gcs.py` in the backend must have a corresponding entry in `GCS_BLOB_SCHEMA.md` in the infra repo. The backend agent should update this feedback doc (or create a follow-up) whenever a new prefix is introduced, and the infra agent should update the schema doc and lifecycle rules accordingly.

This is a process convention, not an automated check. The infra agent should note this in the blob schema doc header so future agents know to check for backend feedback before modifying lifecycle rules.

---

**End of feedback. The infra agent should interview the user on Q1, Q2, Q3 (Section 3) and the lifecycle fix option (Section 2) before starting implementation.**
