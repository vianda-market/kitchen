# Supplier Invoice Storage — Infrastructure Requirements

**Audience**: infra-kitchen-gcp agent (Pulumi)
**Last Updated**: 2026-03
**Status**: Required for MVP

---

## Overview

Supplier invoice documents (PDFs, XMLs) are stored in the existing `GCS_SUPPLIER_BUCKET` alongside product images. This document defines the storage schema and lifecycle policy requirements for the infra-kitchen-gcp Pulumi stack.

---

## GCS Bucket Storage Schema

No new buckets are needed. The existing `GCS_SUPPLIER_BUCKET` is extended with a new `invoices/` prefix:

```
GCS_SUPPLIER_BUCKET/
├── products/                          # existing — product images
│   └── {institution_id}/
│       └── {product_id}/
│           ├── image
│           └── thumbnail
├── invoices/                          # supplier invoice documents
│   └── {country_code}/               # AR, PE, US
│       └── {institution_entity_id}/
│           └── {supplier_invoice_id}/
│               └── document           # PDF or XML
└── w9/                                # US supplier W-9 documents
    └── {institution_entity_id}/
        └── {w9_id}/
            └── document               # signed W-9 PDF
```

### Why country_code in the path

Each country has different legal document retention requirements:
- **AR (Argentina)**: AFIP requires 10-year retention
- **PE (Peru)**: SUNAT requires 5-year retention
- **US (United States)**: IRS requires 7-year retention

The `country_code` prefix enables GCS lifecycle policies scoped per country without affecting existing product image storage or other countries' invoice storage.

---

## GCS Lifecycle Policies Required

Configure object lifecycle rules on the `GCS_SUPPLIER_BUCKET` with prefix conditions:

| Prefix | Retention | Action |
|--------|-----------|--------|
| `invoices/AR/` | 10 years (3650 days) | Delete after retention period |
| `invoices/PE/` | 5 years (1825 days) | Delete after retention period |
| `invoices/US/` | 7 years (2555 days) | Delete after retention period |
| `products/` | No lifecycle policy | Existing behavior unchanged |

**Implementation note**: GCS lifecycle rules use prefix matching. The `products/` prefix has no lifecycle rule, so existing product images are unaffected.

---

## Environment Variables

No new environment variables are needed. The application uses existing settings:

| Variable | Purpose | Already provisioned |
|----------|---------|-------------------|
| `GCS_SUPPLIER_BUCKET` | Bucket name for supplier assets | Yes |
| `GCS_SIGNED_URL_EXPIRATION_SECONDS` | Signed URL TTL (default 3600 = 1h) | Yes |
| `GCS_SIGNING_SA_EMAIL` | Service account for signing URLs | Yes |

---

## Upload Constraints (Application Layer)

These are enforced by the application, not infrastructure:

- **Max file size**: 10 MB (`MAX_INVOICE_DOCUMENT_BYTES` setting)
- **Allowed content types**: `application/pdf`, `text/xml`, `application/xml`
- **Integrity**: MD5 hash verification on upload (GCS server-side check)

---

## Access Control

Same IAM permissions as existing product image uploads:
- Cloud Run service account needs `storage.objects.create` and `storage.objects.get` on `GCS_SUPPLIER_BUCKET`
- Signing service account (`GCS_SIGNING_SA_EMAIL`) needs `iam.serviceAccounts.signBlob` for generating signed URLs

No additional IAM changes required.

---

## Checklist for Pulumi

- [ ] Add lifecycle policy for `invoices/AR/` prefix — 3650 days retention
- [ ] Add lifecycle policy for `invoices/PE/` prefix — 1825 days retention
- [ ] Add lifecycle policy for `invoices/US/` prefix — 2555 days retention
- [ ] Add lifecycle policy for `w9/` prefix — 2555 days retention (7 years, same as US invoices)
- [ ] Verify existing `GCS_SUPPLIER_BUCKET` IAM permissions cover `invoices/` and `w9/` prefixes (they should, since permissions are bucket-level)
