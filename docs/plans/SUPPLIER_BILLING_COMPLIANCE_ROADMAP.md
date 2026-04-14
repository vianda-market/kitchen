# Supplier Billing Compliance Roadmap

**Status**: In Progress (AR MVP done, US W-9 in progress)
**Last Updated**: 2026-03

---

## Overview

As vianda expands into Argentina, Peru, and USA, each market has distinct legal requirements for supplier invoicing. When we pay a supplier entity via Stripe Connect, the supplier must also provide a legally compliant invoice or tax document. This roadmap covers:

1. Country-specific compliance requirements
2. Normalized internal data model (`supplier_invoice` table)
3. Invoice-to-bill matching via `bill_invoice_match` junction table
4. UI path: supplier or internal operator registration via vianda-platform B2B
5. Configurable payout gate with market defaults and per-entity overrides
6. Invoice validation progression: manual → field validation → AI analysis → tax authority API
7. ERP integration as future state

---

## User Stories

These user stories drive the implementation across all phases:

1. **Existing payout flow untouched** — The daily flow (`plate_selection → restaurant_transaction → restaurant_balance → bill_info → bill_payout`) continues operating as designed. Daily outbound payments keep supplier cashflow healthy.

2. **Invoice registration with bill matching** — Either a Supplier user or an Internal Operator (Clerk) registers invoices via the B2B Vianda Platform UI. The UI provides a way to select which bills the invoice covers, creating structured `bill_invoice_match` records. This ensures no gaps between invoices and related bills.

3. **Configurable payout hold** — When a supplier has not regularized invoices beyond a configurable threshold (e.g. more than 30 days of unmatched bills), the system can hold additional payments until the situation is regularized. Configuration uses market defaults with per-entity overrides.

4. **Progressive invoice validation** — Invoices provided by suppliers are validated with increasing sophistication across phases:
   - **Phase 2 (MVP)**: Software field validation on input — required fields, CAE format (14 digits), CUIT format
   - **Phase 4**: AI image validation — verify the invoice image accurately represents the values provided in the input form; alternatively, AI analyzes the image and pre-fills the form
   - **Phase 5**: Tax authority API integration — verify invoice data against AFIP (AR), SUNAT (PE), or pull e-invoice information directly from their system

---

## 1. Country Requirements

### Argentina — AFIP Electronic Invoice (Comprobante Electrónico)

- **Authority**: AFIP (Administración Federal de Ingresos Públicos)
- **Document type**: Factura Electrónica (Tipo A for IVA-registered recipients, Tipo B otherwise) or Recibo
- **Required fields**: CAE (Código de Autorización Electrónico), CAE expiry date, CUIT supplier, CUIT recipient, IVA breakdown (21%, 10.5%, or exempt), point of sale number, document number
- **Process**: Supplier issues the invoice through AFIP's RCEL portal or a certified billing software (e.g. Colppy, Xubio, Alegra) → receives a CAE code → sends us the PDF + CAE
- **Our obligation**: Record the CAE so we can reconcile IVA credit in the Libro IVA Compras. Missing CAE = no IVA deduction.
- **Fallback threshold**: Every invoice must have a CAE — there is no below-threshold exemption for business payments.

### Peru — SUNAT Electronic Voucher (Comprobante de Pago Electrónico / CPE)

- **Authority**: SUNAT (Superintendencia Nacional de Aduanas y Administración Tributaria)
- **Document type**: Factura Electrónica (for business recipients) — format is UBL 2.1 XML
- **Validation path**: Supplier issues via an OSE (Operador de Servicios Electrónicos, e.g. Efact, Nubefact) or PSE and receives a CDR (Constancia de Recepción) XML. The CDR is the proof of SUNAT acceptance.
- **Required fields**: Serie (Fxxx) + correlativo, RUC supplier, RUC recipient, IGV (18%), hash XML, CDR status
- **Our obligation**: Record the CDR or the XML so vianda can claim IGV credit. Without a valid CDR, the invoice is legally void.
- **Fallback threshold**: All B2B invoices above S/ 0.00 must be electronic — no paper invoices.

### USA — IRS Form 1099-NEC

