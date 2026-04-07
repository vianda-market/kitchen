# Supplier Invoice Registration — B2B Integration Guide

**Audience**: vianda-platform (B2B React) frontend agent
**Last Updated**: 2026-03
**Status**: MVP (Argentina market)

---

## Domain Context

A **supplier invoice** (`billing.supplier_invoice`) is a tax-compliant document (e.g., AFIP Factura Electronica for Argentina) that a supplier provides after receiving a payout. Invoices are linked to **institution bills** (`billing.institution_bill_info`) via `billing.bill_invoice_match`.

The existing payout flow is untouched — daily payouts continue via Stripe Connect. This feature adds invoice tracking and bill-to-invoice matching for compliance.

---

## Who Can Register Invoices

| Role | Scope | Status on create |
|------|-------|------------------|
| **Supplier Admin** | Own entity only | `Pending Review` |
| **Supplier Manager** | Own entity only | `Pending Review` |
| **Supplier Operator** | Own entity only | `Pending Review` |
| **Internal Operator / Clerk** | Any entity | `Approved` (auto-approved) |

All Supplier roles (Admin, Manager, Operator) can register, list, and match invoices — scoped to their own institution. The review endpoint (`PATCH /review`) is Internal-only.

---

## Invoice Registration Flow

### Step 1 — Fetch bills for the entity

```
GET /api/v1/institution-bills/?institution_id={institution_id}
```

Display bills as selectable checkboxes. The user picks which bills this invoice covers.

### Step 2 — Fill invoice form

**Common fields (all markets):**
- `amount` — invoice total
- `currency_code` — e.g. ARS, PEN, USD
- `tax_amount` — IVA/IGV amount
- `tax_rate` — e.g. 21.00 for AR, 18.00 for PE
- `issued_date` — date the invoice was issued
- `external_invoice_number` — supplier's document number

**Country-specific fields** — sent as `country_details_json` (a single JSON string field):

**Argentina (country_code='AR'):**
```json
{"cae_code": "12345678901234", "cae_expiry_date": "2026-04-30", "afip_point_of_sale": "0001", "supplier_cuit": "20-12345678-9", "recipient_cuit": "30-98765432-1", "afip_document_type": "A"}
```
- `cae_code` — 14 digits (required)
- `cae_expiry_date` — date (required)
- `afip_point_of_sale` — punto de venta (required)
- `supplier_cuit` — format XX-XXXXXXXX-X (required)
- `recipient_cuit` — vianda's CUIT (optional)
- `afip_document_type` — one of: A, B, C (optional)

**Peru (country_code='PE'):**
```json
{"sunat_serie": "F001", "sunat_correlativo": "12345678", "supplier_ruc": "20123456789", "recipient_ruc": "20987654321", "cdr_status": "accepted"}
```
- `sunat_serie` — F + 3 digits, e.g. F001 (required)
- `sunat_correlativo` — 1-8 digit number (required)
- `supplier_ruc` — 11 digits (required)
- `recipient_ruc` — 11 digits (optional)
- `cdr_status` — one of: accepted, rejected, pending (optional)

**USA (country_code='US'):**
```json
{"tax_year": 2026}
```
- `tax_year` — year for 1099-NEC filing (required)

### Step 3 — Select bill matches

For each selected bill, the user enters the `matched_amount` (portion of the bill covered by this invoice). Common case: one invoice covers one bill for the full amount.

### Step 4 — Attach document

Upload the invoice PDF (AR/PE) or XML + PDF (PE).
- Allowed types: `application/pdf`, `text/xml`, `application/xml`
- Max size: 10 MB

### Step 5 — Submit

```
POST /api/v1/supplier-invoices
Content-Type: multipart/form-data
```

**Form fields:**
- `institution_entity_id` (UUID, required)
- `country_code` (string, required) — "AR", "PE", or "US"
- `invoice_type` (string, required) — "Factura Electronica", "CPE", or "1099 NEC"
- `issued_date` (date, required)
- `amount` (decimal, required)
- `currency_code` (string, required)
- `country_details_json` (string, required) — JSON object with country-specific fields (see Step 2 above)
- `bill_matches_json` (string, optional) — JSON array: `[{"institution_bill_id": "uuid", "matched_amount": 1234.56}]`
- `document` (file, optional) — the invoice PDF/XML

**Response:** `SupplierInvoiceResponseSchema` with `document_url` (signed URL, 1h expiry).

