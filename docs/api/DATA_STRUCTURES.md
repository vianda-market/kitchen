# Data Structures — Enum Convention

## Enum Pattern (all enums)

Every enum in the system follows this structure:

| Concern | Where | Format | Example |
|---------|-------|--------|---------|
| **Member name** | Python class | UPPER_SNAKE_CASE | `Status.HANDED_OUT` |
| **Value** | DB column, API request/response payloads, query params | lowercase slug | `"handed_out"` |
| **Title** | `GET /api/v1/enums` response `labels` map | Title Case (locale-dependent) | `"Handed Out"` (en), `"Entregado"` (es) |

---

## Frontend-Backend Enum Contract

This is the authoritative standard for how enum data flows between frontend and backend.

### The rule

| Direction | What travels | Format | Example |
|-----------|-------------|--------|---------|
| **Frontend → Backend** (request body, query param, filter) | **value** | lowercase slug | `?status=active`, `{ "role_type": "internal" }` |
| **Backend → Frontend** (entity response) | **value** | lowercase slug | `{ "status": "active", "role_type": "internal" }` |
| **Backend → Frontend** (enum lookup) | **value + title** | `{ values: [...], labels: {value: title} }` | See [Enum API Endpoint](#enum-api-endpoint) below |

### How it works

1. **Frontend fetches `GET /api/v1/enums?language={locale}` once** on login, caches for 1 hour.
2. The response contains both `values` (canonical codes) and `labels` (localized display titles) for every enum.
3. **Entity endpoints** (`/users/me`, `/institution-bills`, `/vianda-pickup/pending`, etc.) return **values only** — never titles.
4. **Frontend resolves titles locally** by looking up the cached enum labels: `enums.status.labels["active"]` → `"Active"` (en) / `"Activo"` (es).
5. **Frontend sends values in all requests** — query params, request bodies, filters. Never send a title to the API.

### Why this pattern

- **DRY**: Titles live in one place (`GET /enums`), not duplicated across every entity response.
- **i18n-ready**: The same value maps to different titles per locale. Entity responses are locale-agnostic.
- **Cache-friendly**: Enum labels change rarely; entity data changes constantly. Decoupling them lets each be cached independently.

### Common mistakes

| Mistake | Fix |
|---------|-----|
| Sending `?status=Active` (capitalized) | Send `?status=active` (lowercase slug) |
| Sending `?status=active` for bills | Bills don't have `active` status — valid bill statuses: `pending`, `processed`, `cancelled` |
| Displaying `role_type: "internal"` as-is in UI | Look up `enums.role_type.labels["internal"]` → `"Internal"` |
| Hardcoding display labels in frontend code | Use `GET /enums?language={locale}` — labels update without frontend deploy |

Full enum API docs: [ENUM_SERVICE_API.md](shared_client/ENUM_SERVICE_API.md)

---

## Enum API Endpoint

`GET /api/v1/enums?language={locale}`

Returns all system enums. Each enum key contains:

```json
{
  "status": {
    "values": ["active", "inactive", "pending", "arrived", "handed_out", "completed", "cancelled", "processed"],
    "labels": {
      "active": "Active",
      "inactive": "Inactive",
      "pending": "Pending",
      "arrived": "Arrived",
      "handed_out": "Handed Out",
      "completed": "Completed",
      "cancelled": "Cancelled",
      "processed": "Processed"
    }
  }
}
```

### Usage Rules

- **`value`** (lowercase slug) — use in API requests, query params, comparisons, and business logic
- **`label`** / title (display string) — use for UI rendering only; never send to the API
- **`?language=`** param controls locale for labels (`en`, `es`, `pt`). Default: `en`

### JWT Token Values

Role values in JWT tokens (`role_type`, `role_name`) are lowercase slugs:
- `role_type`: `"internal"`, `"supplier"`, `"customer"`, `"employer"`
- `role_name`: `"admin"`, `"super_admin"`, `"manager"`, `"operator"`, `"comensal"`, `"global_manager"`

### All Enum Types

| Enum | Sample values |
|------|-------------|
| `status` | `active`, `inactive`, `pending`, `arrived`, `handed_out`, `completed`, `cancelled`, `processed` |
| `role_type` | `internal`, `supplier`, `customer`, `employer` |
| `role_name` | `admin`, `super_admin`, `manager`, `operator`, `comensal`, `global_manager` |
| `subscription_status` | `active`, `on_hold`, `pending`, `cancelled` |
| `address_type` | `restaurant`, `entity_billing`, `entity_address`, `customer_home`, `customer_billing`, `customer_employer`, `customer_other` |
| `transaction_type` | `order`, `credit`, `debit`, `refund`, `discretionary`, `payment` |
| `kitchen_day` | `monday`, `tuesday`, `wednesday`, `thursday`, `friday` |
| `pickup_type` | `offer`, `request`, `self` |
| `street_type` | `st`, `ave`, `blvd`, `rd`, `dr`, `ln`, `way`, `ct`, `pl`, `cir` |
| `bill_resolution` | `pending`, `paid`, `rejected`, `failed` |
| `bill_payout_status` | `pending`, `completed`, `failed` |
| `discretionary_status` | `pending`, `cancelled`, `approved`, `rejected` |
| `discretionary_reason` | `marketing_campaign`, `credit_refund`, `order_incorrectly_marked`, `full_order_refund` |
| `supplier_invoice_status` | `pending_review`, `approved`, `rejected` |
| `supplier_invoice_type` | `factura_electronica`, `cpe`, `1099_nec` |
| `employer_bill_payment_status` | `pending`, `paid`, `failed`, `overdue` |
| `payment_method_provider` | `stripe`, `mercado_pago`, `payu` |
| `audit_operation` | `create`, `update`, `archive`, `delete` |
| `favorite_entity_type` | `vianda`, `restaurant` |
| `dietary_flag` | `vegan`, `vegetarian`, `gluten_free`, `dairy_free`, `nut_free`, `halal`, `kosher` |
| `portion_size_display` | `light`, `standard`, `large`, `insufficient_reviews` |
| `billing_cycle` | `daily`, `weekly`, `monthly` |
| `payment_frequency` | `daily`, `weekly`, `biweekly`, `monthly` |
| `benefit_cap_period` | `per_renewal`, `monthly` |
| `enrollment_mode` | `managed`, `domain_gated` |
| `tax_classification` | `individual`, `c_corp`, `s_corp`, `partnership`, `llc`, `other` |
| `interest_type` | `customer`, `employer`, `supplier` |
| `lead_interest_status` | `active`, `notified`, `unsubscribed` |
| `lead_interest_source` | `marketing_site`, `b2c_app` |