- **Authority**: IRS
- **Document type**: 1099-NEC (Non-Employee Compensation), filed annually by January 31 for prior tax year
- **Threshold**: Required when total annual payments to a US-based supplier exceed USD $600
- **Required information**: Supplier's EIN or SSN (collected via W-9), legal name, address
- **Our obligation**: Collect W-9 before first payment, track cumulative annual payments per supplier entity, file 1099-NEC electronically via IRS FIRE system or a third-party filer (e.g. Track1099, Tax1099)
- **No per-invoice document**: Unlike LATAM, US suppliers do not issue per-invoice tax documents to us — we issue the 1099 to them at year end
- **State-level**: Some states have additional 1099 filing requirements — verify per entity's state

---

## 2. Data Model

### `billing.supplier_invoice` table

Stores per-invoice tax/compliance records from suppliers. One row per invoice submitted by the supplier. Invoices are linked to bills (not payouts) via `billing.bill_invoice_match`.

```sql
CREATE TABLE IF NOT EXISTS billing.supplier_invoice (
    supplier_invoice_id     UUID        PRIMARY KEY DEFAULT uuidv7(),
    institution_entity_id   UUID        NOT NULL REFERENCES ops.institution_entity_info(institution_entity_id),
    country_code            VARCHAR(2)  NOT NULL,           -- 'AR', 'PE', 'US'
    invoice_type            supplier_invoice_type_enum NOT NULL,
    external_invoice_number VARCHAR(100) NULL,              -- supplier's doc number (AR/PE)
    issued_date             DATE        NOT NULL,
    amount                  NUMERIC(12,2) NOT NULL,
    currency_code           VARCHAR(10) NOT NULL,
    tax_amount              NUMERIC(12,2) NULL,             -- IVA/IGV amount
    tax_rate                NUMERIC(5,2) NULL,              -- e.g. 21.00 for AR, 18.00 for PE

    -- Argentina-specific
    cae_code                VARCHAR(50) NULL,               -- AFIP CAE (14 digits)
    cae_expiry_date         DATE        NULL,
    afip_point_of_sale      VARCHAR(10) NULL,               -- punto de venta
    supplier_cuit           VARCHAR(13) NULL,               -- supplier's CUIT
    recipient_cuit          VARCHAR(13) NULL,               -- vianda's CUIT
    afip_document_type      VARCHAR(20) NULL,               -- 'A', 'B', 'C'

    -- Peru-specific
    sunat_serie             VARCHAR(10) NULL,               -- e.g. F001
    sunat_correlativo       VARCHAR(20) NULL,
    cdr_status              VARCHAR(20) NULL,               -- 'accepted', 'rejected', 'pending'
    cdr_received_at         TIMESTAMPTZ NULL,

    -- USA-specific
    tax_year                SMALLINT    NULL,               -- for 1099-NEC

    -- Document storage
    document_storage_path   TEXT        NULL,               -- GCS blob path (signed URL resolved at API layer)
    document_format         VARCHAR(20) NULL,               -- 'pdf', 'xml', 'pdf+xml'

    -- Internal status
    status                  supplier_invoice_status_enum NOT NULL DEFAULT 'Pending Review',
    rejection_reason        TEXT        NULL,
    reviewed_by             UUID        NULL,
    reviewed_at             TIMESTAMPTZ NULL,

    -- Audit
    is_archived             BOOLEAN     NOT NULL DEFAULT FALSE,
    created_date            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by              UUID        NULL,
    modified_date           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by             UUID        NOT NULL
);
```

### `billing.bill_invoice_match` junction table

Links supplier invoices to institution bills. Suppliers select which bills each invoice covers during registration. This structured matching ensures no gaps between invoices and bills, and enables the payout gate to check coverage.

```sql
CREATE TABLE IF NOT EXISTS billing.bill_invoice_match (
    match_id                UUID        PRIMARY KEY DEFAULT uuidv7(),
    institution_bill_id     UUID        NOT NULL REFERENCES billing.institution_bill_info(institution_bill_id),
    supplier_invoice_id     UUID        NOT NULL REFERENCES billing.supplier_invoice(supplier_invoice_id),
    matched_amount          NUMERIC(12,2) NOT NULL,
    matched_by              UUID        NOT NULL,
    matched_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (institution_bill_id, supplier_invoice_id)
);
```

### Payout gate configuration

Two-tier config: market-level defaults with per-entity overrides.