---

## Invoice List View

### Enriched endpoint (recommended for list views)

```
GET /api/v1/supplier-invoices/enriched?institution_entity_id={entity_id}&status={status}
```

Returns all invoice fields plus:
- `institution_entity_name` — from `ops.institution_entity_info`
- `institution_name` — from `core.institution_info`
- `created_by_name` — full name of the user who registered the invoice

Use this endpoint for table/list views to avoid N+1 lookups.

### Basic list endpoint

```
GET /api/v1/supplier-invoices?institution_entity_id={entity_id}&status={status}
```

Query params (all optional, both endpoints):
- `institution_entity_id` — filter by entity
- `status` — filter by: `Pending Review`, `Approved`, `Rejected`

Display status badges:
- `Pending Review` — yellow/warning
- `Approved` — green/success
- `Rejected` — red/error (show `rejection_reason`)

---

## Invoice Detail

```
GET /api/v1/supplier-invoices/{invoice_id}
```

Returns full invoice data with `document_url` (signed URL).

---

## Review Flow (Internal Only)

```
PATCH /api/v1/supplier-invoices/{invoice_id}/review
Content-Type: application/json

{
  "status": "Approved",          // or "Rejected"
  "rejection_reason": "..."      // required when Rejected
}
```

Auth: `get_employee_user` (Internal role only).

---

## Add Bill Matches to Existing Invoice

```
POST /api/v1/supplier-invoices/{invoice_id}/match
Content-Type: application/json

[
  {"institution_bill_id": "uuid", "matched_amount": 1234.56}
]
```

---

## Document Display

`document_url` is a time-limited signed URL (1h). Handle 403 by re-fetching from the API — same pattern as product images.

---

## Validation Rules (enforced at API level)

**AR (`country_code='AR'`):**
- `cae_code` must be exactly 14 digits
- `supplier_cuit` must match `XX-XXXXXXXX-X` format
- `cae_code`, `cae_expiry_date`, `afip_point_of_sale`, `supplier_cuit` are all required
- `afip_document_type` must be one of: A, B, C

**PE (`country_code='PE'`):**
- `sunat_serie` must match `F` + 3 digits (e.g. F001)
- `sunat_correlativo` must be 1-8 digits
- `supplier_ruc` must be exactly 11 digits
- `recipient_ruc` must be exactly 11 digits (if provided)
- `cdr_status` must be one of: accepted, rejected, pending
- `sunat_serie`, `sunat_correlativo`, `supplier_ruc` are all required

**US (`country_code='US'`):**
- `tax_year` is required

**All countries:** `country_details_json` is required — API returns 422 if missing or if the wrong country's details are provided.

---

## Scoping

- **Supplier users** only see invoices for their own institution's entities
- **Internal users** see all invoices across all entities
- Backend enforces scoping — no client-side filtering needed

---

## W-9 Collection (US Entities Only)

US supplier entities must submit a W-9 before payouts can be processed. One W-9 per entity.

### Submit W-9

```
POST /api/v1/supplier-w9
Content-Type: multipart/form-data
```

**Form fields:**
- `institution_entity_id` (UUID, required)
- `legal_name` (string, required) — legal business name from W-9
- `business_name` (string, optional) — DBA / trade name
- `tax_classification` (string, required) — one of: `individual`, `c_corp`, `s_corp`, `partnership`, `llc`, `other`
- `ein_last_four` (string, required) — last 4 digits of EIN or SSN (exactly 4 digits)
- `address_line` (string, required) — mailing address from W-9
- `document` (file, optional) — signed W-9 PDF

If a W-9 already exists for this entity, it is updated (upsert behavior).

### Get W-9

```
GET /api/v1/supplier-w9/{entity_id}
```

Returns 404 if no W-9 is on file. Response includes `document_url` (signed URL, 1h expiry).

### US Invoice Validation

When creating a supplier invoice with `country_code='US'`, `tax_year` is required. The API returns 422 if omitted.

---

## Payout Gate Configuration (Future)

The payout aggregator endpoint now includes invoice compliance fields:

```
GET /api/v1/institution-entities/{entity_id}/payout-aggregator
```

Response includes:
- `require_invoice` (boolean) — whether invoices are required for this market
- `max_unmatched_bill_days` (integer) — max days of bills without matched invoices

When `require_invoice=true`, the UI should show a compliance status indicator on the supplier billing dashboard.
