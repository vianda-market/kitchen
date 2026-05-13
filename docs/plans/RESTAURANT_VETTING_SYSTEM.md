# Restaurant Vetting System

**Status:** Phase 1 complete (2026-04-09). Forms TBD, API integrations TBD.
**Goal:** Structured vetting pipeline for restaurant suppliers joining the Vianda marketplace. Covers initial interest capture, business qualification forms, external verification services (credit, tax, licensing), and approval workflow.
**Scope:** Backend + marketing site form requirements. Tied to B2B restaurant acquisition ad campaigns (see `docs/plans/GOOGLE_META_ADS_INTEGRATION_V2.md` section 11.7).

---

## Table of Contents

1. [Context](#1-context)
2. [Current State](#2-current-state)
3. [Target Architecture](#3-target-architecture)
4. [Interest Form Separation](#4-interest-form-separation)
5. [Restaurant Vetting Form (Phase 1)](#5-restaurant-vetting-form-phase-1)
6. [External Verification APIs (Phase 2)](#6-external-verification-apis-phase-2)
7. [Approval Workflow](#7-approval-workflow)
8. [Database Design](#8-database-design)
9. [Ad Campaign Integration](#9-ad-campaign-integration)
10. [Implementation Phases](#10-implementation-phases)
11. [Feedback for B2B Agent](#11-feedback-for-b2b-agent)
12. [Feedback for Marketing Site Agent](#12-feedback-for-marketing-site-agent)
13. [Open Questions](#13-open-questions)

---

## 1. Context

Vianda operates a B2B2C model: restaurants are **suppliers** who prepare meals, customers are **subscribers** who receive them. Restaurants must be vetted before onboarding to maintain food safety, financial reliability, and marketplace quality.

Currently, all three interest types (customer, employer, supplier) share a single `POST /leads/interest` endpoint with minimal fields. For the B2B restaurant acquisition track, we need:

1. A dedicated supplier interest form with vetting questions
2. External verification APIs for business creditworthiness and compliance
3. An approval workflow that feeds back into ad platform optimization (CAPI `ApprovedPartner` event)

---

## 2. Current State

The existing lead interest system (`marketing.lead_interest` table) supports three `interest_type` values: `customer`, `employer`, `supplier`. All share the same schema:

- `email`, `country_code`, `city_name`, `zipcode`
- `business_name`, `message` (optional)
- `cuisine_id` (optional)
- `employee_count_range` (employer only)

This is insufficient for restaurant vetting. Supplier leads currently only capture email + location + optional business name.

---

## 3. Target Architecture

```
Ad Click (Google/Meta B2B campaign)
    |
    v
Marketing Site: /for-restaurants landing page
    |
    v
Step 1: Restaurant Interest Form (enhanced, public)
    |-- Basic info: business name, contact, location, cuisine type
    |-- Vetting questions: seat count, food permit, years in business, etc.
    |-- TBD: exact questions provided by operator later
    |
    v
POST /api/v1/leads/restaurant-interest
    |-- Stores in new restaurant_lead table
    |-- Fires CAPI Lead event (for ad optimization)
    |
    v
Internal Review Queue (B2B admin dashboard)
    |-- Manual review of submitted applications
    |-- Optional: trigger external verification APIs
    |
    v
External Verification (Phase 2, per-country)
    |-- Argentina: AFIP CUIT validation, Nosis credit score
    |-- Peru: SUNAT RUC validation, Sentinel credit
    |-- US: Dun & Bradstreet, state licensing APIs
    |
    v
Approval / Rejection
    |-- Approved: create Supplier institution + fire CAPI ApprovedPartner event
    |-- Rejected: notify applicant, store reason
    |
    v
Supplier Onboarding (existing flow)
    |-- Address, entity, restaurant, product, vianda, kitchen day, QR code
```

---

## 4. Interest Form Separation

The current single `POST /leads/interest` endpoint will be preserved for customers and employers. A new dedicated endpoint handles restaurant suppliers.

| Endpoint | Purpose | Auth |
|----------|---------|------|
| `POST /api/v1/leads/interest` | Customer + employer interest (existing, unchanged) | None (reCAPTCHA) |
| `POST /api/v1/leads/restaurant-interest` | Restaurant supplier application (new, enhanced) | None (reCAPTCHA) |

The existing `interest_type: supplier` on the old endpoint remains for backward compatibility but is soft-deprecated for new restaurant leads once the dedicated endpoint is live.

---

## 5. Restaurant Vetting Form (Phase 1)

### 5.1 Form Fields

The exact vetting questions will be provided later by the operator. The schema below is a structural placeholder showing field categories. Fields marked **TBD** will be finalized before implementation.

**Contact Information:**
- Business legal name (required)
- Contact person name (required)
- Contact email (required)
- Contact phone (required)
- Country (required)
- City / address (required)

**Business Profile:**
- Cuisine type(s) (required, multi-select from existing cuisine catalog)
- Years in operation (required)
- Number of employees (required, range)
- Seating capacity / kitchen capacity (required)
- Current daily meal output estimate (required)
- Website or social media URL (optional)

**Compliance (TBD -- questions vary by country):**
- Food handling permit / license number (TBD)
- Tax ID (CUIT for AR, RUC for PE, EIN for US) (TBD)
- Health inspection status (TBD)
- Additional country-specific questions (TBD)

**Motivation:**
- Why do you want to join Vianda? (free text, optional)
- How did you hear about us? (dropdown: ad, referral, search, other)

### 5.2 Schema Design

```python
# app/schemas/restaurant_lead.py (new file)
class RestaurantLeadCreateSchema(BaseModel):
    """POST /leads/restaurant-interest"""
    # Contact
    business_name: str = Field(..., max_length=200)
    contact_name: str = Field(..., max_length=200)
    contact_email: str = Field(...)
    contact_phone: str = Field(..., max_length=30)
    country_code: str = Field(..., min_length=2, max_length=2)
    city_name: str = Field(..., max_length=100)
    # Business profile
    cuisine_ids: list[UUID] = Field(..., min_length=1)
    years_in_operation: int = Field(..., ge=0)
    employee_count_range: str = Field(...)  # "1-5", "6-15", "16-50", "50+"
    kitchen_capacity_daily: int = Field(..., ge=1)
    website_url: Optional[str] = Field(None, max_length=500)
    # Motivation
    referral_source: str = Field(...)  # "ad", "referral", "search", "other"
    message: Optional[str] = Field(None, max_length=2000)
    # TBD: vetting questions added here when finalized
    # compliance_answers: dict = Field(default_factory=dict)
```

---

## 6. External Verification APIs (Phase 2)

Per-country external services for business verification. These are called by internal admins during the review process (not automatically on form submission).

### 6.1 Service Architecture

Follows the existing gateway pattern (`app/gateways/base_gateway.py`):

```
app/gateways/
+-- verification/
    +-- __init__.py
    +-- base.py                  # BusinessVerificationGateway ABC
    +-- factory.py               # get_verification_gateway(country_code)
    +-- mock_gateway.py           # Returns sample data for DEV_MODE
    +-- ar/
    |   +-- afip_gateway.py      # CUIT validation via AFIP web services
    |   +-- nosis_gateway.py     # Credit score lookup
    +-- pe/
    |   +-- sunat_gateway.py     # RUC validation via SUNAT
    |   +-- sentinel_gateway.py  # Credit bureau lookup
    +-- us/
        +-- dnb_gateway.py       # Dun & Bradstreet business profile
        +-- licensing_gateway.py # State food licensing (varies by state)
```

### 6.2 Per-Country Capabilities

| Country | Tax ID Validation | Credit Score | Business Licensing | Notes |
|---------|------------------|--------------|--------------------|-------|
| Argentina | AFIP CUIT/CUIL lookup (free web service) | Nosis (paid API) | Municipal habilitacion (manual for now) | AFIP is free; Nosis requires contract |
| Peru | SUNAT RUC validation (free API) | Sentinel/Equifax Peru (paid) | Municipal licencia de funcionamiento (manual) | SUNAT has a public consultation API |
| US | IRS EIN validation (limited) | Dun & Bradstreet (paid API) | State health dept APIs (varies wildly) | State licensing is fragmented; may start manual |

### 6.3 Gateway Interface

```python
# app/gateways/verification/base.py
class BusinessVerificationGateway(ABC):
    @abstractmethod
    def validate_tax_id(self, tax_id: str) -> TaxIdValidationResult: ...

    @abstractmethod
    def get_credit_score(self, tax_id: str, business_name: str) -> CreditScoreResult | None: ...

    @abstractmethod
    def check_licensing(self, tax_id: str, city: str) -> LicensingResult | None: ...
```

### 6.4 Verification Results Storage

Verification results are stored per restaurant lead application, not on the institution record (which does not exist yet at this stage).

```sql
CREATE TABLE public.restaurant_lead_verification (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    restaurant_lead_id UUID NOT NULL REFERENCES public.restaurant_lead(id),
    verification_type VARCHAR(50) NOT NULL,   -- 'tax_id', 'credit_score', 'licensing'
    provider VARCHAR(50) NOT NULL,            -- 'afip', 'nosis', 'sunat', 'dnb', etc.
    status VARCHAR(50) NOT NULL,              -- 'passed', 'failed', 'inconclusive', 'error'
    result_summary TEXT,                       -- Human-readable summary (no raw PII)
    raw_response_hash VARCHAR(64),            -- SHA256 of raw response (for audit, not stored raw)
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_by UUID REFERENCES public.users(id)  -- Internal user who triggered check
);
```

---

## 7. Approval Workflow

### 7.1 Lead Status Lifecycle

```
submitted -> under_review -> [verification_pending] -> approved | rejected
```

| Status | Meaning |
|--------|---------|
| `submitted` | Form submitted, awaiting initial review |
| `under_review` | Admin has opened the application |
| `verification_pending` | External verification in progress |
| `approved` | Vetted and approved. Trigger: create Supplier institution + CAPI `ApprovedPartner` event |
| `rejected` | Not approved. Reason stored. Applicant notified. |

### 7.2 On Approval

When an admin approves a restaurant lead:

1. Create a Supplier institution via existing `CRUDService`
2. Create an admin user for the contact person
3. Send onboarding invite email
4. Fire CAPI `ApprovedPartner` event back to Meta (for campaign optimization)
5. Fire Google Ads conversion event (if applicable)
6. Update `restaurant_lead.status = 'approved'`

### 7.3 CAPI Event Flow

```
Restaurant lead submits form
    -> CAPI fires "Lead" event (immediate, with hashed email)

Admin approves restaurant
    -> CAPI fires "ApprovedPartner" (custom event, with lead_id + value)
```

The `ApprovedPartner` event allows Meta to optimize for quality leads, not just volume. This is critical for B2B campaigns where lead quality matters more than quantity.

---

## 8. Database Design

### 8.1 restaurant_lead Table

```sql
CREATE TABLE public.restaurant_lead (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Contact
    business_name VARCHAR(200) NOT NULL,
    contact_name VARCHAR(200) NOT NULL,
    contact_email VARCHAR(255) NOT NULL,
    contact_phone VARCHAR(30) NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    city_name VARCHAR(100) NOT NULL,
    -- Business profile
    years_in_operation INTEGER NOT NULL,
    employee_count_range VARCHAR(20) NOT NULL,
    kitchen_capacity_daily INTEGER NOT NULL,
    website_url VARCHAR(500),
    referral_source VARCHAR(50) NOT NULL,
    message TEXT,
    -- Vetting (JSONB for flexibility until questions are finalized)
    vetting_answers JSONB DEFAULT '{}',
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'submitted',
    rejection_reason TEXT,
    reviewed_by UUID REFERENCES public.users(id),
    reviewed_at TIMESTAMPTZ,
    -- Links
    institution_id UUID REFERENCES public.institutions(id),  -- Set on approval
    -- Ad tracking
    gclid VARCHAR(255),
    fbclid VARCHAR(255),
    fbc VARCHAR(500),
    fbp VARCHAR(255),
    event_id VARCHAR(255),
    source_platform VARCHAR(20),  -- 'google', 'meta', 'organic', 'referral'
    -- Timestamps
    created_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modified_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cuisine junction (many-to-many)
CREATE TABLE public.restaurant_lead_cuisine (
    restaurant_lead_id UUID NOT NULL REFERENCES public.restaurant_lead(id),
    cuisine_id UUID NOT NULL REFERENCES ops.cuisine(id),
    PRIMARY KEY (restaurant_lead_id, cuisine_id)
);
```

**Note:** `vetting_answers` uses JSONB intentionally. The exact vetting questions are TBD and will vary by country. JSONB allows iterating on questions without schema changes. Once finalized, high-priority fields can be promoted to typed columns.

### 8.2 DB Schema Change Protocol

When implementing, follow the migration workflow: migration file -> `schema.sql` -> `trigger.sql` -> `seed/reference_data.sql` (if needed) -> `dto/models.py` -> `consolidated_schemas.py`. Apply with `bash app/db/migrate.sh`.

---

## 9. Ad Campaign Integration

This system is tightly integrated with the B2B restaurant acquisition track in the Ads Platform plan.

### 9.1 Events Sent to Ad Platforms

| Event | When | Platform | Purpose |
|-------|------|----------|---------|
| `Lead` | Restaurant submits interest form | Google + Meta (CAPI) | Optimize for lead volume |
| `CompleteRegistration` | Restaurant completes full vetting form | Google + Meta (CAPI) | Optimize for quality leads |
| `ApprovedPartner` | Admin approves restaurant | Meta (CAPI, custom event) | Optimize for approved partners (highest value signal) |

### 9.2 Conversion Value Hierarchy

| Event | Value Signal | Rationale |
|-------|-------------|-----------|
| `Lead` | Low (e.g., $1) | Many leads, few convert |
| `CompleteRegistration` | Medium (e.g., $10) | Completed form shows intent |
| `ApprovedPartner` | High (e.g., $100-500) | Actual business value of onboarded restaurant |

The `ApprovedPartner` event is the most valuable signal for campaign optimization. It tells Meta/Google: "this type of lead actually converts to a paying partner."

### 9.3 Lead-Gen vs Self-Serve Decision

The system must support both acquisition paths:

| Path | Flow | Dependency |
|------|------|------------|
| **Lead-gen (initial launch)** | Ad -> landing page -> interest form -> manual review -> approval -> onboarding invite | This plan only |
| **Self-serve (future)** | Ad -> B2B portal -> self-registration -> auto-vetting -> approval -> onboarding | B2B portal registration flow must be built first |

Initial launch will use lead-gen to validate demand and simplify vetting. The form and backend are designed to support both paths without refactoring.

---

## 10. Implementation Phases

| Phase | Scope | Depends On |
|-------|-------|------------|
| **Phase 1** | `restaurant_lead` table, DTO, schema. New `POST /leads/restaurant-interest` endpoint. **DONE** (migration 0001). | Nothing |
| **Phase 2** | Wire CAPI `Lead` event on form submission (uses Ads Platform infra) | Ads Platform Phase 6 (Meta CAPI gateway) |
| **Phase 3** | Admin review dashboard: list, view, approve/reject restaurant leads | Phase 1 |
| **Phase 4** | On-approval automation: create institution, send invite, fire `ApprovedPartner` CAPI event | Phases 1, 2, 3 |
| **Phase 5** | Vetting questions finalized (operator provides exact questions) | Operator input |
| **Phase 6** | External verification gateways (AFIP, SUNAT, etc.) | Phase 3, API contracts per country |
| **Phase 7** | Marketing site: /for-restaurants landing page + form UI | Phase 1 (API ready) |

---

## 11. Feedback for B2B Agent

> **Audience:** vianda-platform agent (B2B portal). This section describes requirements that affect the B2B admin interface.

### 11.1 Restaurant Lead Review Dashboard

New admin page: `/admin/restaurant-leads`

**List view:**
- Table of restaurant lead applications
- Columns: business name, contact, city, country, cuisine, status, submitted date
- Filters: status, country, date range
- Sort: most recent first

**Detail view:**
- Full application data (all form fields)
- Verification results (if any external checks were run)
- Action buttons: Approve, Reject (with reason), Request Verification
- On Approve: triggers backend to create Supplier institution + onboarding invite

**API endpoints (backend will provide):**
- `GET /api/v1/admin/restaurant-leads` (list, paginated)
- `GET /api/v1/admin/restaurant-leads/{id}` (detail)
- `POST /api/v1/admin/restaurant-leads/{id}/approve`
- `POST /api/v1/admin/restaurant-leads/{id}/reject` (body: `{ reason: "..." }`)
- `POST /api/v1/admin/restaurant-leads/{id}/verify` (trigger external verification)

### 11.2 Future: Self-Serve Registration

If the self-serve path is chosen later, the B2B portal will need a public registration flow:
- `/register` page with the same form fields as the restaurant interest form
- Auto-creates the restaurant lead record via the same API
- May include email verification before submission
- Requires building an approval queue view that is different from the admin review (supplier sees their own status)

This is NOT in scope for initial launch. Noted here for awareness.

---

## 12. Feedback for Marketing Site Agent

> **Audience:** vianda-home agent (marketing site). This section describes requirements for the restaurant-facing landing page.

### 12.1 New Landing Page: /for-restaurants

Create a dedicated landing page for restaurant acquisition campaigns. This is where B2B ads will drive traffic.

**Page structure:**
- Hero section: value proposition for restaurants joining Vianda
- How it works: 3-step process (apply, get verified, start receiving orders)
- Testimonials / social proof (placeholder for now)
- Application form (the restaurant interest form from section 5)
- FAQ section

### 12.2 Form Requirements

The form on this page submits to `POST /api/v1/leads/restaurant-interest`.

- Must capture all fields from section 5.1 (contact, business profile, motivation)
- Multi-step form recommended (contact -> business profile -> motivation) to reduce abandonment
- Must capture ad click identifiers from URL params (`gclid`, `fbclid`) and include in submission
- Must fire Meta Pixel `Lead` event on successful submission: `fbq('track', 'Lead', {content_name: 'restaurant_application'})`
- reCAPTCHA v3 required (same as existing leads endpoints)

### 12.3 Tracking Requirements

- Install Meta Pixel JS on this page (same Pixel ID as rest of marketing site)
- Fire `ViewContent` on page load with `content_type: 'restaurant_landing'`
- Fire `Lead` on successful form submission
- Capture `fbclid` from URL and `_fbc`/`_fbp` cookies, include in form submission

---

## 13. Open Questions

1. **Vetting questions:** Exact questions TBD. Operator will provide country-specific qualification questions. The `vetting_answers` JSONB field accommodates iteration.
2. **External API contracts:** Which verification providers to use per country? Nosis (AR) and Sentinel (PE) require paid contracts. Should we start with manual verification and add APIs later?
3. **Lead-gen vs self-serve timing:** When does the self-serve path become necessary? Depends on volume.
4. **Approval SLA:** What is the target turnaround time for reviewing a restaurant application? This affects the admin dashboard priority.
5. **Payment provider for B2B restaurant onboarding:** Currently Stripe only. MercadoPago integration is planned (see Ads Platform plan, payment provider agnosticism section). Restaurants in LATAM markets may prefer MercadoPago.
6. **Minimum vetting requirements by country:** Are there legal minimums (e.g., food handler certification) that must be verified before onboarding in each market?