**On `billing.market_payout_aggregator`:**
- `require_invoice BOOLEAN NOT NULL DEFAULT FALSE` — enable/disable invoice requirement for the market
- `max_unmatched_bill_days INTEGER NOT NULL DEFAULT 30` — max days of bills without matched invoices before payouts are held

**On `ops.institution_entity_info`:**
- `invoice_hold_override_days INTEGER NULL` — per-entity override; `NULL` = use market default

### USA: `billing.supplier_w9` table (Implemented)

Stores W-9 data for US-based entities. Collected once per entity; used for all annual 1099 filings.

```sql
CREATE TABLE IF NOT EXISTS billing.supplier_w9 (
    w9_id                   UUID        PRIMARY KEY DEFAULT uuidv7(),
    institution_entity_id   UUID        NOT NULL UNIQUE REFERENCES ops.institution_entity_info(institution_entity_id),
    legal_name              VARCHAR(255) NOT NULL,
    business_name           VARCHAR(255) NULL,
    tax_classification      VARCHAR(50) NOT NULL,  -- 'individual', 'c_corp', 's_corp', 'partnership', 'llc', 'other'
    ein_last_four           VARCHAR(4)  NOT NULL,  -- last 4 digits of EIN or SSN only
    address_line            TEXT        NOT NULL,
    document_storage_path   TEXT        NULL,      -- GCS blob path for signed W-9 PDF
    is_archived             BOOLEAN     NOT NULL DEFAULT FALSE,
    collected_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by              UUID        NULL,
    modified_date           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_by             UUID        NOT NULL
);
```

> **Security approach**: Only the last 4 digits of EIN/SSN are stored in the database (`ein_last_four`). The full EIN/SSN value is only on the signed W-9 PDF document stored in GCS. This avoids KMS encryption complexity while keeping sensitive data out of the DB.

---

## 3. Invoice Registration Flow

### Who can register invoices

Both **Supplier Admin** users (for their own entity) and **Internal Operators/Clerks** (for any entity) can register invoices via the vianda-platform B2B React application.

### Registration flow (vianda-platform B2B React)

User navigates to **Billing → Invoices**:

1. **User sees bills for the entity** via `GET /api/v1/institution-bills/?institution_id=X` (scoped)
2. **User fills invoice form**: country-specific fields (AR: CAE, CUIT, punto de venta, document type A/B/C), amount, tax breakdown, issued date
3. **User selects which bills this invoice covers** via checkboxes + matched amount per bill. This creates `bill_invoice_match` records.
4. **User attaches invoice document**: PDF (AR/PE), XML + PDF (PE preferred)
5. **Backend validates** fields (format, required fields by country) and stores document in GCS
6. **Status assignment**:
   - If registered by Internal Operator → `status='Approved'` immediately (no review needed)
   - If registered by Supplier → `status='Pending Review'` (Internal operator reviews later)
7. **On review approval**: `supplier_invoice.status` → `'Approved'`
8. **On review rejection**: `supplier_invoice.status` → `'Rejected'`; reason provided

### Country-specific validation at registration time

| Country | Auto-validate (MVP — Phase 2) | Future: AI/API validation (Phases 4-5) |
|---------|------------------------------|----------------------------------------|
| AR | CAE format (14 digits), CUIT format (XX-XXXXXXXX-X), required AR fields | AI image analysis of invoice PDF; AFIP WSFE/WSCDC API verification |
| PE | Serie format (F + 3 digits), CDR status if XML provided | AI image analysis; SUNAT CDR validation via OSE API |
| US | W-9 collected before first payment, EIN format | $600 threshold tracking; IRS FIRE batch filing |

---

## 4. API Endpoints

All endpoints below are under `/api/v1/`.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/supplier-invoices` | Supplier Admin (own entity) / Internal | Upload invoice with bill matches |
| `GET` | `/supplier-invoices` | Supplier Admin / Internal | List invoices (scoped) |
| `GET` | `/supplier-invoices/{invoice_id}` | Supplier Admin (own) / Internal | Get single invoice |
| `PATCH` | `/supplier-invoices/{invoice_id}/review` | Internal Admin only | Approve or reject |
| `POST` | `/supplier-invoices/{invoice_id}/match` | Supplier Admin / Internal | Add bill matches to existing invoice |
| `POST` | `/supplier-w9` | Supplier Admin (own entity) | Submit W-9 (US only, Phase 3+) |
| `GET` | `/supplier-w9/{entity_id}` | Internal Admin only | Get W-9 on file (Phase 3+) |

---

## 5. Payout Gate

The payout endpoint (`POST /institution-entities/{entity_id}/stripe-connect/payout`) can be gated based on invoice compliance.

### Configuration

- **Market level**: `billing.market_payout_aggregator.require_invoice` (BOOLEAN) and `max_unmatched_bill_days` (INTEGER, default 30)
- **Entity level**: `ops.institution_entity_info.invoice_hold_override_days` (INTEGER, NULL = use market default)
- **Logic**: When `require_invoice=true`, check if the entity has bills older than `max_unmatched_bill_days` (or `invoice_hold_override_days` if set) without a matching approved invoice. If yes, hold payout.

### Rollout

For initial launch, `require_invoice=false` for all markets — payouts flow regardless of invoice status. This allows us to pay suppliers while the compliance workflow is being adopted. Enable per market as invoice registration adoption matures.

---

## 6. Invoice Validation Progression

| Phase | Validation level | Description |
|-------|-----------------|-------------|
| **Phase 2 (MVP)** | Field validation | Software checks on input: required fields, CAE 14-digit format, CUIT format, punto de venta present |
| **Phase 4** | AI image analysis | Use an AI vision model to: (a) verify uploaded invoice image matches form values, OR (b) analyze the image and pre-fill the registration form, OR (c) both |
| **Phase 5** | Tax authority API | Integrate with AFIP WSFE/WSCDC (AR) or SUNAT OSE API (PE) to verify invoice data against the tax authority's records, or pull e-invoice information directly from their system |

---

## 7. ERP Integration (Future State)

When transaction volume warrants it, vianda will integrate with an ERP (e.g. SAP Business One, Odoo, or a LATAM-specialist like Siigo or Defontana) to automate:

- Automatic ingestion of AFIP-validated invoices via AFIP's web services (WSFE, WSCDC)
- Automatic ingestion of SUNAT CDRs via OSE API
- Libro IVA Compras generation (AR)
- IGV credit ledger (PE)
- 1099 batch filing via IRS FIRE or third-party (US)

**Junction table design is ERP-ready**: `bill_invoice_match` links our internal bill records to `supplier_invoice_id`. When ERP records are ingested, they map to the same `supplier_invoice` rows. No schema change needed at integration time.

---

## 8. Implementation Phases

| Phase | Scope | Prerequisite |
|-------|-------|-------------|
| **0 — Payout flow (done)** | Daily payouts via Stripe Connect; existing bill pipeline | Stripe Connect onboarding |
| **1 — Data model (done)** | `supplier_invoice`, `bill_invoice_match` tables; payout gate config columns; AR field validation | Phase 0 |
| **2 — API layer (done)** | Upload, list, enriched list, review, match endpoints; GCS storage for documents | Phase 1 |
| **3 — W-9 + US support (in progress)** | `supplier_w9` table + endpoints; EIN last-4 storage; US validation (`tax_year` required). $600 threshold tracking deferred to Phase 5. | Phase 2 |
| **4 — AI validation** | AI image analysis for invoice verification or auto-fill | Phase 2 |
| **5 — Tax authority API** | AFIP WSFE/WSCDC (AR), SUNAT OSE API (PE), payout gate enforcement | Phase 4 |
| **6 — ERP integration** | Full ERP ingestion for automated invoice processing | Phase 5 |

---

## 9. GCS Document Storage Schema

Invoice documents are stored in `GCS_SUPPLIER_BUCKET` alongside existing product images:

```
GCS_SUPPLIER_BUCKET/
├── products/                          # existing
│   └── {institution_id}/
│       └── {product_id}/
│           ├── image
│           └── thumbnail
└── invoices/                          # supplier invoice documents
    └── {country_code}/                # AR, PE, US
        └── {institution_entity_id}/
            └── {supplier_invoice_id}/
                └── document           # PDF or XML
```

Country code in path enables per-country GCS lifecycle policies for document retention:
- `invoices/AR/` — 10-year retention (AFIP requirement)
- `invoices/PE/` — 5-year retention (SUNAT requirement)
- `invoices/US/` — 7-year retention (IRS requirement)

---

## 10. Open Questions

1. **AR tax classification**: Are all vianda supplier entities issuing Factura A (IVA Responsable Inscripto) or Factura B/C (monotributistas)? Need supplier tax status at entity registration to route to the correct AFIP document type.
2. **PE OSE provider**: Which OSE will vianda use for validating CDRs server-side? Options: Efact, Nubefact, Greenter (open source). This affects Phase 5 API integration.
3. **EIN/SSN encryption**: Confirm GCP KMS key ring naming and access policy before storing W-9 data in Phase 3.
4. **AI model selection**: Which AI vision model for invoice image analysis in Phase 4? Options: Claude vision, Google Document AI, custom fine-tuned model.
5. **Payout gate rollout order**: Which markets go live first with `require_invoice=true`? Suggested order: AR (primary market) → US → PE.

---

## 11. Future Vision — Full Market Coverage

The three markets currently defined in `app/config/market_config.py` and `app/config/location_config.py` are:

| Market | Country | Timezones | Stripe Connect | Billing compliance |
|--------|---------|-----------|---------------|--------------------|
| **AR** | Argentina | `America/Argentina/Buenos_Aires` | Supported (`is_active=true`) | AFIP Factura Electronica + CAE |
| **PE** | Peru | `America/Lima` | Not supported (`is_active=false`) | SUNAT CPE + UBL 2.1 XML + CDR |
| **US** | United States | Eastern · Central · Mountain · Pacific | Supported (`is_active=true`) | IRS 1099-NEC + W-9 |

### Compliance readiness by market at each phase

| Phase | AR | PE | US |
|-------|----|----|-----|
| Phase 0 — Payout flow | Done | Stripe not active | Done |
| Phase 1 — Data model + field validation | MVP (in progress) | Schema ready | Schema ready |
| Phase 2 — API layer | MVP (in progress) | API ready | API ready |
| Phase 3 — W-9 + US support | N/A | N/A | W-9 form + 1099 tracking |
| Phase 4 — AI validation | AI image analysis | AI image analysis | AI image analysis |
| Phase 5 — Tax authority API + payout gate | AFIP WSFE/WSCDC + gate | SUNAT OSE API + gate | Gate (after W-9) |
| Phase 6 — ERP integration | AFIP WSFE/WSCDC | SUNAT OSE provider API | IRS FIRE / Tax1099 batch |

### What changes if new markets are added

When a new country is added to `MarketConfiguration.MARKETS` in `market_config.py`:

1. Add a row to `billing.market_payout_aggregator` in `seed.sql` with the appropriate aggregator, `is_active` flag, and `require_invoice`/`max_unmatched_bill_days` settings
2. Add a country-specific section to this document covering the tax authority, document format, and required fields
3. Add country-specific nullable columns to `billing.supplier_invoice` if the country's invoice format requires fields not covered by existing columns
4. Add a GCS lifecycle policy for `invoices/{country_code}/` with the country's document retention requirement
5. Update `billing.supplier_w9` scope if the country has an equivalent KYC/tax-ID collection requirement

The normalized `supplier_invoice` table is designed to absorb new countries without schema changes for most cases — country-specific fields beyond the core set are the exception, not the rule.

---

## References

- `docs/billing/INSTITUTION_BILLING_EXECUTION_PLAN.md` — internal bill lifecycle
- `docs/billing/RESTAURANT_BALANCE_SYSTEM.md` — balance accounting model
- `docs/api/b2b_client/API_CLIENT_SUPPLIER_PAYOUT.md` — payout onboarding endpoints
- `docs/api/b2b_client/API_CLIENT_SUPPLIER_INVOICES.md` — B2B frontend integration guide for invoice registration
- `docs/api/infrastructure/SUPPLIER_INVOICE_STORAGE_INFRASTRUCTURE.md` — GCS bucket schema + lifecycle policies
- `docs/infrastructure/STRIPE_INTEGRATION_HANDOFF.md` — Stripe Connect setup
- AFIP: https://www.afip.gob.ar/facturae/
- SUNAT: https://www.sunat.gob.pe/legislacion/superin/2017/resolution-0097-2017.pdf (CPE format)
- IRS 1099-NEC: https://www.irs.gov/forms-pubs/about-form-1099-nec
